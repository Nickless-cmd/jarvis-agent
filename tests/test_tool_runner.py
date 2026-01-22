import time

import jarvis.agent_core.tool_registry as tr


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
