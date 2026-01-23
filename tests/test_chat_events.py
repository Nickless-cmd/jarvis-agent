import uuid
import pytest

import jarvis.events as bus
from fastapi.testclient import TestClient


def test_chat_events_flow(monkeypatch):
    from jarvis import server

    # Mock run_agent to avoid heavy work
    def fake_run_agent(user_id, prompt, session_id=None, allowed_tools=None, ui_city=None, ui_lang=None):
        return {"text": "hi there", "meta": {}}

    monkeypatch.setattr(server, "run_agent", fake_run_agent)
    monkeypatch.setenv("JARVIS_TEST_MODE", "1")

    client = TestClient(server.app, raise_server_exceptions=False)

    # Ensure a user exists and get token
    from jarvis.auth import register_user, login_user
    try:
        register_user("events_user2", "secret", email="ev2@example.com")
    except Exception:
        pass
    token = login_user("events_user2", "secret")["token"]
    client.cookies.set("jarvis_token", token)

    # Clear any previous events from store
    from jarvis.event_store import get_event_store
    get_event_store().clear()

    with client as c:
        resp = c.post(
            "/v1/chat/completions",
            json={
                "model": "test-model",
                "messages": [{"role": "user", "content": "hello"}],
                "stream": False,
            },
        )
        assert resp.status_code == 200

        # Read events
        ev_resp = c.get("/v1/events?after=0")
        assert ev_resp.status_code == 200
        data = ev_resp.json()
        types = [e["type"] for e in data["events"]]
        assert "chat.start" in types
        assert "chat.token" in types
        assert "chat.end" in types
        assert "chat.user_message" in types
        assert "chat.assistant_message" in types
        
        # Ensure event order: chat.start before chat.token before chat.end
        start_idx = types.index("chat.start")
        token_idx = types.index("chat.token")
        end_idx = types.index("chat.end")
        assert start_idx < token_idx < end_idx


def test_chat_events_error_path(monkeypatch):
    from jarvis import server

    def boom_agent(user_id, prompt, session_id=None, allowed_tools=None, ui_city=None, ui_lang=None):
        raise RuntimeError("boom")

    monkeypatch.setattr(server, "run_agent", boom_agent)
    monkeypatch.setenv("JARVIS_TEST_MODE", "1")

    client = TestClient(server.app)

    from jarvis.auth import register_user, login_user
    try:
        register_user("events_user_error", "secret", email="ev3@example.com")
    except Exception:
        pass
    token = login_user("events_user_error", "secret")["token"]
    client.cookies.set("jarvis_token", token)

    from jarvis.event_store import get_event_store
    get_event_store().clear()

    with client as c:
        with pytest.raises(RuntimeError):
            c.post(
                "/v1/chat/completions",
                json={
                    "model": "test-model",
                    "messages": [{"role": "user", "content": "hello"}],
                    "stream": False,
                },
            )

        ev_resp = c.get("/v1/events?after=0")
        assert ev_resp.status_code == 200
        data = ev_resp.json()
        types = [e["type"] for e in data["events"]]
        assert "chat.start" in types
        assert "chat.error" in types
        assert "chat.end" in types
