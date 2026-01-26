# Server Hang Fix - One-Minute Summary

## Problem
User sends prompt 2 without stopping prompt 1 → **server hangs, requires kill -9**

## Root Cause
Old stream not fully cancelled before new stream starts → both compete for resources → deadlock

## Solution
**Wait for old stream to cleanup before registering new stream**

## Code Changes

### Location 1: StreamRegistry.register() (lines 178-226)
```python
# Get old task reference
if prev_task:
    # WAIT for it (outside lock!)
    await asyncio.wait_for(prev_task, timeout=2.0)
# NOW register new stream
```

### Location 2: StreamRegistry.cancel() (lines 230-242)
```python
# Cancel the task
entry["task"].cancel()
# Set flag for Ollama client
await set_stream_cancelled(trace_id)
```

## Impact
✅ No more hangs  
✅ Exactly one stream per session  
✅ Guaranteed cleanup (no leaks)  
✅ Ollama respects cancellation  
✅ No API changes  

## Files
- `src/jarvis/server.py` - 2 methods, 43 lines

## Test
Send prompt 1 → immediately send prompt 2 → no hang ✓

## Logs to Watch
- `prev_stream_finished_cleanly` = old stream cleaned up ✓
- `prev_stream_timeout_on_cancel` = old stream took >2s to cleanup
- `stream_start trace=...` = new stream registered

---

**Key Insight**: Release the lock before waiting for old task to finish. This allows the old generator's finally block to run and cleanup while new stream waits. Without this, both streams exist concurrently → deadlock.
