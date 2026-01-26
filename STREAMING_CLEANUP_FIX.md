# Streaming Cleanup Fix

## Root Cause

- Streaming generator had no shared registry to track active tasks per session/trace.
- Client disconnects/Stop endpoint only flipped a flag; agent task could keep running, leaving zombie tasks.
- Cleanup did not always run on cancellation/disconnect/timeout, so stream_end/cleanup logs were missing and processes could hang.

## What Changed

- Added `StreamRegistry` to manage one active stream per session/trace, cancel older streams, and expose cancel for the Stop endpoint.
- Streaming generator now registers itself, detects external cancel, inactivity, disconnects, and always cleans up in `finally` (removing registry entry, cancelling and awaiting agent task with timeout).
- Added inactivity watchdog and force-cancel logging; improved cancellation logging for disconnect/timeout/stop.
- Stop endpoint now cancels via registry.

## How to Manually Verify (3 steps)

1) **Disconnect test**: Start a chat stream, then close the tab. Expected logs: `stream_disconnected`, `stream_cancelled reason=external_cancel|disconnect`, `stream_cleanup`, `stream_end`. Registry should be empty (no zombie tasks).
2) **Stop endpoint**: Start a chat stream, call `POST /v1/chat/stop` with `trace_id` from stream. Expected: stream ends, logs show `stream_cancelled reason=stop_endpoint`, cleanup/end logged.
3) **Concurrent stream**: Start stream A for a session, then start stream B for same session. Expected: A gets cancelled before B runs; logs show cancellation for A, and B proceeds normally.

## Logs to Watch

- `stream_start`, `first_chunk`, `stream_cancelled reason=<...>`, `stream_cleanup`, `stream_force_cancel` (if task did not stop promptly), `stream_end` with `duration_ms`.
