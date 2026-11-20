import pytest
from sqlalchemy.orm import Session

from app import auth, database


def enable_login(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://wintop.test")
    monkeypatch.setenv("ADMIN_EMAILS", "boss@example.com")


def login_cookies(
    monkeypatch: pytest.MonkeyPatch,
    email: str = "boss@example.com",
    sub: str | None = None,
    role: str | None = None,
) -> dict[str, str]:
    """Logs a user in directly (without Google) and returns the session cookie."""
    enable_login(monkeypatch)
    claims = {"sub": sub or f"sub-{email}", "email": email, "name": email.split("@")[0]}
    database.Base.metadata.create_all(database.get_engine())
    with Session(database.get_engine()) as session:
        token = auth.sign_in(session, claims)
        if role is not None:
            user = session.query(database.UserRecord).filter_by(email=email).one()
            user.role = role
            session.commit()
    return {auth.SESSION_COOKIE: token}
