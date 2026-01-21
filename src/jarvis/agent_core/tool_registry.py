"""
Safe tool registry with allowlist and audit logging.
"""

import json
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Callable, Optional
from datetime import datetime, timezone

from jarvis.db import get_conn


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


def call_tool(name: str, args: Dict[str, Any], user_id: int, session_id: Optional[str] = None) -> Any:
    """
    Call a tool safely through the registry.
    
    Args:
        name: Tool name
        args: Tool arguments
        user_id: User ID for audit
        session_id: Session ID for audit
        
    Returns:
        Tool result
        
    Raises:
        ValueError: If tool is not allowed or not registered
    """
    # Load allowlist if not loaded
    if not _allowlist:
        _load_allowlist()
    
    # Check if tool is allowed
    if name not in _allowlist:
        raise ValueError(f"Tool '{name}' is not in allowlist")
    
    # Check if tool is registered
    if name not in _tool_registry:
        raise ValueError(f"Tool '{name}' is not registered")
    
    spec, fn = _tool_registry[name]
    
    # Call tool and measure latency
    start_time = time.time()
    try:
        result = fn(**args)
        success = True
    except Exception as e:
        result = {"error": str(e)}
        success = False
        raise  # Re-raise to preserve error propagation
    
    finally:
        latency_ms = (time.time() - start_time) * 1000
        _audit_tool_call(user_id, session_id, name, args, success, latency_ms)
    
    return result


def _reset_registry_for_tests() -> None:
    """Clear registry and allowlist (tests only)."""
    _tool_registry.clear()
    _allowlist.clear()


# Initialize allowlist on import
_load_allowlist()

# Import adapters to register tools
try:
    from jarvis.agent_core import tool_adapters  # noqa: F401
except ImportError:
    pass
