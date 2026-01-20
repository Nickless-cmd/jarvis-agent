import os

from jarvis.notifications.store import add_event, list_events


def test_add_and_list_events(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("JARVIS_DB_PATH", str(db_path))
    evt_id = add_event(1, type="info", title="Hello", body="World")
    assert evt_id
    events = list_events(1)
    assert events
    assert events[0]["title"] == "Hello"
    assert events[0]["body"] == "World"
