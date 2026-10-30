from fastapi.testclient import TestClient

from app.main import app


def _client() -> TestClient:
    return TestClient(app, base_url="https://testserver")


def test_test_endpoints_disabled_in_production(monkeypatch):
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.delenv("ENABLE_TEST_ENDPOINTS", raising=False)
    monkeypatch.setenv("FIRESTORE_MODE", "production")

    with _client() as client:
        assert client.post("/test/reset").status_code == 404
        assert (
            client.post(
                "/e2e/seed",
                json={
                    "roomId": "blocked",
                    "title": "Blocked",
                    "width": 2,
                    "height": 2,
                },
            ).status_code
            == 404
        )


def test_test_endpoints_can_be_enabled_explicitly(monkeypatch):
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setenv("FIRESTORE_MODE", "production")
    monkeypatch.setenv("ENABLE_TEST_ENDPOINTS", "true")

    with _client() as client:
        assert client.post("/test/reset").status_code == 200


def test_test_endpoints_enabled_locally_by_default(monkeypatch):
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.delenv("ENABLE_TEST_ENDPOINTS", raising=False)
    monkeypatch.setenv("FIRESTORE_MODE", "local")

    with _client() as client:
        assert client.post("/test/reset").status_code == 200
