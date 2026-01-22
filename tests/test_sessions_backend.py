from fastapi.testclient import TestClient

from jarvis import server
from jarvis.auth import get_or_create_default_user
from jarvis.session_store import list_sessions, add_message, ensure_session


def test_chat_without_session_creates_default_session(monkeypatch):
    user = get_or_create_default_user()
    client = TestClient(server.app)
    resp = client.post(
        "/v1/chat/completions",
        headers={"Authorization": "Bearer devkey"},
        json={"model": "local", "messages": [{"role": "user", "content": "hej"}]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "session_id" in data
    sid = data["session_id"]
    sessions = list_sessions(user["id"])
    assert any(s["id"] == sid for s in sessions)


def test_chat_unknown_session_returns_404(monkeypatch):
    client = TestClient(server.app)
    resp = client.post(
        "/v1/chat/completions",
        headers={"Authorization": "Bearer devkey", "x-session-id": "unknown-session"},
        json={"model": "local", "messages": [{"role": "user", "content": "hej"}]},
    )
    assert resp.status_code == 404
    payload = resp.json()
    assert payload.get("ok") is False
    assert payload.get("error", {}).get("type") == "SessionNotFound"


def test_list_sessions_includes_count_and_preview(monkeypatch):
    user = get_or_create_default_user()
    sid = ensure_session("session-test", user["id"], name="Test")
    add_message(sid, "user", "hello there")
    sessions = list_sessions(user["id"])
    found = next(s for s in sessions if s["id"] == sid)
    assert found["message_count"] >= 1
    assert found["last_message_preview"].startswith("hello")
    assert "updated_at" in found
    assert found["updated_at"] is not None
