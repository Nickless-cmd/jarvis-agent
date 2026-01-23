import time
from jarvis import events

import jarvis.agent_core.tool_registry as tr
from jarvis.events import subscribe, publish


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


def test_events_published_success():
    seen = []
    unsub = events.subscribe("tool.ok", lambda event_type, payload: seen.append(payload))
    tr.register_tool(tr.ToolSpec("echo", "echo", {}, "low"), lambda: "ok")
    tr._allowlist.add("echo")
    res = tr.call_tool("echo", {}, user_id=1, session_id="s1")
    unsub()
    assert res["ok"] is True
    assert any(p["tool"] == "echo" for p in seen)


def test_events_published_failure_timeout():
    seen = []
    unsub = events.subscribe("tool.timeout", lambda event_type, payload: seen.append(payload))

    def slow():
        time.sleep(0.2)
        return "late"

    tr.register_tool(tr.ToolSpec("too_slow", "slow", {}, "low"), lambda: slow())
    tr._allowlist.add("too_slow")
    res = tr.call_tool("too_slow", {}, user_id=1, session_id="s1", timeout=0.05)
    unsub()
    assert res["ok"] is False
    assert any(p["tool"] == "too_slow" for p in seen)


def test_tool_events_emitted():
    """Test that tool lifecycle events are emitted via EventBus."""
    events = []
    
    def capture_start_event(event_type, payload):
        events.append(("start", payload))
    
    def capture_end_event(event_type, payload):
        events.append(("end", payload))
    
    # Subscribe to events
    unsubscribe_start = subscribe("tool.start", capture_start_event)
    unsubscribe_end = subscribe("tool.end", capture_end_event)
    
    try:
        # Test successful tool
        def good_tool(**kwargs):
            return "success"
        
        tr.register_tool(tr.ToolSpec("good", "good", {}, "low"), good_tool)
        tr._allowlist.add("good")
        
        result = tr.call_tool("good", {"arg1": "value1", "api_key": "secret"}, user_id=1, session_id="test_session")
        
        assert result["ok"] is True
        assert len(events) == 2  # start and end
        
        start_event_type, start_payload = events[0]
        end_event_type, end_payload = events[1]
        
        assert start_event_type == "start"
        assert start_payload["tool"] == "good"
        assert start_payload["input_summary"]["arg1"] == "value1"
        assert start_payload["input_summary"]["api_key"] == "[REDACTED]"  # Redacted
        assert "trace_id" in start_payload
        assert "started_at" in start_payload
        assert "timeout_s" in start_payload
        
        assert end_event_type == "end"
        assert end_payload["tool"] == "good"
        assert "duration_ms" in end_payload
        assert end_payload["trace_id"] == start_payload["trace_id"]
        assert end_payload["error"] is None
        assert end_payload["output_summary"] == "7 chars"  # length of "success"
        
    finally:
        unsubscribe_start()
        unsubscribe_end()


def test_tool_failed_event_emitted():
    """Test that tool.error event is emitted on error."""
    events = []
    
    def capture_end_event(event_type, payload):
        events.append(payload)
    
    # Subscribe to error event
    unsubscribe_end = subscribe("tool.error", capture_end_event)
    
    try:
        def bad_tool(**kwargs):
            raise RuntimeError("test error")
        
        tr.register_tool(tr.ToolSpec("bad_event", "bad", {}, "low"), bad_tool)
        tr._allowlist.add("bad_event")
        
        result = tr.call_tool("bad_event", {}, user_id=1, session_id="test_session")
        
        assert result["ok"] is False
        assert len(events) >= 1
        
        end_payload = events[0]
        assert end_payload["tool"] == "bad_event"
        assert end_payload["error"]["type"] == "RuntimeError"
        assert end_payload["error"]["message"] == "test error"
        assert "duration_ms" in end_payload
        assert "trace_id" in end_payload
        assert end_payload["output_summary"] is None
        
    finally:
        unsubscribe_end()


def test_tool_timeout_event_emitted():
    """Test that tool.timeout event is emitted on timeout."""
    events = []
    errors = []
    
    def capture_end_event(event_type, payload):
        events.append(payload)
    def capture_error_event(event_type, payload):
        errors.append(payload)
    
    # Subscribe to timeout event
    unsubscribe_end = subscribe("tool.timeout", capture_end_event)
    unsubscribe_err = subscribe("tool.error", capture_error_event)
    
    try:
        def slow_tool(**kwargs):
            time.sleep(0.2)
            return "done"
        
        tr.register_tool(tr.ToolSpec("slow_timeout", "slow", {}, "low"), slow_tool)
        tr._allowlist.add("slow_timeout")
        
        result = tr.call_tool("slow_timeout", {}, user_id=1, session_id="test_session", timeout=0.05)
        
        assert result["ok"] is False
        assert result["error"]["type"] == "TimeoutError"
        assert len(events) >= 1
        
        end_payload = events[0]
        assert end_payload["tool"] == "slow_timeout"
        assert end_payload["error"]["type"] == "TimeoutError"
        assert "timed out" in end_payload["error"]["message"]
        assert "duration_ms" in end_payload
        assert "trace_id" in end_payload
        assert end_payload["output_summary"] is None
        # tool.error should also be emitted for failures
        assert any(err.get("tool") == "slow_timeout" for err in errors)
        
    finally:
        unsubscribe_end()
        unsubscribe_err()


def test_tool_error_event_includes_redacted_args():
    seen = []
    def capture_error(event_type, payload):
        seen.append(payload)
    unsub = subscribe("tool.error", capture_error)
    try:
        def bad_secret(**kwargs):
            raise RuntimeError("nope")
        tr.register_tool(tr.ToolSpec("secret_tool", "bad", {}, "low"), bad_secret)
        tr._allowlist.add("secret_tool")
        tr.call_tool("secret_tool", {"api_key": "supersecret", "plain": "ok"}, user_id=1, session_id="s1")
        assert seen, "expected tool.error event"
        payload = seen[0]
        # args are redacted in payload
        assert payload["args"]["api_key"] == "[REDACTED]"
        assert payload["args"]["plain"] == "ok"
        assert payload["error"]["type"] == "RuntimeError"
    finally:
        unsub()
