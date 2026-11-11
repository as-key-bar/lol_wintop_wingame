from conftest import api_get


def test_health_returns_ok() -> None:
    response = api_get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
