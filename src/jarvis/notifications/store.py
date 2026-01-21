"""SQLite-backed notification/event store."""

from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

import jarvis.db as db
from jarvis.db import get_conn


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
    _sync_db_path_from_env()
    _ensure_table()
    meta_json = json.dumps(meta or {}, ensure_ascii=False)
    created = datetime.now(timezone.utc).isoformat()
    body = _truncate_body(body)
    event_id = str(int(time.time() * 1000)) + "-" + uuid.uuid4().hex
    with get_conn() as conn:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(events)").fetchall()}
        data = {
            "id": event_id,
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
        conn.execute(
            f"INSERT INTO events ({col_clause}) VALUES ({placeholders})",
            payload,
        )
        conn.commit()
        return event_id


def list_events(user_id: int, since_id: int | None = None, limit: int = 50) -> List[Dict[str, Any]]:
    """List events for a user in ascending id order."""
    _sync_db_path_from_env()
    query = "SELECT id, created_utc, type, severity, title, body, meta_json, read FROM events WHERE user_id = ?"
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
                "read": bool(row[7]) if len(row) > 7 else False,
            }
        )
    return events


def mark_read(user_id: int, event_id: int) -> bool:
    """Mark an event as read."""
    _sync_db_path_from_env()
    with get_conn() as conn:
        cur = conn.execute("UPDATE events SET read = 1 WHERE id = ? AND user_id = ?", (event_id, user_id))
        conn.commit()
        return cur.rowcount > 0


# Notification aliases for the event functions
def add_notification(user_id: int, level: str, title: str, body: str, meta: Dict[str, Any] | None = None) -> int | str:
    """Add a notification (alias for add_event)."""
    return add_event(user_id, "notification", title, body, level, meta)


def list_notifications(user_id: int, limit: int = 50, since_id: int | None = None) -> List[Dict[str, Any]]:
    """List notifications for a user (alias for list_events, filtered to notifications)."""
    events = list_events(user_id, since_id, limit)
    notifications = []
    for e in events:
        if e.get("type") == "notification":
            notifications.append({
                "id": e["id"],
                "created_at": e["created_utc"],
                "level": e["severity"],
                "title": e["title"],
                "body": e["body"],
                "meta": e["meta"],
                "read": e["read"],
            })
    return notifications


def mark_notification_read(user_id: int, notification_id: int) -> bool:
    """Mark a notification as read (alias for mark_read)."""
    return mark_read(user_id, notification_id)


def get_unread_notifications_count(user_id: int) -> int:
    """Get count of unread notifications for a user."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM events WHERE user_id = ? AND read = 0",
            (user_id,),
        ).fetchone()
        return row[0] if row else 0


def mark_all_notifications_read(user_id: int) -> None:
    """Mark all notifications as read for a user."""
    with get_conn() as conn:
        conn.execute(
            "UPDATE events SET read = 1 WHERE user_id = ? AND read = 0",
            (user_id,),
        )
        conn.commit()


def _ensure_table() -> None:
    """Create events table if it does not exist (idempotent)."""
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                created_utc TEXT NOT NULL,
                type TEXT NOT NULL,
                severity TEXT NOT NULL,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                meta_json TEXT,
                read INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        conn.commit()


def _sync_db_path_from_env() -> None:
    """Ensure db module picks up JARVIS_DB_PATH for tests/dev overrides."""
    env_db = os.getenv("JARVIS_DB_PATH")
    if env_db:
        db.DB_PATH = os.path.abspath(env_db)
