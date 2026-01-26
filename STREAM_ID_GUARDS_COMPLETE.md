# Stream ID Safety Guards - Implementation Complete

## Summary
Added temporary stream_id validation guards to prevent stale streams from updating the UI after a new stream has started. These guards validate that each token/event belongs to the currently active stream before processing.

## Purpose
When a user sends multiple prompts in quick succession, the old stream may still be emitting tokens while the new stream has begun. These guards catch that condition and prevent the stale tokens from updating the UI.

## Implementation

### Backend Changes (src/jarvis/server.py)
- **Lines 302-325**: Updated NDJSON helper functions to accept optional `stream_id` parameter
  - `_ndjson_event()`: Now accepts `stream_id: str | None = None` 
  - Added `stream_id` to NDJSON payload if provided
  - All helper functions (`_ndjson_status`, `_ndjson_token`, `_ndjson_done`, `_ndjson_error`) updated

- **Line 2943**: Generate `stream_id = request_id` (UUID per request)
- **Line 2944**: Enhanced logging: stream lifecycle now includes stream_id
- **Lines 3134-3178**: All 12 event emissions now pass `stream_id` parameter:
  - Status events (2 locations)
  - Token events (2 locations)  
  - Done events (2 locations)
  - Error event
  - Error done message
  - Other event references

### Frontend Changes

#### ChatContext.tsx
- **Line 45**: Added `activeStreamIdRef` to track current stream_id
- **Line 105-108**: Generate new `stream_id` per request:
  ```typescript
  const newStreamId = `stream-${Date.now()}-${Math.random().toString(36).slice(2,8)}`
  activeStreamIdRef.current = newStreamId
  ```

- **Lines 131-135**: Token handler now:
  - Accepts `streamId` parameter
  - Validates `streamId === activeStreamIdRef.current`
  - Logs mismatch for debugging
  - Skips processing if mismatch detected

- **Lines 158-162**: Done handler now:
  - Accepts `streamId` parameter
  - Validates stream ID
  - Logs mismatches

- **Lines 169-173**: Error handler now:
  - Accepts `streamId` parameter
  - Validates stream ID
  - Logs mismatches

- **Lines 181-185**: Status handler now:
  - Accepts `streamId` parameter
  - Validates stream ID
  - Logs mismatches

#### stream.ts
- **Lines 26-29**: Updated function signature for all callbacks:
  ```typescript
  onDelta: (text: string, streamId?: string) => void,
  onDone: (streamId?: string) => void,
  onError: (errText: string, streamId?: string) => void,
  onStatus?: (status: string, streamId?: string) => void,
  ```

- **Line 38**: Declare `streamId` variable to track stream ID from response

- **Lines 88-94**: Non-stream JSON response path:
  - Extract `stream_id` from response
  - Pass to all callbacks

- **Line 101**: Pass `streamId` to error handler

- **Line 106**: Pass `streamId` to initial thinking status

- **Lines 120-122**: Extract `stream_id` from first NDJSON event received:
  ```typescript
  if (!streamId && parsed.stream_id) {
    streamId = parsed.stream_id
  }
  ```

- **Lines 126, 131, 136, 142**: Pass `streamId` to status/token/done/error handlers

- **Lines 170, 173, 189**: Pass `streamId` in error paths

## Debug Logging
When a stream_id mismatch is detected, the browser console logs:
```
[ChatContext] Stream ID mismatch in token: { expected: "stream-1234-abc", received: "stream-5678-def" }
```

This helps identify if stale streams are still occurring and need further investigation.

## Marked as Temporary
All changes are clearly marked with `// TEMP: ... (remove after debugging)` comments to indicate these are debug guards that should be removed once streaming stability is verified.

## Files Modified
1. `src/jarvis/server.py` - Backend NDJSON helpers and generator
2. `ui/src/contexts/ChatContext.tsx` - Frontend stream lifecycle tracking
3. `ui/src/lib/stream.ts` - Stream parsing with stream_id validation

## Compilation Status
✅ No TypeScript errors
✅ All backends changes in place
✅ Frontend stream_id tracking active
✅ Validation guards active

## Next Steps
1. Test with rapid multi-prompt sends to verify no stale tokens appear
2. Monitor browser console for any "Stream ID mismatch" logs
3. Once verified stable, remove all TEMP guards and stream_id parameters
