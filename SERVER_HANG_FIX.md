# Server Hang Fix: Streaming Cancellation & Cleanup

## Problem: Server Hangs on New Prompt

When a user sends a new prompt without pressing stop:
1. Old stream continues running, holding resources
2. New stream starts for same session
3. Both streams compete for agent_task, event queue, resources
4. **Deadlock occurs**: task switching, resource conflicts → server must be killed with `kill -9`

**Root Cause**: Previous stream was not being cancelled/cleaned up before new stream started.

## Solution: Proper Per-Session Stream Cancellation

### 1. Synchronous Wait on Stream Replacement (StreamRegistry.register)

**BEFORE:**
```python
async def register(self, entry: _StreamEntry):
    async with self._lock:
        # Cancel previous stream but DON'T wait
        if prev_trace in self._by_trace:
            prev["task"].cancel()  # Fire & forget
        self._by_trace[entry["trace_id"]] = entry  # Register immediately
```

**AFTER:**
```python
async def register(self, entry: _StreamEntry):
    async with self._lock:
        # Get previous task reference and cancel
        prev_task = prev["task"]
    # Release lock, wait outside to avoid blocking
    if prev_task:
        await asyncio.wait_for(prev_task, timeout=2.0)  # Wait max 2s
    # Then register new stream
    async with self._lock:
        self._by_trace[entry["trace_id"]] = entry
```

**Why this works:**
- Old stream's finally block runs to completion (cleanup)
- Resources are released: event queue, agent task cancelled, registry entry removed
- New stream only registers after old one is fully done
- No resource contention or deadlock

### 2. Cancellation Flag Propagation to Ollama

StreamRegistry.cancel() now also calls `set_stream_cancelled(trace_id)`:
```python
async def cancel(self, trace_id: str, reason: str | None = None):
    # Cancel the async task
    entry["task"].cancel()
    # Set flag so ollama_client checks it on next attempt
    await set_stream_cancelled(trace_id)
```

This allows Ollama HTTP client (running in `asyncio.to_thread()`) to:
1. Check `check_stream_cancelled_sync(trace_id)` before requests
2. Immediately return cancelled error instead of blocking indefinitely
3. Allow the agent_task to finish and be garbage collected

### 3. Guaranteed Cleanup in Generator Finally

The generator's finally block ensures cleanup always happens:
```python
finally:
    # Cancel old agent task
    if agent_task and not agent_task.done():
        agent_task.cancel()
        await asyncio.wait_for(agent_task, timeout=0.5)
    # Unregister from registry
    await _stream_registry.pop(trace_id)
    # Clear cancellation flag
    await clear_stream_cancelled(trace_id)
```

### 4. Disconnect Detection

Every event loop iteration checks:
```python
while True:
    if cancel_event.is_set():
        raise asyncio.CancelledError()
    if await req.is_disconnected():
        # Cancel agent_task, cleanup
        return
```

This ensures quick cleanup if client disconnects.

## Stream Lifecycle Guarantee

```
Session A sends prompt 1
  ↓
Stream 1 starts, registers with session_id
  ↓
Session A sends prompt 2 (WITHOUT pressing stop)
  ↓
Stream 1.register() is called with Stream 2 data
  Stream 1's task is retrieved: prev_task = stream1_task
  ↓ [Lock released, Stream 1 can finish]
  ↓
Stream 1 generator.finally runs:
  - Cancels agent_task (if still running)
  - Pops self from registry (_by_trace, _by_session)
  - Clears all resources
  ↓
Stream 1 task completes (2s timeout expired OR finally finished)
  ↓ [Lock re-acquired]
  ↓
Stream 2 registered cleanly, no conflicts
```

## Logs to Watch

New logs show the flow:
```
stream_start trace=abc123 stream_id=abc123 session=sess-123
...
stream_cancelled trace=abc123 reason=new_stream_registered
prev_stream_finished_cleanly session=sess-123 trace=abc123
stream_end trace=abc123 stream_id=abc123 session=sess-123 duration_ms=145
stream_start trace=def456 stream_id=def456 session=sess-123  [NEW]
```

## Why No More Hang

1. **No resource leaks**: Old stream fully cleaned up before new one starts
2. **No task conflicts**: Only one agent_task per stream, properly cancelled
3. **No deadlocks**: Sequential cleanup (old → new), not concurrent
4. **Cancellation respected**: Ollama client checks flag in thread, exits early
5. **Client disconnect safe**: Immediate cleanup on disconnect detection

## Configuration

- Stream cancellation wait timeout: **2.0 seconds** (tunable in register method)
- Agent task cancel timeout: **0.5 seconds** (tunable in finally block)
- Event queue timeout: **0.1 seconds** (per event loop)
- Inactivity timeout: **120 seconds** (configurable via JARVIS_STREAM_INACTIVITY_SECONDS)

## Testing

To verify the fix:
1. Send prompt 1, don't wait for completion
2. Send prompt 2 immediately (no stop button)
3. Observe: Server doesn't hang, prompt 2 responds normally
4. Check logs for `prev_stream_finished_cleanly` or `prev_stream_timeout_on_cancel`

If hanging persists, check:
- Is Ollama process blocked? (netstat, top)
- Are there logs after stream_cancelled? (should see stream_end)
- Is asyncio event loop stuck? (logs should show progress)
