import hashlib
import hmac
import os
import uuid
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass

from jarvis.db import get_conn, update_login_session_activity

SESSION_TTL_HOURS = int(os.getenv("SESSION_TTL_HOURS", "24"))
SESSION_IDLE_MINUTES = int(os.getenv("SESSION_IDLE_MINUTES", "60"))
DEFAULT_API_KEY = "devkey"


def _hash_password(password: str, salt: bytes | None = None) -> str:
    if salt is None:
        salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120_000)
    return salt.hex() + ":" + digest.hex()


def _verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, digest_hex = stored.split(":", 1)
        salt = bytes.fromhex(salt_hex)
        candidate = _hash_password(password, salt)
        return hmac.compare_digest(candidate, stored)
    except Exception:
        return False


def verify_user_password(user_id: int, password: str) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT password_hash FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if not row:
            return False
        return _verify_password(password, row["password_hash"])


def register_user(
    username: str,
    password: str,
    is_admin: int = 0,
    email: str | None = None,
    full_name: str | None = None,
    last_name: str | None = None,
    city: str | None = None,
    phone: str | None = None,
    note: str | None = None,
) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    password_hash = _hash_password(password)
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO users (username, password_hash, email, full_name, last_name, city, phone, note, is_admin, is_disabled, created_at, last_seen) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (username, password_hash, email, full_name, last_name, city, phone, note, is_admin, 0, now, now),
        )
        conn.commit()
        row = conn.execute(
            "SELECT id, username, is_admin, is_disabled FROM users WHERE username = ?",
            (username,),
        ).fetchone()
    return {
        "id": row["id"],
        "username": row["username"],
        "is_admin": row["is_admin"],
        "is_disabled": row["is_disabled"],
    }


def login_user(username: str, password: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, password_hash, is_disabled FROM users WHERE username = ?",
            (username,),
        ).fetchone()
        if not row or not _verify_password(password, row["password_hash"]):
            return None
        if row["is_disabled"]:
            return {"disabled": True}

        token = uuid.uuid4().hex
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=SESSION_TTL_HOURS)
        conn.execute(
            "UPDATE users SET token = ?, token_expires_at = ?, last_seen = ? WHERE id = ?",
            (token, expires_at.isoformat(), now.isoformat(), row["id"]),
        )
        conn.commit()
        return {"token": token, "expires_at": expires_at.isoformat()}


def get_user_by_token(token: str | None) -> dict | None:
    if not token:
        return None
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, username, is_admin, is_disabled, token_expires_at, last_seen FROM users WHERE token = ?",
            (token,),
        ).fetchone()
        if not row:
            return None
        last_seen = row["last_seen"]
        if last_seen and not row["is_admin"]:
            try:
                if datetime.now(timezone.utc) - datetime.fromisoformat(last_seen) > timedelta(minutes=SESSION_IDLE_MINUTES):
                    conn.execute(
                        "UPDATE users SET token = NULL, token_expires_at = NULL WHERE id = ?",
                        (row["id"],),
                    )
                    conn.commit()
                    return None
            except ValueError:
                pass
        expires_at = row["token_expires_at"]
        if expires_at:
            try:
                if datetime.now(timezone.utc) >= datetime.fromisoformat(expires_at):
                    conn.execute(
                        "UPDATE users SET token = NULL, token_expires_at = NULL WHERE id = ?",
                        (row["id"],),
                    )
                    conn.commit()
                    return None
            except ValueError:
                pass
            now = datetime.now(timezone.utc)
            new_expires = now + timedelta(hours=SESSION_TTL_HOURS)
            conn.execute(
                "UPDATE users SET token_expires_at = ?, last_seen = ? WHERE id = ?",
                (new_expires.isoformat(), now.isoformat(), row["id"]),
            )
            conn.commit()
            update_login_session_activity(token, now.isoformat())
        else:
            now = datetime.now(timezone.utc)
            expires_at = now + timedelta(hours=SESSION_TTL_HOURS)
            conn.execute(
                "UPDATE users SET token_expires_at = ? WHERE id = ?",
                (expires_at.isoformat(), row["id"]),
            )
            conn.commit()
            update_login_session_activity(token, now.isoformat())
        return {
            "id": row["id"],
            "username": row["username"],
            "is_admin": row["is_admin"],
            "is_disabled": row["is_disabled"],
        }


def get_user_profile(username: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, username, email, full_name, last_name, city, phone, note, created_at, last_seen, is_admin FROM users WHERE username = ?",
            (username,),
        ).fetchone()
    return dict(row) if row else None


@dataclass
class AuthContext:
    user: dict | None
    is_authenticated: bool
    is_admin: bool
    token_source: str | None = None


def _auth_ok(authorization: str | None) -> bool:
    if not authorization:
        return False
    token = authorization.replace("Bearer", "", 1).strip()
    candidates = {
        DEFAULT_API_KEY,
        os.getenv("BEARER_TOKEN"),
        os.getenv("API_BEARER_TOKEN"),
    }
    candidates = {c for c in candidates if c}
    return token in candidates


def build_auth_context(
    authorization: str | None,
    x_user_token: str | None,
    cookie_token: str | None,
) -> AuthContext:
    """
    Central auth helper. Priority: devkey (admin) > cookie token.
    x_user_token is deprecated - use cookie jarvis_token instead.
    """
    if x_user_token:
        # Reject x_user_token - use cookie instead
        return AuthContext(user=None, is_authenticated=False, is_admin=False, token_source="rejected_x_user_token")
    
    if _auth_ok(authorization):
        user = get_or_create_default_user()
        user["is_admin"] = True
        return AuthContext(user=user, is_authenticated=True, is_admin=True, token_source="devkey")

    if cookie_token:
        user = get_user_by_token(cookie_token)
        if not user:
            return AuthContext(user=None, is_authenticated=False, is_admin=False, token_source="invalid")
        if user.get("is_disabled"):
            return AuthContext(user=user, is_authenticated=False, is_admin=False, token_source="disabled")
        return AuthContext(
            user=user,
            is_authenticated=True,
            is_admin=bool(user.get("is_admin")),
            token_source="cookie",
        )
    return AuthContext(user=None, is_authenticated=False, is_admin=False, token_source=None)


def get_or_create_default_user() -> dict:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, username, is_admin, is_disabled FROM users WHERE username = ?",
            ("default",),
        ).fetchone()
        if row:
            return {"id": row["id"], "username": row["username"], "is_admin": row["is_admin"], "is_disabled": row["is_disabled"]}

        now = datetime.now(timezone.utc).isoformat()
        placeholder_hash = _hash_password(uuid.uuid4().hex)
        conn.execute(
            "INSERT INTO users (username, password_hash, is_admin, is_disabled, created_at) VALUES (?,?,?,?,?)",
            ("default", placeholder_hash, 0, 0, now),
        )
        conn.commit()
        row = conn.execute(
            "SELECT id, username, is_admin, is_disabled FROM users WHERE username = ?",
            ("default",),
        ).fetchone()
        return {
            "id": row["id"],
            "username": row["username"],
            "is_admin": row["is_admin"],
            "is_disabled": row["is_disabled"],
        }


def ensure_demo_user() -> None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM users WHERE username = ?",
            ("demo",),
        ).fetchone()
        if row:
            return
    try:
        register_user(
            "demo",
            "demo",
            email="demo@example.com",
            full_name="Demo Bruger",
        )
    except Exception:
        pass
