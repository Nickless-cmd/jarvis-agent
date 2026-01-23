import uuid

from fastapi.testclient import TestClient

from jarvis.server import app
from jarvis.auth import register_user, login_user
from jarvis.db import get_conn


def _create_non_admin_user(username: str = "user1") -> str:
    # Ensure clean slate
    with get_conn() as conn:
        conn.execute("DELETE FROM users WHERE username = ?", (username,))
        conn.commit()
    register_user(username, "password123", email="u@example.com", full_name="User One")
    login = login_user(username, "password123")
    assert login and "token" in login
    return login["token"]


def test_admin_tickets_with_devkey_authorization():
    client = TestClient(app)
    resp = client.get("/admin/tickets", headers={"Authorization": "Bearer devkey"})
    assert resp.status_code == 200
    assert "tickets" in resp.json()


def test_admin_tickets_rejected_for_non_admin_cookie():
    token = _create_non_admin_user(f"user-{uuid.uuid4().hex[:6]}")
    client = TestClient(app)
    client.cookies.set("jarvis_token", token)
    resp = client.get("/admin/tickets")
    assert resp.status_code in (401, 403)
