from fastapi.testclient import TestClient

from jarvis import server
from jarvis.auth import get_or_create_default_user


def test_public_status_accessible_without_auth():
    client = TestClient(server.app)
    resp = client.get("/status")
    assert resp.status_code == 200


def test_admin_endpoint_without_auth_is_401():
    client = TestClient(server.app)
    resp = client.post("/v1/dev/run-tests")
    assert resp.status_code == 401


def test_admin_endpoint_with_devkey_allowed(monkeypatch):
    monkeypatch.setenv("JARVIS_TEST_MODE", "1")
    import jarvis.server as srv
    srv._TEST_MODE = True
    client = TestClient(server.app)
    resp = client.post("/v1/dev/run-tests", headers={"Authorization": "Bearer devkey"})
    # handler returns ok even if tests not run synchronously
    assert resp.status_code == 200
    assert resp.json().get("ok") is True
