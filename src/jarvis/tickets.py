from datetime import datetime, timezone

from jarvis.db import get_conn


def create_ticket(user_id: int, title: str, message: str, priority: str = "moderate") -> dict:
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO tickets (user_id, title, status, priority, created_at, updated_at) VALUES (?,?,?,?,?,?)",
            (user_id, title, "open", priority, now, now),
        )
        row = conn.execute("SELECT last_insert_rowid() as id").fetchone()
        ticket_id = row["id"]
        conn.execute(
            "INSERT INTO ticket_messages (ticket_id, user_id, role, content, created_at) VALUES (?,?,?,?,?)",
            (ticket_id, user_id, "user", message, now),
        )
        conn.commit()
    return {"id": ticket_id, "title": title, "status": "open", "priority": priority, "created_at": now}


def list_tickets(user_id: int) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, title, status, priority, updated_at FROM tickets WHERE user_id = ? ORDER BY updated_at DESC",
            (user_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_ticket(user_id: int, ticket_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, title, status, priority, created_at, updated_at FROM tickets WHERE id = ? AND user_id = ?",
            (ticket_id, user_id),
        ).fetchone()
        if not row:
            return None
        msgs = conn.execute(
            "SELECT role, content, created_at FROM ticket_messages WHERE ticket_id = ? ORDER BY id ASC",
            (ticket_id,),
        ).fetchall()
    result = dict(row)
    result["messages"] = [dict(m) for m in msgs]
    return result


def add_ticket_message(ticket_id: int, user_id: int | None, role: str, content: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO ticket_messages (ticket_id, user_id, role, content, created_at) VALUES (?,?,?,?,?)",
            (ticket_id, user_id, role, content, now),
        )
        conn.execute(
            "UPDATE tickets SET updated_at = ? WHERE id = ?",
            (now, ticket_id),
        )
        conn.commit()


def list_tickets_admin() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT t.id, t.title, t.status, t.priority, t.updated_at, u.username "
            "FROM tickets t JOIN users u ON t.user_id = u.id ORDER BY t.updated_at DESC",
        ).fetchall()
    return [dict(r) for r in rows]


def get_ticket_admin(ticket_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT t.id, t.title, t.status, t.priority, t.created_at, t.updated_at, u.username "
            "FROM tickets t JOIN users u ON t.user_id = u.id WHERE t.id = ?",
            (ticket_id,),
        ).fetchone()
        if not row:
            return None
        msgs = conn.execute(
            "SELECT role, content, created_at FROM ticket_messages WHERE ticket_id = ? ORDER BY id ASC",
            (ticket_id,),
        ).fetchall()
    result = dict(row)
    result["messages"] = [dict(m) for m in msgs]
    return result


def update_ticket_admin(ticket_id: int, status: str | None, priority: str | None) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        if status is not None:
            conn.execute("UPDATE tickets SET status = ? WHERE id = ?", (status, ticket_id))
        if priority is not None:
            conn.execute("UPDATE tickets SET priority = ? WHERE id = ?", (priority, ticket_id))
        conn.execute("UPDATE tickets SET updated_at = ? WHERE id = ?", (now, ticket_id))
        conn.commit()
