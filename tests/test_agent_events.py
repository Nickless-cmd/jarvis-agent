import json
from fastapi.testclient import TestClient
import jarvis.server as server
from jarvis.event_store import get_event_store


def test_streaming_emits_agent_events(monkeypatch, tmp_path):
    # isolate event store
    store = get_event_store()
    store.clear()

    # minimal stubs to avoid DB/auth
    monkeypatch.setenv("JARVIS_DB_PATH", str(tmp_path / "db.sqlite"))
    monkeypatch.setenv("JARVIS_TEST_MODE", "1")
    monkeypatch.setattr(server, "_auth_or_token_ok", lambda a, b: True)
    monkeypatch.setattr(server, "_resolve_user", lambda token: {"id": 1, "username": "u", "is_admin": False})
    monkeypatch.setattr(server, "_resolve_session_id", lambda user, sess, logged: "sess-1")
    monkeypatch.setattr(server, "get_user_by_token", lambda tok: {"id": 1, "username": "u", "is_admin": False, "is_disabled": False})
    monkeypatch.setattr(server, "add_message", lambda *a, **k: None)
    monkeypatch.setattr(server, "_cleanup_user_assets", lambda u: None)
    monkeypatch.setattr(server, "_get_user_quota", lambda uid: (0, 0))
    monkeypatch.setattr(server, "_quota_warning", lambda *a, **k: None)
    monkeypatch.setattr(server, "choose_tool", lambda *a, **k: None)
    monkeypatch.setattr(server, "_contains_sensitive", lambda p: False)
    monkeypatch.setattr(server, "_butlerize_text", lambda t, u: t)
    monkeypatch.setattr(server, "run_agent", lambda *a, **k: {"text": "hello world", "meta": {}})

    with TestClient(server.app) as client:
        with client.stream("POST", "/v1/chat/completions", json={"model": "x", "prompt": "hi", "stream": True}) as r:
            list(r.iter_lines())

        events_resp = client.get("/v1/events?after=0")
        assert events_resp.status_code == 200
        events = events_resp.json().get("events", [])
        types = {e["type"] for e in events}
        assert {"agent.start", "agent.done", "agent.stream.start", "agent.stream.delta", "agent.stream.final", "chat.token"}.issubset(types)


def test_streaming_chat_token_even_without_delta(monkeypatch, tmp_path):
    store = get_event_store()
    store.clear()

    monkeypatch.setenv("JARVIS_DB_PATH", str(tmp_path / "db.sqlite"))
    monkeypatch.setenv("JARVIS_TEST_MODE", "1")
    monkeypatch.setattr(server, "_auth_or_token_ok", lambda a, b: True)
    monkeypatch.setattr(server, "_resolve_user", lambda token: {"id": 1, "username": "u", "is_admin": False})
    monkeypatch.setattr(server, "_resolve_session_id", lambda user, sess, logged: "sess-1")
    monkeypatch.setattr(server, "get_user_by_token", lambda tok: {"id": 1, "username": "u", "is_admin": False, "is_disabled": False})
    monkeypatch.setattr(server, "add_message", lambda *a, **k: None)
    monkeypatch.setattr(server, "_cleanup_user_assets", lambda u: None)
    monkeypatch.setattr(server, "_get_user_quota", lambda uid: (0, 0))
    monkeypatch.setattr(server, "_quota_warning", lambda *a, **k: None)
    monkeypatch.setattr(server, "choose_tool", lambda *a, **k: None)
    monkeypatch.setattr(server, "_contains_sensitive", lambda p: False)
    monkeypatch.setattr(server, "_butlerize_text", lambda t, u: t)
    monkeypatch.setattr(server, "run_agent", lambda *a, **k: {"text": "hi", "meta": {}})
    monkeypatch.setattr(server, "_chunk_text", lambda text, max_len=24: [])  # force no deltas

    with TestClient(server.app) as client:
        with client.stream("POST", "/v1/chat/completions", json={"model": "x", "prompt": "hi", "stream": True}) as r:
            list(r.iter_lines())

        events_resp = client.get("/v1/events?after=0")
        assert events_resp.status_code == 200
        events = events_resp.json().get("events", [])
        types = {e["type"] for e in events}
        assert "chat.token" in types


def test_streaming_response_from_events(monkeypatch, tmp_path):
    """Test that streaming response is generated from EventBus events."""
    import asyncio
    from jarvis.events import subscribe_async
    
    # isolate event store
    store = get_event_store()
    store.clear()

    # minimal stubs
    monkeypatch.setenv("JARVIS_DB_PATH", str(tmp_path / "db.sqlite"))
    monkeypatch.setenv("JARVIS_TEST_MODE", "1")
    monkeypatch.setattr(server, "_auth_or_token_ok", lambda a, b: True)
    monkeypatch.setattr(server, "_resolve_user", lambda token: {"id": 1, "username": "u", "is_admin": False})
    monkeypatch.setattr(server, "_resolve_session_id", lambda user, sess, logged: "sess-1")
    monkeypatch.setattr(server, "get_user_by_token", lambda tok: {"id": 1, "username": "u", "is_admin": False, "is_disabled": False})
    monkeypatch.setattr(server, "add_message", lambda *a, **k: None)
    monkeypatch.setattr(server, "_cleanup_user_assets", lambda u: None)
    monkeypatch.setattr(server, "_get_user_quota", lambda uid: (0, 0))
    monkeypatch.setattr(server, "_quota_warning", lambda *a, **k: None)
    monkeypatch.setattr(server, "choose_tool", lambda *a, **k: None)
    monkeypatch.setattr(server, "_contains_sensitive", lambda p: False)
    monkeypatch.setattr(server, "_butlerize_text", lambda t, u: t)
    monkeypatch.setattr(server, "run_agent", lambda *a, **k: {"text": "hello world", "meta": {}})

    with TestClient(server.app) as client:
        # Collect streaming response
        streaming_chunks = []
        with client.stream("POST", "/v1/chat/completions", json={"model": "x", "prompt": "hi", "stream": True}) as response:
            for line in response.iter_lines():
                if line:
                    streaming_chunks.append(line)
        
        # Verify we got streaming chunks
        assert len(streaming_chunks) > 0
        
        # Check for expected SSE format
        data_lines = [line for line in streaming_chunks if line.startswith("data: ")]
        assert len(data_lines) >= 4  # status, head, at least one content, tail
        
        # Parse first chat completion chunk (skip status event)
        chat_data_lines = [line for line in data_lines if '"object": "chat.completion.chunk"' in line]
        assert len(chat_data_lines) >= 3  # head, at least one content, tail
        
        # Parse first data chunk (head)
        head_data = json.loads(chat_data_lines[0][6:])  # Remove "data: "
        assert head_data["object"] == "chat.completion.chunk"
        assert "choices" in head_data
        assert head_data["choices"][0]["delta"]["role"] == "assistant"
        
        # Check for DONE marker
        done_lines = [line for line in streaming_chunks if line == "data: [DONE]"]
        assert len(done_lines) == 1
