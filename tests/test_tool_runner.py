import time

import jarvis.agent_core.tool_registry as tr
from jarvis.event_bus import Event, get_event_bus


def setup_function(_) -> None:
    tr._reset_registry_for_tests()


def test_tool_timeout(monkeypatch):
    def slow_tool():
        time.sleep(0.2)
        return "done"

    tr.register_tool(tr.ToolSpec("slow", "slow", {}, "low"), lambda: slow_tool())
    tr._allowlist.add("slow")
    result = tr.call_tool("slow", {}, user_id=1, session_id="s1", timeout=0.05)
    assert result["ok"] is False
    assert result["error"]["type"] == "TimeoutError"


def test_tool_retry_succeeds(monkeypatch):
    attempts = {"n": 0}

    def flaky():
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise RuntimeError("fail once")
        return "ok"

    tr.register_tool(tr.ToolSpec("flaky", "flaky", {}, "low"), lambda: flaky())
    tr._allowlist.add("flaky")
    result = tr.call_tool("flaky", {}, user_id=1, session_id="s1", retries=1)
    assert result["ok"] is True
    assert attempts["n"] == 2


def test_tool_exception_envelope():
    def bad():
        raise ValueError("boom")

    tr.register_tool(tr.ToolSpec("bad", "bad", {}, "low"), lambda: bad())
    tr._allowlist.add("bad")
    res = tr.call_tool("bad", {}, user_id=1, session_id="s1")
    assert res["ok"] is False
    assert res["error"]["type"] == "ValueError"
    assert res["error"]["where"] == "bad"


def test_tool_events_emitted():
    """Test that tool lifecycle events are emitted via EventBus."""
    bus = get_event_bus()
    bus.clear_backlog()  # Clear any previous events
    
    events = []
    def capture_event(event):
        events.append(event)
    
    bus.subscribe("tool.started", capture_event)
    bus.subscribe("tool.finished", capture_event)
    bus.subscribe("tool.failed", capture_event)
    
    # Test successful tool
    def good_tool(**kwargs):
        return "success"
    
    tr.register_tool(tr.ToolSpec("good", "good", {}, "low"), good_tool)
    tr._allowlist.add("good")
    
    result = tr.call_tool("good", {"arg1": "value1", "api_key": "secret"}, user_id=1, session_id="test_session")
    
    assert result["ok"] is True
    assert len(events) == 2  # started and finished
    
    started_event = events[0]
    finished_event = events[1]
    
    assert started_event.type == "tool.started"
    assert started_event.session_id == "test_session"
    assert started_event.payload["tool_name"] == "good"
    assert started_event.payload["input_summary"]["arg1"] == "value1"
    assert started_event.payload["input_summary"]["api_key"] == "[REDACTED]"  # Redacted
    assert "trace_id" in started_event.payload
    
    assert finished_event.type == "tool.finished"
    assert finished_event.session_id == "test_session"
    assert finished_event.payload["tool_name"] == "good"
    assert finished_event.payload["ok"] is True
    assert "duration_ms" in finished_event.payload
    assert finished_event.payload["trace_id"] == started_event.payload["trace_id"]


def test_tool_failed_event_emitted():
    """Test that tool.failed event is emitted on error."""
    bus = get_event_bus()
    bus.clear_backlog()
    
    events = []
    def capture_event(event):
        events.append(event)
    
    bus.subscribe("tool.failed", capture_event)
    
    def bad_tool(**kwargs):
        raise RuntimeError("test error")
    
    tr.register_tool(tr.ToolSpec("bad_event", "bad", {}, "low"), bad_tool)
    tr._allowlist.add("bad_event")
    
    result = tr.call_tool("bad_event", {}, user_id=1, session_id="test_session")
    
    assert result["ok"] is False
    assert len(events) == 1
    
    failed_event = events[0]
    assert failed_event.type == "tool.failed"
    assert failed_event.session_id == "test_session"
    assert failed_event.payload["tool_name"] == "bad_event"
    assert failed_event.payload["error"]["type"] == "RuntimeError"
    assert failed_event.payload["error"]["message"] == "test error"
    assert "duration_ms" in failed_event.payload
    assert "trace_id" in failed_event.payload
