import sqlite3
from jarvis.db import get_db_path


def migrate():
    path = get_db_path()
    with sqlite3.connect(path) as conn:
        # Existing additive migrations
        try:
            conn.execute("ALTER TABLE sessions ADD COLUMN last_city TEXT")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE sessions ADD COLUMN mode TEXT")
        except Exception:
            pass

        # Notifications/events table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
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


if __name__ == "__main__":
    migrate()
