from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class JarvisConfig:
    env: str
    test_mode: bool
    db_path: str
    event_backlog_maxlen: int
    tool_timeout_default: float
    tool_retries: int
    devkey: Optional[str]
    cookie_name: str
    cookie_secure: bool
    cookie_samesite: str
    cookie_ttl_seconds: int


def load_config() -> JarvisConfig:
    """Load configuration from environment at call time (runtime-safe)."""
    env = os.getenv("JARVIS_ENV", "dev")
    test_mode = os.getenv("JARVIS_TEST_MODE", "0") == "1"
    default_db = Path(__file__).resolve().parent.parent.parent / "data" / "jarvis.db"
    db_path = os.path.abspath(os.getenv("JARVIS_DB_PATH", str(default_db)))
    event_backlog_maxlen = int(os.getenv("JARVIS_EVENT_BACKLOG", "1000"))
    tool_timeout_default = float(os.getenv("JARVIS_TOOL_TIMEOUT", "30"))
    tool_retries = int(os.getenv("JARVIS_TOOL_RETRIES", "0"))
    devkey = os.getenv("JARVIS_DEVKEY", "devkey")
    cookie_name = os.getenv("JARVIS_COOKIE_NAME", "jarvis_token")
    cookie_secure = os.getenv("JARVIS_COOKIE_SECURE", "0") == "1"
    cookie_samesite = os.getenv("JARVIS_COOKIE_SAMESITE", "lax")
    cookie_ttl_seconds = int(os.getenv("JARVIS_COOKIE_TTL_SECONDS", str(24 * 3600)))

    return JarvisConfig(
        env=env,
        test_mode=test_mode,
        db_path=db_path,
        event_backlog_maxlen=event_backlog_maxlen,
        tool_timeout_default=tool_timeout_default,
        tool_retries=tool_retries,
        devkey=devkey,
        cookie_name=cookie_name,
        cookie_secure=cookie_secure,
        cookie_samesite=cookie_samesite,
        cookie_ttl_seconds=cookie_ttl_seconds,
    )


def is_test_mode() -> bool:
    """Helper for callers that only need the test flag."""
    return load_config().test_mode
