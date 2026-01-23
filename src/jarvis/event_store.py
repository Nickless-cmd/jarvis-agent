"""
In-memory event store fed by the EventBus. This module does not change
any runtime wiring; it simply provides storage helpers for future use.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from threading import Lock
from typing import Any, Deque, Dict, List, Optional

from jarvis import events

def _get_lock_class():
    import os
    if os.getenv("JARVIS_TEST_MODE") == "1":
        class DummyLock:
            def __enter__(self):
                pass
            def __exit__(self, *args):
                pass
        return DummyLock
    else:
        from threading import Lock
        return Lock


@dataclass
class StoredEvent:
    id: int
    type: str
    ts: float
    payload: Dict[str, Any]
    session_id: Optional[str] = None


def _format_event(ev: StoredEvent) -> Dict[str, Any]:
    data = {
        "id": ev.id,
        "type": ev.type,
        "ts": ev.ts,
        "payload": ev.payload,
        "session_id": ev.session_id,
    }
    # Bubble up common identifiers for easier consumption
    for key in ("request_id", "message_id", "trace_id"):
        if key in ev.payload:
            data[key] = ev.payload[key]
    return data


class EventStore:
    """Bounded in-memory event store."""

    def __init__(self, max_size: int = 1000) -> None:
        self._events: Deque[StoredEvent] = deque(maxlen=max_size)
        self._next_id = 1
        self._lock = _get_lock_class()()

    def append(self, event_type: str, payload: Dict[str, Any], session_id: Optional[str] = None) -> StoredEvent:
        with self._lock:
            ev = StoredEvent(
                id=self._next_id,
                type=event_type,
                ts=time.time(),
                payload=payload,
                session_id=session_id or payload.get("session_id"),
            )
            self._events.append(ev)
            self._next_id += 1
            return ev

    def get_events(self, after: Optional[int] = None, limit: Optional[int] = None) -> Dict[str, Any]:
        with self._lock:
            items = [ev for ev in self._events if after is None or ev.id > after]
            if limit is not None:
                items = items[:limit]
            last_id = items[-1].id if items else (after or 0)
            return {
                "events": [
                    _format_event(ev) for ev in items
                ],
                "last_id": last_id,
            }

    def get_events_snapshot(self, after: Optional[int] = None, limit: Optional[int] = None) -> Dict[str, Any]:
        """Non-blocking snapshot of current events. No wait() or Condition usage."""
        return self.get_events(after=after, limit=limit)

    def _reset_for_tests(self) -> None:
        with self._lock:
            self._events.clear()
            self._next_id = 1

    def clear(self) -> None:
        self._reset_for_tests()

    def shutdown(self) -> None:
        """Shutdown the event store, clearing events and closing the bus."""
        with self._lock:
            self._events.clear()
            self._next_id = 1
        # Close the bus if available
        try:
            events.close()
        except Exception:
            pass


_store: Optional[EventStore] = None
_bus_unsubscribe = None


def get_event_store() -> EventStore:
    global _store
    if _store is None:
        _store = EventStore()
    return _store


def wire_event_store_to_bus() -> None:
    """Ensure the global EventStore is subscribed to the EventBus."""
    global _bus_unsubscribe
    if _bus_unsubscribe:
        try:
            _bus_unsubscribe()
        except Exception:
            pass
    store = get_event_store()
    try:
        _bus_unsubscribe = events.subscribe_all(lambda et, payload: store.append(et, payload))
    except Exception:
        _bus_unsubscribe = None
