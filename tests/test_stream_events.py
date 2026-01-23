from fastapi.testclient import TestClient
import jarvis.server as server
from jarvis.event_store import get_event_store

def setup_stubs(monkeypatch, tmp_path):
    monkeypatch.setenv("JARVIS_DB_PATH", str(tmp_path / "db.sqlite"))
    monkeypatch.setenv("JARVIS_TEST_MODE", "1")
    monkeypatch.setattr(server, "_auth_or_token_ok", lambda a, b: True)
    monkeypatch.setattr(server, "_resolve_user", lambda token: {"id": 1, "username": "u", "is_admin": False, "lang": "da"})
    monkeypatch.setattr(server, "get_user_by_token", lambda tok: {"id": 1, "username": "u", "is_admin": False, "is_disabled": False})
    monkeypatch.setattr(server, "_resolve_session_id", lambda user, sess, logged: "sess-1")
    monkeypatch.setattr(server, "add_message", lambda *a, **k: None)
    monkeypatch.setattr(server, "_cleanup_user_assets", lambda u: None)
    monkeypatch.setattr(server, "_get_user_quota", lambda uid: (0, 0))
    monkeypatch.setattr(server, "_quota_warning", lambda *a, **k: None)
    monkeypatch.setattr(server, "choose_tool", lambda *a, **k: None)
    monkeypatch.setattr(server, "_contains_sensitive", lambda p: False)
    monkeypatch.setattr(server, "_butlerize_text", lambda t, u: t)


def test_stream_events_happy_path(monkeypatch, tmp_path):
    store = get_event_store()
    store.clear()
    setup_stubs(monkeypatch, tmp_path)
    monkeypatch.setattr(server, "run_agent", lambda *a, **k: {"text": "hello there", "meta": {}})

    with TestClient(server.app) as client:
        with client.stream("POST", "/v1/chat/completions", json={"model": "x", "prompt": "hi", "stream": True}) as r:
            list(r.iter_lines())
        events = client.get("/v1/events?after=0").json()["events"]
    types = [e["type"] for e in events]
    assert "agent.stream.start" in types
    assert "agent.stream.final" in types
    assert "chat.start" in types
    assert "chat.end" in types
    token_events = [e for e in events if e["type"] == "chat.token"]
    assert token_events, "expected chat.token events"
    # Delta events sequence should increase
    deltas = [e for e in events if e["type"] == "agent.stream.delta"]
    assert deltas
    seqs = [d["payload"].get("sequence") for d in deltas]
    assert seqs == sorted(seqs)


def test_stream_events_error(monkeypatch, tmp_path):
    store = get_event_store()
    store.clear()
    setup_stubs(monkeypatch, tmp_path)
    def boom(*a, **k):
        raise RuntimeError("boom")
    monkeypatch.setattr(server, "run_agent", boom)

    with TestClient(server.app) as client:
        with client.stream("POST", "/v1/chat/completions", json={"model": "x", "prompt": "hi", "stream": True}) as r:
            list(r.iter_lines())
        events = client.get("/v1/events?after=0").json()["events"]
    types = [e["type"] for e in events]
    assert "agent.stream.error" in types
