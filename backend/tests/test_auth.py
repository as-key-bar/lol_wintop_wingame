import base64
import json
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import auth, database, matchups
from conftest import api_request
from login_helpers import enable_login, login_cookies


@pytest.fixture(autouse=True)
def fresh_database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    engine = create_engine(f"sqlite:///{tmp_path / 'auth.db'}", future=True)
    database.set_engine(engine)
    database.Base.metadata.create_all(engine)
    matchups.clear_seeded_cache()
    monkeypatch.setenv("RATE_LIMIT_MULTIPLIER", "0")
    yield
    engine.dispose()
    database.set_engine(None)
    matchups.clear_seeded_cache()


def _id_token(**overrides) -> str:
    claims = {
        "iss": "https://accounts.google.com",
        "aud": "test-client-id",
        "exp": int(time.time()) + 600,
        "nonce": "",
        "sub": "google-sub-1",
        "email": "boss@example.com",
        "email_verified": True,
        "name": "Boss",
    }
    claims.update(overrides)
    body = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()
    return f"x.{body}.y"


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload

    def json(self) -> dict:
        return self._payload


def _start(monkeypatch: pytest.MonkeyPatch, return_to: str = "/"):
    """Runs the first leg and returns (state, nonce, flow cookie)."""
    enable_login(monkeypatch)
    response = api_request("GET", f"/api/v1/auth/google/login?returnTo={return_to}")
    assert response.status_code == 302
    query = parse_qs(urlparse(response.headers["location"]).query)
    flow_cookie = response.cookies[auth.FLOW_COOKIE]
    return query, flow_cookie


def _callback(monkeypatch, query, flow_cookie, *, token_claims=None, state=None, status=200):
    nonce = query["nonce"][0]
    token = _id_token(**{"nonce": nonce, **(token_claims or {})})
    monkeypatch.setattr(
        auth.httpx,
        "post",
        lambda *a, **k: _FakeResponse(status, {"id_token": token}),
    )
    return api_request(
        "GET",
        f"/api/v1/auth/google/callback?code=abc&state={state or query['state'][0]}",
        cookies={auth.FLOW_COOKIE: flow_cookie},
    )


def test_login_sends_the_browser_to_google_with_pkce_and_state(monkeypatch) -> None:
    query, flow_cookie = _start(monkeypatch)

    assert query["client_id"] == ["test-client-id"]
    assert query["redirect_uri"] == ["https://wintop.test/api/v1/auth/google/callback"]
    assert query["code_challenge_method"] == ["S256"]
    assert query["scope"] == ["openid email profile"]
    assert query["state"][0] and query["nonce"][0] and flow_cookie


def test_login_is_unavailable_until_google_is_configured(monkeypatch) -> None:
    for name in ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "PUBLIC_BASE_URL"):
        monkeypatch.delenv(name, raising=False)

    assert api_request("GET", "/api/v1/auth/google/login").status_code == 503
    me = api_request("GET", "/api/v1/auth/me").json()
    assert me == {"loginEnabled": False, "user": None}


def test_a_successful_login_sets_a_secure_session_and_makes_the_admin_email_an_admin(
    monkeypatch,
) -> None:
    query, flow_cookie = _start(monkeypatch, return_to="/matchup/Aatrox/Darius")

    response = _callback(monkeypatch, query, flow_cookie)

    assert response.status_code == 302
    assert response.headers["location"] == "https://wintop.test/matchup/Aatrox/Darius"
    set_cookie = response.headers.get_list("set-cookie")
    session_cookie = next(c for c in set_cookie if c.startswith(auth.SESSION_COOKIE))
    assert "HttpOnly" in session_cookie and "Secure" in session_cookie
    assert "SameSite=lax" in session_cookie

    me = api_request(
        "GET", "/api/v1/auth/me", cookies={auth.SESSION_COOKIE: response.cookies[auth.SESSION_COOKIE]}
    ).json()
    assert me["user"] == {"displayName": "Boss", "email": "boss@example.com", "role": "admin"}


def test_the_session_value_is_stored_only_as_a_hash(monkeypatch) -> None:
    query, flow_cookie = _start(monkeypatch)
    response = _callback(monkeypatch, query, flow_cookie)
    token = response.cookies[auth.SESSION_COOKIE]

    with Session(database.get_engine()) as session:
        stored = [row.token_hash for row in session.query(database.LoginSessionRecord)]
    assert stored == [auth.hash_token(token)]
    assert token not in stored


def test_an_unknown_google_account_starts_as_pending(monkeypatch) -> None:
    query, flow_cookie = _start(monkeypatch)

    response = _callback(
        monkeypatch,
        query,
        flow_cookie,
        token_claims={"sub": "other", "email": "friend@example.com", "name": "Friend"},
    )

    me = api_request(
        "GET", "/api/v1/auth/me", cookies={auth.SESSION_COOKIE: response.cookies[auth.SESSION_COOKIE]}
    ).json()
    assert me["user"]["role"] == "pending"


@pytest.mark.parametrize(
    "claims",
    [
        {"iss": "https://evil.example"},
        {"aud": "someone-elses-client"},
        {"exp": 1},
        {"email_verified": False},
        {"nonce": "wrong-nonce"},
    ],
)
def test_a_token_that_fails_a_check_does_not_log_anyone_in(monkeypatch, claims) -> None:
    query, flow_cookie = _start(monkeypatch)

    response = _callback(monkeypatch, query, flow_cookie, token_claims=claims)

    assert response.status_code == 302
    assert "loginError=failed" in response.headers["location"]
    assert auth.SESSION_COOKIE not in response.cookies
    with Session(database.get_engine()) as session:
        assert session.query(database.LoginSessionRecord).count() == 0


def test_a_callback_with_the_wrong_state_or_a_forged_flow_cookie_is_rejected(monkeypatch) -> None:
    query, flow_cookie = _start(monkeypatch)

    wrong_state = _callback(monkeypatch, query, flow_cookie, state="not-the-state")
    forged = _callback(monkeypatch, query, "e30." + "A" * 43)
    missing = api_request("GET", "/api/v1/auth/google/callback?code=abc&state=x")

    for response in (wrong_state, forged, missing):
        assert response.status_code == 302
        assert "loginError=failed" in response.headers["location"]
        assert auth.SESSION_COOKIE not in response.cookies


def test_google_refusing_the_code_is_a_failed_login(monkeypatch) -> None:
    query, flow_cookie = _start(monkeypatch)

    response = _callback(monkeypatch, query, flow_cookie, status=400)

    assert "loginError=failed" in response.headers["location"]


def test_the_return_path_cannot_leave_the_site(monkeypatch) -> None:
    for hostile in ("//evil.example", "https://evil.example", "/\\evil.example"):
        query, flow_cookie = _start(monkeypatch, return_to=hostile)
        response = _callback(monkeypatch, query, flow_cookie)
        assert response.headers["location"] == "https://wintop.test/"


def test_logout_ends_the_session_for_good(monkeypatch) -> None:
    cookies = login_cookies(monkeypatch)

    out = api_request("POST", "/api/v1/auth/logout", cookies=cookies)

    assert out.status_code == 200
    me = api_request("GET", "/api/v1/auth/me", cookies=cookies).json()
    assert me["user"] is None


def test_an_expired_session_is_not_accepted(monkeypatch) -> None:
    cookies = login_cookies(monkeypatch)
    with Session(database.get_engine()) as session:
        row = session.query(database.LoginSessionRecord).one()
        row.expires_at = "2000-01-01T00:00:00+00:00"
        session.commit()

    assert api_request("GET", "/api/v1/auth/me", cookies=cookies).json()["user"] is None


def test_a_save_from_another_origin_is_refused_even_with_a_valid_session(monkeypatch) -> None:
    cookies = login_cookies(monkeypatch)

    response = api_request(
        "PUT",
        "/api/v1/matchups/Aatrox/Darius/waves",
        {"video": {}, "waves": []},
        headers={"Origin": "https://evil.example"},
        cookies=cookies,
    )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "bad_origin"


# --- user management: the admin approves and revokes editors ---


def test_only_the_admin_can_list_or_change_users(monkeypatch) -> None:
    pending = login_cookies(monkeypatch, email="friend@example.com")
    editor = login_cookies(monkeypatch, email="editor@example.com", role="editor")

    assert api_request("GET", "/api/v1/admin/users").status_code == 401
    assert api_request("GET", "/api/v1/admin/users", cookies=pending).status_code == 403
    denied = api_request("GET", "/api/v1/admin/users", cookies=editor)
    assert denied.status_code == 403
    assert denied.json()["detail"]["code"] == "admin_only"


def test_the_admin_approves_and_revokes_an_editor_and_it_takes_effect_at_once(monkeypatch) -> None:
    admin = login_cookies(monkeypatch)
    friend = login_cookies(monkeypatch, email="friend@example.com")
    users = api_request("GET", "/api/v1/admin/users", cookies=admin).json()
    friend_id = next(u["id"] for u in users if u["email"] == "friend@example.com")
    save = lambda: api_request(  # noqa: E731
        "PUT", "/api/v1/matchups/Aatrox/Darius/waves", {"video": {}, "waves": []}, cookies=friend
    ).status_code

    assert save() == 403  # pending

    approved = api_request(
        "PUT", f"/api/v1/admin/users/{friend_id}/role", {"role": "editor"}, cookies=admin
    )
    assert approved.status_code == 200 and approved.json()["role"] == "editor"
    assert save() == 422  # editor: now past the permission check (the empty video is invalid)

    api_request("PUT", f"/api/v1/admin/users/{friend_id}/role", {"role": "pending"}, cookies=admin)
    assert save() == 403  # revoked: the very next request is refused


def test_the_admin_cannot_change_their_own_role_or_another_admin(monkeypatch) -> None:
    admin = login_cookies(monkeypatch)
    monkeypatch.setenv("ADMIN_EMAILS", "boss@example.com,second@example.com")
    login_cookies(monkeypatch, email="second@example.com")
    monkeypatch.setenv("ADMIN_EMAILS", "boss@example.com,second@example.com")
    users = api_request("GET", "/api/v1/admin/users", cookies=admin).json()
    boss_id = next(u["id"] for u in users if u["email"] == "boss@example.com")
    second_id = next(u["id"] for u in users if u["email"] == "second@example.com")

    own = api_request("PUT", f"/api/v1/admin/users/{boss_id}/role", {"role": "pending"}, cookies=admin)
    other = api_request("PUT", f"/api/v1/admin/users/{second_id}/role", {"role": "pending"}, cookies=admin)

    assert own.status_code == 400 and own.json()["detail"]["code"] == "own_role"
    assert other.status_code == 400 and other.json()["detail"]["code"] == "admin_fixed"


def test_the_admin_role_comes_from_the_environment_even_if_the_row_was_lost(monkeypatch) -> None:
    login_cookies(monkeypatch)
    with Session(database.get_engine()) as session:
        session.query(database.UserRecord).one().role = "pending"
        session.commit()

    cookies = login_cookies(monkeypatch)

    me = api_request("GET", "/api/v1/auth/me", cookies=cookies).json()
    assert me["user"]["role"] == "admin"
