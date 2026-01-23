from fastapi.testclient import TestClient

from jarvis.event_store import EventStore, get_event_store
from jarvis import events
from jarvis.auth import register_user, login_user
import jarvis.agent_core.tool_registry as tr


def setup_function(_) -> None:
    tr._reset_registry_for_tests()


def test_event_store_filtering_and_limit():
    store = EventStore(max_size=3)
    store.append("a", {"v": 1})
    store.append("b", {"v": 2})
    store.append("c", {"v": 3})
    # after filter
    res = store.get_events(after=1)
    assert [e["type"] for e in res["events"]] == ["b", "c"]
    # limit
    res = store.get_events(after=None, limit=2)
    assert len(res["events"]) == 2
    assert res["last_id"] == res["events"][-1]["id"]


def test_events_endpoint_returns_bus_events():
    from jarvis import server
    client = TestClient(server.app)

    store = get_event_store()
    store._reset_for_tests()

    # Ensure user/token
    try:
        register_user("events_user", "secret", email="events@example.com")
    except Exception:
        pass
    token = login_user("events_user", "secret")["token"]

    client.cookies.set("jarvis_token", token)

    with client as c:
        # publish events after startup so subscriber is active
        events.publish("agent.started", {"x": 1})
        events.publish("agent.finished", {"x": 2})
        resp = c.get("/v1/events?after=0")
        assert resp.status_code == 200
        data = resp.json()
        assert "events" in data
        assert any(ev["type"] == "agent.started" for ev in data["events"])


def test_events_endpoint_returns_tool_events():
    from jarvis import server
    client = TestClient(server.app)

    store = get_event_store()
    store._reset_for_tests()

    # Register a test tool
    def test_tool():
        return "tool result"
    
    tr.register_tool(tr.ToolSpec("test_tool", "test", {}, "low"), test_tool)
    tr._allowlist.add("test_tool")

    # Ensure user/token
    try:
        register_user("tool_user", "secret", email="tool@example.com")
    except Exception:
        pass
    token = login_user("tool_user", "secret")["token"]

    client.cookies.set("jarvis_token", token)

    with client as c:
        # Call the tool (this should publish tool.start and tool.ok events)
        result = tr.call_tool("test_tool", {}, user_id=1, session_id="test_session")
        assert result["ok"] is True
        
        # Check that tool events appear in /v1/events
        resp = c.get("/v1/events?after=0")
        assert resp.status_code == 200
        data = resp.json()
        assert "events" in data
        
        tool_events = [ev for ev in data["events"] if ev["type"].startswith("tool.")]
        assert len(tool_events) >= 2  # At least tool.start and tool.ok
        
        # Check for tool.start
        start_events = [ev for ev in tool_events if ev["type"] == "tool.start"]
        assert len(start_events) == 1
        assert start_events[0]["payload"]["tool"] == "test_tool"
        
        # Check for tool.ok
        ok_events = [ev for ev in tool_events if ev["type"] == "tool.ok"]
        assert len(ok_events) == 1
        assert ok_events[0]["payload"]["tool"] == "test_tool"
        assert "duration_ms" in ok_events[0]["payload"]


def test_events_endpoint_returns_agent_events(monkeypatch):
    from jarvis import server

    # Mock run_agent to avoid heavy work
    def fake_run_agent(user_id, prompt, session_id=None, allowed_tools=None, ui_city=None, ui_lang=None):
        return {"text": "hi there", "meta": {}}

    monkeypatch.setattr(server, "run_agent", fake_run_agent)
    monkeypatch.setenv("JARVIS_TEST_MODE", "1")

    client = TestClient(server.app)

    store = get_event_store()
    store._reset_for_tests()

    # Ensure user/token
    try:
        register_user("agent_user", "secret", email="agent@example.com")
    except Exception:
        pass
    token = login_user("agent_user", "secret")["token"]

    client.cookies.set("jarvis_token", token)

    with client as c:
        # Make a simple chat request
        resp = c.post("/v1/chat/completions", json={
            "model": "test-model",
            "messages": [{"role": "user", "content": "Hello"}],
            "stream": False
        })
        assert resp.status_code == 200
        
        # Check that agent events appear in /v1/events
        resp = c.get("/v1/events?after=0")
        assert resp.status_code == 200
        data = resp.json()
        assert "events" in data
        
        agent_events = [ev for ev in data["events"] if ev["type"].startswith("agent.")]
        assert len(agent_events) >= 2  # At least agent.start and agent.done
        
        # Check for agent.start
        start_events = [ev for ev in agent_events if ev["type"] == "agent.start"]
        assert len(start_events) >= 1
        
        # Check for agent.done
        done_events = [ev for ev in agent_events if ev["type"] == "agent.done"]
        assert len(done_events) >= 1


def test_no_background_threads_after_test():
    """Ensure no non-daemon threads are left running after tests."""
    import threading
    import time
    
    # Import server to trigger any startup background tasks
    from jarvis import server
    
    # Give a moment for any async startup to complete
    time.sleep(0.1)
    
    # Check that only main thread and possibly daemon threads exist
    threads = threading.enumerate()
    non_daemon = [t for t in threads if not t.daemon and t != threading.main_thread()]
    
    # In test mode, there should be no non-daemon background threads
    assert len(non_daemon) == 0, f"Non-daemon threads found: {[t.name for t in non_daemon]}"
