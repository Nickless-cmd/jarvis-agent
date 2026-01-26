# Streaming Chat Fix - Final Implementation

## Problem Statement

Streaming chat was exhibiting several issues:
1. Frontend received streaming response but HTTP client hit 60s read timeout
2. Retries would occur, potentially re-entering stream logic
3. Backend logs showed `stream_end` and `stream_cleanup` but UI wouldn't update without browser refresh
4. Input stayed disabled after streaming completed
5. Status indicator ("Thinking…") remained visible

## Root Causes

1. **Backend**: Non-streaming inference had `read_timeout=60.0, retries=2` hardcoded, causing retry loops
2. **Frontend**: `pump()` async function was called without `await`, causing premature return from streamChat

## Solutions Implemented

### Backend Fixes (src/jarvis/agent.py)

**Changed**: Non-streaming inference timeout/retry configuration
```python
# Before:
resp = ollama_request(
    os.getenv("OLLAMA_URL"),
    payload,
    connect_timeout=2.0,
    read_timeout=60.0,    # ❌ Hardcoded
    retries=2,             # ❌ Causes retry loop on timeout
)

# After:
timeout = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "120"))
resp = ollama_request(
    os.getenv("OLLAMA_URL"),
    payload,
    connect_timeout=2.0,
    read_timeout=timeout,  # ✅ Uses env-configured timeout
    retries=0,             # ✅ Single attempt, no retry loop
)
```

**Impact**: 
- Eliminates retry-induced timeout doubling
- Respects `OLLAMA_TIMEOUT_SECONDS` env var (default 120s)
- Single-shot guarantee: no retries means at most one attempt per request

### Backend Fixes (src/jarvis/server.py)

**Already in place**: Streaming generator emits explicit done event in finally block
```python
finally:
    _req_logger.info(f"stream_cleanup trace={trace_id} session={session_id}")
    # Emit final stream_end event if not already sent
    if not done_sent:
        try:
            yield f'data: {{"type":"done","trace_id":"{trace_id}"}}\n\n'
        except Exception:
            pass
    # ... cleanup code
```

**Impact**: 
- Frontend ALWAYS receives a terminal signal (stream_end event)
- Guarantees stream finalization even on error/cancellation
- Placement in finally ensures it runs exactly once

### Frontend Fix (ui/src/lib/stream.ts) - CRITICAL

**Changed**: Added `await` to `pump()` call
```typescript
// Before:
    pump()
  } catch (err: any) {

// After:
    await pump()
  } catch (err: any) {
```

**Why this was critical**:
- `pump()` is an async function that reads all SSE events
- Without `await`, streamChat() returned immediately
- pump() continued running in the background
- When onDone() was eventually called, state updates were asynchronous
- React didn't re-render properly because timing was undefined

**Now with `await pump()`**:
1. All events are processed (including done event)
2. onDone() callbacks are called BEFORE streamChat returns
3. State updates happen synchronously in the React component
4. UI re-renders with updated state
5. Frontend receives deterministic "end of stream" signal

## Event Flow (Fixed)

### Before (Broken)
```
User sends message
  ↓
streamChat() called
  ↓
pump() started (NOT awaited) ← streamChat returns here
  ↓
Component renders with isStreaming=true
  ↓
... pump() continues in background ...
  ↓
Backend sends done event
  ↓
pump() processes done event
  ↓
onDone() called (sets isStreaming=false)
  ↓
But timing is undefined, state may not update properly
```

### After (Fixed)
```
User sends message
  ↓
streamChat() called
  ↓
pump() started
  ↓
All events processed...
  ↓
Backend sends {"type":"done"} event
  ↓
handlePayload detects type="done"
  ↓
onDone() called (sets isStreaming=false)
  ↓
await pump() completes
  ↓
streamChat() returns
  ↓
Component renders with isStreaming=false
  ↓
Composer shows Send button (not Stop)
  ↓
Input is enabled
  ↓
Status indicator removed
```

## Frontend State Management

### ChatContext (ui/src/contexts/ChatContext.tsx)

Already correctly wired to handle done event:

```typescript
const handle = await streamChat(
  { sessionId, prompt, signal: controller.signal },
  (delta: string) => {
    // Append text delta
    setMessages(prev => {
      const copy = prev.slice()
      const idx = copy.findIndex(m => m.id === assistantId)
      if (idx === -1) return copy
      const msg = copy[idx]
      copy[idx] = { ...msg, content: (msg.content || '') + delta, status: msg.status === 'thinking' ? 'streaming' : msg.status }
      return copy
    })
  },
  () => {  // ← onDone callback
    setIsStreaming(false)  // ✅ Disables input, shows Send button
    setMessages(prev => prev.map(m => m.id === assistantId ? { ...m, status: 'done' } : m))  // ✅ Removes status indicator
  },
  // ... error and status callbacks
)
```

### Composer Component (ui/src/components/Composer.tsx)

Correctly handles isStreaming state:

```typescript
const disabled = busy || isStreaming || !value.trim() || !activeSessionId

{!isStreaming && (
  <button onClick={onSend} disabled={disabled}>Send</button>
)}
{isStreaming && (
  <button onClick={stopStreaming}>Stop</button>
)}
```

### ChatView Component (ui/src/components/ChatView.tsx)

Correctly hides status when done:

```typescript
const statusLabel = !isUser && m.status && m.status !== 'done' ? m.status : null

{!isUser && statusLabel && (
  <div className="mb-1 text-xs text-amber-400">
    {statusLabel === 'thinking' ? 'Thinking…' : statusLabel}
  </div>
)}
```

## Key Invariants Now Guaranteed

1. **Single-shot**: No retries on Ollama requests (retries=0)
2. **Deterministic**: Frontend ALWAYS receives done event via {"type":"done"} JSON
3. **Synchronous state**: onDone() called before streamChat returns (due to await pump())
4. **Proper cleanup**: finally block ensures cleanup runs exactly once
5. **UI responsiveness**: isStreaming=false immediately enables input and shows Send button
6. **Status indicator**: Removed when status='done'

## Environment Variables

```bash
# Ollama inference timeout (seconds)
OLLAMA_TIMEOUT_SECONDS=120

# Maximum stream duration (seconds)
JARVIS_MAX_STREAM_SECONDS=120

# Stream inactivity timeout (seconds)
JARVIS_STREAM_INACTIVITY_SECONDS=120
```

## Testing Checklist

- [x] Backend emits explicit done event in finally block
- [x] Frontend receives done event (type="done" JSON)
- [x] handlePayload detects done and calls onDone()
- [x] pump() is awaited before streamChat returns
- [x] onDone() sets isStreaming=false
- [x] Message status set to 'done'
- [x] UI re-renders (Composer shows Send, input enabled)
- [x] Status indicator removed
- [x] Stop button works (calls abortRef.current)
- [x] No retry loops (retries=0)
- [x] Timeout from env var (not hardcoded)

## Files Changed

1. **src/jarvis/agent.py** - Dynamic timeout, disabled retries
2. **ui/src/lib/stream.ts** - Added await to pump() call

## Backwards Compatibility

- No breaking changes
- All changes are improvements with better semantics
- SSE parser already had done event handling
- ChatContext already had proper state management
- No API changes

## Related Documentation

- [src/jarvis/server.py](src/jarvis/server.py) - StreamRegistry, lifecycle management
- [ui/src/lib/stream.ts](ui/src/lib/stream.ts) - SSE parser with done event support
- [ui/src/contexts/ChatContext.tsx](ui/src/contexts/ChatContext.tsx) - Chat state and streaming
