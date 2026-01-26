"""
Minimal synchronous in-process event bus.

This abstraction is intentionally small and does not alter existing streaming behavior.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Callable, Dict, List, Any
import asyncio
import logging
import inspect

_logger = logging.getLogger(__name__)

# Mapping of event_type -> list of callbacks
_subs: Dict[str, List[Callable[[Any], None]]] = defaultdict(list)
# Wildcard subscribers receive (event_type, payload)
_wildcard_subs: List[Callable[[str, Any], None]] = []
_closed = False

# Async chat token batching state (NO LOCKS, NO BLOCKING)
_chat_token_buffers: Dict[str, Dict[str, Any]] = {}  # request_id -> buffer state
_flush_tasks: Dict[str, asyncio.Task] = {}  # request_id -> flush task
_callback_tasks: Dict[str, List[asyncio.Task]] = {}  # request_id -> list of callback tasks
_MAX_BATCH_TIME_MS = 75  # Flush every 75ms (debounce)
_MAX_BATCH_SIZE_BYTES = 1024  # Flush when buffer exceeds 1KB


def _run_callback(cb: Callable[[Any], None], event_type: str, payload: Any) -> None:
    """Run a subscriber callback; await/schedule if it is async to avoid RuntimeWarning."""
    try:
        res = cb(event_type, payload)
        if inspect.iscoroutine(res):
            try:
                # Create task and track it for cleanup
                task = asyncio.create_task(res)
                
                # Track task by request_id if available in payload
                request_id = payload.get("request_id") if isinstance(payload, dict) else None
                if request_id:
                    if request_id not in _callback_tasks:
                        _callback_tasks[request_id] = []
                    _callback_tasks[request_id].append(task)
                    _logger.debug(f"callback_task_created request_id={request_id} event={event_type}")
                
                # Add done callback to cleanup finished tasks
                def cleanup_task(t):
                    if request_id and request_id in _callback_tasks:
                        try:
                            _callback_tasks[request_id].remove(t)
                            if not _callback_tasks[request_id]:
                                _callback_tasks.pop(request_id, None)
                        except (ValueError, KeyError):
                            pass
                
                task.add_done_callback(cleanup_task)
                
            except RuntimeError:
                # If no running loop, run synchronously best-effort
                loop = asyncio.new_event_loop()
                try:
                    loop.run_until_complete(res)
                finally:
                    loop.close()
    except Exception as e:
        # Swallow subscriber exceptions to avoid affecting publisher
        _logger.debug(f"callback_error event={event_type} err={e}")
        pass


def _publish_direct(event_type: str, payload: Any) -> None:
    """Publish an event directly without batching logic."""
    callbacks = list(_subs.get(event_type, []))
    # Also notify wildcard subscribers
    if "*" in _subs:
        callbacks.extend(_subs["*"])
    for cb in callbacks:
        _run_callback(cb, event_type, payload)
    for cb in list(_wildcard_subs):
        _run_callback(cb, event_type, payload)


async def _flush_chat_token_buffer_async(request_id: str) -> None:
    """Async flush accumulated chat tokens for a request_id (debounced)."""
    try:
        # Wait for debounce period (NON-BLOCKING async sleep)
        await asyncio.sleep(_MAX_BATCH_TIME_MS / 1000.0)
        
        if request_id not in _chat_token_buffers:
            return
        
        buffer = _chat_token_buffers[request_id]
        accumulated_text = buffer["accumulated_text"]
        
        _logger.debug(f"flush_start request_id={request_id} size={len(accumulated_text)}")
        
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
            _logger.debug(f"flush_done request_id={request_id} tokens_sent={len(accumulated_text)}")
        
        # Remove the buffer and flush task
        _chat_token_buffers.pop(request_id, None)
        _flush_tasks.pop(request_id, None)
        
    except asyncio.CancelledError:
        _logger.debug(f"flush_cancelled request_id={request_id}")
        # Clean up on cancellation
        _chat_token_buffers.pop(request_id, None)
        _flush_tasks.pop(request_id, None)
        raise
    except Exception as e:
        _logger.warning(f"flush_error request_id={request_id} err={e}")
        _chat_token_buffers.pop(request_id, None)
        _flush_tasks.pop(request_id, None)


def _should_flush_immediately(buffer: Dict[str, Any]) -> bool:
    """Check if buffer should be flushed immediately (size limit reached)."""
    size_bytes = len(buffer["accumulated_text"].encode('utf-8'))
    return size_bytes >= _MAX_BATCH_SIZE_BYTES


def _handle_chat_token_event(payload: Dict[str, Any]) -> None:
    """Handle chat.token event with async batching (NON-BLOCKING)."""
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
    
    # NO LOCK - async-safe because we're only modifying dict in event loop
    if request_id not in _chat_token_buffers:
        _chat_token_buffers[request_id] = {
            "accumulated_text": "",
            "session_id": payload.get("session_id"),
            "trace_id": payload.get("trace_id"),
            "sequence": payload.get("sequence", 0),
        }
    
    buffer = _chat_token_buffers[request_id]
    buffer["accumulated_text"] += token
    
    # Update sequence if provided
    if "sequence" in payload:
        buffer["sequence"] = payload["sequence"]
    
    # If buffer too large, cancel existing flush and flush immediately
    if _should_flush_immediately(buffer):
        # Cancel existing debounce task
        if request_id in _flush_tasks:
            _flush_tasks[request_id].cancel()
        
        # Flush immediately (no debounce)
        accumulated = buffer["accumulated_text"]
        _publish_direct("chat.token", {
            "session_id": buffer["session_id"],
            "trace_id": buffer["trace_id"],
            "request_id": request_id,
            "token": accumulated,
            "sequence": buffer["sequence"],
            "batched": True,
        })
        _logger.debug(f"flush_immediate request_id={request_id} size={len(accumulated)}")
        _chat_token_buffers.pop(request_id, None)
        _flush_tasks.pop(request_id, None)
    else:
        # Schedule/reschedule debounced flush
        if request_id in _flush_tasks:
            # Cancel existing flush task (reset debounce timer)
            _flush_tasks[request_id].cancel()
        
        # Schedule new flush task (debounced)
        try:
            task = asyncio.create_task(_flush_chat_token_buffer_async(request_id))
            _flush_tasks[request_id] = task
            _logger.debug(f"flush_scheduled request_id={request_id}")
        except RuntimeError:
            # No event loop - fallback to immediate publish
            _publish_direct("chat.token", payload)


def _handle_chat_end_error(event_type: str, payload: Dict[str, Any]) -> None:
    """Handle chat.end and chat.error events by flushing any pending buffers."""
    request_id = payload.get("request_id")
    if not request_id:
        return
    
    # Cancel flush task and flush immediately
    if request_id in _flush_tasks:
        _flush_tasks[request_id].cancel()
        _flush_tasks.pop(request_id, None)
    
    # Flush buffer immediately (synchronously)
    if request_id in _chat_token_buffers:
        buffer = _chat_token_buffers[request_id]
        accumulated = buffer["accumulated_text"]
        
        if accumulated:
            _publish_direct("chat.token", {
                "session_id": buffer["session_id"],
                "trace_id": buffer["trace_id"],
                "request_id": request_id,
                "token": accumulated,
                "sequence": buffer["sequence"],
                "batched": True,
            })
            _logger.debug(f"flush_on_end request_id={request_id} size={len(accumulated)}")
        
        _chat_token_buffers.pop(request_id, None)


def subscribe(event_type: str, callback: Callable[[str, Any], None]) -> Callable[[], None]:
    """
    Subscribe to an event type. Callback receives (event_type, payload).

    Returns:
        unsubscribe function.
    """
    if _closed:
        return lambda: None
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
    if _closed:
        return lambda: None
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
    if _closed:
        return
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
        _run_callback(cb, event_type, payload)
    for cb in list(_wildcard_subs):
        _run_callback(cb, event_type, payload)


def close() -> None:
    """Idempotent shutdown to help tests exit cleanly."""
    global _closed
    _closed = True
    _subs.clear()
    _wildcard_subs.clear()
    
    # Cancel all flush tasks
    for task in list(_flush_tasks.values()):
        task.cancel()
    _flush_tasks.clear()
    
    # Cancel all callback tasks
    for tasks in list(_callback_tasks.values()):
        for task in tasks:
            if not task.done():
                task.cancel()
    _callback_tasks.clear()
    
    # Flush any remaining buffers synchronously
    for request_id, buffer in list(_chat_token_buffers.items()):
        accumulated = buffer["accumulated_text"]
        if accumulated:
            _publish_direct("chat.token", {
                "session_id": buffer["session_id"],
                "trace_id": buffer["trace_id"],
                "request_id": request_id,
                "token": accumulated,
                "sequence": buffer["sequence"],
                "batched": True,
            })
    _chat_token_buffers.clear()
    _logger.info("events_bus_closed")


def reset_for_tests() -> None:
    """Clear subscriptions and reopen the bus (used by tests)."""
    global _closed
    _closed = False
    _subs.clear()
    _wildcard_subs.clear()
    
    # Cancel all flush tasks
    for task in list(_flush_tasks.values()):
        task.cancel()
    _flush_tasks.clear()
    
    # Cancel all callback tasks
    for tasks in list(_callback_tasks.values()):
        for task in tasks:
            if not task.done():
                task.cancel()
    _callback_tasks.clear()
    
    _chat_token_buffers.clear()


def shutdown() -> None:
    """Alias for close() to make lifecycle naming explicit."""
    close()


def cleanup_request_buffers(request_id: str) -> None:
    """Cancel flush task, callback tasks, and clear buffer for a specific request (for cleanup on stream end)."""
    # Cancel flush task
    if request_id in _flush_tasks:
        _flush_tasks[request_id].cancel()
        _flush_tasks.pop(request_id, None)
        _logger.debug(f"cleanup_flush_task request_id={request_id}")
    
    # Cancel all callback tasks for this request
    if request_id in _callback_tasks:
        tasks = _callback_tasks[request_id]
        for task in tasks:
            if not task.done():
                task.cancel()
        _callback_tasks.pop(request_id, None)
        _logger.debug(f"cleanup_callback_tasks request_id={request_id} count={len(tasks)}")
    
    # Flush remaining tokens
    if request_id in _chat_token_buffers:
        buffer = _chat_token_buffers[request_id]
        accumulated = buffer["accumulated_text"]
        
        # Flush any remaining tokens before cleanup
        if accumulated:
            _publish_direct("chat.token", {
                "session_id": buffer["session_id"],
                "trace_id": buffer["trace_id"],
                "request_id": request_id,
                "token": accumulated,
                "sequence": buffer["sequence"],
                "batched": True,
            })
            _logger.debug(f"flush_on_cleanup request_id={request_id} size={len(accumulated)}")
        
        _chat_token_buffers.pop(request_id, None)
        _logger.debug(f"cleanup_buffer request_id={request_id}")
    
    _logger.info(f"cleanup_request_complete request_id={request_id}")
