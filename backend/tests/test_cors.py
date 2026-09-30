from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_frontend_dev_origin_is_allowed() -> None:
    response = client.options(
        "/users",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert "http://localhost:5173" in (response.headers["access-control-allow-origin"])


def test_unknown_origin_is_not_allowed() -> None:
    response = client.options(
        "/users",
        headers={
            "Origin": "https://example.com",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert "access-control-allow-origin" not in response.headers
