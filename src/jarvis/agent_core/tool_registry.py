"""
Safe tool registry with allowlist, audit logging, and robust execution.
"""

import copy
import json
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Callable, Optional
from datetime import datetime, timezone

from jarvis.db import get_conn
from jarvis.agent_core.cache import TTLCache
import traceback
import uuid
import logging
import concurrent.futures
import threading
import math


@dataclass
class ToolSpec:
    """Specification for a tool."""
    name: str
    description: str
    args_schema: Dict[str, Any]
    risk_level: str  # "low", "medium", "high"


# Global registry
_tool_registry: Dict[str, tuple[ToolSpec, Callable]] = {}
_allowlist: set[str] = set()
_tool_cache = TTLCache(default_ttl=60)

# Cache TTLs per tool (seconds)
TOOL_CACHE_TTLS: Dict[str, int] = {
    "weather_now": 600,
    "weather_forecast": 600,
    "news_search": 300,
    "search_combined": 300,
    "read_article": 300,
    "system_info": 30,
    "currency_convert": 600,
}

TOOL_TIMEOUTS: Dict[str, float] = {
    "news_search": 30.0,
    "web_search": 30.0,
    "search_combined": 30.0,
    "read_article": 30.0,
    "system_info": 15.0,
    "ping_host": 15.0,
}

log = logging.getLogger(__name__)


@dataclass
class ToolResult:
    """Standardized result object for tool execution."""
    tool_name: str
    ok: bool
    started_at: float
    ended_at: float
    duration_ms: float
    input_summary: Dict[str, Any]
    output: Any | None
    error: Optional[Dict[str, Any]]
    trace_id: str


class ToolRunner:
    """Execute registered tools with timeout, retries, and audit logging."""

    def __init__(self) -> None:
        self.default_timeout = float(os.getenv("JARVIS_TOOL_TIMEOUT_DEFAULT", "30.0"))
        self.default_retries = int(os.getenv("JARVIS_TOOL_RETRIES", "0"))
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=8, thread_name_prefix="tool-runner")
        self._lock = threading.Lock()

    def _enforce_allowlist(self, name: str, trace_id: str) -> Optional[ToolResult]:
        if not _allowlist:
            _load_allowlist()
        if name not in _allowlist:
            return ToolResult(
                tool_name=name,
                ok=False,
                started_at=time.time(),
                ended_at=time.time(),
                duration_ms=0.0,
                input_summary={},
                output=None,
                error={
                    "type": "ToolError",
                    "message": f"Tool '{name}' is not in allowlist",
                    "trace_id": trace_id,
                    "where": name,
                },
                trace_id=trace_id,
            )
        if name not in _tool_registry:
            return ToolResult(
                tool_name=name,
                ok=False,
                started_at=time.time(),
                ended_at=time.time(),
                duration_ms=0.0,
                input_summary={},
                output=None,
                error={
                    "type": "ToolError",
                    "message": f"Tool '{name}' is not registered",
                    "trace_id": trace_id,
                    "where": name,
                },
                trace_id=trace_id,
            )
        return None

    def _run_once(self, fn: Callable, args: Dict[str, Any], timeout: float) -> Any:
        future = self._executor.submit(fn, **args)
        return future.result(timeout=timeout)

    def run(
        self,
        name: str,
        args: Dict[str, Any],
        user_id: int,
        session_id: Optional[str] = None,
        timeout: Optional[float] = None,
        retries: Optional[int] = None,
    ) -> ToolResult:
        trace_id = uuid.uuid4().hex[:8]
        allowlist_res = self._enforce_allowlist(name, trace_id)
        if allowlist_res:
            return allowlist_res

        spec, fn = _tool_registry[name]
        ttl = TOOL_CACHE_TTLS.get(name, 0)
        cache_key = None
        if ttl and args is not None:
            cache_key = (name, _freeze_args(args))
            cached = _tool_cache.get(cache_key)
            if cached is not None:
                _record_cache_metric({"tool": name, "cache": "hit"})
                return cached
        _record_cache_metric({"tool": name, "cache": "miss"})

        t_start = time.time()
        success = False
        result: Any | None = None
        error_obj: Dict[str, Any] | None = None
        timeout_val = timeout if timeout is not None else TOOL_TIMEOUTS.get(name, self.default_timeout)
        retries_val = retries if retries is not None else self.default_retries

        attempt = 0
        while attempt <= retries_val:
            attempt_start = time.time()
            try:
                result = self._run_once(fn, args or {}, timeout=timeout_val)
                success = True
                break
            except concurrent.futures.TimeoutError:
                error_obj = {
                    "type": "TimeoutError",
                    "message": f"Tool '{name}' timed out after {timeout_val:.1f}s",
                    "trace_id": trace_id,
                    "where": name,
                }
                log.warning("Tool %s timeout (trace_id=%s, timeout=%.2fs)", name, trace_id, timeout_val)
            except Exception as e:  # noqa: BLE001
                error_obj = {
                    "type": e.__class__.__name__,
                    "message": str(e),
                    "trace_id": trace_id,
                    "where": name,
                }
                log.exception("Tool %s failed (trace_id=%s)", name, trace_id)
            finally:
                latency_ms = (time.time() - attempt_start) * 1000
                _audit_tool_call(user_id, session_id, name, args or {}, success, latency_ms)
            if success:
                break
            attempt += 1
            if attempt <= retries_val:
                backoff = 0.2 * math.pow(2, attempt - 1)
                time.sleep(backoff)

        ended_at = time.time()
        duration_ms = (ended_at - t_start) * 1000
        input_summary = _redact_args(args or {})
        tool_result = ToolResult(
            tool_name=name,
            ok=success,
            started_at=t_start,
            ended_at=ended_at,
            duration_ms=duration_ms,
            input_summary=input_summary,
            output=result if success else None,
            error=error_obj,
            trace_id=trace_id,
        )
        if success and cache_key:
            _tool_cache.set(cache_key, tool_result, ttl=ttl)
        return tool_result


_runner = ToolRunner()


def _load_allowlist() -> set[str]:
    """Load allowlist from environment or settings."""
    global _allowlist
    
    # Check environment variable first
    env_allowlist = os.getenv("JARVIS_TOOL_ALLOWLIST")
    if env_allowlist:
        _allowlist = set(env_allowlist.split(","))
        return _allowlist
    
    # Fall back to settings
    with get_conn() as conn:
        cursor = conn.execute("SELECT value FROM settings WHERE key = ?", ("tool_allowlist",))
        row = cursor.fetchone()
        if row:
            _allowlist = set(json.loads(row[0]))
        else:
            # Default allowlist - safe tools only
            _allowlist = {
                "system_info",
                "ping_host", 
                "list_processes",
                "find_process",
                "kill_process",  # High risk but used in agent
                "news_search",
                "web_search",
                "weather_now",
                "weather_forecast",
                "currency_convert",
                "time_now",
                "search_combined",
                "read_article",
            }
            # Save default to settings
            conn.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                ("tool_allowlist", json.dumps(list(_allowlist)))
            )
            conn.commit()
    
    return _allowlist


def register_tool(spec: ToolSpec, fn: Callable) -> None:
    """Register a tool in the registry."""
    _tool_registry[spec.name] = (spec, fn)


def get_spec(name: str) -> ToolSpec | None:
    """Return tool spec if registered."""
    entry = _tool_registry.get(name)
    return entry[0] if entry else None


def _freeze_args(args: Dict[str, Any]) -> str:
    """Create a stable, hashable representation of args."""
    try:
        return json.dumps(args, sort_keys=True, separators=(",", ":"))
    except TypeError:
        # Fallback for non-serializable args
        return repr(sorted(args.items()))


def _redact_args(args: Dict[str, Any]) -> Dict[str, Any]:
    """Redact sensitive fields from args."""
    redacted = {}
    sensitive_keys = {"key", "token", "password", "secret", "api_key", "auth"}
    
    for k, v in args.items():
        if any(sensitive in k.lower() for sensitive in sensitive_keys):
            redacted[k] = "[REDACTED]"
        else:
            redacted[k] = v
    return redacted


def _audit_tool_call(
    user_id: int,
    session_id: Optional[str],
    tool_name: str,
    args: Dict[str, Any],
    success: bool,
    latency_ms: float
) -> None:
    """Write audit record for tool call."""
    try:
        with get_conn() as conn:
            conn.execute("""
                INSERT INTO tool_audit (
                    timestamp, user_id, session_id, tool_name, 
                    args_redacted, success, latency_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                datetime.now(timezone.utc).isoformat(),
                user_id,
                session_id,
                tool_name,
                json.dumps(_redact_args(args)),
                1 if success else 0,
                latency_ms
            ))
            conn.commit()
    except Exception as e:
        # Log error but don't fail the tool call
        print(f"Failed to write audit log: {e}")


def _record_cache_metric(entry: Dict[str, Any]) -> None:
    """Send cache hit/miss info to orchestrator metrics if available."""
    try:
        from jarvis.agent_core.orchestrator import set_last_metric  # local import to avoid cycles
        set_last_metric("tool_cache", entry)
    except Exception:
        pass


def _make_envelope(result: ToolResult) -> Dict[str, Any]:
    envelope = {
        "ok": result.ok,
        "data": result.output,
        "error": result.error,
        "trace_id": result.trace_id,
        "tool": result.tool_name,
        "duration_ms": result.duration_ms,
    }
    # Backwards compatibility: surface dict data at top-level so existing callers using .get("items") still work.
    if result.ok and isinstance(result.output, dict):
        envelope.update(result.output)
    return envelope


def call_tool(
    name: str,
    args: Dict[str, Any],
    user_id: int,
    session_id: Optional[str] = None,
    timeout: Optional[float] = None,
    retries: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Call a tool safely through the registry.
    Returns an envelope containing ok/data/error/trace_id.
    """
    tool_result = _runner.run(name, args or {}, user_id, session_id=session_id, timeout=timeout, retries=retries)
    return _make_envelope(tool_result)


def safe_tool_call(tool_name: str, fn: Callable, *args, **kwargs) -> dict:
    """
    Safe wrapper for tool function calls.
    
    Returns:
        {"ok": bool, "data": any|None, "error": {type,message,trace_id,where}|None}
    """
    trace_id = uuid.uuid4().hex[:8]
    try:
        result = fn(*args, **kwargs)
        return {"ok": True, "data": result, "error": None}
    except Exception as e:
        error_info = {
            "type": e.__class__.__name__,
            "message": str(e),
            "trace_id": trace_id,
            "where": tool_name,
        }
        # Log the exception with trace_id and tool_name
        log.exception("Tool '%s' failed (trace_id=%s)", tool_name, trace_id)
        return {"ok": False, "data": None, "error": error_info}


def _reset_registry_for_tests() -> None:
    """Clear registry and allowlist (tests only)."""
    _tool_registry.clear()
    _allowlist.clear()
    _tool_cache.clear()
    global _runner
    _runner = ToolRunner()


# Initialize allowlist on import
_load_allowlist()

# Import adapters to register tools
try:
    from jarvis.agent_core import tool_adapters  # noqa: F401
except ImportError:
    pass
