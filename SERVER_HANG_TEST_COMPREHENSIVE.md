# Streaming Stability - Comprehensive Test & Fix Plan

## Current Issue: Why kill -9 is Needed

### The Hang Scenario
1. User sends **Prompt A** → Backend creates Stream A, agent_task A, event_queue A
2. User immediately sends **Prompt B** (while A still running) → Backend calls register(Stream B)
3. StreamRegistry cancels Stream A's task and WAITS for cleanup
4. **BUT**: If agent_task A is blocked in Ollama call (sync HTTP request in asyncio.to_thread), it takes >2s to respond to cancellation
5. Register times out and forces Stream B to register anyway
6. **Both streams now exist**: 
   - Stream A's finally block tries to run, conflicts with Stream B
   - Event queues get corrupted
   - Resource contention → DEADLOCK
7. Server becomes unresponsive → **kill -9 needed**

### Why This Happens
- `run_agent()` includes blocking Ollama HTTP calls
- Wrapped in `asyncio.to_thread()`, but cancellation doesn't interrupt network wait
- 2-second wait_for timeout expires before cleanup finishes
- New stream proceeds with old stream still running in background

## The Solution: Multi-Layer Cancellation

### Layer 1: Immediate Cancellation Signal (Already Implemented)
```python
prev["cancel_event"].set()  # Signal to generator
prev["task"].cancel()        # Cancel asyncio task
await set_stream_cancelled(trace_id)  # Flag for Ollama client
```

### Layer 2: Extended Cleanup Wait (Need to Verify)
```python
# Wait up to 2s for old stream to cleanup
# If timeout, new stream STILL registers (not ideal but prevents system hang)
try:
    await asyncio.wait_for(prev_task, timeout=2.0)
except asyncio.TimeoutError:
    _req_logger.warning(f"Stream cleanup timeout, proceeding with new stream")
    # New stream registers despite old stream still running
```

**Problem**: This allows both streams to run concurrently if cleanup takes >2s

### Layer 3: Generator Cancellation Checks (Need to Improve)
```python
while True:
    # Check for disconnect/cancel BEFORE processing events
    if cancel_event.is_set():
        raise asyncio.CancelledError()
    if await req.is_disconnected():
        # Cancel agent_task, cleanup
        return
```

**Problem**: Generator still yields events even after new stream registered

### Layer 4: Finally Block Cleanup (Need to Verify)
```python
finally:
    # MUST run regardless of how we exit
    if agent_task and not agent_task.done():
        agent_task.cancel()
        try:
            await asyncio.wait_for(agent_task, timeout=0.5)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass
    
    # MUST unregister - this is critical!
    await _stream_registry.pop(trace_id)
```

**Critical**: If this doesn't run, trace_id stays in registry → next request for same session won't know old stream was there

## Comprehensive Test Plan

### Test 1: Normal Streaming (Baseline)
```bash
# Expected: Immediate response, clean logs
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer devkey" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Hello","stream":true}' \
  | head -20

# Check logs for:
# stream_start trace=abc
# stream_end trace=abc (not cancelled)
```

### Test 2: User Stops Stream (Baseline)
```bash
# Start stream in one terminal
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer devkey" \
  -d '{"prompt":"Write a very long poem","stream":true}' &
PID=$!

# Stop it in another terminal after 2 seconds
sleep 2 && kill $PID

# Check logs for:
# stream_start trace=abc
# stream_cancelled trace=abc reason=client_disconnect
# stream_end trace=abc
```

### Test 3: Rapid New Requests (THE CRITICAL TEST)
```bash
# This is the test that reveals the hang
SESSION_ID="test-session-$(date +%s)"

# Send Prompt A
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer devkey" \
  -H "X-Session-Id: $SESSION_ID" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Write a 10 paragraph essay","stream":true}' > /tmp/a.txt &
A_PID=$!

# Wait only 100ms (before first token arrives)
sleep 0.1

# Send Prompt B - this triggers the critical path
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer devkey" \
  -H "X-Session-Id: $SESSION_ID" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"What is 2+2?","stream":true}' > /tmp/b.txt

# Wait for A to finish in background
wait $A_PID 2>/dev/null

# Check files
echo "=== Response A (should be cancelled) ==="
tail -5 /tmp/a.txt
echo ""
echo "=== Response B (should have answer) ==="
cat /tmp/b.txt | head -10

# Check logs MUST show:
# stream_start trace=A_TRACE session=test-session-XXX
# stream_cancelled trace=A_TRACE reason=registry_new_stream
# prev_stream_finished_cleanly session=test-session-XXX
# stream_start trace=B_TRACE session=test-session-XXX
# stream_end trace=B_TRACE
```

**EXPECTED RESULT**: B responds quickly, no hang, logs show A was cancelled

**BAD RESULT**: Hangs or shows "prev_stream_timeout_on_cancel" means old stream didn't cleanup in time

### Test 4: Rapid Requests (Stress Test)
```bash
# Send 5 requests in rapid succession
for i in {1..5}; do
  curl -X POST http://localhost:8000/v1/chat/completions \
    -H "Authorization: Bearer devkey" \
    -H "Content-Type: application/json" \
    -d "{\"prompt\":\"Prompt $i\",\"stream\":true}" \
    --max-time 3 \
    > /tmp/resp_$i.txt &
  sleep 0.05  # 50ms between requests
done

wait

# All requests should complete without hang
echo "=== All responses completed without hang ==="
for i in {1..5}; do
  echo "Response $i: $(wc -c < /tmp/resp_$i.txt) bytes"
done
```

### Test 5: Multiple Sessions (No Cross-Contamination)
```bash
# Two sessions sending rapid requests
SESSION1="session-1"
SESSION2="session-2"

# Start Session 1, Prompt A
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "X-Session-Id: $SESSION1" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Session 1 Prompt A","stream":true}' &
S1_PID=$!

# Start Session 2, Prompt A
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "X-Session-Id: $SESSION2" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Session 2 Prompt A","stream":true}' &
S2_PID=$!

sleep 0.1

# Send Session 1, Prompt B (should cancel S1_A but not affect S2)
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "X-Session-Id: $SESSION1" \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Session 1 Prompt B","stream":true}'

# Wait for all
wait

echo "=== Sessions did not interfere ==="
```

## Verification Checklist

### Logs to Monitor
```bash
# In one terminal, tail logs
tail -f logs/system.log | grep -E "stream_start|stream_cancelled|stream_end|prev_stream"
```

Expected log sequence for Test 3:
```
stream_start trace=abc123 stream_id=abc123 session=test-session-XXX
stream_start trace=def456 stream_id=def456 session=test-session-XXX  <-- New request
stream_cancelled trace=abc123 reason=registry_new_stream           <-- Old cancelled
prev_stream_finished_cleanly session=test-session-XXX trace=abc123 <-- Old cleaned up
stream_end trace=abc123 ...                                         <-- Old finalized
stream_end trace=def456 ...                                         <-- New finalized
```

### Code Points to Verify

1. **StreamRegistry.register()** should:
   - Get prev_task reference
   - Release lock before waiting
   - Wait up to 2s with timeout
   - Handle TimeoutError gracefully (log warning, continue)
   - Re-acquire lock and register new stream

2. **Generator finally block** should:
   - Cancel agent_task with timeout
   - Pop from registry (CRITICAL - must not skip this)
   - Clear cancellation flag
   - Log stream_end

3. **register() cancel path** should:
   - Set cancel_event
   - Cancel task
   - Set cancellation flag for Ollama client

### Runtime Checks

```bash
# While test running, in another terminal:

# Check no duplicate session_ids in registry
# (If registry.py exposes this, add monitoring)

# Check asyncio task count (should stay stable)
ps aux | grep uvicorn | head -3
# Task count should not grow over multiple requests

# Check memory (should stay stable)
while true; do
  ps aux | grep -E 'uvicorn|python' | grep -v grep | awk '{print $6}' | head -1
  sleep 2
done
```

## If Tests Fail

### Symptom: "Stream cleanup timeout, proceeding..." appears
**Cause**: Old stream's finally block didn't run before 2s timeout
**Fix**: 
- Check if agent_task is stuck in Ollama call
- Increase timeout to 3s or 5s (temporary)
- Or implement non-blocking Ollama client

### Symptom: Server hangs during Test 3
**Cause**: Both streams running concurrently, deadlock
**Debug**:
- Check logs for "stream_start" appearing twice for same session
- Check if "stream_end" appears for first stream before second starts
- Add more detailed logging to generator's event processing loop

### Symptom: Test 5 fails (sessions interfere)
**Cause**: Session IDs not being used to separate streams
**Fix**: Verify registry is keying by session_id correctly

## Why Current Code Should Work

1. **Cancellation signals sent** → cancel_event.set() + task.cancel() + set_stream_cancelled()
2. **Generator checks signals** → if cancel_event.is_set() raise CancelledError
3. **Finally block guarantees cleanup** → pop from registry, cancel agent_task
4. **Registry waits for cleanup** → wait_for(prev_task, timeout=2.0)
5. **New stream only registers** → after cleanup or timeout
6. **No concurrent streams** → only one task per session at a time

## Implementation Verification

Before running tests, verify these in server.py:

✅ Line ~190: `prev["cancel_event"].set()` exists
✅ Line ~191: `prev["task"].cancel()` exists  
✅ Line ~195: `await set_stream_cancelled(trace_id)` exists
✅ Line ~209: `await asyncio.wait_for(prev_task, timeout=2.0)` exists
✅ Line ~3100: `if cancel_event.is_set(): raise asyncio.CancelledError()` exists
✅ Line ~3350: `if await req.is_disconnected(): ... return` exists
✅ Line ~3400: `finally: ... await _stream_registry.pop(trace_id)` exists

If any are missing, that's the bug.

---

**Test Date**: 2026-01-26  
**Critical Test**: Rapid New Requests (Test 3) - must not hang  
**Pass Criteria**: No hang, clean logs showing A cancelled then B completes
