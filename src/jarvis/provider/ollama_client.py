"""
Shared Ollama HTTP client with retries, timeouts, and error envelopes.
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Dict, Tuple

import requests

logger = logging.getLogger(__name__)


def ollama_request(
    url: str,
    payload: Dict[str, Any],
    *,
    connect_timeout: float = 5.0,
    read_timeout: float = 120.0,
    retries: int = 2,
    backoff: Tuple[float, ...] = (0.2, 0.5, 1.0),
) -> Dict[str, Any]:
    """
    Perform a POST request to Ollama with bounded retries/timeouts.

    Returns an envelope: {"ok": bool, "data": dict|None, "error": {...}|None, "trace_id": str}
    """
    trace_id = uuid.uuid4().hex[:8]
    last_err: Exception | None = None
    for attempt in range(retries + 1):
        try:
            started = time.time()
            resp = requests.post(url, json=payload, timeout=(connect_timeout, read_timeout))
            latency_ms = (time.time() - started) * 1000
            resp.raise_for_status()
            data = resp.json()
            return {"ok": True, "data": data, "error": None, "trace_id": trace_id, "latency_ms": latency_ms}
        except Exception as exc:  # broad catch to prevent crash
            last_err = exc
            latency_ms = None
            logger.warning("ollama_request failed (attempt %s/%s, trace_id=%s): %s", attempt + 1, retries + 1, trace_id, exc)
            if attempt < retries:
                sleep_for = backoff[attempt] if attempt < len(backoff) else backoff[-1]
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
        "trace_id": trace_id,
        "where": url,
    }
    return {"ok": False, "data": None, "error": error_obj, "trace_id": trace_id, "latency_ms": latency_ms}
