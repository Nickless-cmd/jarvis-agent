import pytest
from fastapi.testclient import TestClient
from jarvis import server
from jarvis.event_invariants import assert_event_system_clean

def test_events_teardown_invariants():
    """
    Regression: After using /v1/events and /v1/events/stream, all event system invariants must hold (no leaks).
    """
    client = TestClient(server.app)
    # Ensure user/token
    from jarvis.auth import register_user, login_user
    try:
        register_user("regression_user", "secret", email="regression@example.com")
    except Exception:
        pass
    token = login_user("regression_user", "secret")["token"]
    client.cookies.set("jarvis_token", token)
    with client as c:
        # Hit /v1/events
        resp = c.get("/v1/events?after=0")
        assert resp.status_code == 200
        # Hit /v1/events/stream with max_ms (short poll)
        resp = c.get("/v1/events/stream?max_ms=100")
        assert resp.status_code == 200
    # After context exit, assert invariants
    assert_event_system_clean()
