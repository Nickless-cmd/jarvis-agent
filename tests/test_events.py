from jarvis import events


def test_subscribe_and_publish():
    seen = []

    def cb(event_type, payload):
        seen.append(payload)

    events.subscribe("ping", cb)
    events.publish("ping", {"x": 1})
    events.publish("ping", {"x": 2})
    assert seen == [{"x": 1}, {"x": 2}]


def test_multiple_subscribers():
    seen_a = []
    seen_b = []

    def cb_a(event_type, payload):
        seen_a.append(payload)

    def cb_b(event_type, payload):
        seen_b.append(payload)

    events.subscribe("pong", cb_a)
    events.subscribe("pong", cb_b)
    events.publish("pong", 42)
    assert seen_a == [42]
    assert seen_b == [42]


def test_isolated_event_types():
    seen = []

    def cb(event_type, payload):
        seen.append(payload)

    events.subscribe("alpha", cb)
    events.publish("beta", 1)
    events.publish("alpha", 2)
    assert seen == [2]
