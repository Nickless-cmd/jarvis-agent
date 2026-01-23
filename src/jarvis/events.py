"""
Minimal synchronous in-process event bus.

This abstraction is intentionally small and does not alter existing streaming behavior.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Callable, Dict, List, Any
import asyncio
import time
import threading

# Mapping of event_type -> list of callbacks
_subs: Dict[str, List[Callable[[Any], None]]] = defaultdict(list)
# Wildcard subscribers receive (event_type, payload)
_wildcard_subs: List[Callable[[str, Any], None]] = []


# Chat token batching state
_chat_token_buffers: Dict[str, Dict[str, Any]] = {}
_chat_token_lock = threading.Lock()
_MAX_BATCH_TIME_MS = 75  # Flush every 75ms
_MAX_BATCH_SIZE_BYTES = 1024  # Flush when buffer exceeds 1KB


def _publish_direct(event_type: str, payload: Any) -> None:
    """Publish an event directly without batching logic."""
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


def _flush_chat_token_buffer(request_id: str) -> None:
    """Flush accumulated chat tokens for a request_id."""
    with _chat_token_lock:
        if request_id not in _chat_token_buffers:
            return
        
        buffer = _chat_token_buffers[request_id]
        accumulated_text = buffer["accumulated_text"]
        
        if accumulated_text:
            # Publish the batched event directly (avoid recursion)
            _publish_direct("chat.token", {
                "session_id": buffer["session_id"],
                "trace_id": buffer["trace_id"],
                "request_id": request_id,
                "token": accumulated_text,
                "sequence": buffer["sequence"],
                "batched": True,
            })
        
        # Remove the buffer
        del _chat_token_buffers[request_id]


def _should_flush_buffer(buffer: Dict[str, Any]) -> bool:
    """Check if buffer should be flushed based on time or size."""
    now = time.time() * 1000  # milliseconds
    time_elapsed = now - buffer["last_flush_time"]
    size_bytes = len(buffer["accumulated_text"].encode('utf-8'))
    
    return time_elapsed >= _MAX_BATCH_TIME_MS or size_bytes >= _MAX_BATCH_SIZE_BYTES


def _handle_chat_token_event(payload: Dict[str, Any]) -> None:
    """Handle chat.token event with batching."""
    request_id = payload.get("request_id")
    if not request_id:
        # No request_id, publish immediately
        _publish_direct("chat.token", payload)
        return
    
    token = payload.get("token", "")
    if not token:
        # Empty token, publish immediately
        _publish_direct("chat.token", payload)
        return
    
    with _chat_token_lock:
        if request_id not in _chat_token_buffers:
            _chat_token_buffers[request_id] = {
                "accumulated_text": "",
                "last_flush_time": time.time() * 1000,  # milliseconds
                "session_id": payload.get("session_id"),
                "trace_id": payload.get("trace_id"),
                "sequence": payload.get("sequence", 0),
            }
        
        buffer = _chat_token_buffers[request_id]
        buffer["accumulated_text"] += token
        
        # Update sequence if provided
        if "sequence" in payload:
            buffer["sequence"] = payload["sequence"]
        
        # Check if we should flush
        if _should_flush_buffer(buffer):
            _flush_chat_token_buffer(request_id)


def _cleanup_old_buffers() -> None:
    """Clean up buffers that haven't been flushed for too long."""
    now = time.time() * 1000  # milliseconds
    to_remove = []
    
    with _chat_token_lock:
        for request_id, buffer in _chat_token_buffers.items():
            if now - buffer["last_flush_time"] > 5000:  # 5 seconds
                to_remove.append(request_id)
        
        for request_id in to_remove:
            _flush_chat_token_buffer(request_id)


def _handle_chat_end_error(event_type: str, payload: Dict[str, Any]) -> None:
    """Handle chat.end and chat.error events by flushing any pending buffers."""
    request_id = payload.get("request_id")
    if request_id:
        _flush_chat_token_buffer(request_id)
    
    # Also cleanup old buffers periodically
    _cleanup_old_buffers()


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


async def subscribe_async(event_types: List[str], session_filter: str | None = None) -> asyncio.Queue:
    """
    Subscribe to multiple event types and return an async queue.
    Events are filtered by session_id if provided.
    
    Returns a queue that will receive (event_type, payload) tuples.
    """
    queue = asyncio.Queue()
    
    def handler(event_type, payload):
        if session_filter and payload.get("session_id") != session_filter:
            return
        queue.put_nowait((event_type, payload))
    
    unsubscribers = []
    for event_type in event_types:
        unsubscribers.append(subscribe(event_type, handler))
    
    # Return queue and cleanup function
    def cleanup():
        for unsub in unsubscribers:
            try:
                unsub()
            except Exception:
                pass
    
    queue.cleanup = cleanup  # type: ignore
    return queue


def publish(event_type: str, payload: Any) -> None:
    """Publish an event to subscribers of the given type."""
    # Handle chat token batching
    if event_type == "chat.token":
        _handle_chat_token_event(payload)
        return
    elif event_type in ("chat.end", "chat.error"):
        _handle_chat_end_error(event_type, payload)
    
    # Normal publishing
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
