import uuid
from datetime import datetime, timezone

from jarvis.db import get_conn


DEFAULT_SESSION_PREFIX = "session-default"


def _default_session_id(user_id: int) -> str:
    return f"{DEFAULT_SESSION_PREFIX}-{user_id}"


def create_session(user_id: int, name: str | None = None) -> str:
    session_id = uuid.uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO sessions (id, user_id, name, last_city, mode, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
            (session_id, user_id, name, None, "balanced", now, now),
        )
        conn.commit()
    return session_id


def ensure_session(session_id: str, user_id: int, name: str | None = None) -> str:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM sessions WHERE id = ? AND user_id = ?",
            (session_id, user_id),
        ).fetchone()
        if row:
            return session_id

        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT INTO sessions (id, user_id, name, last_city, mode, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
            (session_id, user_id, name, None, "balanced", now, now),
        )
        conn.commit()
        return session_id


def ensure_default_session(user_id: int, name: str | None = None) -> str:
    """
    Deterministic, idempotent session for a user when no session_id is provided.
    Prevents duplicate sessions on concurrent requests.
    """
    default_id = _default_session_id(user_id)
    return ensure_session(default_id, user_id, name=name or "Default")


def list_sessions(user_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT s.id, s.name, s.last_city, s.mode, s.created_at, s.updated_at, "
            "(SELECT MAX(created_at) FROM messages m WHERE m.session_id = s.id) AS last_message_at, "
            "(SELECT COUNT(*) FROM messages m WHERE m.session_id = s.id) AS message_count, "
            "(SELECT content FROM messages m WHERE m.session_id = s.id ORDER BY id DESC LIMIT 1) AS last_message_preview "
            "FROM sessions s WHERE user_id = ? ORDER BY s.created_at DESC",
            (user_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def rename_session(session_id: str, user_id: int, name: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        conn.execute(
            "UPDATE sessions SET name = ?, updated_at = ? WHERE id = ? AND user_id = ?",
            (name, now, session_id, user_id),
        )
        conn.commit()


def delete_session(session_id: str, user_id: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM session_state WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM sessions WHERE id = ? AND user_id = ?", (session_id, user_id))
        conn.commit()


def session_belongs_to_user(session_id: str, user_id: int) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM sessions WHERE id = ? AND user_id = ?",
            (session_id, user_id),
        ).fetchone()
    return row is not None


def add_message(session_id: str, role: str, content: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    content_bytes = len(content.encode("utf-8")) if content else 0
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO messages (session_id, role, content, content_bytes, created_at) VALUES (?,?,?,?,?)",
            (session_id, role, content, content_bytes, now),
        )
        conn.execute(
            "UPDATE sessions SET updated_at = ? WHERE id = ?",
            (now, session_id),
        )
        conn.commit()


def get_recent_messages(session_id: str, limit: int = 8) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT role, content, created_at FROM messages WHERE session_id = ? ORDER BY id DESC LIMIT ?",
            (session_id, limit),
        ).fetchall()
    items = [dict(row) for row in rows]
    return list(reversed(items))


def get_all_messages(session_id: str) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT role, content, created_at FROM messages WHERE session_id = ? ORDER BY id ASC",
            (session_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_last_city(session_id: str) -> str | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT last_city FROM sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
    if not row:
        return None
    return row["last_city"]


def set_last_city(session_id: str, city: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        conn.execute(
            "UPDATE sessions SET last_city = ?, updated_at = ? WHERE id = ?",
            (city, now, session_id),
        )
        conn.commit()


def get_mode(session_id: str) -> str:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT mode FROM sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
    if not row or not row["mode"]:
        return "balanced"
    return row["mode"]


def set_mode(session_id: str, mode: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        conn.execute(
            "UPDATE sessions SET mode = ?, updated_at = ? WHERE id = ?",
            (mode, now, session_id),
        )
        conn.commit()


def get_custom_prompt(session_id: str) -> str | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT custom_prompt FROM sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
    if not row:
        return None
    return row["custom_prompt"]


def set_custom_prompt(session_id: str, prompt: str | None) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        conn.execute(
            "UPDATE sessions SET custom_prompt = ?, updated_at = ? WHERE id = ?",
            (prompt, now, session_id),
        )
        conn.commit()


def set_last_news(session_id: str, payload: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO session_state (session_id, last_news_json, updated_at) VALUES (?,?,?) "
            "ON CONFLICT(session_id) DO UPDATE SET last_news_json = excluded.last_news_json, updated_at = excluded.updated_at",
            (session_id, payload, now),
        )
        conn.commit()


def get_last_news(session_id: str) -> str | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT last_news_json FROM session_state WHERE session_id = ?",
            (session_id,),
        ).fetchone()
    if not row:
        return None
    return row["last_news_json"]


def set_last_search(session_id: str, payload: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO session_state (session_id, last_search_json, updated_at) VALUES (?,?,?) "
            "ON CONFLICT(session_id) DO UPDATE SET last_search_json = excluded.last_search_json, updated_at = excluded.updated_at",
            (session_id, payload, now),
        )
        conn.commit()


def get_last_search(session_id: str) -> str | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT last_search_json FROM session_state WHERE session_id = ?",
            (session_id,),
        ).fetchone()
    if not row:
        return None
    return row["last_search_json"]


def set_last_image_prompt(session_id: str, payload: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO session_state (session_id, last_image_prompt_json, updated_at) VALUES (?,?,?) "
            "ON CONFLICT(session_id) DO UPDATE SET last_image_prompt_json = excluded.last_image_prompt_json, updated_at = excluded.updated_at",
            (session_id, payload, now),
        )
        conn.commit()


def get_last_image_prompt(session_id: str) -> str | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT last_image_prompt_json FROM session_state WHERE session_id = ?",
            (session_id,),
        ).fetchone()
    if not row:
        return None
    return row["last_image_prompt_json"]


def set_conversation_state(session_id: str, payload: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO session_state (session_id, conversation_state_json, updated_at) VALUES (?,?,?) "
            "ON CONFLICT(session_id) DO UPDATE SET conversation_state_json = excluded.conversation_state_json, updated_at = excluded.updated_at",
            (session_id, payload, now),
        )
        conn.commit()


def get_conversation_state(session_id: str) -> str | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT conversation_state_json FROM session_state WHERE session_id = ?",
            (session_id,),
        ).fetchone()
    if not row:
        return None
    return row["conversation_state_json"]


def set_last_tool(session_id: str, payload: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO session_state (session_id, last_tool_json, updated_at) VALUES (?,?,?) "
            "ON CONFLICT(session_id) DO UPDATE SET last_tool_json = excluded.last_tool_json, updated_at = excluded.updated_at",
            (session_id, payload, now),
        )
        conn.commit()


def get_last_tool(session_id: str) -> str | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT last_tool_json FROM session_state WHERE session_id = ?",
            (session_id,),
        ).fetchone()
    if not row:
        return None
    return row["last_tool_json"]


def set_pending_weather(session_id: str, payload: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO session_state (session_id, pending_weather_json, updated_at) VALUES (?,?,?) "
            "ON CONFLICT(session_id) DO UPDATE SET pending_weather_json = excluded.pending_weather_json, updated_at = excluded.updated_at",
            (session_id, payload, now),
        )
        conn.commit()


def get_pending_weather(session_id: str) -> str | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT pending_weather_json FROM session_state WHERE session_id = ?",
            (session_id,),
        ).fetchone()
    if not row:
        return None
    return row["pending_weather_json"]


def clear_pending_weather(session_id: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE session_state SET pending_weather_json = NULL WHERE session_id = ?",
            (session_id,),
        )
        conn.commit()


def set_pending_note(session_id: str, payload: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO session_state (session_id, pending_note_json, updated_at) VALUES (?,?,?) "
            "ON CONFLICT(session_id) DO UPDATE SET pending_note_json = excluded.pending_note_json, updated_at = excluded.updated_at",
            (session_id, payload, now),
        )
        conn.commit()


def get_pending_note(session_id: str) -> str | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT pending_note_json FROM session_state WHERE session_id = ?",
            (session_id,),
        ).fetchone()
    if not row:
        return None
    return row["pending_note_json"]


def clear_pending_note(session_id: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE session_state SET pending_note_json = NULL WHERE session_id = ?",
            (session_id,),
        )
        conn.commit()


def set_pending_reminder(session_id: str, payload: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO session_state (session_id, pending_reminder_json, updated_at) VALUES (?,?,?) "
            "ON CONFLICT(session_id) DO UPDATE SET pending_reminder_json = excluded.pending_reminder_json, updated_at = excluded.updated_at",
            (session_id, payload, now),
        )
        conn.commit()


def get_pending_reminder(session_id: str) -> str | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT pending_reminder_json FROM session_state WHERE session_id = ?",
            (session_id,),
        ).fetchone()
    if not row:
        return None
    return row["pending_reminder_json"]


def clear_pending_reminder(session_id: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE session_state SET pending_reminder_json = NULL WHERE session_id = ?",
            (session_id,),
        )
        conn.commit()


def set_pending_file(session_id: str, payload: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO session_state (session_id, pending_file_json, updated_at) VALUES (?,?,?) "
            "ON CONFLICT(session_id) DO UPDATE SET pending_file_json = excluded.pending_file_json, updated_at = excluded.updated_at",
            (session_id, payload, now),
        )
        conn.commit()


def get_pending_file(session_id: str) -> str | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT pending_file_json FROM session_state WHERE session_id = ?",
            (session_id,),
        ).fetchone()
    if not row:
        return None
    return row["pending_file_json"]


def clear_pending_file(session_id: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE session_state SET pending_file_json = NULL WHERE session_id = ?",
            (session_id,),
        )
        conn.commit()


def set_pending_image_preview(session_id: str, payload: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO session_state (session_id, pending_image_preview_json, updated_at) VALUES (?,?,?) "
            "ON CONFLICT(session_id) DO UPDATE SET pending_image_preview_json = excluded.pending_image_preview_json, updated_at = excluded.updated_at",
            (session_id, payload, now),
        )
        conn.commit()


def get_pending_image_preview(session_id: str) -> str | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT pending_image_preview_json FROM session_state WHERE session_id = ?",
            (session_id,),
        ).fetchone()
    if not row:
        return None
    return row["pending_image_preview_json"]


def clear_pending_image_preview(session_id: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE session_state SET pending_image_preview_json = NULL WHERE session_id = ?",
            (session_id,),
        )
        conn.commit()


def set_reminder_state(session_id: str, payload: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO session_state (session_id, reminder_state_json, updated_at) VALUES (?,?,?) "
            "ON CONFLICT(session_id) DO UPDATE SET reminder_state_json = excluded.reminder_state_json, updated_at = excluded.updated_at",
            (session_id, payload, now),
        )
        conn.commit()


def get_reminder_state(session_id: str) -> str | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT reminder_state_json FROM session_state WHERE session_id = ?",
            (session_id,),
        ).fetchone()
    if not row:
        return None
    return row["reminder_state_json"]


def set_ticket_state(session_id: str, payload: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO session_state (session_id, ticket_state_json, updated_at) VALUES (?,?,?) "
            "ON CONFLICT(session_id) DO UPDATE SET ticket_state_json = excluded.ticket_state_json, updated_at = excluded.updated_at",
            (session_id, payload, now),
        )
        conn.commit()


def get_ticket_state(session_id: str) -> str | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT ticket_state_json FROM session_state WHERE session_id = ?",
            (session_id,),
        ).fetchone()
    if not row:
        return None
    return row["ticket_state_json"]


def set_process_state(session_id: str, payload: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO session_state (session_id, process_state_json, updated_at) VALUES (?,?,?) "
            "ON CONFLICT(session_id) DO UPDATE SET process_state_json = excluded.process_state_json, updated_at = excluded.updated_at",
            (session_id, payload, now),
        )
        conn.commit()


def get_process_state(session_id: str) -> str | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT process_state_json FROM session_state WHERE session_id = ?",
            (session_id,),
        ).fetchone()
    if not row:
        return None
    return row["process_state_json"]


def set_quota_state(session_id: str, payload: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO session_state (session_id, quota_state_json, updated_at) VALUES (?,?,?) "
            "ON CONFLICT(session_id) DO UPDATE SET quota_state_json = excluded.quota_state_json, updated_at = excluded.updated_at",
            (session_id, payload, now),
        )
        conn.commit()


def get_quota_state(session_id: str) -> str | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT quota_state_json FROM session_state WHERE session_id = ?",
            (session_id,),
        ).fetchone()
    if not row:
        return None
    return row["quota_state_json"]


def set_cv_state(session_id: str, payload: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO session_state (session_id, cv_state_json, updated_at) VALUES (?,?,?) "
            "ON CONFLICT(session_id) DO UPDATE SET cv_state_json = excluded.cv_state_json, updated_at = excluded.updated_at",
            (session_id, payload, now),
        )
        conn.commit()


def get_cv_state(session_id: str) -> str | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT cv_state_json FROM session_state WHERE session_id = ?",
            (session_id,),
        ).fetchone()
    if not row:
        return None
    return row["cv_state_json"]


def set_story_state(session_id: str, payload: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO session_state (session_id, story_state_json, updated_at) VALUES (?,?,?) "
            "ON CONFLICT(session_id) DO UPDATE SET story_state_json = excluded.story_state_json, updated_at = excluded.updated_at",
            (session_id, payload, now),
        )
        conn.commit()


def get_story_state(session_id: str) -> str | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT story_state_json FROM session_state WHERE session_id = ?",
            (session_id,),
        ).fetchone()
    if not row:
        return None
    return row["story_state_json"]
