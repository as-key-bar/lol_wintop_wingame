"""Google login for editors.

Viewing and upvoting stay open to everyone. Saving the build and the waves needs a logged-in
user whose role is admin or editor. The flow is the OpenID Connect authorization code flow with
PKCE: the browser is sent to Google, comes back to /auth/google/callback with a code, and this
server exchanges the code at Google's token endpoint over TLS. The ID token therefore comes
straight from Google, so only its claims are checked (issuer, audience, expiry, nonce, verified
email); no signature check is needed for a token received that way.

A login lasts SESSION_DAYS and is kept as a random cookie value. Only its hash is stored.
"""

import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
from fastapi import Depends, HTTPException, Request
from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import LoginSessionRecord, UserRecord, get_engine
from app.retention import now_iso, parse_iso

logger = logging.getLogger(__name__)

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_ISSUERS = ("https://accounts.google.com", "accounts.google.com")

SESSION_COOKIE = "wintop_session"
FLOW_COOKIE = "wintop_login_flow"
SESSION_DAYS = 14
FLOW_SECONDS = 600

ROLES = ("admin", "editor", "pending")
EDIT_ROLES = ("admin", "editor")


class LoginError(Exception):
    """The login could not be completed; the message is safe to show to the user."""


def google_client_id() -> str:
    return os.getenv("GOOGLE_CLIENT_ID", "").strip()


def google_client_secret() -> str:
    return os.getenv("GOOGLE_CLIENT_SECRET", "").strip()


def public_base_url() -> str:
    """The site's public origin, e.g. https://wintop-wingame.com (no trailing slash)."""
    return os.getenv("PUBLIC_BASE_URL", "").strip().rstrip("/")


def redirect_uri() -> str:
    return f"{public_base_url()}/api/v1/auth/google/callback"


def admin_emails() -> set[str]:
    raw = os.getenv("ADMIN_EMAILS", "")
    return {item.strip().lower() for item in raw.split(",") if item.strip()}


def login_enabled() -> bool:
    return bool(google_client_id() and google_client_secret() and public_base_url())


def cookies_are_secure() -> bool:
    return public_base_url().startswith("https://")


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _sign(value: str) -> str:
    # The flow cookie is signed so that a forged cookie cannot pick the state or the verifier.
    secret = (google_client_secret() or "unset").encode("utf-8")
    return _b64url(hmac.new(secret, value.encode("utf-8"), hashlib.sha256).digest())


def start_login(return_to: str = "/") -> tuple[str, str]:
    """Returns (url to send the browser to, value of the flow cookie)."""
    state = secrets.token_urlsafe(24)
    nonce = secrets.token_urlsafe(24)
    verifier = secrets.token_urlsafe(48)
    challenge = _b64url(hashlib.sha256(verifier.encode("ascii")).digest())
    query = urlencode(
        {
            "client_id": google_client_id(),
            "redirect_uri": redirect_uri(),
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "nonce": nonce,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "prompt": "select_account",
        }
    )
    payload = json.dumps(
        {"s": state, "n": nonce, "v": verifier, "r": return_to, "t": int(time.time())},
        separators=(",", ":"),
    )
    encoded = _b64url(payload.encode("utf-8"))
    return f"{GOOGLE_AUTH_URL}?{query}", f"{encoded}.{_sign(encoded)}"


def read_flow_cookie(value: str | None) -> dict:
    if not value or "." not in value:
        raise LoginError("ログインの状態が見つかりません。もう一度ログインしてください。")
    encoded, signature = value.rsplit(".", 1)
    if not hmac.compare_digest(signature, _sign(encoded)):
        raise LoginError("ログインの状態が正しくありません。もう一度ログインしてください。")
    try:
        padded = encoded + "=" * (-len(encoded) % 4)
        flow = json.loads(base64.urlsafe_b64decode(padded))
    except ValueError as error:
        raise LoginError("ログインの状態が正しくありません。") from error
    if time.time() - int(flow.get("t", 0)) > FLOW_SECONDS:
        raise LoginError("ログインの有効時間が切れました。もう一度ログインしてください。")
    return flow


def exchange_code(code: str, verifier: str) -> dict:
    """Trades the authorization code for tokens at Google. Returns the ID token's claims."""
    try:
        response = httpx.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": google_client_id(),
                "client_secret": google_client_secret(),
                "redirect_uri": redirect_uri(),
                "grant_type": "authorization_code",
                "code_verifier": verifier,
            },
            timeout=10,
        )
    except httpx.HTTPError as error:
        logger.warning("Google token request failed: %s", type(error).__name__)
        raise LoginError("Google と通信できませんでした。しばらくしてからやり直してください。") from error
    if response.status_code != 200:
        logger.warning("Google token endpoint returned %s", response.status_code)
        raise LoginError("Google のログインを完了できませんでした。もう一度お試しください。")
    id_token = response.json().get("id_token", "")
    parts = id_token.split(".")
    if len(parts) != 3:
        raise LoginError("Google から ID トークンを受け取れませんでした。")
    try:
        padded = parts[1] + "=" * (-len(parts[1]) % 4)
        return json.loads(base64.urlsafe_b64decode(padded))
    except ValueError as error:
        raise LoginError("Google の応答を読み取れませんでした。") from error


def check_claims(claims: dict, nonce: str) -> None:
    if claims.get("iss") not in GOOGLE_ISSUERS:
        raise LoginError("Google の応答が正しくありません。")
    audience = claims.get("aud")
    audiences = audience if isinstance(audience, list) else [audience]
    if google_client_id() not in audiences:
        raise LoginError("Google の応答が正しくありません。")
    if int(claims.get("exp", 0)) < time.time():
        raise LoginError("Google の応答の有効期限が切れています。")
    if not hmac.compare_digest(str(claims.get("nonce", "")), nonce):
        raise LoginError("ログインの確認に失敗しました。もう一度お試しください。")
    if claims.get("email_verified") is not True or not claims.get("email"):
        raise LoginError("メールアドレスが確認できる Google アカウントでログインしてください。")
    if not claims.get("sub"):
        raise LoginError("Google の応答が正しくありません。")


def sign_in(session: Session, claims: dict) -> str:
    """Creates or updates the user for these claims and starts a login. Returns the cookie value."""
    email = str(claims["email"]).strip().lower()
    user = session.scalar(select(UserRecord).where(UserRecord.google_sub == claims["sub"]))
    if user is None:
        user = UserRecord(
            google_sub=str(claims["sub"]),
            email=email,
            display_name=str(claims.get("name") or email)[:255],
            role="admin" if email in admin_emails() else "pending",
            created_at=now_iso(),
        )
        session.add(user)
        session.flush()
    else:
        user.email = email
        user.display_name = str(claims.get("name") or email)[:255]
        # The environment variable is the way back in if the database role is ever lost.
        if email in admin_emails() and user.role != "admin":
            user.role = "admin"

    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    session.add(
        LoginSessionRecord(
            token_hash=hash_token(token),
            user_id=user.id,
            created_at=now.isoformat(timespec="seconds"),
            expires_at=(now + timedelta(days=SESSION_DAYS)).isoformat(timespec="seconds"),
        )
    )
    session.commit()
    return token


def purge_expired_sessions(session: Session) -> None:
    now = datetime.now(timezone.utc)
    rows = session.scalars(select(LoginSessionRecord)).all()
    expired = [
        row.token_hash
        for row in rows
        if (parse_iso(row.expires_at) or now - timedelta(days=1)) <= now
    ]
    if expired:
        session.execute(
            delete(LoginSessionRecord).where(LoginSessionRecord.token_hash.in_(expired))
        )
        session.commit()


def current_user(request: Request) -> UserRecord | None:
    """The logged-in user for this request's cookie, or None. The role is read fresh every
    time, so a revoked editor loses access on the next request."""
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    try:
        with Session(get_engine()) as session:
            row = session.get(LoginSessionRecord, hash_token(token))
            if row is None:
                return None
            expires = parse_iso(row.expires_at)
            if expires is None or expires <= datetime.now(timezone.utc):
                return None
            user = session.get(UserRecord, row.user_id)
            if user is not None:
                session.expunge(user)
            return user
    except SQLAlchemyError:
        logger.warning("Could not read the login session", exc_info=True)
        return None


def end_session(request: Request) -> None:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return
    with Session(get_engine()) as session:
        session.execute(
            delete(LoginSessionRecord).where(
                LoginSessionRecord.token_hash == hash_token(token)
            )
        )
        session.commit()


def _same_origin_or_reject(request: Request) -> None:
    """Cookies are sent automatically, so a state-changing request must come from this site.
    SameSite=Lax already blocks cross-site PUT/POST; the Origin check is a second line."""
    base = public_base_url()
    origin = request.headers.get("origin")
    if base and origin and origin.rstrip("/") != base:
        raise HTTPException(
            status_code=403,
            detail={"code": "bad_origin", "message": "このサイト以外からの操作は受け付けません。"},
        )


def require_editor(request: Request) -> UserRecord:
    if not login_enabled():
        raise HTTPException(
            status_code=403,
            detail={
                "code": "login_disabled",
                "message": "ログイン機能が無効です。サーバーの設定が必要です。",
            },
        )
    _same_origin_or_reject(request)
    user = current_user(request)
    if user is None:
        raise HTTPException(
            status_code=401,
            detail={"code": "login_required", "message": "ログインしてください。"},
        )
    if user.role not in EDIT_ROLES:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "not_approved",
                "message": "編集には、管理者の承認が必要です。",
            },
        )
    return user


def require_admin(user: UserRecord = Depends(require_editor)) -> UserRecord:
    if user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail={"code": "admin_only", "message": "管理者だけが行える操作です。"},
        )
    return user
