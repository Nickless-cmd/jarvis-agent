import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from contextlib import contextmanager

from jarvis.personality import SYSTEM_PROMPT

DEFAULT_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "data")
DATA_DIR = os.path.abspath(os.getenv("JARVIS_DATA_DIR", DEFAULT_DATA_DIR))
DB_PATH = os.path.abspath(os.getenv("JARVIS_DB_PATH", os.path.join(DATA_DIR, "jarvis.db")))


def _ensure_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                email TEXT,
                full_name TEXT,
                city TEXT,
                phone TEXT,
                note TEXT,
                last_seen TEXT,
                token TEXT,
                token_expires_at TEXT,
                is_admin INTEGER DEFAULT 0,
                is_disabled INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            )
            """
        )
        _ensure_column(conn, "users", "is_admin", "INTEGER DEFAULT 0")
        _ensure_column(conn, "users", "is_disabled", "INTEGER DEFAULT 0")
        _ensure_column(conn, "users", "email", "TEXT")
        _ensure_column(conn, "users", "full_name", "TEXT")
        _ensure_column(conn, "users", "last_name", "TEXT")
        _ensure_column(conn, "users", "city", "TEXT")
        _ensure_column(conn, "users", "phone", "TEXT")
        _ensure_column(conn, "users", "note", "TEXT")
        _ensure_column(conn, "users", "last_seen", "TEXT")
        _ensure_column(conn, "users", "token_expires_at", "TEXT")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS login_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token TEXT NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                last_seen TEXT,
                ip TEXT,
                user_agent TEXT,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
            """
        )
        _ensure_column(conn, "login_sessions", "last_seen", "TEXT")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                name TEXT,
                last_city TEXT,
                mode TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
            """
        )
        _ensure_column(conn, "sessions", "last_city", "TEXT")
        _ensure_column(conn, "sessions", "mode", "TEXT")
        _ensure_column(conn, "sessions", "custom_prompt", "TEXT")
        _ensure_column(conn, "sessions", "updated_at", "TEXT")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                content_bytes INTEGER,
                created_at TEXT NOT NULL,
                FOREIGN KEY(session_id) REFERENCES sessions(id)
            )
            """
        )
        _ensure_column(conn, "messages", "content_bytes", "INTEGER")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS session_state (
                session_id TEXT PRIMARY KEY,
                last_news_json TEXT,
                updated_at TEXT NOT NULL
            )
            """
        )
        _ensure_column(conn, "session_state", "last_search_json", "TEXT")
        _ensure_column(conn, "session_state", "cv_state_json", "TEXT")
        _ensure_column(conn, "session_state", "story_state_json", "TEXT")
        _ensure_column(conn, "session_state", "reminder_state_json", "TEXT")
        _ensure_column(conn, "session_state", "ticket_state_json", "TEXT")
        _ensure_column(conn, "session_state", "process_state_json", "TEXT")
        _ensure_column(conn, "session_state", "quota_state_json", "TEXT")
        _ensure_column(conn, "session_state", "last_tool_json", "TEXT")
        _ensure_column(conn, "session_state", "pending_weather_json", "TEXT")
        _ensure_column(conn, "session_state", "pending_note_json", "TEXT")
        _ensure_column(conn, "session_state", "pending_reminder_json", "TEXT")
        _ensure_column(conn, "session_state", "pending_file_json", "TEXT")
        _ensure_column(conn, "session_state", "pending_image_preview_json", "TEXT")
        _ensure_column(conn, "session_state", "last_image_prompt_json", "TEXT")
        _ensure_column(conn, "session_state", "conversation_state_json", "TEXT")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT,
                content TEXT NOT NULL,
                expires_at TEXT,
                remind_at TEXT,
                warned_at TEXT,
                remind_enabled INTEGER DEFAULT 0,
                remind_stage INTEGER DEFAULT 0,
                updated_at TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
            """
        )
        _ensure_column(conn, "notes", "title", "TEXT")
        _ensure_column(conn, "notes", "expires_at", "TEXT")
        _ensure_column(conn, "notes", "remind_at", "TEXT")
        _ensure_column(conn, "notes", "warned_at", "TEXT")
        _ensure_column(conn, "notes", "remind_enabled", "INTEGER DEFAULT 0")
        _ensure_column(conn, "notes", "remind_stage", "INTEGER DEFAULT 0")
        _ensure_column(conn, "notes", "updated_at", "TEXT")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                original_name TEXT NOT NULL,
                stored_name TEXT NOT NULL,
                content_type TEXT,
                size_bytes INTEGER,
                expires_at TEXT,
                remind_at TEXT,
                warned_at TEXT,
                updated_at TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                remind_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                reminded_at TEXT,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                status TEXT NOT NULL,
                priority TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ticket_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER NOT NULL,
                user_id INTEGER,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(ticket_id) REFERENCES tickets(id),
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tool_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                user_id INTEGER,
                session_id TEXT,
                tool_name TEXT NOT NULL,
                args_redacted TEXT,
                success INTEGER NOT NULL,
                latency_ms REAL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS performance_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                user_id TEXT NOT NULL,
                session_id TEXT,
                memory_retrieval_ms REAL DEFAULT 0,
                tool_calls_total_ms REAL DEFAULT 0,
                llm_call_ms REAL DEFAULT 0,
                total_request_ms REAL DEFAULT 0,
                context_items TEXT,  -- JSON
                context_chars INTEGER DEFAULT 0,
                budget_exceeded INTEGER DEFAULT 0,
                items_trimmed INTEGER DEFAULT 0,
                tool_calls TEXT  -- JSON
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS download_tokens (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                file_path TEXT NOT NULL,
                max_downloads INTEGER NOT NULL,
                downloads INTEGER DEFAULT 0,
                delete_file INTEGER DEFAULT 0,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_quota (
                user_id INTEGER PRIMARY KEY,
                monthly_limit_mb INTEGER NOT NULL,
                credits_mb INTEGER NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                message TEXT,
                created_at TEXT,
                dismissed_at TEXT,
                created_utc TEXT,
                type TEXT,
                severity TEXT,
                title TEXT,
                body TEXT,
                meta_json TEXT,
                read INTEGER DEFAULT 0,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
            """
        )
        _ensure_column(conn, "events", "created_utc", "TEXT")
        _ensure_column(conn, "events", "type", "TEXT")
        _ensure_column(conn, "events", "severity", "TEXT")
        _ensure_column(conn, "events", "title", "TEXT")
        _ensure_column(conn, "events", "body", "TEXT")
        _ensure_column(conn, "events", "meta_json", "TEXT")
        _ensure_column(conn, "events", "read", "INTEGER DEFAULT 0")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tool_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                session_id TEXT,
                tool_name TEXT NOT NULL,
                args_redacted TEXT NOT NULL,
                success INTEGER NOT NULL,
                latency_ms REAL NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
            """
        )
        _ensure_setting(conn, "footer_text", "Jarvis v.1 - 2026")
        _ensure_setting(conn, "footer_support_url", "#")
        _ensure_setting(conn, "footer_contact_url", "#")
        _ensure_setting(conn, "register_enabled", "1")
        _ensure_setting(conn, "captcha_enabled", "1")
        _ensure_setting(conn, "system_prompt", SYSTEM_PROMPT)
        _ensure_setting(conn, "updates_log", "")
        _ensure_setting(conn, "quota_default_mb", "100")
        default_banner = json.dumps(
            [
                {
                    "text": "Driftstatus: Jarvis er online • Opdateringer kommer løbende.",
                    "ts": datetime.now(timezone.utc).isoformat(),
                }
            ]
        )
        _ensure_setting(conn, "banner_messages", default_banner)
        conn.commit()
        _ensure_bs_admin(conn)


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, col_type: str) -> None:
    cols = conn.execute(f"PRAGMA table_info({table})").fetchall()
    if any(c[1] == column for c in cols):
        return
    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")


def _ensure_bs_admin(conn: sqlite3.Connection) -> None:
    row = conn.execute(
        "SELECT id FROM users WHERE username = ?",
        ("bs",),
    ).fetchone()
    if not row:
        return
    conn.execute("UPDATE users SET is_admin = 1 WHERE username = ?", ("bs",))


def _ensure_setting(conn: sqlite3.Connection, key: str, value: str) -> None:
    row = conn.execute("SELECT key FROM settings WHERE key = ?", (key,)).fetchone()
    if row:
        return
    conn.execute("INSERT INTO settings (key, value) VALUES (?, ?)", (key, value))


def _connect():
    conn = sqlite3.connect(DB_PATH, timeout=5.0, isolation_level=None)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
    except Exception:
        # Best-effort pragmas; ignore if not supported
        pass
    return conn


@contextmanager
def get_conn():
    _ensure_db()
    conn = _connect()
    try:
        yield conn
    finally:
        conn.close()


def log_login_session(
    user_id: int,
    token: str,
    created_at: str,
    expires_at: str,
    ip: str | None = None,
    user_agent: str | None = None,
    last_seen: str | None = None,
) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO login_sessions (user_id, token, created_at, expires_at, last_seen, ip, user_agent) VALUES (?,?,?,?,?,?,?)",
            (user_id, token, created_at, expires_at, last_seen, ip, user_agent),
        )
        conn.commit()


def update_login_session_activity(token: str, last_seen: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE login_sessions SET last_seen = ? WHERE token = ?",
            (last_seen, token),
        )
        conn.commit()


def add_event(user_id: int, message: str) -> str:
    # Truncate message to max 8k chars for safety
    message = (message or "").strip()[:8000]
    event_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO events (id, user_id, message, created_at) VALUES (?, ?, ?, ?)",
            (event_id, user_id, message, created_at),
        )
        conn.commit()
    return event_id


def list_events(user_id: int, since_id: str = None) -> list[dict]:
    query = "SELECT id, message, created_at FROM events WHERE user_id = ? AND dismissed_at IS NULL"
    params = [user_id]
    if since_id:
        query += " AND id > ?"
        params.append(since_id)
    query += " ORDER BY created_at DESC"
    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
    return [{"id": row[0], "message": row[1], "created_at": row[2]} for row in rows]


def dismiss_event(user_id: int, event_id: str) -> bool:
    dismissed_at = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        cursor = conn.execute(
            "UPDATE events SET dismissed_at = ? WHERE id = ? AND user_id = ? AND dismissed_at IS NULL",
            (dismissed_at, event_id, user_id),
        )
        conn.commit()
        return cursor.rowcount > 0
