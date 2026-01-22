"""
Minimal EventBus for inter-component communication.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from threading import Lock
from typing import Any, Callable, Dict, Optional


@dataclass
class Event:
    """Represents an event in the system."""
    type: str
    ts: float
    session_id: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None


class EventBus:
    """Thread-safe event bus with backlog buffer."""

    def __init__(self, backlog_size: int = 1000) -> None:
        self._lock = Lock()
        self._subscribers: Dict[str, list[Callable[[Event], None]]] = {}
        self._session_subscribers: Dict[str, Dict[str, list[Callable[[Event], None]]]] = {}
        self._backlog = deque(maxlen=backlog_size)

    def publish(self, event: Event) -> None:
        """Publish an event to all subscribers."""
        with self._lock:
            # Add to backlog
            self._backlog.append(event)

            # Notify global subscribers for this event type
            if event.type in self._subscribers:
                for callback in self._subscribers[event.type]:
                    try:
                        callback(event)
                    except Exception:
                        # Log error but don't crash the publisher
                        pass

            # Notify session-specific subscribers
            if event.session_id and event.session_id in self._session_subscribers:
                session_subs = self._session_subscribers[event.session_id]
                if event.type in session_subs:
                    for callback in session_subs[event.type]:
                        try:
                            callback(event)
                        except Exception:
                            # Log error but don't crash the publisher
                            pass

    def subscribe(self, event_type: str, callback: Callable[[Event], None]) -> None:
        """Subscribe to events of a specific type globally."""
        with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            self._subscribers[event_type].append(callback)

    def unsubscribe(self, event_type: str, callback: Callable[[Event], None]) -> None:
        """Unsubscribe from events of a specific type globally."""
        with self._lock:
            if event_type in self._subscribers:
                try:
                    self._subscribers[event_type].remove(callback)
                    # Clean up empty lists
                    if not self._subscribers[event_type]:
                        del self._subscribers[event_type]
                except ValueError:
                    pass  # Callback not found, ignore

    def subscribe_session(self, session_id: str, event_type: str, callback: Callable[[Event], None]) -> None:
        """Subscribe to events of a specific type for a specific session."""
        with self._lock:
            if session_id not in self._session_subscribers:
                self._session_subscribers[session_id] = {}
            if event_type not in self._session_subscribers[session_id]:
                self._session_subscribers[session_id][event_type] = []
            self._session_subscribers[session_id][event_type].append(callback)

    def unsubscribe_session(self, session_id: str, event_type: str, callback: Callable[[Event], None]) -> None:
        """Unsubscribe from events of a specific type for a specific session."""
        with self._lock:
            if session_id in self._session_subscribers and event_type in self._session_subscribers[session_id]:
                try:
                    self._session_subscribers[session_id][event_type].remove(callback)
                    # Clean up empty lists
                    if not self._session_subscribers[session_id][event_type]:
                        del self._session_subscribers[session_id][event_type]
                    if not self._session_subscribers[session_id]:
                        del self._session_subscribers[session_id]
                except ValueError:
                    pass  # Callback not found, ignore

    def get_backlog(self, event_type: Optional[str] = None, session_id: Optional[str] = None) -> list[Event]:
        """Get events from backlog, optionally filtered by type and/or session."""
        with self._lock:
            events = list(self._backlog)
            if event_type:
                events = [e for e in events if e.type == event_type]
            if session_id:
                events = [e for e in events if e.session_id == session_id]
            return events

    def clear_backlog(self) -> None:
        """Clear the event backlog."""
        with self._lock:
            self._backlog.clear()


# Global instance
_event_bus = EventBus()


def get_event_bus() -> EventBus:
    """Get the global event bus instance."""
    return _event_bus

