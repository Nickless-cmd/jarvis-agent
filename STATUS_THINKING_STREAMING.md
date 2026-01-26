# Status/Thinking Streaming Implementation

## Oversigt

Implementerer separat thinking/status streaming der:
- **Ikke blokerer content streaming**
- **Rate-limited** (max 10 updates/sek)
- **Ikke buffered** (publiceres umiddelbart)
- **Kan droppes** ved rate limit uden at påvirke content

## Arkitektur

### Event Types

**`chat.status`** - Status/thinking events
- Publiceres direkte (IKKE buffered som tokens)
- Rate-limited til 10/sek per request_id
- Kan droppes ved disconnect eller rate limit
- Frontend viser i UI (fx "Thinking...")

**`chat.token`** - Content tokens (eksisterende)
- Buffered for batching (75ms debounce)
- Garanteret levering
- Må ALDRIG blokere

### Rate Limiting

```python
_status_rate_limit: Dict[str, List[float]] = {}  # request_id -> timestamps
_MAX_STATUS_UPDATES_PER_SEC = 10
```

**Mekanisme:**
1. Track timestamps per request_id (sidste sekunds events)
2. Hvis >10 events i sidste sekund: drop event
3. Cleanup automatisk ved end/error/disconnect
4. Reset efter 1 sekund (sliding window)

### Flow

```
Agent emits thinking update
  ↓
publish("chat.status", {...})
  ↓
_handle_status_event()
  ↓
Check rate limit (request_id)
  ↓
If under limit (≤10/sec):
  - Publish directly (NO BUFFER)
  - Add timestamp to rate limit tracker
  ↓
If over limit (>10/sec):
  - Drop event (prevent spam)
  - Log debug message
  ↓
Event reaches subscribers
  ↓
NDJSON stream sends to frontend:
  {"type": "thinking", "content": "Analyzing...", ...}
```

## API Usage

### Backend (Python)

```python
from jarvis.server import emit_chat_status

# Emit thinking/status update
emit_chat_status(
    session_id="session-123",
    request_id="req-456", 
    status="Analyzing code...",
    trace_id="trace-789"
)

# Events auto rate-limited and cleaned up
```

### Frontend (TypeScript)

```typescript
// NDJSON stream handler
for await (const line of response.body) {
  const event = JSON.parse(line);
  
  if (event.type === "thinking" || event.type === "status") {
    // Show thinking indicator
    setStatus(event.status || event.content);
    // "Analyzing code..." -> UI displays
  }
  
  if (event.type === "token") {
    // Normal content streaming
    appendToken(event.content);
  }
}
```

## Kode Ændringer

### src/jarvis/events.py

**Tilføjet:**
- `_status_rate_limit: Dict[str, List[float]]` - Rate limit state
- `_MAX_STATUS_UPDATES_PER_SEC = 10` - Max 10/sek
- `_check_status_rate_limit(request_id)` - Check/update rate limit
- `_handle_status_event(payload)` - Handle status events separat

**Opdateret:**
- `publish()` - Route `chat.status`/`chat.thinking` til handler
- `cleanup_request_buffers()` - Clear rate limit state
- `close()`, `reset_for_tests()` - Clear rate limit state

### src/jarvis/server.py

**Tilføjet:**
- `emit_chat_status(session_id, request_id, status, trace_id)` - Emit helper
- `_ndjson_thinking(message, ...)` - NDJSON formatter

**Eksempel streaming:**
```python
# In streaming generator
yield _ndjson_thinking("Analyzing...", stream_id=stream_id)
# ... continue with tokens ...
yield _ndjson_token("Hello", stream_id=stream_id)
```

## Testing

### Automated Tests

```bash
python test_status_streaming.py
```

**Tests:**
1. ✅ Rate Limiting - Max 10/sek enforced
2. ✅ Not Buffered - Status immediate, tokens buffered
3. ✅ Cleanup - Rate limit state cleaned up
4. ✅ Rate Limit Recovery - Reset after 1 second
5. ✅ Async Support - Works with event loop

**Resultat:**
```
✓✓✓ ALL TESTS PASSED (5/5) ✓✓✓
```

### Manual Testing

```bash
# Start server
make run

# Send prompt with thinking updates
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [{"role": "user", "content": "Analyze this code"}],
    "stream": true
  }'

# Expected output (NDJSON):
{"type":"thinking","content":"Analyzing..."}
{"type":"status","status":"Reading files..."}
{"type":"token","content":"Here"}
{"type":"token","content":" is"}
{"type":"done","reason":"success"}
```

## Logs

**Ved status update:**
```
DEBUG status_published request_id=req-1 status=thinking
```

**Ved rate limit:**
```
DEBUG status_rate_limited request_id=req-1 count=11
```

**Ved cleanup:**
```
INFO cleanup_request_complete request_id=req-1
```

## Garantier

✅ **Status events kan ALDRIG blokere content tokens**
  - Separate event paths
  - No shared buffers
  - Direct publish (no debounce)

✅ **Rate limiting forhindrer spam**
  - Max 10 updates/sek
  - Sliding 1-second window
  - Dropped events logged

✅ **Cleanup er komplet**
  - Rate limit state removed ved end/error
  - No memory leaks
  - Idempotent cleanup

✅ **Frontend kan opdatere UI smooth**
  - Up to 10 status changes/sek
  - Doesn't interfere with content
  - Can show "Thinking..." → "Analyzing..." → "Done"

## Eksempel Use Cases

### 1. Long-running Analysis
```python
emit_chat_status(session, req, "Reading files...", trace)
# ... read 1000 files ...
emit_chat_status(session, req, "Analyzing patterns...", trace)
# ... analyze ...
emit_chat_status(session, req, "Generating report...", trace)
# ... emit tokens ...
```

### 2. Multi-step Reasoning
```python
emit_chat_status(session, req, "Step 1: Understanding query", trace)
emit_chat_status(session, req, "Step 2: Searching knowledge", trace)
emit_chat_status(session, req, "Step 3: Formulating answer", trace)
# ... emit answer tokens ...
```

### 3. Progress Updates
```python
for i, chunk in enumerate(large_dataset):
    if i % 100 == 0:  # Every 100 items
        emit_chat_status(session, req, f"Processed {i}/{total}", trace)
    # ... process ...
```

## Begrænsninger

- **Max 10 status updates/sek** - Mere droppes
- **No buffering** - Status sendes direkte (kan tabe ved netværksfejl)
- **No retry** - Droppede events sendes ikke igen
- **No ordering guarantee** ved concurrent updates

Dette er design choices for at sikre performance og stabilitet.

## Migration Guide

### Hvis du har eksisterende status logic:

**Før:**
```python
# Manual status via tokens (blander content)
emit_chat_token(session, req, "[Thinking...]", trace)
# ... actual content ...
emit_chat_token(session, req, "Answer", trace)
```

**Efter:**
```python
# Separate status channel
emit_chat_status(session, req, "Thinking...", trace)
# ... actual content ...
emit_chat_token(session, req, "Answer", trace)
```

**Frontend opdatering:**
```typescript
// Før: status blandet med content
if (token.startsWith("[") && token.endsWith("]")) {
  setStatus(token);
} else {
  appendContent(token);
}

// Efter: separate event types
if (event.type === "status" || event.type === "thinking") {
  setStatus(event.status || event.content);
} else if (event.type === "token") {
  appendContent(event.content);
}
```

---

**Status:** ✅ Implementeret og testet  
**Version:** 1.0  
**Dato:** 26. januar 2026
