from datetime import datetime, timedelta, timezone

from jarvis.db import get_conn

EXPIRY_DAYS = 30
WARN_HOURS = 24


def _compute_expiry_from_created(created: datetime) -> tuple[str, str]:
    expires = created + timedelta(days=EXPIRY_DAYS)
    remind = expires - timedelta(hours=WARN_HOURS)
    return expires.isoformat(), remind.isoformat()


def _compute_remind_for_expires(expires: datetime) -> str:
    return (expires - timedelta(hours=WARN_HOURS)).isoformat()


def add_note(
    user_id: int,
    content: str,
    title: str | None = None,
    expires_at: str | None = None,
    remind_enabled: bool = False,
) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    clean_title = (title or "").strip()
    if not clean_title:
        words = content.split()
        clean_title = " ".join(words[:6]) if words else "Note"
    if expires_at:
        try:
            expires_dt = datetime.fromisoformat(expires_at)
        except Exception:
            created_dt = datetime.fromisoformat(now)
            expires_at, remind_at = _compute_expiry_from_created(created_dt)
        else:
            remind_at = _compute_remind_for_expires(expires_dt)
            expires_at = expires_dt.isoformat()
    else:
        created_dt = datetime.fromisoformat(now)
        expires_at, remind_at = _compute_expiry_from_created(created_dt)
    remind_enabled_val = 1 if remind_enabled else 0
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO notes (user_id, title, content, expires_at, remind_at, warned_at, updated_at, created_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (user_id, clean_title, content, expires_at, remind_at, None, now, now),
        )
        conn.execute(
            "UPDATE notes SET remind_enabled = ?, remind_stage = 0 WHERE id = last_insert_rowid()",
            (remind_enabled_val,),
        )
        conn.commit()
        row = conn.execute("SELECT last_insert_rowid() as id").fetchone()
    return {
        "id": row["id"],
        "title": clean_title,
        "content": content,
        "created_at": now,
        "expires_at": expires_at,
    }


def list_notes(user_id: int, limit: int = 20) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, title, content, created_at, expires_at, remind_at FROM notes WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
        results = []
        for r in rows:
            item = dict(r)
            if not item.get("expires_at"):
                try:
                    created = datetime.fromisoformat(item["created_at"])
                except Exception:
                    created = datetime.now(timezone.utc)
                expires_at, remind_at = _compute_expiry_from_created(created)
                conn.execute(
                    "UPDATE notes SET expires_at = ?, remind_at = ?, updated_at = ? WHERE id = ? AND user_id = ?",
                    (expires_at, remind_at, datetime.now(timezone.utc).isoformat(), item["id"], user_id),
                )
                item["expires_at"] = expires_at
                item["remind_at"] = remind_at
            results.append(item)
        conn.commit()
    return results


def list_notes_since(user_id: int, since_iso: str) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, title, content, created_at, expires_at, remind_at FROM notes "
            "WHERE user_id = ? AND created_at >= ? ORDER BY created_at DESC",
            (user_id, since_iso),
        ).fetchall()
    return [dict(r) for r in rows]


def delete_note(user_id: int, note_id: int) -> bool:
    with get_conn() as conn:
        cur = conn.execute(
            "DELETE FROM notes WHERE id = ? AND user_id = ?",
            (note_id, user_id),
        )
        conn.commit()
        return cur.rowcount > 0


def keep_note(user_id: int, note_id: int) -> bool:
    now = datetime.now(timezone.utc)
    expires_at, remind_at = _compute_expiry_from_created(now)
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE notes SET expires_at = ?, remind_at = ?, warned_at = NULL, updated_at = ?, remind_stage = 0 "
            "WHERE id = ? AND user_id = ?",
            (expires_at, remind_at, now.isoformat(), note_id, user_id),
        )
        conn.commit()
        return cur.rowcount > 0


def get_note(user_id: int, note_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, title, content, created_at, expires_at FROM notes WHERE id = ? AND user_id = ?",
            (note_id, user_id),
        ).fetchone()
    return dict(row) if row else None


def update_note_content(user_id: int, note_id: int, content: str) -> bool:
    now = datetime.now(timezone.utc).isoformat()
    clean = content.strip()
    if not clean:
        return False
    words = clean.split()
    title = " ".join(words[:6]) if words else "Note"
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE notes SET content = ?, title = ?, updated_at = ? WHERE id = ? AND user_id = ?",
            (clean, title, now, note_id, user_id),
        )
        conn.commit()
        return cur.rowcount > 0


def update_note_due(user_id: int, note_id: int, expires_at: str, remind_enabled: bool | None = None) -> bool:
    now = datetime.now(timezone.utc)
    try:
        expires_dt = datetime.fromisoformat(expires_at)
    except Exception:
        return False
    new_expires = expires_dt.isoformat()
    new_remind_at = _compute_remind_for_expires(expires_dt)
    with get_conn() as conn:
        if remind_enabled is None:
            cur = conn.execute(
                "UPDATE notes SET expires_at = ?, remind_at = ?, warned_at = NULL, updated_at = ?, remind_stage = 0 "
                "WHERE id = ? AND user_id = ?",
                (new_expires, new_remind_at, now.isoformat(), note_id, user_id),
            )
        else:
            cur = conn.execute(
                "UPDATE notes SET expires_at = ?, remind_at = ?, warned_at = NULL, updated_at = ?, remind_stage = 0, remind_enabled = ? "
                "WHERE id = ? AND user_id = ?",
                (new_expires, new_remind_at, now.isoformat(), 1 if remind_enabled else 0, note_id, user_id),
            )
        conn.commit()
        return cur.rowcount > 0


def set_note_remind(user_id: int, note_id: int, enabled: bool) -> bool:
    now = datetime.now(timezone.utc)
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE notes SET remind_enabled = ?, updated_at = ?, remind_stage = 0 WHERE id = ? AND user_id = ?",
            (1 if enabled else 0, now.isoformat(), note_id, user_id),
        )
        conn.commit()
        return cur.rowcount > 0


def list_due_note_reminders(user_id: int) -> list[dict]:
    now = datetime.now(timezone.utc)
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, title, content, expires_at, remind_stage FROM notes "
            "WHERE user_id = ? AND remind_enabled = 1 AND expires_at IS NOT NULL",
            (user_id,),
        ).fetchall()
    due = []
    for r in rows:
        try:
            expires_dt = datetime.fromisoformat(r["expires_at"])
        except Exception:
            continue
        hours_left = (expires_dt - now).total_seconds() / 3600
        stage = r["remind_stage"] or 0
        new_stage = stage
        if hours_left <= 2 and stage < 3:
            new_stage = 3
        elif hours_left <= 12 and stage < 2:
            new_stage = 2
        elif hours_left <= 24 and stage < 1:
            new_stage = 1
        if new_stage > stage:
            due.append(dict(r) | {"stage": new_stage})
    if due:
        with get_conn() as conn:
            for d in due:
                conn.execute(
                    "UPDATE notes SET remind_stage = ?, updated_at = ? WHERE id = ? AND user_id = ?",
                    (d["stage"], now.isoformat(), d["id"], user_id),
                )
            conn.commit()
    return due


def list_expiring_notes(user_id: int) -> list[dict]:
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, title, content, expires_at FROM notes WHERE user_id = ? AND remind_at <= ? AND expires_at > ?",
            (user_id, now, now),
        ).fetchall()
    return [dict(r) for r in rows]


def purge_expired_notes(user_id: int) -> int:
    now_dt = datetime.now(timezone.utc)
    now = now_dt.isoformat()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, created_at FROM notes WHERE user_id = ? AND (expires_at IS NULL OR expires_at = '')",
            (user_id,),
        ).fetchall()
        for r in rows:
            try:
                created = datetime.fromisoformat(r["created_at"])
            except Exception:
                created = now_dt
            expires_at, remind_at = _compute_expiry_from_created(created)
            conn.execute(
                "UPDATE notes SET expires_at = ?, remind_at = ?, updated_at = ? WHERE id = ? AND user_id = ?",
                (expires_at, remind_at, now, r["id"], user_id),
            )
        cur = conn.execute(
            "DELETE FROM notes WHERE user_id = ? AND expires_at IS NOT NULL AND expires_at <= ?",
            (user_id, now),
        )
        conn.commit()
        return cur.rowcount


def add_reminder(user_id: int, content: str, remind_at: str) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO reminders (user_id, content, remind_at, created_at) VALUES (?,?,?,?)",
            (user_id, content, remind_at, now),
        )
        conn.commit()
        row = conn.execute("SELECT last_insert_rowid() as id").fetchone()
    return {"id": row["id"], "content": content, "remind_at": remind_at}


def list_reminders(user_id: int, include_done: bool = False, limit: int = 20) -> list[dict]:
    with get_conn() as conn:
        if include_done:
            rows = conn.execute(
                "SELECT id, content, remind_at, created_at, reminded_at FROM reminders WHERE user_id = ? ORDER BY id DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, content, remind_at, created_at, reminded_at FROM reminders WHERE user_id = ? AND reminded_at IS NULL ORDER BY remind_at ASC LIMIT ?",
                (user_id, limit),
            ).fetchall()
    return [dict(r) for r in rows]


def get_due_reminders(user_id: int) -> list[dict]:
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, content, remind_at FROM reminders WHERE user_id = ? AND reminded_at IS NULL AND remind_at <= ? ORDER BY remind_at ASC",
            (user_id, now),
        ).fetchall()
    return [dict(r) for r in rows]


def mark_reminded(user_id: int, reminder_ids: list[int]) -> None:
    if not reminder_ids:
        return
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        conn.executemany(
            "UPDATE reminders SET reminded_at = ? WHERE user_id = ? AND id = ?",
            [(now, user_id, rid) for rid in reminder_ids],
        )
        conn.commit()
