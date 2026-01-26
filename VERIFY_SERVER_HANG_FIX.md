# Quick Verification - Server Hang Fix

## The Fix in 30 Seconds

**Problem**: Kill -9 needed when sending prompt B before prompt A finishes.

**Solution**: StreamRegistry waits for old stream cleanup before registering new stream.

**Code Change**: [ServerRegistry.register()](src/jarvis/server.py#L200-L225) - Added `await asyncio.wait_for(prev_task, timeout=2.0)` OUTSIDE the lock.

---

## One-Minute Test

```bash
# Open terminal in project root
cd /home/bs/vscode/jarvis-agent

# Start server
python -m uvicorn src.jarvis.server:app --reload --host 0.0.0.0 --port 8000

# In another terminal, watch logs:
tail -f logs/system.log | grep -E "stream_start|stream_cancelled|stream_end"

# In a third terminal, run rapid request test:
python -c "
import time, requests, json

SESSION = 'test-' + str(int(time.time() * 1000))
print(f'SESSION: {SESSION}')

# Send long prompt
print('[1/2] Sending long prompt A...')
r1 = requests.post(
    'http://localhost:8000/v1/chat/completions',
    json={'messages': [{'role': 'user', 'content': 'Write a long essay about quantum computing'}]},
    headers={'X-Session-Id': SESSION},
    stream=True
)
print(f'[1/2] Response status: {r1.status_code}')

# Immediately send new prompt (CRITICAL: no stop button)
time.sleep(0.05)  # 50ms later
print('[2/2] Sending prompt B immediately...')
r2 = requests.post(
    'http://localhost:8000/v1/chat/completions',
    json={'messages': [{'role': 'user', 'content': 'What is 2+2?'}]},
    headers={'X-Session-Id': SESSION},
    stream=True
)
print(f'[2/2] Response status: {r2.status_code}')

# Read responses
print()
print('RESPONSE A (should be cut short):')
for i, line in enumerate(r1.iter_lines()):
    if i < 5: print('  ', line.decode() if isinstance(line, bytes) else line)
    if i == 4: print('  ...'); break

print()
print('RESPONSE B (should be complete):')
for i, line in enumerate(r2.iter_lines()):
    if i < 5: print('  ', line.decode() if isinstance(line, bytes) else line)
    if i == 4: print('  ...'); break

print()
print('✓ If no hang occurred and both got responses, the fix works!')
"
```

## Expected Logs (Success)

```
stream_start trace=abc123 session=test-1705...
stream_cancelled trace=abc123 reason=registry_new_stream
prev_stream_finished_cleanly session=test-1705 trace=abc123
stream_end trace=abc123 duration_ms=250

stream_start trace=def456 session=test-1705
stream_end trace=def456 duration_ms=500
```

## Expected Logs (Timeout OK - Still Works)

```
stream_start trace=abc123 session=test-1705...
stream_cancelled trace=abc123 reason=registry_new_stream
prev_stream_timeout_on_cancel session=test-1705 trace=abc123 timeout_ms=2000
stream_start trace=def456 session=test-1705  ← New stream started despite timeout!
stream_end trace=def456 duration_ms=500     ← Still responsive
... (later)
stream_end trace=abc123 duration_ms=3000    ← Old one finalized much later
```

**Timeout is OK** - means old stream took >2s to cleanup but new stream still became responsive immediately.

## Bad Logs (Hang - NOT Fixed)

```
stream_start trace=abc123 session=test-1705...
stream_cancelled trace=abc123 reason=registry_new_stream
prev_stream_timeout_on_cancel session=test-1705 trace=abc123
stream_start trace=def456 session=test-1705
... NOTHING AFTER THIS ...
(Connection hangs, need to kill -9)
```

---

## Files That Changed

1. **[src/jarvis/server.py](src/jarvis/server.py)**
   - StreamRegistry class added (lines 178-226)
   - register() method: waits for old cleanup outside lock
   - cancel() method: sends 3 cancellation signals
   - pop() method: unregisters stream
   - Generator checks cancel_event every iteration
   - Finally block always calls registry.pop()

2. **[ui/src/lib/stream.ts](ui/src/lib/stream.ts)**
   - AbortError caught silently (expected when user stops)
   - stream_id validation on callbacks
   - Proper reader cleanup in finally block

3. **[ui/src/contexts/ChatContext.tsx](ui/src/contexts/ChatContext.tsx)**
   - activeStreamIdRef to validate callbacks
   - Cancel previous stream before new one starts
   - Guard checks on all callbacks

---

## Why It Works

**Before**: New stream registered while old one still running → 2 generators per session → resource contention → deadlock → kill -9 needed

**After**: New stream waits (max 2s) for old stream to finish cleanup before registering → Only 1 generator per session → Clean resource release → No deadlock

```
OLD:  Request A registered → Request B arrives → Request B registered immediately
      Result: A and B running concurrently ← DEADLOCK

NEW:  Request A registered → Request B arrives → Registry.register() waits for A cleanup
      → A finalized (finally block) → B registered
      Result: A finalized, then B started ← CLEAN
```

---

## Configuration

**Cleanup timeout**: 2 seconds (tunable in StreamRegistry.register line 209)

```python
await asyncio.wait_for(prev_task, timeout=2.0)  # ← Change here if needed
```

- **2.0s**: Default, balances cleanup with user perception
- **1.0s**: Faster but might allow concurrent streams if cleanup slow
- **3.0s**: More permissive but user waits longer for new prompt responsiveness
- **5.0s+**: Safe but might feel sluggish

---

## Debug: If Test Hangs

1. **Check logs for timeout**:
   ```
   grep "prev_stream_timeout_on_cancel" logs/system.log
   ```
   If yes: Old stream took >2s to cleanup. Check why (Ollama API slow? Network latency?)

2. **Check if concurrent streams in logs**:
   ```
   grep "stream_start" logs/system.log | grep -c "session=test-1705"
   ```
   Should be 2 (one cancelled, one active). If more: concurrent streams bug.

3. **Kill and restart server**:
   ```bash
   pkill -f "python -m uvicorn"
   sleep 1
   python -m uvicorn src.jarvis.server:app --reload
   ```

4. **Check Ollama is responsive**:
   ```bash
   curl http://localhost:11434/api/tags
   # Should respond immediately
   ```

---

## Success Criteria

✅ Test completes without hang
✅ Response B arrives before A finishes (not blocking on A)
✅ Logs show: stream_cancelled → prev_stream_finished_cleanly or prev_stream_timeout_on_cancel
✅ No need for kill -9
✅ Stress test (5+ rapid requests) completes without hang

---

**Status**: Ready for testing  
**Priority**: CRITICAL - If this test hangs, the fix didn't work  
**Time**: 1 minute to verify
