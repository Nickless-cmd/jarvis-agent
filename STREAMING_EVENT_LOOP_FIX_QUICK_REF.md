# Quick Reference - Streaming Event Loop Fix

## 🎯 What Was Fixed

**Problem**: Event loop blocked by `time.sleep()` and `threading.Lock()` in events.py
**Result**: Server hangs, requires kill -9

**Solution**: Made events publishing fully async and non-blocking

## 📝 Changes Made

### 1. src/jarvis/events.py
- ✅ Removed `threading.Lock` (no locks needed)
- ✅ Removed `time.sleep()` (blocking)
- ✅ Added async flush: `await asyncio.sleep()` (non-blocking)
- ✅ Debounced token batching (75ms)
- ✅ Cancellable flush tasks
- ✅ New function: `cleanup_request_buffers(request_id)`

### 2. src/jarvis/server.py
- ✅ Call `cleanup_request_buffers()` in generator finally block
- ✅ Added log: `cleanup_done=True`

### 3. test_streaming_stability.py (NEW)
- ✅ Automated test script
- ✅ Tests rapid requests (5 iterations)

## 🧪 Testing

### Run Test
```bash
python test_streaming_stability.py
```

### Expected Output
```
✓✓✓ ALL TESTS PASSED ✓✓✓
  Server handles rapid requests without hanging!
  Fix is working correctly.
```

### Manual Test
```bash
# Terminal 1: Watch logs
tail -f logs/system.log | grep -E "flush_|stream_|cleanup_"

# Terminal 2: Send rapid requests
SESSION="test-$(date +%s)"
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "X-Session-Id: $SESSION" \
  -d '{"messages":[{"role":"user","content":"Long essay"}],"stream":true}' &
sleep 0.05
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "X-Session-Id: $SESSION" \
  -d '{"messages":[{"role":"user","content":"2+2?"}],"stream":true}'
```

### Success Indicators
- ✓ Both requests complete
- ✓ No timeout errors
- ✓ Logs show: `flush_scheduled` → `flush_done`
- ✓ Logs show: `cleanup_flush_task` when stream cancelled
- ✓ Logs show: `cleanup_done=True` in stream_end

## 📊 Log Reference

### New Logs
| Log Entry | Meaning |
|-----------|---------|
| `flush_scheduled request_id=...` | Flush task created (75ms debounce) |
| `flush_start request_id=... size=...` | Flush beginning |
| `flush_done request_id=... tokens_sent=...` | Flush complete |
| `flush_cancelled request_id=...` | Flush task cancelled |
| `flush_immediate request_id=... size=...` | Buffer >1KB, immediate flush |
| `flush_on_end request_id=... size=...` | Flush on chat.end/error |
| `flush_on_cleanup request_id=... size=...` | Flush on stream cleanup |
| `cleanup_flush_task request_id=...` | Flush task cancelled in cleanup |
| `cleanup_buffer request_id=...` | Buffer cleared in cleanup |
| `event_buffers_cleaned trace=...` | Buffers cleaned in generator |
| `cleanup_done=True` | Added to stream_end log |

### Expected Sequence (Rapid Requests)
```
stream_start trace=A stream_id=req-1
flush_scheduled request_id=req-1
flush_start request_id=req-1
flush_done request_id=req-1

stream_start trace=B stream_id=req-2  ← NEW REQUEST
stream_cancelled trace=A  ← OLD CANCELLED
cleanup_flush_task request_id=req-1  ← OLD TASK CANCELLED
flush_on_cleanup request_id=req-1  ← OLD BUFFER FLUSHED
cleanup_buffer request_id=req-1  ← OLD BUFFER CLEARED
event_buffers_cleaned trace=A  ← OLD CLEANUP DONE
stream_end trace=A cleanup_done=True  ← OLD FINALIZED

prev_stream_finished_cleanly  ← WAIT OK
flush_scheduled request_id=req-2  ← NEW STARTS
flush_start request_id=req-2
flush_done request_id=req-2
event_buffers_cleaned trace=B
stream_end trace=B cleanup_done=True
```

## 🔧 How It Works

### Before (BLOCKING)
```python
def _flush_buffer(request_id):
    with lock:  # ← BLOCKS EVENT LOOP
        time.sleep(0.075)  # ← BLOCKS EVENT LOOP
        publish(...)
```

### After (NON-BLOCKING)
```python
async def _flush_buffer_async(request_id):
    await asyncio.sleep(0.075)  # ← YIELDS TO EVENT LOOP
    _publish_direct(...)  # No lock

def handle_token(payload):
    task = asyncio.create_task(_flush_buffer_async(request_id))
    _flush_tasks[request_id] = task  # Store for cleanup
```

### Cleanup
```python
def cleanup_request_buffers(request_id):
    # Cancel flush task
    if request_id in _flush_tasks:
        _flush_tasks[request_id].cancel()
    
    # Flush remaining tokens
    if request_id in _chat_token_buffers:
        buffer = _chat_token_buffers[request_id]
        if buffer["accumulated_text"]:
            _publish_direct("chat.token", {...})
```

## 🚨 Troubleshooting

### Server still hanging?
1. Check logs for `flush_start` without `flush_done`
2. Check if asyncio event loop is running
3. Verify cleanup_request_buffers is called (search logs for `event_buffers_cleaned`)

### Tokens not batching?
1. Check logs for `flush_scheduled`
2. Verify buffer accumulation (should see multiple tokens before flush)
3. Check if immediate flush triggered (buffer >1KB)

### Cleanup not working?
1. Check logs for `cleanup_flush_task`
2. Verify stream_end has `cleanup_done=True`
3. Check if flush tasks are being cancelled

## 📚 Documentation

- **Full Details**: [STREAMING_EVENT_LOOP_FIX.md](STREAMING_EVENT_LOOP_FIX.md)
- **Test Script**: [test_streaming_stability.py](test_streaming_stability.py)

## ✅ Status

- [x] Event loop non-blocking
- [x] Async debounced flush
- [x] Cancellable flush tasks
- [x] Guaranteed cleanup
- [x] Structured logging
- [x] Test script
- [x] Documentation

**Ready for testing** ✓

---

**Date**: 2026-01-26  
**Issue**: Blocking event loop  
**Fix**: Async debounced flush  
**Status**: Complete
