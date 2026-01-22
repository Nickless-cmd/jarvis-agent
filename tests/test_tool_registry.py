import os

import jarvis.agent_core.tool_registry as registry
from jarvis.db import get_conn


def test_allow_and_deny_tool(tmp_path, monkeypatch):
    # Isolate DB and registry
    monkeypatch.setenv("JARVIS_DB_PATH", str(tmp_path / "db.sqlite"))
    registry._reset_registry_for_tests()
    monkeypatch.setenv("JARVIS_TOOL_ALLOWLIST", "foo")
    registry._allowlist.clear()

    calls = {}

    def foo(arg=None):
        calls["arg"] = arg
        return "ok"

    registry.register_tool(registry.ToolSpec("foo", "test", {}, "low"), foo)
    result = registry.call_tool("foo", {"arg": 1}, user_id=1)
    assert result["ok"] is True
    assert result["data"] == "ok"
    assert calls["arg"] == 1

    # Unknown tool should be denied
    res = registry.call_tool("bar", {}, user_id=1)
    assert res["ok"] is False
    assert res["error"]["type"] in {"ToolError", "ToolError"}


def test_audit_and_redaction(tmp_path, monkeypatch):
    monkeypatch.setenv("JARVIS_DB_PATH", str(tmp_path / "db.sqlite"))
    registry._reset_registry_for_tests()
    monkeypatch.setenv("JARVIS_TOOL_ALLOWLIST", "secret_tool")
    registry._allowlist.clear()

    def secret_tool(token, value):
        return {"value": value}

    registry.register_tool(
        registry.ToolSpec("secret_tool", "test", {"token": {}, "value": {}}, "medium"),
        secret_tool,
    )
    registry.call_tool("secret_tool", {"token": "supersecret", "value": 42}, user_id=5, session_id="s1")

    # Verify audit log redacts token
    with get_conn() as conn:
        rows = conn.execute("SELECT args_redacted FROM tool_audit ORDER BY id DESC LIMIT 1").fetchall()
    assert rows
    payload = rows[0][0]
    assert "REDACTED" in payload
    assert "supersecret" not in payload


def test_tool_cache(monkeypatch, tmp_path):
    monkeypatch.setenv("JARVIS_DB_PATH", str(tmp_path / "db.sqlite"))
    monkeypatch.setenv("JARVIS_TOOL_ALLOWLIST", "cached_tool")
    import jarvis.agent_core.tool_registry as registry

    registry._reset_registry_for_tests()
    calls = {"n": 0}

    def cached_tool(x):
        calls["n"] += 1
        return {"x": x}

    registry.TOOL_CACHE_TTLS["cached_tool"] = 1
    registry.register_tool(registry.ToolSpec("cached_tool", "test", {}, "low"), cached_tool)

    res1 = registry.call_tool("cached_tool", {"x": 1}, user_id=1)
    assert res1["ok"] is True and res1["data"] == {"x": 1}
    assert calls["n"] == 1

    res2 = registry.call_tool("cached_tool", {"x": 1}, user_id=1)
    assert res2["ok"] is True and res2["data"] == {"x": 1}
    assert calls["n"] == 1  # cached, not invoked again

    registry._tool_cache.clear()
    registry.call_tool("cached_tool", {"x": 1}, user_id=1)
    assert calls["n"] == 2


def test_tool_exception_envelope(monkeypatch, tmp_path):
    monkeypatch.setenv("JARVIS_DB_PATH", str(tmp_path / "db.sqlite"))
    monkeypatch.setenv("JARVIS_TOOL_ALLOWLIST", "boom")
    import jarvis.agent_core.tool_registry as registry
    registry._reset_registry_for_tests()
    def boom():
        raise RuntimeError("explode")
    registry.register_tool(registry.ToolSpec("boom", "test", {}, "low"), boom)
    res = registry.call_tool("boom", {}, user_id=1)
    assert res["ok"] is False
    assert res["error"]["type"] == "RuntimeError"
    assert res["error"]["trace_id"]


def test_safe_tool_call_catches_exception():
    import jarvis.agent_core.tool_registry as registry
    
    def failing_fn():
        raise ValueError("test error")
    
    result = registry.safe_tool_call("test_tool", failing_fn)
    assert result["ok"] is False
    assert result["data"] is None
    assert result["error"]["type"] == "ValueError"
    assert result["error"]["message"] == "test error"
    assert result["error"]["trace_id"]
    assert result["error"]["where"] == "test_tool"


def test_agent_flow_survives_tool_exception():
    # This is a minimal test to ensure the agent flow doesn't crash on tool exceptions
    # We'll mock a tool that fails and ensure the agent returns a controlled error response
    import jarvis.agent_core.tool_registry as registry
    from jarvis.agent import _tool_failed
    
    # Simulate a failed tool result as returned by safe_tool_call
    failed_result = {
        "ok": False,
        "data": None,
        "error": {
            "type": "ValueError",
            "message": "test error",
            "trace_id": "abc123",
            "where": "test_tool"
        }
    }
    
    # Test that _tool_failed detects the failure
    failure = _tool_failed("test_tool", failed_result)
    assert failure is not None
    reason, detail = failure
    assert reason == "test error"
    assert detail is None
