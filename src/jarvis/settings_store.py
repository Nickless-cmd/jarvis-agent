from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional

from jarvis.db import get_conn

TABLE_NAME = "settings"


def _ensure_table() -> None:
    """Ensure settings table exists with expected columns."""
    with get_conn() as conn:
        conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
                key TEXT PRIMARY KEY,
                value_json TEXT,
                scope TEXT,
                updated_at TEXT
            )
            """
        )
        # Backwards compatibility: older schema may have value column
        cols = conn.execute(f"PRAGMA table_info({TABLE_NAME})").fetchall()
        names = {c[1] for c in cols}
        if "value_json" not in names:
            conn.execute(f"ALTER TABLE {TABLE_NAME} ADD COLUMN value_json TEXT")
        if "scope" not in names:
            conn.execute(f"ALTER TABLE {TABLE_NAME} ADD COLUMN scope TEXT")
        if "updated_at" not in names:
            conn.execute(f"ALTER TABLE {TABLE_NAME} ADD COLUMN updated_at TEXT")
        conn.commit()


def set_setting(key: str, value: Any, scope: str = "public") -> None:
    """Upsert a setting value with scope."""
    _ensure_table()
    payload = json.dumps(value)
    ts = time.time()
    with get_conn() as conn:
        conn.execute(
            f"""
            INSERT INTO {TABLE_NAME} (key, value_json, scope, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value_json = excluded.value_json,
                                          scope = excluded.scope,
                                          updated_at = excluded.updated_at
            """,
            (key, payload, scope, ts),
        )
        conn.commit()


def get_setting(key: str, default: Any = None) -> Any:
    """Get setting value or default."""
    _ensure_table()
    with get_conn() as conn:
        row = conn.execute(
            f"SELECT value_json, scope FROM {TABLE_NAME} WHERE key = ?",
            (key,),
        ).fetchone()
    if not row:
        return default
    try:
        return json.loads(row["value_json"]) if row["value_json"] is not None else default
    except Exception:
        return default


def list_settings(scope: Optional[str] = None) -> List[Dict[str, Any]]:
    """List settings, optionally filtered by scope."""
    _ensure_table()
    with get_conn() as conn:
        if scope:
            rows = conn.execute(
                f"SELECT key, value_json, scope, updated_at FROM {TABLE_NAME} WHERE scope = ? ORDER BY key",
                (scope,),
            ).fetchall()
        else:
            rows = conn.execute(
                f"SELECT key, value_json, scope, updated_at FROM {TABLE_NAME} ORDER BY key"
            ).fetchall()
    result = []
    for row in rows:
        try:
            val = json.loads(row["value_json"]) if row["value_json"] else None
        except Exception:
            val = None
        result.append(
            {
                "key": row["key"],
                "value": val,
                "scope": row["scope"] or "public",
                "updated_at": row["updated_at"],
            }
        )
    return result


def reset_for_tests() -> None:
    """Clear settings table for isolation in tests."""
    _ensure_table()
    with get_conn() as conn:
        conn.execute(f"DELETE FROM {TABLE_NAME}")
        conn.commit()
