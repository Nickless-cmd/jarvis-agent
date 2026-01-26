# Streaming Stability - Debugging Decision Tree

## Decision Flow: "Why is it still hanging?" or "Why isn't the fix working?"

```
START: Server hangs or behaves unexpectedly
  │
  ├─→ Does server respond after 2 seconds?
  │    │
  │    ├─ YES: Not a deadlock → See "Response Delays" section
  │    │
  │    └─ NO: Still hung → See "System Deadlock" section
  │
  └─→ Check logs for "stream_start" entries for same session
```

---

## 1️⃣ System Deadlock (Server Completely Hung)

### Symptom
- Send Prompt A
- Wait 100ms, send Prompt B
- Server stops responding to ANY requests
- Need `kill -9 server` to recover

### Root Cause Analysis

**Check 1: Is StreamRegistry.register() waiting?**

```bash
grep -c "prev_stream_finished_cleanly\|prev_stream_timeout_on_cancel" logs/system.log
```

- **Count = 0**: ❌ register() is not waiting. Code changes not deployed.
  - Fix: Redeploy server.py with StreamRegistry.register() containing `await asyncio.wait_for(prev_task, timeout=2.0)`

- **Count > 0**: ✓ register() is waiting properly. Issue elsewhere.
  - Move to Check 2.

**Check 2: Are concurrent streams existing?**

```bash
grep "stream_start" logs/system.log | \
  awk -F'session=' '{print $2}' | awk '{print $1}' | \
  sort | uniq -c
```

Look for the session that hung:
```
      1 sess-abc123  ← Only 1 stream_start for this session = GOOD
      2 sess-def456  ← 2 stream_start entries = PROBLEM (concurrent!)
```

If concurrent streams:
- ❌ Old stream was not cancelled before new one registered
- Registry.register() either didn't run or didn't wait properly
- Check: Is StreamRegistry being used? See `/server.py` line ~2800 where `/chat/completions` calls `await _stream_registry.register()`

**Check 3: Did old stream's finally block run?**

```bash
SESSION="sess-abc123"  # Use session that hung
grep "stream_start.*session=$SESSION" logs/system.log | head -1
# Output: stream_start trace=abc123 session=sess-abc123

grep "stream_end.*trace=abc123" logs/system.log
```

- **Found**: ✓ Finally block ran (cleanup happened)
- **Not found**: ❌ Finally block didn't run (task orphaned)
  - Check if generator exception: `grep "trace=abc123" logs/system.log | grep -i error`
  - If no cleanup logged, generator crashed without triggering finally

**Check 4: Is registry.pop() being called?**

```bash
# Check source code directly
grep -n "await _stream_registry.pop" src/jarvis/server.py
```

Must find in finally block (around line 3450):
```python
finally:
    try:
        await _stream_registry.pop(trace_id)
    except:
        pass
```

- **Not found**: ❌ CRITICAL - registry.pop() missing. Add it to finally block.
- **Found**: ✓ Check if it's being called. Add debug log:
  ```python
  finally:
      _req_logger.info(f"stream_cleanup_START trace={trace_id}")
      
      try:
          await _stream_registry.pop(trace_id)
          _req_logger.info(f"stream_registry_pop_success trace={trace_id}")
      except Exception as e:
          _req_logger.error(f"stream_registry_pop_failed trace={trace_id}: {e}")
  ```

**Check 5: Is the old task actually completing?**

```bash
SESSION="sess-abc123"
grep "stream_start.*session=$SESSION" logs/system.log | head -1
# abc123

# Does task show as done/cancelled?
grep "task.*abc123\|cancelled.*abc123" logs/system.log
```

If no task cancellation logged:
- ❌ task.cancel() not called or not effective
- Check: Is cancel() method being called in register()?
  ```python
  async def register(self, entry):
      ...
      prev_entry["task"].cancel()  # ← Must be here
  ```

### Solutions

| Root Cause | Solution |
|-----------|----------|
| register() not waiting | Redeploy src/jarvis/server.py with wait_for |
| Concurrent streams | Check registry usage, ensure register() called for every stream |
| registry.pop() missing | Add `await _stream_registry.pop(trace_id)` to finally block |
| Task not cancelling | Check task.cancel() called in register() |
| Finally block not running | Check generator for unhandled exceptions before finally |

---

## 2️⃣ Response Delays (Server responds but slowly)

### Symptom
- Send Prompt B while A is running
- B eventually responds, but takes extra time
- No hang, but laggy

### Diagnosis: "When do I get response from B?"

**Expected**:
```
0ms   - Send A
100ms - Send B
100ms-200ms - Registry wait for A cleanup
200ms - B response starts
500ms - B response completes
Total: 500ms (normal)
```

**Actual** (if lag):
```
0ms   - Send A
100ms - Send B
100ms-2100ms - Registry wait for A (TIMEOUT after 2s)
2100ms - B response starts
2600ms - B response completes
Total: 2600ms (laggy!)
```

**Check: How long is cleanup taking?**

```bash
grep "stream_start.*session=TEST" logs/system.log | head -1
# stream_start trace=abc123 ...

grep "prev_stream_timeout_on_cancel.*trace=abc123" logs/system.log
```

- **Found timeout**: ✓ Normal. Old stream cleanup just slow (2s timeout hit).
  - Is this acceptable for your use case?
  - Options:
    - Leave it (2s is safe, better to wait than risk concurrent streams)
    - Increase timeout to 3-5s if you want even safer cleanup
    - Implement non-blocking Ollama cancel (advanced)

- **Not found timeout**: Check if cleanup_finished logged:
  ```bash
  grep "prev_stream_finished_cleanly.*trace=abc123" logs/system.log
  ```
  - **Found**: Cleanup finished in <2s normally. Why is B slow?
    - Check if B's actual generation is slow (not a hang, just slow Ollama)
    - Monitor Ollama API response times

---

## 3️⃣ UI Not Updating

### Symptom
- New response A streams in
- Click Stop, send Prompt B
- UI shows A's tokens on B's response (mixed up)
- Or UI freezes showing old response

### Root Cause Analysis

**Check 1: Are stream_id values in response?**

```bash
tail -20 logs/system.log | grep "stream_" | head -5
```

Look for `stream_id=` in logs:
```
stream_start trace=abc123 stream_id=abc123 ...
stream_token text="hello" stream_id=abc123 ...
```

- **Missing**: ❌ Backend not emitting stream_id. Check NDJSON helpers:
  ```python
  def _ndjson_token(trace_id, token, stream_id=None):
      return json.dumps({
          "type": "token",
          "text": token,
          "stream_id": stream_id or trace_id,  # ← Must pass stream_id
          ...
      })
  ```

**Check 2: Is frontend extracting stream_id?**

Frontend logs (browser console):
```bash
# Open browser console (F12)
# Look for [stream] debug messages
```

Should show:
```
[stream] Extracted stream_id from response: abc123
[stream] Processing token with stream_id: abc123
```

If not, check [ui/src/lib/stream.ts](ui/src/lib/stream.ts#L120-L122):
```typescript
// Must extract from first event
if (isFirstEvent && event.stream_id) {
  streamId = event.stream_id
  isFirstEvent = false
}
```

- **Missing**: ❌ Add extraction logic

**Check 3: Are callbacks validating stream_id?**

Browser console should show (if mismatch):
```
[chat] Ignoring token from inactive stream {active: 'def456', received: 'abc123'}
```

If NOT showing this (meaning no validation):
- ❌ ChatContext guards not active
- Check [ui/src/contexts/ChatContext.tsx](ui/src/contexts/ChatContext.tsx#L125-L135):
  ```typescript
  const handleDelta = useCallback((text, streamId) => {
    if (streamId && activeStreamIdRef.current && streamId !== activeStreamIdRef.current) {
      console.warn('[chat] Ignoring delta from inactive stream')
      return  // ← CRITICAL: Must return here
    }
    // ... process delta ...
  }, [])
  ```

**Check 4: Is activeStreamIdRef being updated?**

Add debug to ChatContext:
```typescript
const handleStatus = useCallback((status, streamId) => {
  if (status === 'thinking') {
    activeStreamIdRef.current = streamId
    console.log('[chat] Stream started:', streamId)
  }
}, [])
```

Browser console should show:
```
[chat] Stream started: abc123
[chat] Ignoring token from inactive stream (after new stream starts)
[chat] Stream started: def456
```

### Solutions

| UI Issue | Root Cause | Fix |
|----------|-----------|-----|
| Mixed tokens | stream_id not emitted | Add stream_id to NDJSON responses |
| UI frozen | stream_id not validated | Add guard checks to callbacks |
| Wrong response shown | activeStreamIdRef not updated | Update ref when new stream starts |

---

## 4️⃣ No Logs At All (Silent Failure)

### Symptom
- Send requests
- No logs appear
- Server seems to run but no output

### Checks

**Check 1: Is logging configured?**

```bash
python -c "import logging; print(logging.basicConfig.__doc__)"
# Should show configured handlers
```

**Check 2: Is logger initialized?**

```bash
grep "_req_logger = " src/jarvis/server.py
# Should find: _req_logger = logging.getLogger(__name__)
```

**Check 3: Can you see ANY logs?**

```bash
# Try a basic endpoint
curl http://localhost:8000/health
tail -5 logs/system.log
```

- **See logs**: ✓ Logging works. Issue is specific to streaming endpoint.
- **No logs**: ❌ Logging not configured. Check logging setup in server.py

**Check 4: Is streaming endpoint being called?**

```bash
curl -v http://localhost:8000/v1/chat/completions \
  -H "X-Session-Id: test-123" \
  -d '{"messages":[{"role":"user","content":"hello"}]}'
  
# Should see 200 response headers and stream start
```

- **No response**: Server not responding. Check if running: `ps aux | grep uvicorn`
- **Empty response**: Streaming endpoint crashes. Check error logs.

---

## Quick Fix Priority List

1. **IF: Server completely hung**
   - Check: Is `prev_stream_finished_cleanly` logged?
   - If NO → Add wait_for() to register()
   - If YES → Check for concurrent streams

2. **IF: Responses laggy (2s+ delay)**
   - Normal if `prev_stream_timeout_on_cancel` logged
   - Can increase timeout if needed (but 2s is safer)

3. **IF: UI mixed up (wrong tokens showing)**
   - Check: stream_id in NDJSON responses?
   - Check: stream_id validation in ChatContext?

4. **IF: No logs**
   - Check: Logging configured in server?
   - Check: Endpoint called at all?

---

## Emergency: If Still Hanging

**Step 1: Kill server**
```bash
pkill -9 -f "python -m uvicorn"
```

**Step 2: Check logs for last stream_start**
```bash
tail -50 logs/system.log | grep stream_
```

**Step 3: Identify the issue using sections above**

**Step 4: Apply fix**

**Step 5: Restart and test**
```bash
python -m uvicorn src.jarvis.server:app --reload
# Run Test Case 3 (rapid requests)
```

**Step 6: If still fails**
- Verify code changes deployed: `grep -n "await asyncio.wait_for" src/jarvis/server.py`
- Verify StreamRegistry instance created: `grep "_stream_registry = StreamRegistry" src/jarvis/server.py`
- Verify register() called: `grep "await _stream_registry.register" src/jarvis/server.py`

---

## One-Minute Diagnostic Script

```bash
#!/bin/bash
echo "=== STREAMING HANG DIAGNOSTIC ==="
echo

echo "1. Is StreamRegistry.register() waiting?"
grep -c "prev_stream_finished_cleanly\|prev_stream_timeout_on_cancel" logs/system.log || echo "  ❌ NEVER LOGGED - register() not waiting!"

echo

echo "2. Any concurrent streams?"
grep "stream_start" logs/system.log | tail -2 | awk -F'session=' '{print $2}' | awk '{print $1}' | sort | uniq -c | grep -v '^\s*1 ' && echo "  ❌ CONCURRENT STREAMS DETECTED!" || echo "  ✓ No concurrent streams"

echo

echo "3. Finally blocks running?"
STARTS=$(grep -c "stream_start" logs/system.log)
ENDS=$(grep -c "stream_end" logs/system.log)
echo "  stream_start: $STARTS"
echo "  stream_end: $ENDS"
[ "$STARTS" -eq "$ENDS" ] && echo "  ✓ Match!" || echo "  ❌ MISMATCH - orphaned streams!"

echo

echo "4. registry.pop() being called?"
grep -q "stream_registry_pop" src/jarvis/server.py && echo "  ✓ Code present" || echo "  ❌ NOT IN CODE"

echo

echo "=== END DIAGNOSTIC ==="
```

Save as `diagnose.sh` and run: `bash diagnose.sh`

---

## Test Case Matrix

| Test | Command | Expected | If Hangs |
|------|---------|----------|----------|
| Baseline | `Send A` | Tokens stream | Check logging |
| Stop | `Send A, click Stop` | A cancelled | Check abort handling |
| Rapid | `Send A, 50ms later Send B` | A cancelled, B streams | **CRITICAL - See System Deadlock section** |
| Stress | `Send A-E rapidly` | Newest responds, old cancelled | Check concurrent streams |
| Multi | `Session-1: Send A, Session-2: Send B` | Both stream independently | Check if isolated |

---

**Last Updated**: 2026-01-26  
**Use When**: "Why is it still hanging?" or "The fix doesn't work"
