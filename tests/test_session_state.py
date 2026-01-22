from jarvis.session_state import get_session_state_manager
from jarvis.events import subscribe_all


def test_session_state_isolated_and_resets_between_sessions():
    mgr = get_session_state_manager()
    mgr._reset_for_tests()
    events = []
    unsub = subscribe_all(lambda et, payload: events.append((et, payload)))

    s1 = mgr.get_for_request("s1")
    s1.pending_city = "copenhagen"
    # Switch to new session should reset s1 transient state
    s2 = mgr.get_for_request("s2")
    assert s2.pending_city is None
    # Switching back should not see old pending_city (was reset)
    s1_again = mgr.get_for_request("s1")
    assert s1_again.pending_city is None

    # Events should include session.switch and session.reset
    event_types = [et for et, _ in events]
    assert "session.switch" in event_types
    assert "session.reset" in event_types
    unsub()


def test_session_state_no_bleed_same_session():
    mgr = get_session_state_manager()
    mgr._reset_for_tests()
    s1 = mgr.get_for_request("s1")
    s1.pending_city = "aarhus"
    s1_again = mgr.get_for_request("s1")
    assert s1_again.pending_city == "aarhus"
    # Another session should not see it
    s2 = mgr.get_for_request("s2")
    assert s2.pending_city is None
