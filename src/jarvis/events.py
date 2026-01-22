"""
Minimal synchronous in-process event bus.

This abstraction is intentionally small and does not alter existing streaming behavior.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Callable, Dict, List, Any

# Mapping of event_type -> list of callbacks
_subs: Dict[str, List[Callable[[Any], None]]] = defaultdict(list)
# Wildcard subscribers receive (event_type, payload)
_wildcard_subs: List[Callable[[str, Any], None]] = []


def subscribe(event_type: str, callback: Callable[[str, Any], None]) -> Callable[[], None]:
    """
    Subscribe to an event type. Callback receives (event_type, payload).

    Returns:
        unsubscribe function.
    """
    _subs[event_type].append(callback)

    def unsubscribe() -> None:
        try:
            _subs[event_type].remove(callback)
        except ValueError:
            pass

    return unsubscribe


def subscribe_all(callback: Callable[[str, Any], None]) -> Callable[[], None]:
    """
    Subscribe to all events. Callback receives (event_type, payload).
    """
    _wildcard_subs.append(callback)

    def unsubscribe() -> None:
        try:
            _wildcard_subs.remove(callback)
        except ValueError:
            pass

    return unsubscribe


def publish(event_type: str, payload: Any) -> None:
    """Publish an event to subscribers of the given type."""
    callbacks = list(_subs.get(event_type, []))
    # Also notify wildcard subscribers
    if "*" in _subs:
        callbacks.extend(_subs["*"])
    for cb in callbacks:
        try:
            cb(event_type, payload)
        except Exception:
            # Swallow subscriber exceptions to avoid affecting publisher
            pass
    for cb in list(_wildcard_subs):
        try:
            cb(event_type, payload)
        except Exception:
            pass
