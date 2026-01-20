import os

from jarvis.notifications.store import add_event, list_events, add_notification, list_notifications, mark_notification_read


def test_add_and_list_events(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("JARVIS_DB_PATH", str(db_path))
    evt_id = add_event(1, type="info", title="Hello", body="World")
    assert evt_id
    events = list_events(1)
    assert events
    assert events[0]["title"] == "Hello"
    assert events[0]["body"] == "World"


def test_add_and_list_notifications(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("JARVIS_DB_PATH", str(db_path))
    notif_id = add_notification(1, "info", "Test Notification", "This is a test")
    assert notif_id
    notifications = list_notifications(1)
    assert notifications
    assert notifications[0]["title"] == "Test Notification"
    assert notifications[0]["body"] == "This is a test"
    assert notifications[0]["level"] == "info"
    assert not notifications[0]["read"]


def test_mark_notification_read(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("JARVIS_DB_PATH", str(db_path))
    notif_id = add_notification(1, "info", "Test Notification", "This is a test")
    assert notif_id
    
    # Mark as read
    mark_notification_read(1, notif_id)
    
    # Check it's marked as read
    notifications = list_notifications(1)
    assert notifications[0]["read"]
