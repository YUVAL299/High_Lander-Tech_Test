from fastapi.testclient import TestClient

from app.main import create_app


def test_healthz_reports_ok():
    client = TestClient(create_app())
    assert client.get("/healthz").json() == {"status": "ok"}
