from fastapi.testclient import TestClient

from jarvis import server


def _collect_stream_text(stream_resp):
    parts = []
    for chunk in stream_resp.iter_text():
        parts.append(chunk)
    return "".join(parts)


def test_stream_handles_provider_error(monkeypatch):
    monkeypatch.setattr(
        server,
        "_resolve_user",
        lambda token: {"id": 1, "username": "tester", "is_admin": False, "is_disabled": 0},
    )
    monkeypatch.setattr(server, "_resolve_session_id", lambda user, session_id, logged_in: "session-1")
    monkeypatch.setattr(server, "add_message", lambda *args, **kwargs: None)
    monkeypatch.setattr(server, "_cleanup_user_assets", lambda user: None)
    monkeypatch.setattr(server, "_get_user_quota", lambda user_id: (0, 0))
    monkeypatch.setattr(server, "_monthly_usage_bytes", lambda user_id: 0)
    monkeypatch.setattr(server, "_quota_warning", lambda *args, **kwargs: None)

    def boom(*args, **kwargs):
        raise RuntimeError("llm down")

    monkeypatch.setattr(server, "run_agent", boom)

    client = TestClient(server.app)
    with client.stream(
        "POST",
        "/v1/chat/completions",
        headers={"Authorization": "Bearer devkey"},
        json={"model": "local", "messages": [{"role": "user", "content": "hi"}], "stream": True},
    ) as resp:
        body = _collect_stream_text(resp)

    assert resp.status_code == 200
    assert "event: error" in body
    assert "Provider or server error" in body


def test_stream_client_disconnect(monkeypatch):
    monkeypatch.setattr(
        server,
        "_resolve_user",
        lambda token: {"id": 1, "username": "tester", "is_admin": False, "is_disabled": 0},
    )
    monkeypatch.setattr(server, "_resolve_session_id", lambda user, session_id, logged_in: "session-1")
    monkeypatch.setattr(server, "add_message", lambda *args, **kwargs: None)
    monkeypatch.setattr(server, "_cleanup_user_assets", lambda user: None)
    monkeypatch.setattr(server, "_get_user_quota", lambda user_id: (0, 0))
    monkeypatch.setattr(server, "_monthly_usage_bytes", lambda user_id: 0)
    monkeypatch.setattr(server, "_quota_warning", lambda *args, **kwargs: None)

    def quick_reply(*args, **kwargs):
        return {"text": "hello world"}

    monkeypatch.setattr(server, "run_agent", quick_reply)
    client = TestClient(server.app)
    with client.stream(
        "POST",
        "/v1/chat/completions",
        headers={"Authorization": "Bearer devkey"},
        json={"model": "local", "messages": [{"role": "user", "content": "hi"}], "stream": True},
    ) as resp:
        iterator = resp.iter_text()
        next(iterator, None)
    # If disconnect handling is broken, this context would raise
    assert resp.status_code == 200


def test_stream_handles_cancelled_error(monkeypatch):
    """Test that CancelledError in run_agent is handled gracefully without stacktraces."""
    import asyncio
    
    monkeypatch.setattr(
        server,
        "_resolve_user",
        lambda token: {"id": 1, "username": "tester", "is_admin": False, "is_disabled": 0},
    )
    monkeypatch.setattr(server, "_resolve_session_id", lambda user, session_id, logged_in: "session-1")
    monkeypatch.setattr(server, "add_message", lambda *args, **kwargs: None)
    monkeypatch.setattr(server, "_cleanup_user_assets", lambda user: None)
    monkeypatch.setattr(server, "_get_user_quota", lambda user_id: (0, 0))
    monkeypatch.setattr(server, "_monthly_usage_bytes", lambda user_id: 0)
    monkeypatch.setattr(server, "_quota_warning", lambda *args, **kwargs: None)

    def cancelled_agent(*args, **kwargs):
        raise asyncio.CancelledError("Client disconnected")

    monkeypatch.setattr(server, "run_agent", cancelled_agent)

    client = TestClient(server.app)
    with client.stream(
        "POST",
        "/v1/chat/completions",
        headers={"Authorization": "Bearer devkey"},
        json={"model": "local", "messages": [{"role": "user", "content": "hi"}], "stream": True},
    ) as resp:
        body = _collect_stream_text(resp)

    assert resp.status_code == 200
    # Should not contain error event since CancelledError is handled silently
    assert "event: error" not in body
    # Should contain thinking status but not complete
    assert "event: status" in body
