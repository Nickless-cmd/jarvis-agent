"""
Safe tool registry with allowlist and audit logging.
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


def _make_envelope(ok: bool, data: Any, error: Optional[Dict[str, Any]], trace_id: str, tool_name: str) -> Dict[str, Any]:
    envelope = {"ok": ok, "data": data, "error": error, "trace_id": trace_id, "tool": tool_name}
    # Backwards compatibility: surface dict data at top-level so existing callers using .get("items") still work.
    if ok and isinstance(data, dict):
        envelope.update(data)
    return envelope


def call_tool(name: str, args: Dict[str, Any], user_id: int, session_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Call a tool safely through the registry.
    
    Args:
        name: Tool name
        args: Tool arguments
        user_id: User ID for audit
        session_id: Session ID for audit
        
    Returns:
        Envelope containing ok/data/error/trace_id
    """
    trace_id = uuid.uuid4().hex[:8]
    # Load allowlist if not loaded
    if not _allowlist:
        _load_allowlist()
    
    # Check if tool is allowed
    if name not in _allowlist:
        return _make_envelope(False, None, {
            "type": "ToolError",
            "message": f"Tool '{name}' is not in allowlist",
            "trace_id": trace_id,
            "where": name,
        }, trace_id, name)
    
    # Check if tool is registered
    if name not in _tool_registry:
        return _make_envelope(False, None, {
            "type": "ToolError",
            "message": f"Tool '{name}' is not registered",
            "trace_id": trace_id,
            "where": name,
        }, trace_id, name)
    
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

    # Call tool and measure latency
    start_time = time.time()
    success = False
    result = None
    error_obj = None
    try:
        result = fn(**args)
        success = True
        if cache_key:
            _tool_cache.set(cache_key, _make_envelope(True, result, None, trace_id, name), ttl=ttl)
    except Exception as e:
        err_type = e.__class__.__name__
        error_obj = {
            "type": err_type,
            "message": str(e),
            "trace_id": trace_id,
            "where": name,
        }
        success = False
        traceback.print_exc()
    finally:
        latency_ms = (time.time() - start_time) * 1000
        _audit_tool_call(user_id, session_id, name, args, success, latency_ms)
    if success:
        return _make_envelope(True, result, None, trace_id, name)
    return _make_envelope(False, None, error_obj, trace_id, name)


def safe_tool_call(tool_name: str, fn: Callable, *args, **kwargs) -> dict:
    """
    Safe wrapper for tool function calls.
    
    Returns:
        {"ok": bool, "data": any|None, "error": {type,message,trace_id,where}|None}
    """
    trace_id = uuid.uuid4().hex[:8]
    logger = None  # Assuming logger is available, but for now we'll use print or skip
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
        print(f"Tool '{tool_name}' failed (trace_id: {trace_id}): {e}")
        traceback.print_exc()
        return {"ok": False, "data": None, "error": error_info}


def _reset_registry_for_tests() -> None:
    """Clear registry and allowlist (tests only)."""
    _tool_registry.clear()
    _allowlist.clear()
    _tool_cache.clear()


# Initialize allowlist on import
_load_allowlist()

# Import adapters to register tools
try:
    from jarvis.agent_core import tool_adapters  # noqa: F401
except ImportError:
    pass
