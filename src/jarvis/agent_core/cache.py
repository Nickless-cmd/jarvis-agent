"""
Small TTL cache utilities and simple invalidation flags.
"""

from __future__ import annotations

import copy
import threading
import time
from typing import Any, Dict, Hashable


class TTLCache:
    """A minimal thread-safe TTL cache."""

    def __init__(self, default_ttl: float = 60.0):
        self.default_ttl = default_ttl
        self._store: Dict[Hashable, tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get(self, key: Hashable) -> Any | None:
        """Return cached value if not expired; otherwise None."""
        now = time.time()
        with self._lock:
            entry = self._store.get(key)
            if not entry:
                return None
            expires_at, value = entry
            if expires_at and expires_at < now:
                self._store.pop(key, None)
                return None
            return copy.deepcopy(value)

    def set(self, key: Hashable, value: Any, ttl: float | None = None) -> None:
        """Store value with optional TTL (seconds)."""
        ttl_seconds = self.default_ttl if ttl is None else ttl
        expires_at = 0.0 if ttl_seconds <= 0 else time.time() + ttl_seconds
        with self._lock:
            self._store[key] = (expires_at, copy.deepcopy(value))

    def clear(self) -> None:
        """Clear all entries."""
        with self._lock:
            self._store.clear()

    def invalidate(self, key: Hashable) -> None:
        """Remove a single key if present."""
        with self._lock:
            self._store.pop(key, None)


_code_index_stale = False


def mark_code_index_stale() -> None:
    """Mark code index caches as stale."""
    global _code_index_stale
    _code_index_stale = True


def clear_code_index_stale() -> None:
    """Clear the stale flag for code index caches."""
    global _code_index_stale
    _code_index_stale = False


def is_code_index_stale() -> bool:
    """Return True if code index caches should be refreshed."""
    return _code_index_stale
