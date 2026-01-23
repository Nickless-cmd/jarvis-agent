import pytest
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
    unsubscribe = events.subscribe_all(lambda et, payload: store.append(et, payload))

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
    unsubscribe()


def test_events_endpoint_returns_tool_events():
    from jarvis import server
    client = TestClient(server.app)

    store = get_event_store()
    store._reset_for_tests()
    unsubscribe = events.subscribe_all(lambda et, payload: store.append(et, payload))

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
    unsubscribe()


def test_events_endpoint_returns_agent_events(monkeypatch):
    from jarvis import server
    from jarvis.events import publish

    client = TestClient(server.app)

    store = get_event_store()
    store._reset_for_tests()
    unsubscribe = events.subscribe_all(lambda et, payload: store.append(et, payload))

    # Ensure user/token
    try:
        register_user("agent_user", "secret", email="agent@example.com")
    except Exception:
        pass
    token = login_user("agent_user", "secret")["token"]

    client.cookies.set("jarvis_token", token)

    with client as c:
        # Publish agent events directly (avoid heavy chat route)
        publish("agent.start", {"session_id": "sess-agent"})
        publish("agent.done", {"session_id": "sess-agent"})
        
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
    unsubscribe()


@pytest.mark.skip(reason="non-deterministic hang in TestClient teardown; covered by session fixture checks")
def test_no_background_threads_after_test():
    """Ensure no non-daemon threads are left running after tests and chat completion."""
    import threading
    import time
    from fastapi.testclient import TestClient
    
    # Import server to trigger any startup background tasks
    from jarvis import server
    
    # Run a chat completion to trigger event publishing
    client = TestClient(server.app)
    
    # Ensure user/token
    try:
        from jarvis.auth import register_user, login_user
        register_user("thread_test", "secret", email="thread@example.com")
    except Exception:
        pass
    token = login_user("thread_test", "secret")["token"]
    client.cookies.set("jarvis_token", token)
    
    with client as c:
        # Mock run_agent to avoid heavy work
        import jarvis.server
        original_run_agent = jarvis.server.run_agent
        def fake_run_agent(*args, **kwargs):
            return {"text": "test response"}
        jarvis.server.run_agent = fake_run_agent
        
        try:
            resp = c.post("/v1/chat/completions", json={
                "model": "test-model",
                "messages": [{"role": "user", "content": "test"}],
                "stream": False
            })
            assert resp.status_code == 200
        finally:
            jarvis.server.run_agent = original_run_agent
    # Explicitly close client to avoid lingering threads in tests
    client.close()

    # Give a moment for cleanup
    time.sleep(0.5)
    
    # Check that only main thread and possibly daemon threads exist
    threads = threading.enumerate()
    non_daemon = [t for t in threads if not t.daemon and t != threading.main_thread()]
    
    # After chat completion and context exit, there should be no non-daemon background threads
    assert len(non_daemon) == 0, f"Non-daemon threads found: {[t.name for t in non_daemon]}"
