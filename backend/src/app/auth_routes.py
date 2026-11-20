import logging
from typing import Literal

from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Request
from fastapi import Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import auth
from app.database import UserRecord, get_engine
from app.rate_limit import rate_limit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1")


class CurrentUser(BaseModel):
    displayName: str
    email: str
    role: Literal["admin", "editor", "pending"]


class MeResponse(BaseModel):
    loginEnabled: bool
    user: CurrentUser | None = None


class UserSummary(BaseModel):
    id: int
    displayName: str
    email: str
    role: Literal["admin", "editor", "pending"]
    createdAt: str


class SetRoleRequest(BaseModel):
    role: Literal["editor", "pending"]


def _safe_return_path(value: str | None) -> str:
    # Only a path on this site: no scheme, no host, no protocol-relative "//".
    if value and value.startswith("/") and not value.startswith("//") and "\\" not in value:
        return value[:200]
    return "/"


def _finish(return_to: str, error: str | None = None) -> RedirectResponse:
    target = return_to
    if error:
        target += ("&" if "?" in target else "?") + f"loginError={error}"
    response = RedirectResponse(auth.public_base_url() + target, status_code=302)
    response.delete_cookie(auth.FLOW_COOKIE, path="/api/v1/auth")
    return response


@router.get(
    "/auth/google/login",
    dependencies=[Depends(rate_limit("auth-login", 20, 60))],
)
def google_login(returnTo: str | None = Query(default=None, max_length=200)):
    if not auth.login_enabled():
        raise HTTPException(
            status_code=503,
            detail={"code": "login_disabled", "message": "ログイン機能が無効です。"},
        )
    url, flow_cookie = auth.start_login(_safe_return_path(returnTo))
    response = RedirectResponse(url, status_code=302)
    response.set_cookie(
        auth.FLOW_COOKIE,
        flow_cookie,
        max_age=auth.FLOW_SECONDS,
        httponly=True,
        secure=auth.cookies_are_secure(),
        samesite="lax",
        path="/api/v1/auth",
    )
    return response


@router.get(
    "/auth/google/callback",
    dependencies=[Depends(rate_limit("auth-callback", 20, 60))],
)
def google_callback(
    code: str | None = Query(default=None, max_length=2048),
    state: str | None = Query(default=None, max_length=256),
    error: str | None = Query(default=None, max_length=64),
    flow_cookie: str | None = Cookie(default=None, alias=auth.FLOW_COOKIE),
):
    if not auth.login_enabled():
        raise HTTPException(status_code=503, detail={"code": "login_disabled"})
    return_to = "/"
    try:
        flow = auth.read_flow_cookie(flow_cookie)
        return_to = _safe_return_path(flow.get("r"))
        if error:
            return _finish(return_to, "denied")
        if not code or not state or state != flow.get("s"):
            raise auth.LoginError("state mismatch")
        claims = auth.exchange_code(code, flow["v"])
        auth.check_claims(claims, flow["n"])
        with Session(get_engine()) as session:
            auth.purge_expired_sessions(session)
            token = auth.sign_in(session, claims)
    except auth.LoginError as failure:
        logger.warning("Login failed: %s", failure)
        return _finish(return_to, "failed")

    response = _finish(return_to)
    response.set_cookie(
        auth.SESSION_COOKIE,
        token,
        max_age=auth.SESSION_DAYS * 24 * 3600,
        httponly=True,
        secure=auth.cookies_are_secure(),
        samesite="lax",
        path="/",
    )
    return response


@router.get("/auth/me", response_model=MeResponse)
def me(request: Request) -> MeResponse:
    user = auth.current_user(request)
    return MeResponse(
        loginEnabled=auth.login_enabled(),
        user=(
            CurrentUser(displayName=user.display_name, email=user.email, role=user.role)
            if user
            else None
        ),
    )


@router.post(
    "/auth/logout",
    dependencies=[Depends(rate_limit("auth-logout", 20, 60))],
)
def logout(request: Request, response: Response) -> dict[str, str]:
    auth.end_session(request)
    response.delete_cookie(auth.SESSION_COOKIE, path="/")
    return {"status": "ok"}


@router.get(
    "/admin/users",
    response_model=list[UserSummary],
    dependencies=[Depends(rate_limit("admin-users", 60, 60))],
)
def list_users(admin: UserRecord = Depends(auth.require_admin)) -> list[UserSummary]:
    with Session(get_engine()) as session:
        users = session.scalars(select(UserRecord).order_by(UserRecord.id)).all()
        return [
            UserSummary(
                id=user.id,
                displayName=user.display_name,
                email=user.email,
                role=user.role,
                createdAt=user.created_at,
            )
            for user in users
        ]


@router.put(
    "/admin/users/{userId}/role",
    response_model=UserSummary,
    dependencies=[Depends(rate_limit("admin-users", 60, 60))],
)
def set_user_role(
    userId: int,
    body: SetRoleRequest,
    admin: UserRecord = Depends(auth.require_admin),
) -> UserSummary:
    if userId == admin.id:
        raise HTTPException(
            status_code=400,
            detail={"code": "own_role", "message": "自分自身の権限は変更できません。"},
        )
    with Session(get_engine()) as session:
        user = session.get(UserRecord, userId)
        if user is None:
            raise HTTPException(
                status_code=404,
                detail={"code": "unknown_user", "message": "ユーザーが見つかりません。"},
            )
        if user.role == "admin" or user.email in auth.admin_emails():
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "admin_fixed",
                    "message": "管理者の権限は、サーバーの設定（ADMIN_EMAILS）で決まります。",
                },
            )
        user.role = body.role
        session.commit()
        return UserSummary(
            id=user.id,
            displayName=user.display_name,
            email=user.email,
            role=user.role,
            createdAt=user.created_at,
        )
