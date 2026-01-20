"""SQLite-backed notification/event store."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List

from jarvis.db import get_conn
import time
import uuid


def _truncate_body(body: str, limit: int = 8000) -> str:
    return (body or "").strip()[:limit]


def add_event(
    user_id: int,
    type: str,
    title: str,
    body: str,
    severity: str = "info",
    meta: Dict[str, Any] | None = None,
) -> int | str:
    """Insert a new event for a user and return its id."""
    meta_json = json.dumps(meta or {}, ensure_ascii=False)
    created = datetime.now(timezone.utc).isoformat()
    body = _truncate_body(body)
    with get_conn() as conn:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(events)").fetchall()}
        data = {
            "user_id": user_id,
            "created_utc": created,
            "created_at": created,
            "type": type or "generic",
            "severity": severity or "info",
            "title": title or "",
            "body": body,
            "message": body,
            "meta_json": meta_json,
            "read": 0,
        }
        insert_cols = [c for c in data.keys() if c in cols and data[c] is not None]
        placeholders = ", ".join("?" for _ in insert_cols)
        col_clause = ", ".join(insert_cols)
        payload = tuple(data[c] for c in insert_cols)
        try:
            cursor = conn.execute(
                f"INSERT INTO events ({col_clause}) VALUES ({placeholders})",
                payload,
            )
            conn.commit()
            return cursor.lastrowid
        except Exception:
            event_id = str(int(time.time() * 1000)) + "-" + uuid.uuid4().hex
            conn.execute(
                f"INSERT INTO events (id, {col_clause}) VALUES (?, {placeholders})",
                (event_id, *payload),
            )
            conn.commit()
            return event_id


def list_events(user_id: int, since_id: int | None = None, limit: int = 50) -> List[Dict[str, Any]]:
    """List events for a user in ascending id order."""
    query = "SELECT id, created_utc, type, severity, title, body, meta_json FROM events WHERE user_id = ?"
    params: list[Any] = [user_id]
    if since_id is not None:
        query += " AND id > ?"
        params.append(since_id)
    query += " ORDER BY id ASC LIMIT ?"
    params.append(max(1, min(limit, 200)))

    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()

    events: List[Dict[str, Any]] = []
    for row in rows:
        meta_payload = row[6] if len(row) > 6 else None
        meta = {}
        if meta_payload:
            try:
                meta = json.loads(meta_payload)
            except Exception:
                meta = {}
        events.append(
            {
                "id": row[0],
                "created_utc": row[1],
                "type": row[2],
                "severity": row[3],
                "title": row[4],
                "body": row[5],
                "meta": meta,
            }
        )
    return events


def mark_read(user_id: int, event_id: int) -> bool:
    """Mark an event as read."""
    with get_conn() as conn:
        cur = conn.execute("UPDATE events SET read = 1 WHERE id = ? AND user_id = ?", (event_id, user_id))
        conn.commit()
        return cur.rowcount > 0
