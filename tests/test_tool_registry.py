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
    assert result == "ok"
    assert calls["arg"] == 1

    # Unknown tool should be denied
    try:
        registry.call_tool("bar", {}, user_id=1)
    except ValueError as exc:
        assert "not registered" in str(exc) or "allowlist" in str(exc)
    else:  # pragma: no cover
        assert False, "Expected ValueError"


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
    assert res1 == {"x": 1}
    assert calls["n"] == 1

    res2 = registry.call_tool("cached_tool", {"x": 1}, user_id=1)
    assert res2 == {"x": 1}
    assert calls["n"] == 1  # cached, not invoked again

    registry._tool_cache.clear()
    registry.call_tool("cached_tool", {"x": 1}, user_id=1)
    assert calls["n"] == 2
