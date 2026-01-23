"""
Internal invariant checks for event system (test/debug only).
"""
from jarvis import event_bus, event_store, events
import threading

def assert_event_system_clean():
    """
    Assert that there are no active EventBus subscribers, no EventStore waiters, and no background threads.
    Intended for use in tests only.
    """
    # EventBus: no global or session subscribers
    bus = getattr(event_bus, 'EventBus', None)
    if bus:
        # If using instance, check all instances (test may use globals)
        for obj in bus.__subclasses__() + [bus]:
            for inst in getattr(obj, '__dict__', {}).values():
                if hasattr(inst, '_subscribers') and inst._subscribers:
                    assert not any(inst._subscribers.values()), f"EventBus global subscribers not empty: {inst._subscribers}"
                if hasattr(inst, '_session_subscribers') and inst._session_subscribers:
                    assert not any(v for v in inst._session_subscribers.values()), f"EventBus session subscribers not empty: {inst._session_subscribers}"
    # events.py: no _subs or _wildcard_subs
    if hasattr(events, '_subs'):
        assert not any(events._subs.values()), f"events._subs not empty: {events._subs}"
    if hasattr(events, '_wildcard_subs'):
        assert not events._wildcard_subs, f"events._wildcard_subs not empty: {events._wildcard_subs}"
    # EventStore: no waiters/conditions (if implemented)
    if hasattr(event_store, 'get_event_store'):
        store = event_store.get_event_store()
        if hasattr(store, '_waiters'):
            assert not store._waiters, f"EventStore _waiters not empty: {store._waiters}"
        if hasattr(store, '_conditions'):
            assert not store._conditions, f"EventStore _conditions not empty: {store._conditions}"
    # No non-daemon background threads except main
    threads = threading.enumerate()
    non_daemon = [t for t in threads if not t.daemon and t != threading.main_thread()]
    assert not non_daemon, f"Non-daemon threads found: {[t.name for t in non_daemon]}"
