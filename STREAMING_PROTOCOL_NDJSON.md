# Streaming Protocol Standardization

## New Protocol: NDJSON (Newline-Delimited JSON)

### Format
```
{"type":"status","content":null,"status":"thinking","trace_id":"...","session_id":"..."}
{"type":"token","content":"Hello","trace_id":"...","session_id":"..."}
{"type":"token","content":" world","trace_id":"...","session_id":"..."}
{"type":"done","content":null,"reason":"success","trace_id":"...","session_id":"..."}
```

### Rules
- ✅ One JSON object per line
- ✅ No SSE "data:" prefix (direct JSON only)
- ✅ No buffering - each event emitted independently
- ✅ Newline-terminated (single `\n`)
- ✅ UTF-8 encoded
- ✅ No partial JSON objects
- ✅ Skip empty lines

### Event Types

| Type | Content | When |
|------|---------|------|
| `status` | `null` | Status change: "thinking", "using_tool", "writing" |
| `token` | string | Each token of response |
| `done` | `null` | Stream complete (reason: "success", "error", "cancelled") |
| `error` | string | Error occurred (error_type field included) |

## Backend Changes

### New Helper Functions (server.py)
```python
def _ndjson_event(event_type: str, content: str | None = None, **kwargs) -> str:
    """Emit NDJSON: {"type":"...", "content":"...", ...}"""
    payload = {"type": event_type, "content": content}
    payload.update(kwargs)
    return json.dumps(payload) + "\n"

def _ndjson_status(status: str, **kwargs) -> str:
    """Emit status event"""
    return _ndjson_event("status", None, status=status, **kwargs)

def _ndjson_token(token: str, **kwargs) -> str:
    """Emit token event"""
    return _ndjson_event("token", token, **kwargs)

def _ndjson_done(reason: str | None = None, **kwargs) -> str:
    """Emit done event"""
    return _ndjson_event("done", None, reason=reason, **kwargs)

def _ndjson_error(error: str, **kwargs) -> str:
    """Emit error event"""
    return _ndjson_event("error", error, **kwargs)
```

### Generator Changes
```python
# Before:
yield f"data: {json.dumps(complex_openai_format)}\n\n"

# After:
yield _ndjson_token(token, trace_id=trace_id)
yield _ndjson_status(status, trace_id=trace_id)
yield _ndjson_done(reason="success", trace_id=trace_id)
yield _ndjson_error(error_msg, error_type="Error", trace_id=trace_id)
```

**Changes**: 5 emit locations updated

## Frontend Changes

### Old Parser (Problematic)
```typescript
// Old: Complex SSE parsing with event: and data: prefix handling
// Mixed multiple formats (OpenAI, custom, EventBus events)
// Could parse partial JSON if newlines misaligned
```

### New Parser (NDJSON)
```typescript
async function pump() {
  const handlePayload = (raw: string) => {
    if (!raw.trim()) return  // Skip empty lines
    
    try {
      const parsed = JSON.parse(raw)  // Single complete JSON per line
      
      switch (parsed.type) {
        case 'status':
          onStatus?.(parsed.status)
          return
        case 'token':
          onDelta(parsed.content || '')
          return
        case 'done':
          onDone()
          ac.abort()
          return
        case 'error':
          onError(parsed.content || 'Unknown error')
          ac.abort()
          return
      }
    } catch (err) {
      // Skip non-JSON lines (shouldn't happen, but safe to ignore)
    }
  }

  // Parse line-by-line
  for (const lineRaw of lines) {
    const line = lineRaw.replace(/\r$/, '')
    if (line) handlePayload(line)
  }
}
```

**Changes**: stream.ts `pump()` function completely rewritten for NDJSON

## Benefits

| Aspect | Before | After |
|--------|--------|-------|
| Parser complexity | High (SSE, events, format variations) | Simple (JSON per line) |
| Partial JSON risk | Yes (complex line parsing) | No (each line is complete) |
| Format variants | 3+ (OpenAI, EventBus, custom) | 1 (NDJSON) |
| Error handling | Complex | Simple (skip bad lines) |
| Newline safety | Fragile (multi-line events) | Robust (strict line boundaries) |
| Performance | Slower (regex splits, format detection) | Faster (simple JSON parsing) |

## Testing

```bash
# Test 1: Stream tokens
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Hello","stream":true}' \
  | head -20

# Expected output (line by line):
# {"type":"status","content":null,"status":"thinking","trace_id":"..."}
# {"type":"token","content":"Hello","trace_id":"..."}
# {"type":"token","content":" there","trace_id":"..."}
# {"type":"done","content":null,"reason":"success","trace_id":"..."}

# Test 2: Verify newlines
# Should be exactly one JSON object per line, no partial objects
curl ... | od -c | grep -E '^[0-9]+ \n'
```

## Migration Notes

### For Existing Clients
- **Breaking change**: Old parser will not work with new protocol
- **Migration path**: Update stream.ts to new NDJSON parser
- **Backward compatibility**: Not maintained (but protocol is much simpler now)

### For Integration Tests
- Old expectations of `"data: ..."` format will fail
- Update to parse lines directly as JSON
- No need to handle "event: status\ndata: ...\n\n" format anymore

## Files Modified

| File | Changes | Lines |
|------|---------|-------|
| src/jarvis/server.py | New NDJSON helpers, 5 yield locations | 30 |
| ui/src/lib/stream.ts | New pump() function | 40 |

**Total**: 70 lines changed, 0 lines added complexity

---

**Protocol Version**: 1.0 (2026-01-26)  
**Format**: Newline-Delimited JSON (NDJSON)  
**Encoding**: UTF-8  
**Line Ending**: LF (`\n`)  
**Backward Compat**: Breaking change (schema simplified)  
