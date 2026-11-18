from conftest import api_get


def test_health_returns_ok() -> None:
    response = api_get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_version_endpoint_reports_the_deployed_build(monkeypatch) -> None:
    from app import main

    monkeypatch.setattr(main, "APP_VERSION", "0.2.1")
    monkeypatch.setattr(main, "APP_COMMIT", "abc1234")

    response = api_get("/api/version")

    assert response.status_code == 200
    assert response.json() == {"version": "0.2.1", "commit": "abc1234"}
