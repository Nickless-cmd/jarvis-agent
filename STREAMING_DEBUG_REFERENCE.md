# Streaming Stability - Quick Reference

## If Still Having Issues

### Symptom: Still get "timeout" or backend hang on client disconnect

**Check**: Verify headers are being sent
```bash
curl -v http://localhost:8000/v1/chat/completions -d '{"prompt":"test","stream":true}' 2>&1 | grep -i "cache-control\|connection\|accel"
```

Should see:
```
< Cache-Control: no-cache, no-store, must-revalidate, max-age=0
< Connection: keep-alive
< X-Accel-Buffering: no
```

### Symptom: Tokens still delayed 2-3 seconds

**Check 1**: Verify nginx/reverse proxy buffering is off
```bash
# If using nginx
grep -n "proxy_buffering\|proxy_buffer" /etc/nginx/nginx.conf
# Should be: proxy_buffering off; or absent (defaults to off for SSE)
```

**Check 2**: Verify uvicorn is not in test mode
```bash
# uvicorn should be production mode:
uvicorn src.jarvis.server:app --host 0.0.0.0 --port 8000
# NOT: 
# - reload enabled (causes buffering)
# - debug=True (can cause buffering)
```

### Symptom: Still require `kill -9` on disconnect

**Check logs** for:
```
stream_cancelled trace=...   # Generator was cancelled
agent_task_timeout_on_cancel trace=...   # Agent task ignored cancellation
```

If you see `agent_task_timeout_on_cancel`, the blocking `run_agent` call is not responding to thread cancellation. This is a bug in agent.py, not server.py.

### Symptom: Old responses appearing in new stream

**Check**: Previous stream was actually cancelled
```bash
# Monitor logs for a session_id while sending two requests quickly:
tail -f logs/server.log | grep "stream_cancelled\|stream_start"
```

Should see:
```
stream_start trace=aaa session=sess_xyz
stream_cancelled trace=aaa reason=registry_new_stream  # When sending 2nd request
stream_start trace=bbb session=sess_xyz
```

If not cancelling: StreamRegistry might not be updating correctly. Check app startup logs.

## Performance Tuning

### To debug hang (if it still happens)

```bash
# 1. Add faulthandler to startup (already done)
# 2. Send request that hangs
# 3. In another terminal, dump stacks:
kill -SIGUSR1 $(pgrep -f uvicorn)

# 4. Check stderr for stack traces
# Look for where agent.py is blocked
```

### To monitor event throughput

```bash
# Count events per second
tail -f logs/server.log | grep "stream_status\|stream_delta" | wc -l
# Should be: ~20+ events/sec for normal LLM streaming
```

### To verify no task leaks

```bash
# Monitor task count over time (should stay constant)
while true; do echo "$(date '+%H:%M:%S') Tasks: $(ps aux | grep '\[' | wc -l)"; sleep 5; done
```

## Headers Breakdown

**These 5 headers work together:**

1. `Cache-Control: no-cache, no-store, must-revalidate, max-age=0`
   - Tells ALL layers: don't buffer
   - HTTP/1.1 standard
   
2. `Connection: keep-alive`
   - Keep TCP connection open
   - Required for SSE to work

3. `X-Accel-Buffering: no`
   - Nginx-specific directive
   - Disables proxy buffering

4. `Pragma: no-cache`
   - HTTP/1.0 fallback
   - For old proxies

5. `Expires: 0`
   - HTTP/1.0 cache control
   - Immediately expired

If ANY of these is missing or wrong, buffering will happen upstream.

## Cancellation Timeout Tuning

Current setting: **0.5 seconds** for agent task cancellation

```python
await asyncio.wait_for(agent_task, timeout=0.5)
```

If agent tasks frequently timeout:
- Increase to 1.0 (slower cancellation but fewer timeouts)
- Or make agent interruptible (better solution)

If users report "takes too long to stop":
- Decrease to 0.2 (faster but more aggressive)

## Event Protocol

Verify your client can handle all three event types:

```javascript
// Status event (first)
{"type":"status","status":"thinking"}

// Token events (middle, many)
{"type":"delta","content":"hello"}
or
{"id":"...","choices":[{"index":0,"delta":{"content":"hello"}}]}

// Done event (last)
{"type":"done"}
or
{"type":"done","error":"stream_cancelled"}
```

Both formats are supported. Frontend should handle both.

---

**Last Updated**: 2026-01-26
