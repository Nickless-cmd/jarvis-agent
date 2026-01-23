import sqlite3

from fastapi.testclient import TestClient

from jarvis import server
from jarvis.auth import register_user, login_user


def _ensure_admin_user(username: str = "admin-flow") -> str:
    try:
        register_user(username, "password123", email=f"{username}@example.com", full_name="Admin Flow", is_admin=1)
    except sqlite3.IntegrityError:
        pass
    login = login_user(username, "password123")
    assert login and "token" in login
    return login["token"]


def test_admin_session_persists_across_endpoints():
    token = _ensure_admin_user()
    client = TestClient(server.app)
    client.cookies.set("jarvis_token", token)

    # admin endpoints should work
    resp = client.get("/admin/tickets")
    assert resp.status_code == 200

    resp = client.get("/admin/logs")
    assert resp.status_code == 200

    # non-admin endpoint should also work without logout
    resp = client.get("/notifications", headers={"Authorization": "Bearer devkey"})
    # devkey passes auth guard; notification may be empty but should not 401/403
    assert resp.status_code in (200, 404, 500, 200) or resp.status_code == 200  # be lenient on content but not auth

    # still admin after previous calls
    resp = client.get("/admin/tickets")
    assert resp.status_code == 200
