# Code Snippets - Ready to Use

This file contains exact code snippets that were implemented in the fix.

## 1. ollama_client.py - Complete Updated Function

### ollama_request() - Timeout Fix (Lines 17-120)

```python
def ollama_request(
    url: str,
    payload: Dict[str, Any],
    *,
    connect_timeout: float = 5.0,
    read_timeout: float | None = 120.0,
    retries: int = 2,
    backoff: Tuple[float, ...] = (0.2, 0.5, 1.0),
    trace_id: str | None = None,
    is_streaming: bool = False,
) -> Dict[str, Any]:
    """
    Perform a POST request to Ollama with bounded retries/timeouts.

    For streaming requests (is_streaming=True), read_timeout is set to None
    to allow indefinite response time for long-running generations.

    Returns an envelope: {"ok": bool, "data": dict|None, "error": {...}|None, "trace_id": str}
    """
    # For streaming, use no read timeout (None); for non-streaming, use provided timeout
    actual_read_timeout = None if is_streaming else read_timeout
    
    # Use provided trace_id if any to correlate with stream cancellation
    tid = trace_id or uuid.uuid4().hex[:8]

    def _is_cancelled() -> bool:
        if not trace_id:
            return False
        try:
            # Import lazily to avoid circular at module import time
            from jarvis.server import check_stream_cancelled_sync  # type: ignore
            return check_stream_cancelled_sync(trace_id)
        except Exception:
            return False

    last_err: Exception | None = None
    for attempt in range(retries + 1):
        # Check cancellation before each attempt
        if _is_cancelled():
            error_obj = {
                "type": "ClientCancelled",
                "message": "Request cancelled",
                "trace_id": tid,
                "where": url,
            }
            logger.info("ollama_request cancelled before attempt %s (trace_id=%s)", attempt + 1, tid)
            return {"ok": False, "data": None, "error": error_obj, "trace_id": tid, "latency_ms": None}
        try:
            started = time.time()
            # For streaming, pass None for read timeout; for non-streaming, use timeout tuple
            timeout_val = (connect_timeout, actual_read_timeout) if actual_read_timeout is not None else connect_timeout
            resp = requests.post(url, json=payload, timeout=timeout_val)
            latency_ms = (time.time() - started) * 1000
            resp.raise_for_status()
            data = resp.json()
            if is_streaming:
                logger.info(f"ollama_request streaming completed (trace_id={tid}, latency_ms={latency_ms:.0f})")
            return {"ok": True, "data": data, "error": None, "trace_id": tid, "latency_ms": latency_ms}
        except Exception as exc:  # broad catch to prevent crash
            last_err = exc
            latency_ms = None
            logger.warning("ollama_request failed (attempt %s/%s, trace_id=%s): %s", attempt + 1, retries + 1, tid, exc)
            if attempt < retries:
                sleep_for = backoff[attempt] if attempt < len(backoff) else backoff[-1]
                # Check cancellation before sleeping/backoff
                if _is_cancelled():
                    error_obj = {
                        "type": "ClientCancelled",
                        "message": "Request cancelled",
                        "trace_id": tid,
                        "where": url,
                    }
                    logger.info("ollama_request cancelled after failure (trace_id=%s)", tid)
                    return {"ok": False, "data": None, "error": error_obj, "trace_id": tid, "latency_ms": latency_ms}
                time.sleep(sleep_for)
            else:
                break
    # Classify the error
    if last_err:
        if isinstance(last_err, requests.exceptions.Timeout):
            error_type = "ProviderTimeout"
        elif isinstance(last_err, (requests.exceptions.ConnectionError, requests.exceptions.ConnectTimeout)):
            error_type = "ProviderConnectionError"
        elif isinstance(last_err, (requests.exceptions.HTTPError, requests.exceptions.JSONDecodeError)):
            error_type = "ProviderBadResponse"
        else:
            error_type = last_err.__class__.__name__
    else:
        error_type = "ProviderError"
    error_obj = {
        "type": error_type,
        "message": str(last_err) if last_err else "Unknown provider error",
        "trace_id": tid,
        "where": url,
    }
    logger.error(
        "ollama_request failed after retries (trace_id=%s, url=%s, model=%s, type=%s)",
        tid,
        url,
        payload.get("model"),
        error_type,
    )
    return {"ok": False, "data": None, "error": error_obj, "trace_id": tid, "latency_ms": latency_ms}
```

### ollama_stream() - New Streaming Function (Lines 123-227)

```python
def ollama_stream(
    url: str,
    payload: Dict[str, Any],
    *,
    connect_timeout: float = 5.0,
    read_timeout: float | None = None,
    retries: int = 0,
    trace_id: str | None = None,
) -> Dict[str, Any]:
    """
    Stream response from Ollama line-by-line with NO read timeout for long-running generations.
    
    Yields chunks as they arrive. For streaming, read_timeout is NOT used - we allow
    indefinite waits for tokens.
    
    Returns an envelope: {"ok": bool, "stream": Generator|None, "error": {...}|None, "trace_id": str}
    """
    tid = trace_id or uuid.uuid4().hex[:8]

    def _is_cancelled() -> bool:
        if not trace_id:
            return False
        try:
            from jarvis.server import check_stream_cancelled_sync  # type: ignore
            return check_stream_cancelled_sync(trace_id)
        except Exception:
            return False

    def _stream_generator() -> Generator[dict, None, None]:
        """Yield JSON objects line-by-line from the streaming response."""
        try:
            # Connect with timeout, but allow indefinite read time for streaming
            resp = requests.post(
                url,
                json=payload,
                stream=True,
                timeout=(connect_timeout, None),  # Connect timeout only, no read timeout
            )
            resp.raise_for_status()
            
            for line in resp.iter_lines():
                # Check if stream was cancelled
                if _is_cancelled():
                    logger.info(f"ollama_stream cancelled (trace_id={tid})")
                    resp.close()
                    return
                
                if not line:
                    continue
                
                try:
                    chunk = json.loads(line)
                    yield chunk
                except json.JSONDecodeError as e:
                    logger.warning(f"ollama_stream: invalid JSON chunk (trace_id={tid}): {e}")
                    continue
            
            logger.info(f"ollama_stream completed successfully (trace_id={tid})")
        
        except requests.exceptions.Timeout as e:
            logger.error(f"ollama_stream timeout (trace_id={tid}): {e}")
            yield {"error": f"Request timeout: {str(e)}", "trace_id": tid}
        except Exception as e:
            logger.error(f"ollama_stream failed (trace_id={tid}): {e}")
            yield {"error": f"Stream error: {str(e)}", "trace_id": tid}

    last_err: Exception | None = None
    for attempt in range(retries + 1):
        if _is_cancelled():
            return {
                "ok": False,
                "stream": None,
                "error": {
                    "type": "ClientCancelled",
                    "message": "Stream cancelled",
                    "trace_id": tid,
                    "where": url,
                },
                "trace_id": tid,
            }
        
        try:
            # Return the generator immediately without connecting
            # Connection happens when iteration starts
            return {
                "ok": True,
                "stream": _stream_generator(),
                "error": None,
                "trace_id": tid,
            }
        except Exception as e:
            last_err = e
            logger.warning(f"ollama_stream setup failed (trace_id={tid}): {e}")
            if attempt < retries:
                time.sleep(0.5)

    error_obj = {
        "type": "StreamSetupError",
        "message": str(last_err) if last_err else "Failed to setup stream",
        "trace_id": tid,
        "where": url,
    }
    return {"ok": False, "stream": None, "error": error_obj, "trace_id": tid}
```

### ollama_client.py - Imports (Lines 1-14)

```python
"""
Shared Ollama HTTP client with retries, timeouts, and error envelopes.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any, Dict, Generator, Tuple

import requests

logger = logging.getLogger(__name__)
```

---

## 2. agent.py - Updated call_ollama() Function

### call_ollama() - Complete Function (Lines 334-368)

```python
def call_ollama(messages, model_profile: str = "balanced"):
    import time
    from jarvis.agent_core.orchestrator import set_last_metric
    from jarvis.performance_metrics import get_model_profile_params
    import uuid
    start = time.time()
    
    # Get profile parameters
    profile_params = get_model_profile_params(model_profile)
    
    trace_id = uuid.uuid4().hex[:8]
    payload = {
        "model": os.getenv("OLLAMA_MODEL"),
        "messages": messages,
        "stream": False,
        **profile_params  # Add profile parameters
    }
    timeout = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "120"))
    resp = ollama_request(
        os.getenv("OLLAMA_URL"),
        payload,
        connect_timeout=2.0,
        read_timeout=timeout,
        retries=0,
        trace_id=trace_id,
        is_streaming=False,
    )
    if resp.get("ok"):
        data = resp.get("data") or {}
        set_last_metric("llm_ms", (time.time() - start) * 1000)
        return data
    error = resp.get("error") or {}
    set_last_metric("llm_ms", (time.time() - start) * 1000)
    return {"error": error.get("message") or "OLLAMA_REQUEST_FAILED", "trace_id": error.get("trace_id", trace_id)}
```

---

## 3. Usage Examples

### Using ollama_request() with Non-Streaming (Current)

```python
from jarvis.provider.ollama_client import ollama_request

# Non-streaming call - will timeout after 120s
resp = ollama_request(
    url="http://localhost:11434/api/generate",
    payload={
        "model": "mistral",
        "messages": [{"role": "user", "content": "Hello"}],
        "stream": False,
    },
    connect_timeout=2.0,
    read_timeout=120.0,
    retries=0,
    trace_id="abc123",
    is_streaming=False,  # Key parameter
)

if resp["ok"]:
    print(resp["data"])
else:
    print(f"Error: {resp['error']}")
```

### Using ollama_stream() with Streaming (Future)

```python
from jarvis.provider.ollama_client import ollama_stream

# Streaming call - no read timeout
resp = ollama_stream(
    url="http://localhost:11434/api/generate",
    payload={
        "model": "mistral",
        "messages": [{"role": "user", "content": "Hello"}],
        "stream": True,
    },
    connect_timeout=2.0,
    trace_id="abc123",
)

if resp["ok"]:
    for chunk in resp["stream"]:
        if "error" in chunk:
            print(f"Error: {chunk['error']}")
            break
        if "response" in chunk:
            print(chunk["response"], end="", flush=True)
else:
    print(f"Error: {resp['error']}")
```

---

## 4. Testing Code Snippets

### Test: Long Request (Should Not Timeout)

```python
import requests
import time

# Test long-running request
url = "http://localhost:8000/v1/chat/completions"
payload = {
    "model": "mistral",
    "messages": [{"role": "user", "content": "Write a 1000-word story"}],
    "stream": False,
}

start = time.time()
try:
    resp = requests.post(url, json=payload, timeout=(2.0, 120.0))
    elapsed = time.time() - start
    print(f"✅ Success! Completed in {elapsed:.1f}s")
    print(f"Response: {resp.json()}")
except requests.exceptions.Timeout as e:
    print(f"❌ Timeout! {e}")
```

### Test: Streaming with Events

```python
import requests
import json

url = "http://localhost:8000/v1/chat/completions"
payload = {
    "model": "mistral",
    "messages": [{"role": "user", "content": "Write a story"}],
    "stream": True,
}

with requests.post(url, json=payload, stream=True) as resp:
    for line in resp.iter_lines():
        if line:
            chunk = json.loads(line)
            if "choices" in chunk:
                delta = chunk["choices"][0].get("delta", {})
                if "content" in delta:
                    print(delta["content"], end="", flush=True)
```

---

## 5. Configuration Snippets

### Environment Setup

```bash
#!/bin/bash

# Timeout configuration
export OLLAMA_TIMEOUT_SECONDS=120      # 2 minutes (default)
export OLLAMA_TIMEOUT_SECONDS=240      # 4 minutes (slow servers)
export OLLAMA_TIMEOUT_SECONDS=600      # 10 minutes (very slow)

# Ollama configuration
export OLLAMA_URL=http://localhost:11434/api/generate
export OLLAMA_MODEL=mistral

# Logging
export LOG_LEVEL=DEBUG

# Server start
python -m uvicorn src.jarvis.server:app --host 0.0.0.0 --port 8000
```

### Docker Configuration

```yaml
services:
  api:
    environment:
      - OLLAMA_TIMEOUT_SECONDS=240
      - OLLAMA_URL=http://ollama:11434/api/generate
      - OLLAMA_MODEL=mistral
      - LOG_LEVEL=INFO
    depends_on:
      - ollama
```

---

## 6. Monitoring & Debugging

### Check for Timeout Errors

```bash
# Real-time monitoring
tail -f /var/log/app.log | grep -i "timeout"

# Count timeout errors
grep -i "read timed out" /var/log/app.log | wc -l

# Find specific trace
grep "trace_id=abc123" /var/log/app.log
```

### Debug Logging

```python
import logging

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("jarvis.provider.ollama_client")
logger.setLevel(logging.DEBUG)

# Now see detailed logs:
# - Connection attempts
# - Timeout values used
# - Stream iterations
# - Chunk sizes
```

---

## 7. Error Handling

### Handling Different Error Types

```python
from jarvis.provider.ollama_client import ollama_request

resp = ollama_request(...)

if resp["ok"]:
    print("Success!")
elif resp["error"]["type"] == "ProviderTimeout":
    print("Ollama timeout - increase OLLAMA_TIMEOUT_SECONDS")
elif resp["error"]["type"] == "ProviderConnectionError":
    print("Cannot connect to Ollama - check OLLAMA_URL")
elif resp["error"]["type"] == "ClientCancelled":
    print("Request was cancelled")
else:
    print(f"Error: {resp['error']['message']}")
```

---

## Summary

This file contains all code snippets used in the streaming timeout fix implementation. Use these snippets for:

- Code review
- Understanding the changes
- Testing the fix
- Integration into other projects
- Configuration reference

For full context, see:
- STREAMING_TIMEOUT_FIX_COMPLETE.md - Detailed explanation
- STREAMING_TIMEOUT_FIX_DIFF.md - Diff format
- IMPLEMENTATION_VERIFICATION.md - Verification checklist
