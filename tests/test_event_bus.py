import time

from jarvis.event_bus import Event, EventBus


def test_publish_and_subscribe_order():
    """Test that events are delivered in order to subscribers."""
    bus = EventBus(backlog_size=10)
    seen = []

    def cb(ev):
        seen.append(ev.type)

    bus.subscribe("test_event", cb)
    bus.publish(Event("test_event", time.time(), payload={"data": "a"}))
    bus.publish(Event("test_event", time.time(), payload={"data": "b"}))
    assert seen == ["test_event", "test_event"]


def test_unsubscribe():
    """Test that unsubscribe removes the callback."""
    bus = EventBus(backlog_size=10)
    seen = []

    def cb(ev):
        seen.append(ev.type)

    bus.subscribe("test_event", cb)
    bus.publish(Event("test_event", time.time()))
    bus.unsubscribe("test_event", cb)
    bus.publish(Event("test_event", time.time()))
    assert seen == ["test_event"]


def test_session_subscription():
    """Test session-specific subscriptions."""
    bus = EventBus(backlog_size=10)
    seen = []

    def cb(ev):
        seen.append((ev.type, ev.session_id))

    bus.subscribe_session("session1", "test_event", cb)
    bus.publish(Event("test_event", time.time(), session_id="session1"))
    bus.publish(Event("test_event", time.time(), session_id="session2"))
    bus.publish(Event("other_event", time.time(), session_id="session1"))
    assert seen == [("test_event", "session1")]


def test_backlog_maxlen():
    """Test that backlog respects maxlen."""
    bus = EventBus(backlog_size=3)
    for i in range(5):
        bus.publish(Event(f"e{i}", time.time(), payload={"i": i}))
    bl = bus.get_backlog()
    assert len(bl) == 3
    assert [e.type for e in bl] == ["e2", "e3", "e4"]


def test_backlog_filtering():
    """Test backlog filtering by event type and session."""
    bus = EventBus(backlog_size=10)
    bus.publish(Event("type1", time.time(), session_id="s1"))
    bus.publish(Event("type2", time.time(), session_id="s1"))
    bus.publish(Event("type1", time.time(), session_id="s2"))

    # Filter by type
    type1_events = bus.get_backlog(event_type="type1")
    assert len(type1_events) == 2
    assert all(e.type == "type1" for e in type1_events)

    # Filter by session
    s1_events = bus.get_backlog(session_id="s1")
    assert len(s1_events) == 2
    assert all(e.session_id == "s1" for e in s1_events)

    # Filter by both
    type1_s1_events = bus.get_backlog(event_type="type1", session_id="s1")
    assert len(type1_s1_events) == 1
    assert type1_s1_events[0].type == "type1"
    assert type1_s1_events[0].session_id == "s1"
