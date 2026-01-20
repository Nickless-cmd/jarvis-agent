import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from jarvis.db import get_conn

BASE_DIR = Path(__file__).resolve().parent.parent
WORKSPACE_ROOT = (BASE_DIR / "data" / "workspaces").resolve()
UPLOAD_DIR_NAME = "uploads"

EXPIRY_DAYS = 30
WARN_HOURS = 24


def _safe_user_dir(user_id: str) -> Path:
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in user_id)
    return (WORKSPACE_ROOT / safe).resolve()


def ensure_user_dir(user_id: str) -> Path:
    path = _safe_user_dir(user_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def safe_path(user_id: str, rel_path: str) -> Path:
    base = ensure_user_dir(user_id)
    rel = rel_path.lstrip("/").replace("\\", "/")
    full = (base / rel).resolve()
    if not str(full).startswith(str(base)):
        raise ValueError("Unsafe path")
    return full


def write_file(user_id: str, rel_path: str, content: str) -> Path:
    full = safe_path(user_id, rel_path)
    full.parent.mkdir(parents=True, exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(content)
    return full


def make_dir(user_id: str, rel_path: str) -> Path:
    full = safe_path(user_id, rel_path)
    full.mkdir(parents=True, exist_ok=True)
    return full


def list_files(user_id: str) -> list[str]:
    base = ensure_user_dir(user_id)
    items = []
    for root, _, files in os.walk(base):
        for name in files:
            full = Path(root) / name
            rel = full.relative_to(base)
            items.append(str(rel))
    return sorted(items)


def _compute_expiry(now: datetime) -> tuple[str, str]:
    expires = now + timedelta(days=EXPIRY_DAYS)
    remind = expires - timedelta(hours=WARN_HOURS)
    return expires.isoformat(), remind.isoformat()


def _sanitize_filename(name: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in name)
    return safe or "upload"


def save_upload(user_id: int, user_key: str, original_name: str, content_type: str | None, data: bytes) -> dict:
    user_dir = ensure_user_dir(user_key)
    uploads_dir = (user_dir / UPLOAD_DIR_NAME).resolve()
    uploads_dir.mkdir(parents=True, exist_ok=True)
    safe_name = _sanitize_filename(original_name)
    stored_name = f"{uuid.uuid4().hex}_{safe_name}"
    path = (uploads_dir / stored_name).resolve()
    if not str(path).startswith(str(uploads_dir)):
        raise ValueError("Unsafe upload path")
    with open(path, "wb") as f:
        f.write(data)
    now = datetime.now(timezone.utc)
    expires_at, remind_at = _compute_expiry(now)
    size_bytes = len(data)
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO user_files (user_id, original_name, stored_name, content_type, size_bytes, expires_at, remind_at, warned_at, updated_at, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                user_id,
                original_name,
                stored_name,
                content_type,
                size_bytes,
                expires_at,
                remind_at,
                None,
                now.isoformat(),
                now.isoformat(),
            ),
        )
        row = conn.execute("SELECT last_insert_rowid() as id").fetchone()
        conn.commit()
    return {
        "id": row["id"],
        "original_name": original_name,
        "stored_name": stored_name,
        "content_type": content_type,
        "size_bytes": size_bytes,
        "created_at": now.isoformat(),
        "expires_at": expires_at,
    }


def list_uploads(user_id: int, limit: int = 50) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, original_name, stored_name, content_type, size_bytes, created_at, expires_at "
            "FROM user_files WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def find_upload_by_name(user_id: int, original_name: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, original_name, stored_name FROM user_files WHERE user_id = ? AND original_name = ? "
            "ORDER BY id DESC LIMIT 1",
            (user_id, original_name),
        ).fetchone()
    return dict(row) if row else None


def delete_uploads_by_name(user_id: int, user_key: str, original_name: str) -> int:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, stored_name FROM user_files WHERE user_id = ? AND original_name = ?",
            (user_id, original_name),
        ).fetchall()
        if not rows:
            return 0
        conn.execute(
            "DELETE FROM user_files WHERE user_id = ? AND original_name = ?",
            (user_id, original_name),
        )
        conn.commit()
    removed = 0
    for r in rows:
        try:
            path = safe_path(user_key, f"{UPLOAD_DIR_NAME}/{r['stored_name']}")
            if path.exists():
                path.unlink()
        except Exception:
            pass
        removed += 1
    return removed


def delete_uploads_by_ext(user_id: int, user_key: str, ext: str) -> int:
    ext = ext.lower().lstrip(".")
    if not ext:
        return 0
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, stored_name, original_name FROM user_files WHERE user_id = ?",
            (user_id,),
        ).fetchall()
        if not rows:
            return 0
        targets = [r for r in rows if str(r["original_name"]).lower().endswith(f".{ext}")]
        if not targets:
            return 0
        ids = [r["id"] for r in targets]
        placeholders = ",".join("?" for _ in ids)
        conn.execute(f"DELETE FROM user_files WHERE id IN ({placeholders})", ids)
        conn.commit()
    removed = 0
    for r in targets:
        try:
            path = safe_path(user_key, f"{UPLOAD_DIR_NAME}/{r['stored_name']}")
            if path.exists():
                path.unlink()
        except Exception:
            pass
        removed += 1
    return removed


def get_upload(user_id: int, file_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, original_name, stored_name, content_type, size_bytes, created_at, expires_at "
            "FROM user_files WHERE user_id = ? AND id = ?",
            (user_id, file_id),
        ).fetchone()
    return dict(row) if row else None


def delete_upload(user_id: int, user_key: str, file_id: int) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT stored_name FROM user_files WHERE user_id = ? AND id = ?",
            (user_id, file_id),
        ).fetchone()
        if not row:
            return False
        conn.execute("DELETE FROM user_files WHERE user_id = ? AND id = ?", (user_id, file_id))
        conn.commit()
    try:
        path = safe_path(user_key, f"{UPLOAD_DIR_NAME}/{row['stored_name']}")
        if path.exists():
            path.unlink()
    except Exception:
        pass
    return True


def keep_upload(user_id: int, file_id: int) -> bool:
    now = datetime.now(timezone.utc)
    expires_at, remind_at = _compute_expiry(now)
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE user_files SET expires_at = ?, remind_at = ?, warned_at = NULL, updated_at = ? WHERE user_id = ? AND id = ?",
            (expires_at, remind_at, now.isoformat(), user_id, file_id),
        )
        conn.commit()
        return cur.rowcount > 0


def list_expiring_uploads(user_id: int) -> list[dict]:
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, original_name, expires_at FROM user_files WHERE user_id = ? AND remind_at <= ? AND expires_at > ?",
            (user_id, now, now),
        ).fetchall()
    return [dict(r) for r in rows]


def purge_expired_uploads(user_id: int, user_key: str) -> int:
    now_dt = datetime.now(timezone.utc)
    now = now_dt.isoformat()
    with get_conn() as conn:
        rows_missing = conn.execute(
            "SELECT id, created_at FROM user_files WHERE user_id = ? AND (expires_at IS NULL OR expires_at = '')",
            (user_id,),
        ).fetchall()
        for r in rows_missing:
            try:
                created = datetime.fromisoformat(r["created_at"])
            except Exception:
                created = now_dt
            expires_at, remind_at = _compute_expiry(created)
            conn.execute(
                "UPDATE user_files SET expires_at = ?, remind_at = ?, updated_at = ? WHERE id = ? AND user_id = ?",
                (expires_at, remind_at, now, r["id"], user_id),
            )
        rows = conn.execute(
            "SELECT id, stored_name FROM user_files WHERE user_id = ? AND expires_at IS NOT NULL AND expires_at <= ?",
            (user_id, now),
        ).fetchall()
        conn.execute(
            "DELETE FROM user_files WHERE user_id = ? AND expires_at IS NOT NULL AND expires_at <= ?",
            (user_id, now),
        )
        conn.commit()
    removed = 0
    for r in rows:
        try:
            path = safe_path(user_key, f"{UPLOAD_DIR_NAME}/{r['stored_name']}")
            if path.exists():
                path.unlink()
        except Exception:
            pass
        removed += 1
    return removed


def read_upload_text(user_id: int, user_key: str, file_id: int, max_chars: int = 8000) -> dict | None:
    info = get_upload(user_id, file_id)
    if not info:
        return None
    ctype = (info.get("content_type") or "").lower()
    if "text" not in ctype and not info["original_name"].lower().endswith((".txt", ".md")):
        return {"error": "UNSUPPORTED_TYPE", "detail": "Kan kun analysere tekstfiler."}
    path = safe_path(user_key, f"{UPLOAD_DIR_NAME}/{info['stored_name']}")
    if not path.exists():
        return {"error": "NOT_FOUND", "detail": "Filen findes ikke."}
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return {"error": "READ_FAILED", "detail": "Kunne ikke laese filen."}
    text = text.strip()
    if len(text) > max_chars:
        text = text[:max_chars].rstrip() + "..."
    return {"id": info["id"], "name": info["original_name"], "text": text}


def save_generated_text(
    user_id: int,
    user_key: str,
    filename: str,
    text: str,
    content_type: str = "text/plain",
) -> dict:
    data = text.encode("utf-8")
    return save_upload(user_id, user_key, filename, content_type, data)


def create_download_token(
    user_id: int,
    file_path: str,
    delete_file: bool = False,
    max_downloads: int = 1,
    expires_minutes: int = 1440,
) -> str:
    token = uuid.uuid4().hex
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=expires_minutes)
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO download_tokens (token, user_id, file_path, max_downloads, downloads, delete_file, expires_at, created_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (
                token,
                user_id,
                file_path,
                max_downloads,
                0,
                1 if delete_file else 0,
                expires_at.isoformat(),
                now.isoformat(),
            ),
        )
        conn.commit()
    return token


def get_download_token(token: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT token, user_id, file_path, max_downloads, downloads, delete_file, expires_at "
            "FROM download_tokens WHERE token = ?",
            (token,),
        ).fetchone()
    if not row:
        return None
    entry = dict(row)
    try:
        expires_at = datetime.fromisoformat(entry.get("expires_at", ""))
        if expires_at <= datetime.now(timezone.utc):
            with get_conn() as conn:
                conn.execute("DELETE FROM download_tokens WHERE token = ?", (token,))
                conn.commit()
            return None
    except Exception:
        pass
    return entry


def finalize_download(token: str, user_key: str) -> bool:
    now = datetime.now(timezone.utc)
    with get_conn() as conn:
        row = conn.execute(
            "SELECT token, user_id, file_path, max_downloads, downloads, delete_file, expires_at "
            "FROM download_tokens WHERE token = ?",
            (token,),
        ).fetchone()
        if not row:
            return False
        try:
            expires_at = datetime.fromisoformat(row["expires_at"])
        except Exception:
            expires_at = now
        if expires_at <= now:
            conn.execute("DELETE FROM download_tokens WHERE token = ?", (token,))
            conn.commit()
            return False
        downloads = int(row["downloads"] or 0) + 1
        max_downloads = int(row["max_downloads"] or 1)
        delete_file = bool(row["delete_file"])
        file_path = row["file_path"]
        if downloads >= max_downloads:
            conn.execute("DELETE FROM download_tokens WHERE token = ?", (token,))
            conn.commit()
            if delete_file:
                try:
                    path = safe_path(user_key, file_path)
                    if path.exists():
                        path.unlink()
                except Exception:
                    pass
                try:
                    if file_path.startswith(f"{UPLOAD_DIR_NAME}/"):
                        stored = file_path.split("/", 1)[1]
                        conn.execute(
                            "DELETE FROM user_files WHERE user_id = ? AND stored_name = ?",
                            (row["user_id"], stored),
                        )
                        conn.commit()
                except Exception:
                    pass
            return True
        conn.execute(
            "UPDATE download_tokens SET downloads = ? WHERE token = ?",
            (downloads, token),
        )
        conn.commit()
    return True


def list_download_tokens(user_id: int) -> list[dict]:
    now = datetime.now(timezone.utc)
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT token, file_path, expires_at, downloads, max_downloads "
            "FROM download_tokens WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
    items = []
    for r in rows:
        entry = dict(r)
        try:
            expires_at = datetime.fromisoformat(entry.get("expires_at", ""))
            if expires_at <= now:
                with get_conn() as conn:
                    conn.execute("DELETE FROM download_tokens WHERE token = ?", (entry["token"],))
                    conn.commit()
                continue
        except Exception:
            pass
        items.append(entry)
    return items


def delete_download_token(user_id: int, token: str) -> bool:
    with get_conn() as conn:
        cur = conn.execute(
            "DELETE FROM download_tokens WHERE user_id = ? AND token = ?",
            (user_id, token),
        )
        conn.commit()
    return cur.rowcount > 0


def delete_all_download_tokens(user_id: int) -> int:
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM download_tokens WHERE user_id = ?", (user_id,))
        conn.commit()
    return cur.rowcount
