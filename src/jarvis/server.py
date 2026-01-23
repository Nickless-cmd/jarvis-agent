import asyncio
import logging
import json
import os
import re
import time
import random
from pathlib import Path
from zoneinfo import ZoneInfo
from logging.handlers import TimedRotatingFileHandler
import gzip
from datetime import datetime, timezone, timedelta
import uuid
import sqlite3
from fastapi import BackgroundTasks, Cookie, Depends, FastAPI, File, Header, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse, JSONResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Optional


@dataclass
class AppState:
    """Application state container for initialized services."""
    demo_user_ensured: bool = False
    repo_watcher_started: bool = False
    paths_logged: bool = False
    project_root_overridden: bool = False
    startup_time: float = 0.0


# Global application state
app_state = AppState()


from dotenv import load_dotenv
load_dotenv()

from jarvis.agent import run_agent, choose_tool
from jarvis.auth import (
    SESSION_TTL_HOURS,
    AuthContext,
    build_auth_context,
    ensure_demo_user,
    get_or_create_default_user,
    get_user_by_token,
    login_user,
    register_user,
    verify_user_password,
)
from jarvis.db import get_conn, log_login_session
from jarvis.personality import SYSTEM_PROMPT
from jarvis.prompts.system_prompts import SYSTEM_PROMPT_USER, SYSTEM_PROMPT_ADMIN
from jarvis.prompt_manager import get_prompt_manager
from jarvis.event_store import get_event_store, wire_event_store_to_bus
from jarvis.events import subscribe_all
from jarvis.memory import purge_user_memory
from jarvis.files import (
    safe_path,
    save_upload,
    list_uploads,
    delete_upload,
    keep_upload,
    list_expiring_uploads,
    purge_expired_uploads,
    get_download_token,
    finalize_download,
    UPLOAD_DIR_NAME,
)
from jarvis.notes import (
    list_expiring_notes,
    purge_expired_notes,
    add_note,
    keep_note,
    delete_note,
    list_due_note_reminders,
)
import requests
from jarvis.tickets import (
    create_ticket,
    list_tickets,
    get_ticket,
    add_ticket_message,
    list_tickets_admin,
    get_ticket_admin,
    update_ticket_admin,
)
from jarvis.session_store import (
    create_session,
    ensure_session,
    ensure_default_session,
    list_sessions,
    session_belongs_to_user,
    rename_session,
    delete_session,
    get_all_messages,
    add_message,
    get_quota_state,
    set_quota_state,
)
from jarvis.notifications.store import (
    add_event as add_notification_event,
    list_events as list_notification_events,
    mark_read,
    add_notification,
    list_notifications,
    mark_notification_read,
    get_unread_notifications_count,
    mark_all_notifications_read,
)
from jarvis.watchers.repo_watcher import start_repo_watcher_if_enabled
from jarvis.watchers.test_watcher import run_pytest_and_notify
from jarvis.event_store import get_event_store
from jarvis.events import subscribe, publish, subscribe_all

ROOT = Path(__file__).resolve().parents[2]
UI_DIR = ROOT / "ui"
APP_HTML = UI_DIR / "app.html"

# Generate BUILD_ID for cache busting
try:
    import subprocess
    BUILD_ID = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT).decode().strip()
except Exception:
    BUILD_ID = str(int(time.time()))


DATA_DIR = Path(__file__).resolve().parents[2] / "data"
LOG_DIR = Path(os.getenv("JARVIS_LOG_DIR", DATA_DIR / "logs"))
LOG_PATH = Path(os.getenv("JARVIS_LOG_PATH", LOG_DIR / "system.log"))
os.environ.setdefault("JARVIS_LOG_PATH", str(LOG_PATH))
LOG_DIR.mkdir(parents=True, exist_ok=True)

_req_logger = logging.getLogger("jarvis.request")
if not _req_logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    _req_logger.addHandler(_handler)
    file_handler = TimedRotatingFileHandler(
        LOG_PATH,
        when="midnight",
        backupCount=30,
        encoding="utf-8",
        utc=True,
    )
    file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    _req_logger.addHandler(file_handler)
_req_logger.setLevel(logging.INFO)
_last_log_cleanup = 0.0
def is_test_mode():
    return os.getenv("JARVIS_TEST_MODE", "0") == "1"
_PROMPT_CACHE: dict[str, str] = {}
_EXPOSE_SYSTEM_PROMPT = os.getenv("JARVIS_EXPOSE_SYSTEM_PROMPT", "0") == "1"
_PROMPT_MANAGER = get_prompt_manager()

LOGIN_PATH = UI_DIR / "login.html"
REGISTER_PATH = UI_DIR / "registere.html"
ADMIN_LOGIN_PATH = UI_DIR / "admin_login.html"
APP_PATH = UI_DIR / "app.html"
ADMIN_PATH = UI_DIR / "admin.html"
ACCOUNT_PATH = UI_DIR / "account.html"
DOCS_PATH = UI_DIR / "docs.html"
TICKETS_PATH = UI_DIR / "tickets.html"
MAINTENANCE_PATH = UI_DIR / "maintenance.html"


def _log_startup_paths():
    # Log which server file and project root are active so authors can verify the correct repo is used.
    try:
        _req_logger.info(f"STARTUP: jarvis.server file: {__file__}")
        _req_logger.info(f"STARTUP: PROJECT_ROOT: {ROOT}")
        _req_logger.info(f"STARTUP: APP_HTML path: {APP_HTML} exists={APP_HTML.exists()}")
    except Exception:
        pass

# Global watcher instance for shutdown
_repo_watcher = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    app_state.startup_time = time.time()
    app_state.paths_logged = True
    _log_startup_paths()
    
    app_state.demo_user_ensured = True
    ensure_demo_user()
    
    app_state.repo_watcher_started = True
    global _repo_watcher
    if not is_test_mode():
        _repo_watcher = start_repo_watcher_if_enabled()
    
    # Subscribe EventStore to EventBus (always, even in test mode) so /v1/events works in tests
    event_store = get_event_store()
    wire_event_store_to_bus()
    unsubscribe_events = lambda: None  # kept for symmetry

    # Handle project root override and static file mounting at startup
    global ROOT, UI_DIR, APP_HTML
    EXPECTED_ROOT = Path(os.getenv("JARVIS_PROJECT_ROOT", "/home/bs/vscode/jarvis-agent"))
    if EXPECTED_ROOT.exists() and EXPECTED_ROOT != ROOT:
        app_state.project_root_overridden = True
        ROOT = EXPECTED_ROOT
        UI_DIR = ROOT / "ui"
        APP_HTML = UI_DIR / "app.html"
        try:
            app.mount("/ui/static", StaticFiles(directory=str(UI_DIR / "static")), name="ui-static")
            app.mount("/static", StaticFiles(directory=os.path.join(UI_DIR, "static")), name="static")
        except Exception:
            pass
    
    try:
        yield
    finally:
        try:
            unsubscribe_events()
        except Exception:
            pass
        try:
            event_store = get_event_store()
            event_store.shutdown()
        except Exception:
            pass
        try:
            events.close()
        except Exception:
            pass
        try:
            if _repo_watcher:
                _repo_watcher.stop()
        except Exception:
            pass


app = FastAPI(lifespan=lifespan)

# Mount static assets (will be remounted in lifespan if project root changes)
app.mount("/ui/static", StaticFiles(directory=str(UI_DIR / "static")), name="ui-static")
app.mount("/static", StaticFiles(directory=os.path.join(UI_DIR, "static")), name="static")

# Allow overriding project root at runtime (handled in lifespan now)
# EXPECTED_ROOT = Path(os.getenv("JARVIS_PROJECT_ROOT", "/home/bs/vscode/jarvis-agent"))
# if EXPECTED_ROOT.exists() and EXPECTED_ROOT != ROOT:
#     ROOT = EXPECTED_ROOT
#     UI_DIR = ROOT / "ui"
#     APP_HTML = UI_DIR / "app.html"
#     try:
#         app.mount("/ui/static", StaticFiles(directory=str(UI_DIR / "static")), name="ui-static")
#         app.mount("/static", StaticFiles(directory=os.path.join(UI_DIR, "static")), name="static")
#     except Exception:
#         pass

# UI routing: Legacy index.html redirects to modern app.html for deterministic UX
# Users should always land on /app (ui/app.html), not legacy /ui/index.html

@app.api_route("/ui/", methods=["GET", "HEAD"])
async def ui_root_redirect():
    """Redirect /ui/ to /app to ensure users land on modern UI"""
    return RedirectResponse(url="/app", status_code=302)

@app.api_route("/ui/index.html", methods=["GET", "HEAD"])
async def legacy_index_redirect():
    """Redirect legacy index.html to modern app to avoid confusion"""
    return RedirectResponse(url="/app", status_code=302)


@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
    response.headers.setdefault("Cache-Control", "no-store")
    return response


@app.middleware("http")
async def request_logger(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    if not is_test_mode():
        elapsed_ms = int((time.time() - start) * 1000)
        _req_logger.info("%s %s %s %dms", request.method, request.url.path, response.status_code, elapsed_ms)
        global _last_log_cleanup
        if time.time() - _last_log_cleanup > 3600:
            _enforce_log_limits()
            _last_log_cleanup = time.time()
    return response


class RegisterRequest(BaseModel):
    username: str
    password: str
    email: str
    full_name: str | None = None
    last_name: str | None = None
    city: str | None = None
    phone: str | None = None
    note: str | None = None
    captcha_token: str | None = None
    captcha_answer: str | None = None


class LoginRequest(BaseModel):
    username: str
    password: str
    captcha_token: str | None = None
    captcha_answer: str | None = None


class SessionCreateRequest(BaseModel):
    name: str | None = None


class SessionRenameRequest(BaseModel):
    name: str


class SessionPromptRequest(BaseModel):
    prompt: str | None = None


class AdminCreateRequest(BaseModel):
    username: str
    password: str
    is_admin: bool | None = False
    email: str | None = None
    full_name: str | None = None
    last_name: str | None = None
    city: str | None = None
    phone: str | None = None
    note: str | None = None


class AdminDisableRequest(BaseModel):
    is_disabled: bool


class FooterSettingsRequest(BaseModel):
    text: str
    support_url: str
    contact_url: str
    license_text: str | None = None
    license_url: str | None = None
    register_enabled: bool = True
    captcha_enabled: bool = True
    google_auth_enabled: bool = False
    maintenance_enabled: bool = False
    maintenance_message: str | None = None
    system_prompt: str | None = None
    updates_log: str | None = None
    quota_default_mb: int | None = None
    brand_top_label: str | None = None
    brand_core_label: str | None = None
    banner_messages: str | None = None
    banner_enabled: bool | None = None
    public_base_url: str | None = None
    notify_enabled: bool | None = None


class AccountUpdateRequest(BaseModel):
    email: str | None = None
    full_name: str | None = None
    last_name: str | None = None
    city: str | None = None
    phone: str | None = None
    note: str | None = None
    current_password: str | None = None
    new_password: str | None = None


class TicketCreateRequest(BaseModel):
    title: str
    message: str
    priority: str | None = None


class TicketReplyRequest(BaseModel):
    message: str


class TicketUpdateRequest(BaseModel):
    status: str | None = None
    priority: str | None = None


DEFAULT_API_KEY = "devkey"
CAPCHAS = {}
CAPTCHA_TTL_SECONDS = 300


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


def _auth_or_token_ok(authorization: str | None, token: str | None) -> bool:
    if _auth_ok(authorization):
        return True
    if not token:
        return False
    return get_user_by_token(token) is not None


def _resolve_token(
    request: Request,
    x_user_token: str | None = Header(None),
) -> str | None:
    if x_user_token:
        return x_user_token
    return request.cookies.get("jarvis_token")


def _public_user(user: dict) -> dict:
    """Return a user payload with normalized admin flag."""
    return {
        "id": user["id"],
        "username": user["username"],
        "is_admin": is_admin_user(user),
    }


def is_admin_user(user: dict | None) -> bool:
    """Normalize admin detection across payloads."""
    if not user:
        return False
    flag = user.get("is_admin")
    if isinstance(flag, bool):
        return flag
    if isinstance(flag, (int, str)):
        if str(flag).lower() in {"1", "true", "yes", "y", "on"}:
            return True
    role = user.get("role")
    if isinstance(role, str) and role.lower() == "admin":
        return True
    return False


def _check_admin_auth(request: Request, authorization: str | None, token: str | None) -> AuthContext:
    if not _auth_or_token_ok(authorization, token):
        raise HTTPException(401, detail={"ok": False, "error": {"type": "AuthRequired", "message": "auth required"}})
    if _auth_ok(authorization):
        user = get_or_create_default_user()
        user["is_admin"] = True
    else:
        user = get_user_by_token(token)
    if not user:
        raise HTTPException(401, detail={"ok": False, "error": {"type": "AuthRequired", "message": "auth required"}})
    if user.get("is_disabled"):
        raise HTTPException(403, detail={"ok": False, "error": {"type": "AdminRequired", "message": "admin required"}})
    if not is_admin_user(user):
        raise HTTPException(403, detail={"ok": False, "error": {"type": "AdminRequired", "message": "admin required"}})
    return AuthContext(user=user, is_authenticated=True, is_admin=True, token_source="devkey" if _auth_ok(authorization) else "token")


def _clean_expired_captcha() -> None:
    """Remove expired captcha tokens to avoid unbounded growth."""
    now = time.time()
    expired = [k for k, v in CAPCHAS.items() if now - v.get("ts", now) > CAPTCHA_TTL_SECONDS]
    for k in expired:
        CAPCHAS.pop(k, None)


def _verify_captcha(token: str | None, answer: str | None) -> bool:
    if not token or answer is None:
        return False
    entry = CAPCHAS.get(token)
    if not entry:
        return False
    return str(entry["answer"]) == str(answer).strip()


def _debug(msg: str) -> None:
    if os.getenv("JARVIS_DEBUG") == "1":
        print(msg)


def _extract_prompt(body: dict) -> str:
    messages = body.get("messages", [])
    for msg in reversed(messages):
        if msg.get("role") == "user":
            return msg.get("content", "")
    if messages:
        return messages[-1].get("content", "")
    return ""


_SENSITIVE_KEYWORDS = [
    "pin",
    "pinkode",
    "adgangskode",
    "password",
    "kode",
    "cpr",
    "kortnummer",
    "kort",
    "card",
    "cvv",
    "cvc",
    "mitid",
    "nemid",
    "bank",
    "konto",
    "iban",
    "swift",
]


def _contains_sensitive(text: str) -> bool:
    if not text:
        return False
    lowered = text.lower()
    if re.search(r"\b\d{6}-?\d{4}\b", text):
        return True
    if any(k in lowered for k in ["cvv", "cvc"]):
        return True
    if any(k in lowered for k in _SENSITIVE_KEYWORDS):
        if re.search(r"\b\d{4,6}\b", text):
            return True
    if re.search(r"\b(?:\d[ -]*?){13,19}\b", text) and any(
        k in lowered for k in ["kort", "card", "visa", "mastercard", "bank"]
    ):
        return True
    return False


def _auto_session_name(prompt: str, created_at: str | None = None) -> str:
    cleaned = " ".join((prompt or "").split())
    if not cleaned:
        return "Ny chat"
    words = cleaned.split()
    short = " ".join(words[:6])
    if len(short) > 48:
        short = short[:48].rstrip()
    if len(cleaned) > len(short):
        short = short.rstrip(".") + "..."
    if created_at:
        try:
            dt = datetime.fromisoformat(created_at)
        except Exception:
            dt = datetime.now(timezone.utc)
    else:
        dt = datetime.now(timezone.utc)
    dt = dt.astimezone()
    months = ["jan", "feb", "mar", "apr", "maj", "jun", "jul", "aug", "sep", "okt", "nov", "dec"]
    suffix = f"{dt.day:02d}. {months[dt.month - 1]}"
    return f"{short} — {suffix}"


def _rename_empty_sessions(user_id: int) -> int:
    updated = 0
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, created_at FROM sessions WHERE user_id = ? AND (name IS NULL OR name = '' OR name = 'Ny chat')",
            (user_id,),
        ).fetchall()
        for r in rows:
            first = conn.execute(
                "SELECT content FROM messages WHERE session_id = ? AND role = ? ORDER BY id ASC LIMIT 1",
                (r["id"], "user"),
            ).fetchone()
            if not first or not first["content"]:
                continue
            auto_name = _auto_session_name(first["content"], r["created_at"])
            conn.execute(
                "UPDATE sessions SET name = ? WHERE id = ? AND user_id = ?",
                (auto_name, r["id"], user_id),
            )
            updated += 1
        conn.commit()
    return updated


def _chunk_text(text: str, max_len: int = 24) -> list[str]:
    return [text[i : i + max_len] for i in range(0, len(text), max_len)]


def _cleanup_user_assets(user: dict) -> None:
    uid = user.get("id")
    if not uid:
        return
    purge_expired_notes(uid)
    purge_expired_uploads(uid, user["username"])


def _expiry_warning_text(user: dict) -> str | None:
    uid = user.get("id")
    if not uid:
        return None
    notes = list_expiring_notes(uid)
    files = list_expiring_uploads(uid)
    if not notes and not files:
        return None
    parts = []
    if notes:
        note_titles = ", ".join([n.get("title") or f"note {n['id']}" for n in notes[:3]])
        parts.append(f"Noter udløber om 24 timer: {note_titles}.")
    if files:
        file_names = ", ".join([f.get("original_name") or f"fil {f['id']}" for f in files[:3]])
        parts.append(f"Filer udløber om 24 timer: {file_names}.")
    return "⚠ " + " ".join(parts) + " Skriv 'behold note X' eller 'behold fil X' for at forny."


def _note_reminder_text(user: dict) -> str | None:
    uid = user.get("id")
    if not uid:
        return None
    due = list_due_note_reminders(uid)
    if not due:
        return None
    parts = []
    for n in due[:3]:
        title = n.get("title") or f"note {n['id']}"
        content = (n.get("content") or "").replace("\n", " ").strip()
        if len(content) > 120:
            content = content[:120].rstrip() + "..."
        parts.append(f"{title}: {content}")
    return "⏰ Påmindelse om note: " + " | ".join(parts)


MAX_STREAM_SECONDS = int(os.getenv("JARVIS_MAX_STREAM_SECONDS", "120"))


def _stream_error_event(message: str, error_type: str, trace_id: str | None = None, session_id: str | None = None):
    payload = {"ok": False, "error": {"type": error_type, "message": message}}
    if trace_id:
        payload["error"]["trace_id"] = trace_id
    if session_id:
        payload["session_id"] = session_id
    return f"event: error\ndata: {json.dumps(payload)}\n\n"


def _stream_text_events(
    text: str,
    model: str,
    stream_id: str,
    trace_id: str | None = None,
    session_id: str | None = None,
):
    """
    Emit EventBus events for streaming text and yield SSE data.
    This is the canonical way to stream text responses via EventBus.
    """
    created = int(time.time())
    started_at = time.time()
    text_buffer: list[str] = []

    # Emit agent.stream.start
    try:
        publish("agent.stream.start", {
            "session_id": session_id,
            "message_id": stream_id,
            "trace_id": trace_id,
            "started_at": started_at,
        })
    except Exception:
        pass

    head = {
        "id": stream_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "trace_id": trace_id,
        "session_id": session_id,
        "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}],
    }
    yield f"data: {json.dumps(head)}\n\n"

    sequence = 0
    for part in _chunk_text(text):
        text_buffer.append(part)
        # Emit agent.stream.delta event
        try:
            publish("agent.stream.delta", {
                "message_id": stream_id,
                "sequence": sequence,
                "token": part,
                "role": "assistant",
                "trace_id": trace_id,
                "session_id": session_id,
            })
        except Exception:
            pass  # EventBus unavailable, continue
        
        data = {
            "id": stream_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "trace_id": trace_id,
            "session_id": session_id,
            "choices": [{"index": 0, "delta": {"content": part}, "finish_reason": None}],
        }
        yield f"data: {json.dumps(data)}\n\n"
        sequence += 1

    tail = {
        "id": stream_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "trace_id": trace_id,
        "session_id": session_id,
        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
    }
    yield f"data: {json.dumps(tail)}\n\n"
    yield "data: [DONE]\n\n"

    # Emit agent.stream.final
    try:
        duration_ms = int((time.time() - started_at) * 1000)
        publish("agent.stream.final", {
            "session_id": session_id,
            "message_id": stream_id,
            "trace_id": trace_id,
            "text": "".join(text_buffer),
            "duration_ms": duration_ms,
            "parts": sequence,
        })
    except Exception:
        pass


def _stream_chunks(
    text: str,
    model: str,
    stream_id: str,
    trace_id: str | None = None,
    session_id: str | None = None,
):
    """
    DEPRECATED: Use _stream_text_events instead.
    This function is kept for backward compatibility but should not be used for new code.
    """
    return _stream_text_events(text, model, stream_id, trace_id, session_id)


def _status_event(state: str, tool: str | None = None, trace_id: str | None = None, session_id: str | None = None):
    payload = {"state": state}
    if tool:
        payload["tool"] = tool
    if trace_id:
        payload["trace_id"] = trace_id
    if session_id:
        payload["session_id"] = session_id
    return f"event: status\ndata: {json.dumps(payload)}\n\n"


def _resolve_user(user_token: str | None) -> dict:
    if user_token:
        user = get_user_by_token(user_token)
        if not user:
            raise HTTPException(401, detail="Invalid user token")
        if user.get("is_disabled"):
            raise HTTPException(403, detail="User is disabled")
        return user
    return get_or_create_default_user()


def _resolve_session_id(user: dict, session_id: str | None, logged_in: bool) -> str | None:
    if session_id:
        if not (
            len(session_id) == 32
            or session_id.startswith("session-default-")
            or session_id == "default-session"
        ):
            raise HTTPException(
                404,
                detail={"ok": False, "error": {"type": "SessionNotFound", "message": "session not found"}},
            )

    if logged_in:
        if not session_id:
            return ensure_default_session(user["id"], name="Default")
        # simple validation: hex or default-session prefix
        if not session_belongs_to_user(session_id, user["id"]):
            raise HTTPException(404, detail={"ok": False, "error": {"type": "SessionNotFound", "message": "session not found"}})
        return session_id

    # anonymous / default user
    if session_id:
        if not session_belongs_to_user(session_id, user["id"]):
            raise HTTPException(404, detail={"ok": False, "error": {"type": "SessionNotFound", "message": "session not found"}})
        return session_id
    return ensure_default_session(user["id"], name="Default")


def _get_settings(keys: list[str]) -> dict:
    with get_conn() as conn:
        rows = conn.execute(
            f"SELECT key, value FROM settings WHERE key IN ({','.join('?' for _ in keys)})",
            keys,
        ).fetchall()
    result = {row["key"]: row["value"] for row in rows}
    return result


def _get_setting(key: str, default: str) -> str:
    settings = _get_settings([key])
    return settings.get(key, default)


def _load_prompts() -> dict[str, str]:
    """Load system/admin prompts once and cache them."""
    global _PROMPT_CACHE
    if _PROMPT_CACHE:
        return _PROMPT_CACHE
    _PROMPT_CACHE = {
        "user": SYSTEM_PROMPT_USER,
        "admin": SYSTEM_PROMPT_ADMIN,
    }
    return _PROMPT_CACHE


def _current_system_prompt() -> str:
    """Return active system prompt (DB override if set, otherwise bundled prompt)."""
    try:
        return _PROMPT_MANAGER.effective_prompt(is_admin=False).text
    except Exception:
        prompts = _load_prompts()
        return _get_setting("system_prompt", prompts.get("user", SYSTEM_PROMPT))


def _current_admin_prompt() -> str:
    try:
        return _PROMPT_MANAGER.effective_prompt(is_admin=True).text
    except Exception:
        prompts = _load_prompts()
        return prompts.get("admin", SYSTEM_PROMPT)


def _active_prompt_info(is_admin: bool) -> dict:
    bundle = _PROMPT_MANAGER.effective_prompt(is_admin=is_admin)
    info = {
        "name": "admin_system" if is_admin else "system",
        "hash": bundle.sha256,
    }
    if _EXPOSE_SYSTEM_PROMPT or is_admin:
        info["preview"] = bundle.preview(200)
    return info


def _parse_banner_entries(raw: str) -> list[dict]:
    raw = (raw or "").strip()
    if not raw:
        return []
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            entries = []
            for item in data:
                if not isinstance(item, dict):
                    continue
                text = str(item.get("text", "")).strip()
                ts = str(item.get("ts", "")).strip()
                if text and ts:
                    entries.append({"text": text, "ts": ts})
            if entries:
                return entries
    except Exception:
        pass
    now = datetime.now(timezone.utc).isoformat()
    parts = [p.strip() for p in re.split(r"\n|•", raw) if p.strip()]
    entries = []
    for part in parts:
        if " | " in part:
            head, tail = part.split(" | ", 1)
            head = head.strip()
            tail = tail.strip()
            ts = now
            if re.match(r"^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}", head):
                try:
                    ts = datetime.fromisoformat(head.replace(" ", "T")).isoformat()
                except Exception:
                    ts = now
            entries.append({"text": tail or part, "ts": ts})
        else:
            entries.append({"text": part, "ts": now})
    return entries


def _filter_banner_entries(entries: list[dict]) -> list[dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=14)
    filtered = []
    for entry in entries:
        try:
            ts = datetime.fromisoformat(entry.get("ts", ""))
        except Exception:
            ts = datetime.now(timezone.utc)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        if ts >= cutoff:
            filtered.append({"text": entry.get("text", "").strip(), "ts": ts.isoformat()})
    return [e for e in filtered if e["text"]]


def _format_banner_entries(entries: list[dict], tz_name: str) -> str:
    parts = []
    for entry in entries:
        try:
            ts = datetime.fromisoformat(entry["ts"]).astimezone(ZoneInfo(tz_name))
            label = ts.strftime("kl %H:%M - %d/%m/%Y")
        except Exception:
            label = datetime.now(ZoneInfo(tz_name)).strftime("kl %H:%M - %d/%m/%Y")
        parts.append(f"{entry['text']} — {label}")
    return "      •      ".join(parts)


def _auto_updates_list(tz_name: str) -> list[str]:
    base = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    candidates = [
        os.path.join(base, "src"),
        os.path.join(base, "ui"),
        os.path.join(base, "docs"),
        os.path.join(base, "README.md"),
    ]
    files = []
    for path in candidates:
        if os.path.isfile(path):
            try:
                files.append((path, os.path.getmtime(path)))
            except OSError:
                continue
            continue
        if not os.path.isdir(path):
            continue
        for root, _dirs, names in os.walk(path):
            for name in names:
                if name.endswith((".py", ".js", ".css", ".html", ".md")):
                    full = os.path.join(root, name)
                    try:
                        files.append((full, os.path.getmtime(full)))
                    except OSError:
                        continue
    files.sort(key=lambda x: x[1], reverse=True)
    tz = ZoneInfo(tz_name)
    updates = []
    for path, ts in files[:6]:
        rel = os.path.relpath(path, base)
        when = datetime.fromtimestamp(ts, tz).strftime("%d-%m-%Y %H:%M")
        updates.append(f"{rel} • {when}")
    if not updates:
        updates.append("Ingen automatiske opdateringer endnu.")
    return updates


def _command_list() -> list[str]:
    builtin = [
        "/help — Vis kort hjælp",
        "/mode fakta — Kort og nøgternt svar",
        "/mode snak — Varmere svar, maks 1 joke",
        "/personlighed <tekst> — Sæt tone for denne session",
        "/personality <text> — Set tone for this session",
        "/system-prompt — Vis aktiv system‑prompt",
        "/cv hjælp — Start CV‑flow",
        "læs nr <n> — Læs og opsummér valgt nyhed",
        "ping <ip/host> — Tjek om enhed svarer",
        "systeminfo — CPU/RAM/Disk/IP (vælg felter i prompt)",
        "noter — Vis dine noter",
        "mind mig om <tekst> — Opret påmindelse",
    ]
    base = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    docs_path = os.path.join(base, "docs", "README.md")
    if not os.path.exists(docs_path):
        return builtin
    lines = []
    try:
        with open(docs_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if "`/" in line and "—" in line:
                    parts = line.split("`", 2)
                    if len(parts) >= 2:
                        cmd = parts[1]
                        tail = line.split("—", 1)[-1].strip()
                        lines.append(f"{cmd} — {tail}")
    except Exception:
        return builtin
    merged = []
    seen = set()
    for item in builtin + lines:
        if item not in seen:
            merged.append(item)
            seen.add(item)
    return merged[:12]


def _butlerize_text(text: str, user: dict | None) -> str:
    if not text:
        return text
    trimmed = text.lstrip()
    if trimmed.startswith(
        (
            "Selvfølgelig",
            "Forstået",
            "Beklager",
            "Tak",
            "Aha",
            "Ja",
            "Nej",
        )
    ):
        return text
    name = (user or {}).get("full_name") or ""
    first = name.split()[0] if name else ""
    prefixes = [
        "Som De ønsker.",
        "Med glæde.",
        "Straks, naturligvis.",
        "Jeg tager mig af det.",
        "Lige straks.",
        "Selvfølgelig.",
    ]
    prefix = random.choice(prefixes)
    if first:
        prefix = f"{prefix} {first}."
    return f"{prefix}\n{text}"


def _enforce_log_limits(max_bytes: int = 1024 * 1024 * 1024, max_days: int = 30) -> None:
    if not LOG_DIR.exists():
        return
    files = [p for p in LOG_DIR.iterdir() if p.is_file()]
    now = time.time()
    for p in files:
        if now - p.stat().st_mtime > max_days * 86400:
            try:
                p.unlink()
            except Exception:
                pass
    files = [p for p in LOG_DIR.iterdir() if p.is_file()]
    total = sum(p.stat().st_size for p in files)
    if total <= max_bytes:
        return
    files.sort(key=lambda p: p.stat().st_mtime)
    for p in files:
        if total <= max_bytes:
            break
        try:
            size = p.stat().st_size
            p.unlink()
            total -= size
        except Exception:
            pass


def _gzip_rotator(source: str, dest: str) -> None:
    with open(source, "rb") as src, gzip.open(dest + ".gz", "wb") as out:
        out.writelines(src)
    os.remove(source)
    _enforce_log_limits()


def _gzip_namer(name: str) -> str:
    return name + ".gz"


for handler in list(_req_logger.handlers):
    if isinstance(handler, TimedRotatingFileHandler):
        handler.rotator = _gzip_rotator
        handler.namer = _gzip_namer
_enforce_log_limits()


def _extract_system_prompt_from_file() -> str:
    path = Path(__file__).resolve().parent / "personality.py"
    text = path.read_text(encoding="utf-8")
    marker = "SYSTEM_PROMPT"
    idx = text.find(marker)
    if idx == -1:
        return SYSTEM_PROMPT
    start = text.find('"""', idx)
    if start == -1:
        return SYSTEM_PROMPT
    end = text.find('"""', start + 3)
    if end == -1:
        return SYSTEM_PROMPT
    return text[start + 3 : end].strip()


def _update_system_prompt_setting() -> None:
    prompt = _extract_system_prompt_from_file()
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            ("system_prompt", prompt),
        )
        conn.commit()


def _maintenance_enabled() -> bool:
    return _get_setting("maintenance_enabled", "0") == "1"


def _maintenance_message() -> str:
    return _get_setting("maintenance_message", "Jarvis er i vedligeholdelse. Prøv igen senere.")


def _enforce_maintenance(user: dict) -> None:
    if _maintenance_enabled() and not is_admin_user(user):
        raise HTTPException(503, detail=_maintenance_message())


def _month_start_utc() -> datetime:
    now = datetime.now(timezone.utc)
    return datetime(now.year, now.month, 1, tzinfo=timezone.utc)


def _quota_defaults_mb() -> int:
    try:
        return int(_get_setting("quota_default_mb", "100"))
    except Exception:
        return 100


def _get_user_quota(user_id: int) -> tuple[int, int]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT monthly_limit_mb, credits_mb FROM user_quota WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    if row:
        return int(row["monthly_limit_mb"]), int(row["credits_mb"])
    return _quota_defaults_mb(), 0


def _set_user_quota(user_id: int, limit_mb: int, credits_mb: int) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO user_quota (user_id, monthly_limit_mb, credits_mb, updated_at) VALUES (?,?,?,?) "
            "ON CONFLICT(user_id) DO UPDATE SET monthly_limit_mb = excluded.monthly_limit_mb, "
            "credits_mb = excluded.credits_mb, updated_at = excluded.updated_at",
            (user_id, limit_mb, credits_mb, now),
        )
        conn.commit()


def _monthly_usage_bytes(user_id: int) -> int:
    month_start = _month_start_utc().isoformat()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(COALESCE(m.content_bytes, LENGTH(m.content))), 0) AS total "
            "FROM messages m JOIN sessions s ON m.session_id = s.id "
            "WHERE s.user_id = ? AND m.created_at >= ?",
            (user_id, month_start),
        ).fetchone()
    return int(row["total"] or 0)


def _bytes_to_mb(value: int) -> float:
    return value / (1024 * 1024)


def _quota_warning(user_id: int, session_id: str, used_mb: float, limit_mb: int, credits_mb: int) -> str | None:
    total_mb = max(0, limit_mb + credits_mb)
    if total_mb <= 0:
        return None
    remaining_mb = total_mb - used_mb
    if remaining_mb <= 0:
        return None
    remaining_pct = (remaining_mb / total_mb) * 100.0
    thresholds = [30, 20, 10]
    state_raw = get_quota_state(session_id)
    warned = set()
    if state_raw:
        try:
            state = json.loads(state_raw)
            warned = set(state.get("warned", []))
        except Exception:
            warned = set()
    for threshold in thresholds:
        if remaining_pct <= threshold and threshold not in warned:
            warned.add(threshold)
            set_quota_state(session_id, json.dumps({"warned": sorted(warned)}))
            return f"Kvota: {int(remaining_pct)}% tilbage ({remaining_mb:.1f} MB af {total_mb} MB)."
    return None


@app.post("/auth/register")
async def register(req: RegisterRequest, authorization: str | None = Header(None)):
    if not _auth_ok(authorization):
        raise HTTPException(401, detail="Invalid API key")
    if _get_setting("register_enabled", "1") != "1":
        raise HTTPException(403, detail="Registration is disabled")
    if not is_test_mode() and _get_setting("captcha_enabled", "1") == "1":
        if not _verify_captcha(req.captcha_token, req.captcha_answer):
            raise HTTPException(400, detail="Captcha er forkert")
    if not req.full_name or not req.full_name.strip():
        raise HTTPException(400, detail="Navn er påkrævet")
    if "@" not in req.email:
        raise HTTPException(400, detail="Ugyldig email")
    if not req.password or len(req.password) < 6:
        raise HTTPException(400, detail="Password er for kort")
    try:
        user = register_user(
            req.username,
            req.password,
            email=req.email.strip(),
            full_name=req.full_name,
            last_name=req.last_name,
            city=req.city,
            phone=req.phone,
            note=req.note,
        )
    except sqlite3.IntegrityError:
        raise HTTPException(400, detail="Username already exists")
    return _public_user(user)


@app.post("/auth/login")
async def login(request: Request, req: LoginRequest, authorization: str | None = Header(None)):
    if not is_test_mode() and _get_setting("captcha_enabled", "1") == "1":
        if not _verify_captcha(req.captcha_token, req.captcha_answer):
            raise HTTPException(400, detail="Captcha er forkert")
    result = login_user(req.username, req.password)
    if not result:
        raise HTTPException(401, detail="Invalid credentials")
    if result.get("disabled"):
        raise HTTPException(403, detail="User is disabled")
    token = result["token"]
    expires_at = result.get("expires_at")
    user = get_user_by_token(token)
    if user and expires_at:
        ip = request.client.host if request and request.client else None
        ua = request.headers.get("user-agent") if request else None
        now_iso = datetime.now(timezone.utc).isoformat()
        log_login_session(user["id"], token, now_iso, expires_at, ip, ua, now_iso)
    response = JSONResponse({"token": token, "expires_at": expires_at})
    if expires_at:
        secure = os.getenv("JARVIS_COOKIE_SECURE", "0") == "1"
        samesite = os.getenv("JARVIS_COOKIE_SAMESITE", "lax")
        response.set_cookie(
            "jarvis_token",
            token,
            max_age=SESSION_TTL_HOURS * 3600,
            path="/",
            httponly=True,
            secure=secure,
            samesite=samesite,
        )
    return response


@app.post("/auth/admin/login")
async def admin_login(request: Request, req: LoginRequest, authorization: str | None = Header(None)):
    result = login_user(req.username, req.password)
    if not result:
        raise HTTPException(401, detail="Invalid credentials")
    if result.get("disabled"):
        raise HTTPException(403, detail="User is disabled")
    token = result["token"]
    expires_at = result.get("expires_at")
    user = get_user_by_token(token)
    if not is_admin_user(user):
        with get_conn() as conn:
            conn.execute("UPDATE users SET token = NULL, token_expires_at = NULL WHERE token = ?", (token,))
            conn.commit()
        raise HTTPException(403, detail="Admin login kræver admin-bruger")
    if expires_at:
        ip = request.client.host if request and request.client else None
        ua = request.headers.get("user-agent") if request else None
        now_iso = datetime.now(timezone.utc).isoformat()
        log_login_session(user["id"], token, now_iso, expires_at, ip, ua, now_iso)
    response = JSONResponse({"token": token, "expires_at": expires_at})
    if expires_at:
        secure = os.getenv("JARVIS_COOKIE_SECURE", "0") == "1"
        samesite = os.getenv("JARVIS_COOKIE_SAMESITE", "lax")
        response.set_cookie(
            "jarvis_token",
            token,
            max_age=SESSION_TTL_HOURS * 3600,
            path="/",
            httponly=True,
            secure=secure,
            samesite=samesite,
        )
    return response


@app.get("/sessions")
async def get_sessions(
    authorization: str | None = Header(None),
    token: str | None = Depends(_resolve_token),
):
    if not _auth_or_token_ok(authorization, token):
        raise HTTPException(401, detail="Invalid API key")
    user = get_user_by_token(token)
    if not user:
        raise HTTPException(401, detail="Missing or invalid user token")
    if user.get("is_disabled"):
        raise HTTPException(403, detail="User is disabled")
    _enforce_maintenance(user)
    _enforce_maintenance(user)
    _cleanup_user_assets(user)
    _rename_empty_sessions(user["id"])
    return {"sessions": list_sessions(user["id"])}


@app.post("/sessions")
async def create_sessions(
    payload: SessionCreateRequest,
    authorization: str | None = Header(None),
    token: str | None = Depends(_resolve_token),
):
    if not _auth_or_token_ok(authorization, token):
        raise HTTPException(401, detail="Invalid API key")
    user = get_user_by_token(token)
    if not user:
        raise HTTPException(401, detail="Missing or invalid user token")
    if user.get("is_disabled"):
        raise HTTPException(403, detail="User is disabled")
    _enforce_maintenance(user)
    _enforce_maintenance(user)
    session_id = create_session(user["id"], name=payload.name)
    return {"session_id": session_id}


@app.get("/notifications")
async def notifications(
    authorization: str | None = Header(None),
    token: str | None = Depends(_resolve_token),
):
    if not _auth_or_token_ok(authorization, token):
        raise HTTPException(401, detail="Invalid API key")
    user = get_user_by_token(token)
    if not user:
        raise HTTPException(401, detail="Missing or invalid user token")
    if user.get("is_disabled"):
        raise HTTPException(403, detail="User is disabled")
    _enforce_maintenance(user)
    _enforce_maintenance(user)
    _cleanup_user_assets(user)
    warning = _expiry_warning_text(user)
    note_warning = _note_reminder_text(user)
    warnings = []
    if warning:
        warnings.append(warning)
    if note_warning:
        warnings.append(note_warning)
    return {"warnings": warnings}


@app.get("/v1/events")
async def list_events_endpoint(
    after: Optional[int] = Query(None, description="Return events after this ID"),
    limit: Optional[int] = Query(None, description="Maximum number of events to return"),
    authorization: str | None = Header(None),
    token: str | None = Depends(_resolve_token),
):
    if not _auth_or_token_ok(authorization, token):
        raise HTTPException(401, detail="Invalid API key")
    user = get_user_by_token(token)
    if not user:
        raise HTTPException(401, detail="Missing or invalid user token")
    if user.get("is_disabled"):
        raise HTTPException(403, detail="User is disabled")
    _enforce_maintenance(user)
    
    # Use EventStore for EventBus events
    event_store = get_event_store()
    result = event_store.get_events_snapshot(after=after, limit=limit)
    return result


@app.get("/v1/events/stream")
async def stream_events_endpoint(
    request: Request,
    since_id: Optional[int] = Query(None, description="Stream events after this ID"),
    types: Optional[str] = Query(None, description="Comma-separated list of event type prefixes to filter by"),
    session_id: Optional[str] = Query(None, description="Filter events by session_id"),
    max_events: Optional[int] = Query(None, description="Stop stream after N events (for testing)"),
    max_ms: Optional[int] = Query(None, description="Stop stream after T milliseconds (for testing)"),
    authorization: str | None = Header(None),
    token: str | None = Depends(_resolve_token),
):
    if not _auth_or_token_ok(authorization, token):
        raise HTTPException(401, detail="Invalid API key")
    user = get_user_by_token(token)
    if not user:
        raise HTTPException(401, detail="Missing or invalid user token")
    if user.get("is_disabled"):
        raise HTTPException(403, detail="User is disabled")
    _enforce_maintenance(user)

    # Parse types filter (prefix matching)
    type_prefixes = None
    if types:
        type_prefixes = [t.strip() for t in types.split(",") if t.strip()]

    event_store = get_event_store()
    last_id = since_id or 0

    # Fast path for deterministic tests: if max_ms is provided, return a snapshot immediately
    if max_ms is not None:
        snapshot = event_store.get_events_snapshot(after=since_id, limit=1000)["events"]
        lines = [": heartbeat\n\n"]
        for ev in snapshot:
            if type_prefixes and not any(ev["type"].startswith(prefix) for prefix in type_prefixes):
                continue
            if session_id and ev.get("session_id") and ev.get("session_id") != session_id:
                continue
            lines.append(f"event: {ev['type']}\n")
            lines.append(f"data: {json.dumps(ev)}\n")
            lines.append(f"id: {ev['id']}\n\n")
            if max_events is not None and len(lines) >= max_events * 3:
                break
        return Response(
            "".join(lines),
            media_type="text/event-stream; charset=utf-8",
            headers={
                "Cache-Control": "no-store",
                "Connection": "keep-alive",
            },
        )

    async def event_generator():
        nonlocal last_id
        events_sent = 0
        deadline = None
        if max_ms is not None:
            deadline = time.monotonic() + (max_ms / 1000.0)
        # In test mode, force a short deadline so streams cannot hang
        if is_test_mode() and deadline is None:
            deadline = time.monotonic() + 0.5
        if is_test_mode() and max_events is None:
            max_events = 100
        sleep_interval = 0.05 if (max_ms is not None or max_events is not None or is_test_mode()) else 1.0
        try:
            # Send an initial heartbeat so clients don't block forever on connect
            yield ": heartbeat\n\n"
            # Flush current snapshot immediately so pre-existing events are delivered without waiting
            snapshot_events = event_store.get_events_snapshot(after=since_id, limit=1000)["events"]
            seen_max_id = last_id
            filtered_snapshot: list[dict] = []
            for ev in snapshot_events:
                seen_max_id = max(seen_max_id, ev["id"])
                if type_prefixes and not any(ev["type"].startswith(prefix) for prefix in type_prefixes):
                    continue
                if session_id and ev.get("session_id") and ev.get("session_id") != session_id:
                    continue
                filtered_snapshot.append(ev)
            last_id = seen_max_id
            # If a deadline is provided (typical in tests), stream the filtered snapshot and exit deterministically
            if max_ms is not None:
                for ev in filtered_snapshot:
                    last_id = max(last_id, ev["id"])
                    yield f"event: {ev['type']}\ndata: {json.dumps(ev)}\nid: {ev['id']}\n\n"
                    events_sent += 1
                    if max_events is not None and events_sent >= max_events:
                        return
                return
            for ev in filtered_snapshot:
                last_id = max(last_id, ev["id"])
                yield f"event: {ev['type']}\ndata: {json.dumps(ev)}\nid: {ev['id']}\n\n"
                events_sent += 1
                if max_events is not None and events_sent >= max_events:
                    return
            last_id = seen_max_id
            if max_ms is not None or is_test_mode():
                # In tests, a single snapshot delivery is enough; exit to avoid hangs
                return
            while True:
                if await request.is_disconnected():
                    break
                # Check termination conditions even if no events arrive
                if deadline and time.monotonic() > deadline:
                    break
                if max_events is not None and events_sent >= max_events:
                    break
                bus = get_event_bus()
                if bus.is_closed():
                    break
                new_events = event_store.get_events(after=last_id, limit=1000)["events"]
                seen_max_id = last_id
                for ev in new_events:
                    seen_max_id = max(seen_max_id, ev["id"])
                    # Filter by type prefixes
                    if type_prefixes:
                        if not any(ev["type"].startswith(prefix) for prefix in type_prefixes):
                            continue
                    if session_id and ev.get("session_id") and ev.get("session_id") != session_id:
                        continue
                    last_id = max(last_id, ev["id"])
                    yield f"event: {ev['type']}\ndata: {json.dumps(ev)}\nid: {ev['id']}\n\n"
                    events_sent += 1
                    if max_events is not None and events_sent >= max_events:
                        return
                # Always advance the cursor even if events were filtered out
                last_id = seen_max_id
                if is_test_mode():
                    break
                await asyncio.sleep(sleep_interval)
        except asyncio.CancelledError:
            # Handle client disconnect gracefully
            pass
        finally:
            return

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream; charset=utf-8",
        headers={
            "Cache-Control": "no-store",
            "Connection": "keep-alive",
        },
    )


@app.get("/v1/events/tool")
async def tool_events_endpoint(
    since_id: Optional[int] = Query(None, description="Get events after this ID"),
    limit: int = Query(50, description="Maximum number of events to return", ge=1, le=200),
    authorization: str | None = Header(None),
    token: str | None = Depends(_resolve_token),
):
    if not _auth_or_token_ok(authorization, token):
        raise HTTPException(401, detail="Invalid API key")
    user = get_user_by_token(token)
    if not user:
        raise HTTPException(401, detail="Missing or invalid user token")
    if user.get("is_disabled"):
        raise HTTPException(403, detail="User is disabled")
    _enforce_maintenance(user)

    event_store = get_event_store()
    
    # Get all events and filter for tool events
    all_events = event_store.get_events(after=since_id, limit=None)["events"]
    tool_events = [ev for ev in all_events if ev["type"].startswith("tool.")]
    
    # Apply limit to filtered results
    tool_events = tool_events[:limit]
    
    return {
        "events": tool_events,
        "count": len(tool_events),
        "limit": limit,
    }


@app.get("/v1/prompts")
async def prompts_endpoint(
    authorization: str | None = Header(None),
    token: str | None = Depends(_resolve_token),
):
    if not _auth_or_token_ok(authorization, token):
        raise HTTPException(401, detail="Invalid API key")
    user = get_user_by_token(token)
    if not user:
        raise HTTPException(401, detail="Missing or invalid user token")
    if user.get("is_disabled"):
        raise HTTPException(403, detail="User is disabled")
    _enforce_maintenance(user)
    admin_flag = is_admin_user(user)
    info = _active_prompt_info(admin_flag)
    return {"build_id": BUILD_ID, "prompt": info, "is_admin": admin_flag}


@app.get("/v1/prompts/admin")
async def prompts_admin_endpoint(
    authorization: str | None = Header(None),
    token: str | None = Depends(_resolve_token),
):
    if not _auth_or_token_ok(authorization, token):
        raise HTTPException(401, detail="Invalid API key")
    user = get_user_by_token(token)
    if not user:
        raise HTTPException(401, detail="Missing or invalid user token")
    if not is_admin_user(user):
        raise HTTPException(403, detail="Admin required")
    if user.get("is_disabled"):
        raise HTTPException(403, detail="User is disabled")
    _enforce_maintenance(user)
    info = _active_prompt_info(True)
    return {"prompt": info, "is_admin": True, "build_id": BUILD_ID}


@app.get("/v1/prompt/active")
async def prompt_active_endpoint(
    authorization: str | None = Header(None),
    token: str | None = Depends(_resolve_token),
):
    if not _auth_or_token_ok(authorization, token):
        raise HTTPException(401, detail="Invalid API key")
    user = get_user_by_token(token)
    if not user:
        raise HTTPException(401, detail="Missing or invalid user token")
    if user.get("is_disabled"):
        raise HTTPException(403, detail="User is disabled")
    _enforce_maintenance(user)
    admin_flag = is_admin_user(user)
    info = _active_prompt_info(admin_flag)
    return {"prompt": info, "is_admin": admin_flag, "build_id": BUILD_ID}


@app.post("/v1/events/{event_id}/dismiss")
async def dismiss_event_endpoint(
    event_id: int,
    authorization: str | None = Header(None),
    token: str | None = Depends(_resolve_token),
):
    if not _auth_or_token_ok(authorization, token):
        raise HTTPException(401, detail="Invalid API key")
    user = get_user_by_token(token)
    if not user:
        raise HTTPException(401, detail="Missing or invalid user token")
    if user.get("is_disabled"):
        raise HTTPException(403, detail="User is disabled")
    _enforce_maintenance(user)
    if mark_read(user["id"], event_id):
        return {"status": "ok"}
    else:
        raise HTTPException(404, detail="Event not found or already dismissed")


@app.get("/v1/notifications")
async def list_notifications_endpoint(
    limit: int = 50,
    since_id: int | None = None,
    authorization: str | None = Header(None),
    token: str | None = Depends(_resolve_token),
):
    if not _auth_or_token_ok(authorization, token):
        raise HTTPException(401, detail="Invalid API key")
    user = get_user_by_token(token)
    if not user:
        raise HTTPException(401, detail="Missing or invalid user token")
    if user.get("is_disabled"):
        raise HTTPException(403, detail="User is disabled")
    _enforce_maintenance(user)
    notifications = list_notifications(user["id"], limit=limit, since_id=since_id)
    return {"notifications": notifications, "items": notifications}


@app.post("/v1/notifications/{notification_id}/read")
async def mark_notification_read_endpoint(
    notification_id: int,
    authorization: str | None = Header(None),
    token: str | None = Depends(_resolve_token),
):
    if not _auth_or_token_ok(authorization, token):
        raise HTTPException(401, detail="Invalid API key")
    user = get_user_by_token(token)
    if not user:
        raise HTTPException(401, detail="Missing or invalid user token")
    if user.get("is_disabled"):
        raise HTTPException(403, detail="User is disabled")
    _enforce_maintenance(user)
    if mark_notification_read(user["id"], notification_id):
        return {"status": "ok"}
    else:
        raise HTTPException(404, detail="Notification not found or already read")


@app.get("/v1/notifications/unread_count")
async def unread_notifications_count_endpoint(
    authorization: str | None = Header(None),
    token: str | None = Depends(_resolve_token),
):
    if not _auth_or_token_ok(authorization, token):
        raise HTTPException(401, detail="Invalid API key")
    user = get_user_by_token(token)
    if not user:
        raise HTTPException(401, detail="Missing or invalid user token")
    if user.get("is_disabled"):
        raise HTTPException(403, detail="User is disabled")
    _enforce_maintenance(user)
    count = get_unread_notifications_count(user["id"])
    return {"count": count}


@app.post("/v1/notifications/mark_all_read")
async def mark_all_notifications_read_endpoint(
    authorization: str | None = Header(None),
    token: str | None = Depends(_resolve_token),
):
    if not _auth_or_token_ok(authorization, token):
        raise HTTPException(401, detail="Invalid API key")
    user = get_user_by_token(token)
    if not user:
        raise HTTPException(401, detail="Missing or invalid user token")
    if user.get("is_disabled"):
        raise HTTPException(403, detail="User is disabled")
    _enforce_maintenance(user)
    mark_all_notifications_read(user["id"])
    return {"status": "ok"}


@app.post("/v1/dev/run-tests")
async def run_tests_endpoint(
    request: Request,
    authorization: str | None = Header(None),
    token: str | None = Depends(_resolve_token),
):
    ctx = _check_admin_auth(request, authorization, token)
    user = ctx.user
    ui_lang = (user.get("lang") if user else None) or "da"
    if is_test_mode():
        return {"ok": True, "test_mode": True}
    run_pytest_and_notify(user["id"], ui_lang)
    return {"ok": True}


@app.patch("/sessions/{session_id}")
async def rename_session_endpoint(
    session_id: str,
    payload: SessionRenameRequest,
    authorization: str | None = Header(None),
    token: str | None = Depends(_resolve_token),
):
    if not _auth_or_token_ok(authorization, token):
        raise HTTPException(401, detail="Invalid API key")
    user = get_user_by_token(token)
    if not user:
        raise HTTPException(401, detail="Missing or invalid user token")
    if user.get("is_disabled"):
        raise HTTPException(403, detail="User is disabled")
    _enforce_maintenance(user)
    if not session_belongs_to_user(session_id, user["id"]):
        raise HTTPException(404, detail="Session not found")
    rename_session(session_id, user["id"], payload.name)
    return {"ok": True}


@app.get("/sessions/{session_id}/prompt")
async def get_session_prompt_endpoint(
    session_id: str,
    authorization: str | None = Header(None),
    token: str | None = Depends(_resolve_token),
):
    if not _auth_or_token_ok(authorization, token):
        raise HTTPException(401, detail="Invalid API key")
    user = get_user_by_token(token)
    if not user:
        raise HTTPException(401, detail="Missing or invalid user token")
    if user.get("is_disabled"):
        raise HTTPException(403, detail="User is disabled")
    _enforce_maintenance(user)
    if not session_belongs_to_user(session_id, user["id"]):
        raise HTTPException(404, detail="Session not found")
    with get_conn() as conn:
        row = conn.execute(
            "SELECT custom_prompt FROM sessions WHERE id = ? AND user_id = ?",
            (session_id, user["id"]),
        ).fetchone()
    return {"prompt": (row["custom_prompt"] if row else None)}


@app.patch("/sessions/{session_id}/prompt")
async def update_session_prompt_endpoint(
    session_id: str,
    payload: SessionPromptRequest,
    authorization: str | None = Header(None),
    token: str | None = Depends(_resolve_token),
):
    if not _auth_or_token_ok(authorization, token):
        raise HTTPException(401, detail="Invalid API key")
    user = get_user_by_token(token)
    if not user:
        raise HTTPException(401, detail="Missing or invalid user token")
    if user.get("is_disabled"):
        raise HTTPException(403, detail="User is disabled")
    _enforce_maintenance(user)
    if not session_belongs_to_user(session_id, user["id"]):
        raise HTTPException(404, detail="Session not found")
    custom = (payload.prompt or "").strip()
    with get_conn() as conn:
        conn.execute(
            "UPDATE sessions SET custom_prompt = ? WHERE id = ? AND user_id = ?",
            (custom or None, session_id, user["id"]),
        )
        conn.commit()
    return {"ok": True}


@app.delete("/sessions/{session_id}")
async def delete_session_endpoint(
    session_id: str,
    authorization: str | None = Header(None),
    token: str | None = Depends(_resolve_token),
):
    if not _auth_or_token_ok(authorization, token):
        raise HTTPException(401, detail="Invalid API key")
    user = get_user_by_token(token)
    if not user:
        raise HTTPException(401, detail="Missing or invalid user token")
    if user.get("is_disabled"):
        raise HTTPException(403, detail="User is disabled")
    _enforce_maintenance(user)
    if not session_belongs_to_user(session_id, user["id"]):
        raise HTTPException(404, detail="Session not found")
    delete_session(session_id, user["id"])
    return {"ok": True}


@app.get("/share/{session_id}")
async def share_session(
    session_id: str,
    authorization: str | None = Header(None),
    token: str | None = Depends(_resolve_token),
):
    if not _auth_or_token_ok(authorization, token):
        raise HTTPException(401, detail="Invalid API key")
    user = get_user_by_token(token)
    if not user:
        raise HTTPException(401, detail="Missing or invalid user token")
    if user.get("is_disabled"):
        raise HTTPException(403, detail="User is disabled")
    _enforce_maintenance(user)
    if not session_belongs_to_user(session_id, user["id"]):
        raise HTTPException(404, detail="Session not found")
    messages = get_all_messages(session_id)
    return {"session_id": session_id, "messages": messages}


@app.get("/search")
async def search_user_content(
    q: str = "",
    authorization: str | None = Header(None),
    token: str | None = Depends(_resolve_token),
):
    if not _auth_or_token_ok(authorization, token):
        raise HTTPException(401, detail="Invalid API key")
    user = get_user_by_token(token)
    if not user:
        raise HTTPException(401, detail="Missing or invalid user token")
    if user.get("is_disabled"):
        raise HTTPException(403, detail="User is disabled")
    _enforce_maintenance(user)
    query = (q or "").strip()
    if len(query) < 2:
        return {"results": []}
    like = f"%{query}%"
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT s.id, s.name, s.created_at, m.content, m.created_at AS message_created "
            "FROM messages m JOIN sessions s ON m.session_id = s.id "
            "WHERE s.user_id = ? AND m.content LIKE ? "
            "ORDER BY m.created_at DESC LIMIT 8",
            (user["id"], like),
        ).fetchall()
    results = []
    for r in rows:
        content = r["content"] or ""
        snippet = content.replace("\n", " ").strip()
        if len(snippet) > 140:
            snippet = snippet[:140].rstrip() + "..."
        results.append(
            {
                "session_id": r["id"],
                "session_name": r["name"] or r["id"],
                "session_created_at": r["created_at"],
                "snippet": snippet,
                "message_created_at": r["message_created"],
            }
        )
    with get_conn() as conn:
        notes = conn.execute(
            "SELECT id, title, content, created_at FROM notes WHERE user_id = ? AND (content LIKE ? OR title LIKE ?) "
            "ORDER BY created_at DESC LIMIT 5",
            (user["id"], like, like),
        ).fetchall()
        files = conn.execute(
            "SELECT id, original_name, created_at FROM user_files WHERE user_id = ? AND original_name LIKE ? ORDER BY created_at DESC LIMIT 5",
            (user["id"], like),
        ).fetchall()
    for n in notes:
        snippet = (n["content"] or "").replace("\n", " ").strip()
        if len(snippet) > 120:
            snippet = snippet[:120].rstrip() + "..."
        results.append(
            {
                "note_id": n["id"],
                "note_title": n["title"] or f"Note {n['id']}",
                "snippet": snippet,
                "note_created_at": n["created_at"],
                "type": "note",
            }
        )
    for f in files:
        results.append(
            {
                "file_id": f["id"],
                "file_name": f["original_name"],
                "file_created_at": f["created_at"],
                "type": "file",
            }
        )
    return {"results": results}


@app.get("/files/{file_path:path}")
async def download_file(
    file_path: str,
    background_tasks: BackgroundTasks,
    authorization: str | None = Header(None),
    token: str | None = Depends(_resolve_token),
):
    if not _auth_or_token_ok(authorization, token):
        raise HTTPException(401, detail="Invalid API key")
    user = get_user_by_token(token)
    if not user:
        raise HTTPException(401, detail="Missing or invalid user token")
    if user.get("is_disabled"):
        raise HTTPException(403, detail="User is disabled")
    try:
        full = safe_path(user["username"], file_path)
    except Exception:
        raise HTTPException(400, detail="Invalid file path")
    if not full.exists():
        raise HTTPException(404, detail="File not found")
    if full.name.startswith("tmp_"):
        background_tasks.add_task(full.unlink)
    return FileResponse(path=str(full), filename=full.name, media_type="application/octet-stream")


def _serve_download_token(
    token: str,
    user: dict,
    background_tasks: BackgroundTasks,
    file: str | None = None,
) -> FileResponse:
    entry = get_download_token(token)
    if not entry:
        raise HTTPException(404, detail="Download link udløbet")
    if entry.get("user_id") != user.get("id"):
        raise HTTPException(403, detail="Download link tilhører en anden bruger")
    if file and file != entry.get("file_path"):
        raise HTTPException(400, detail="Ugyldigt filnavn")
    try:
        expires_at = datetime.fromisoformat(entry.get("expires_at", ""))
        if expires_at <= datetime.now(timezone.utc):
            raise HTTPException(410, detail="Download link udløbet")
    except HTTPException:
        raise
    except Exception:
        pass
    try:
        full = safe_path(user["username"], entry.get("file_path") or "")
    except Exception:
        raise HTTPException(400, detail="Invalid file path")
    if not full.exists():
        raise HTTPException(404, detail="File not found")
    background_tasks.add_task(finalize_download, token, user["username"])
    return FileResponse(path=str(full), filename=full.name, media_type="application/octet-stream")


@app.get("/download")
async def download_token_file(
    token: str,
    background_tasks: BackgroundTasks,
    file: str | None = None,
    session_id: str | None = None,
    authorization: str | None = Header(None),
    x_user_token: str | None = Depends(_resolve_token),
):
    if not _auth_or_token_ok(authorization, x_user_token):
        raise HTTPException(401, detail="Invalid API key")
    user = get_user_by_token(x_user_token)
    if not user:
        raise HTTPException(401, detail="Missing or invalid user token")
    if user.get("is_disabled"):
        raise HTTPException(403, detail="User is disabled")
    return _serve_download_token(token, user, background_tasks, file=file)


@app.get("/d/{token}")
async def download_short(
    token: str,
    background_tasks: BackgroundTasks,
    authorization: str | None = Header(None),
    x_user_token: str | None = Depends(_resolve_token),
):
    if not _auth_or_token_ok(authorization, x_user_token):
        raise HTTPException(401, detail="Invalid API key")
    user = get_user_by_token(x_user_token)
    if not user:
        raise HTTPException(401, detail="Missing or invalid user token")
    if user.get("is_disabled"):
        raise HTTPException(403, detail="User is disabled")
    return _serve_download_token(token, user, background_tasks)


@app.post("/files/upload")
async def upload_file(
    file: UploadFile = File(...),
    authorization: str | None = Header(None),
    token: str | None = Depends(_resolve_token),
):
    if not _auth_or_token_ok(authorization, token):
        raise HTTPException(401, detail="Invalid API key")
    user = get_user_by_token(token)
    if not user:
        raise HTTPException(401, detail="Missing or invalid user token")
    if user.get("is_disabled"):
        raise HTTPException(403, detail="User is disabled")
    data = await file.read()
    if not is_admin_user(user):
        max_bytes = 10 * 1024 * 1024
        if len(data) > max_bytes:
            raise HTTPException(413, detail="Filen er for stor. Maks 10 MB for almindelige brugere.")
    info = save_upload(user["id"], user["username"], file.filename, file.content_type, data)
    url = f"/files/{UPLOAD_DIR_NAME}/{info['stored_name']}"
    return {"file": info, "url": url}


@app.get("/files")
async def list_user_files(
    authorization: str | None = Header(None),
    token: str | None = Depends(_resolve_token),
):
    if not _auth_or_token_ok(authorization, token):
        raise HTTPException(401, detail="Invalid API key")
    user = get_user_by_token(token)
    if not user:
        raise HTTPException(401, detail="Missing or invalid user token")
    if user.get("is_disabled"):
        raise HTTPException(403, detail="User is disabled")
    _enforce_maintenance(user)
    _cleanup_user_assets(user)
    return {"files": list_uploads(user["id"])}


@app.post("/files/{file_id}/keep")
async def keep_file(
    file_id: int,
    authorization: str | None = Header(None),
    token: str | None = Depends(_resolve_token),
):
    if not _auth_or_token_ok(authorization, token):
        raise HTTPException(401, detail="Invalid API key")
    user = get_user_by_token(token)
    if not user:
        raise HTTPException(401, detail="Missing or invalid user token")
    if user.get("is_disabled"):
        raise HTTPException(403, detail="User is disabled")
    ok = keep_upload(user["id"], file_id)
    return {"ok": ok}


@app.delete("/files/{file_id}")
async def delete_file(
    file_id: int,
    authorization: str | None = Header(None),
    token: str | None = Depends(_resolve_token),
):
    if not _auth_or_token_ok(authorization, token):
        raise HTTPException(401, detail="Invalid API key")
    user = get_user_by_token(token)
    if not user:
        raise HTTPException(401, detail="Missing or invalid user token")
    if user.get("is_disabled"):
        raise HTTPException(403, detail="User is disabled")
    ok = delete_upload(user["id"], user["username"], file_id)
    return {"ok": ok}


def _require_admin(user: dict):
    if not is_admin_user(user):
        raise HTTPException(403, detail="Admin access required")


@app.get("/admin/users")
async def admin_list_users(
    request: Request,
    authorization: str | None = Header(None),
    token: str | None = Depends(_resolve_token),
):
    _check_admin_auth(request, authorization, token)
    return {"users": []}


@app.patch("/admin/users/{username}")
async def admin_update_user(
    username: str,
    request: Request,
    authorization: str | None = Header(None),
    token: str | None = Depends(_resolve_token),
    payload: dict = None,
):
    _check_admin_auth(request, authorization, token)
    payload = payload or {}
    disabled = payload.get("disabled")
    is_admin = payload.get("is_admin")
    email = payload.get("email")
    full_name = payload.get("full_name")
    last_name = payload.get("last_name")
    city = payload.get("city")
    phone = payload.get("phone")
    note = payload.get("note")
    new_password = payload.get("new_password")
    monthly_limit_mb = payload.get("monthly_limit_mb")
    credits_mb = payload.get("credits_mb")
    with get_conn() as conn:
        if disabled is not None:
            conn.execute("UPDATE users SET is_disabled = ? WHERE username = ?", (1 if disabled else 0, username))
        if is_admin is not None:
            conn.execute("UPDATE users SET is_admin = ? WHERE username = ?", (1 if is_admin else 0, username))
        if email is not None:
            conn.execute("UPDATE users SET email = ? WHERE username = ?", (email, username))
        if full_name is not None:
            conn.execute("UPDATE users SET full_name = ? WHERE username = ?", (full_name, username))
        if last_name is not None:
            conn.execute("UPDATE users SET last_name = ? WHERE username = ?", (last_name, username))
        if city is not None:
            conn.execute("UPDATE users SET city = ? WHERE username = ?", (city, username))
        if phone is not None:
            conn.execute("UPDATE users SET phone = ? WHERE username = ?", (phone, username))
        if note is not None:
            conn.execute("UPDATE users SET note = ? WHERE username = ?", (note, username))
        if new_password:
            from jarvis.auth import _hash_password
            conn.execute(
                "UPDATE users SET password_hash = ? WHERE username = ?",
                (_hash_password(new_password), username),
            )
        conn.commit()
    if monthly_limit_mb is not None or credits_mb is not None:
        with get_conn() as conn:
            row = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        if row:
            limit_val = int(monthly_limit_mb) if monthly_limit_mb is not None else _get_user_quota(row["id"])[0]
            credits_val = int(credits_mb) if credits_mb is not None else _get_user_quota(row["id"])[1]
            _set_user_quota(row["id"], limit_val, credits_val)
    return {"ok": True}


@app.delete("/admin/users/{username}")
async def admin_delete_user_by_name(
    username: str,
    request: Request,
    authorization: str | None = Header(None),
    token: str | None = Depends(_resolve_token),
):
    ctx = _check_admin_auth(request, authorization, token)
    if ctx.user["username"] == username:
        raise HTTPException(400, detail={"ok": False, "error": {"type": "BadRequest", "message": "Cannot delete yourself"}})
    with get_conn() as conn:
        row = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
        if not row:
            raise HTTPException(404, detail={"ok": False, "error": {"type": "NotFound", "message": "User not found"}})
        conn.execute("DELETE FROM sessions WHERE user_id = ?", (row["id"],))
        conn.execute("DELETE FROM users WHERE id = ?", (row["id"],))
        conn.commit()
    return {"ok": True}


@app.get("/admin/sessions")
async def admin_list_sessions(
    request: Request,
    username: str | None = None,
    authorization: str | None = Header(None),
    token: str | None = Depends(_resolve_token),
):
    ctx = _check_admin_auth(request, authorization, token)
    with get_conn() as conn:
        target = username or ctx.user["username"]
        row = conn.execute("SELECT id FROM users WHERE username = ?", (target,)).fetchone()
        if not row:
            raise HTTPException(404, detail={"ok": False, "error": {"type": "NotFound", "message": "User not found"}})
        sessions = conn.execute(
            "SELECT id, name, created_at FROM sessions WHERE user_id = ? ORDER BY created_at DESC",
            (row["id"],),
        ).fetchall()
    result = []
    with get_conn() as conn:
        for s in sessions:
            size = conn.execute(
                "SELECT SUM(LENGTH(content)) as size FROM messages WHERE session_id = ?",
                (s["id"],),
            ).fetchone()["size"] or 0
            item = dict(s)
            item["size_bytes"] = int(size)
            result.append(item)
    return {"sessions": result}


@app.get("/admin/online-users")
async def admin_online_users(
    request: Request,
    authorization: str | None = Header(None),
    token: str | None = Depends(_resolve_token),
):
    _check_admin_auth(request, authorization, token)
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=5)
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, username, email, full_name, last_name, last_seen FROM users WHERE last_seen IS NOT NULL",
        ).fetchall()
    online = []
    for r in rows:
        try:
            seen = datetime.fromisoformat(r["last_seen"])
        except Exception:
            continue
        if seen >= cutoff:
            online.append(dict(r))
    return {"users": online}


@app.delete("/admin/sessions/{session_id}")
async def admin_delete_session(
    session_id: str,
    request: Request,
    authorization: str | None = Header(None),
    token: str | None = Depends(_resolve_token),
):
    _check_admin_auth(request, authorization, token)
    with get_conn() as conn:
        conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM session_state WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        conn.commit()
    return {"ok": True}


@app.post("/admin/sessions/rename-empty")
async def admin_rename_empty_sessions(
    request: Request,
    authorization: str | None = Header(None),
    token: str | None = Depends(_resolve_token),
):
    _check_admin_auth(request, authorization, token)
    with get_conn() as conn:
        user_ids = [row["id"] for row in conn.execute("SELECT id FROM users").fetchall()]
    updated = 0
    for uid in user_ids:
        updated += _rename_empty_sessions(uid)
    return {"updated": updated}


@app.post("/admin/users")
async def admin_create_user(
    payload: AdminCreateRequest,
    request: Request,
    authorization: str | None = Header(None),
    token: str | None = Depends(_resolve_token),
):
    _check_admin_auth(request, authorization, token)
    try:
        created = register_user(
            payload.username,
            payload.password,
            1 if payload.is_admin else 0,
            email=payload.email,
            full_name=payload.full_name,
            last_name=payload.last_name,
            city=payload.city,
            phone=payload.phone,
            note=payload.note,
        )
    except sqlite3.IntegrityError:
        raise HTTPException(400, detail={"ok": False, "error": {"type": "BadRequest", "message": "Username already exists"}})
    return _public_user(created)


@app.post("/admin/users/{user_id}/disable")
async def admin_disable_user(
    user_id: int,
    payload: AdminDisableRequest,
    request: Request,
    authorization: str | None = Header(None),
    token: str | None = Depends(_resolve_token),
):
    _check_admin_auth(request, authorization, token)
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET is_disabled = ? WHERE id = ?",
            (1 if payload.is_disabled else 0, user_id),
        )
        conn.commit()
    return {"ok": True}


@app.delete("/admin/users/{user_id}")
async def admin_delete_user(
    user_id: int,
    request: Request,
    authorization: str | None = Header(None),
    token: str | None = Depends(_resolve_token),
):
    ctx = _check_admin_auth(request, authorization, token)
    if ctx.user and ctx.user["id"] == user_id:
        raise HTTPException(400, detail={"ok": False, "error": {"type": "BadRequest", "message": "Cannot delete yourself"}})
    with get_conn() as conn:
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
    return {"ok": True}


@app.post("/v1/dev/run-tests")
async def dev_run_tests(
    request: Request,
    authorization: str | None = Header(None),
    token: str | None = Depends(_resolve_token),
):
    ctx = _check_admin_auth(request, authorization, token)
    user = ctx.user
    run_pytest_and_notify(user["id"], ui_lang=user.get("lang") or "da")
    return {"ok": True}


@app.post("/v1/chat/completions")
async def chat(
    req: Request,
    authorization: str | None = Header(None),
    token: str | None = Depends(_resolve_token),
    x_session_id: str | None = Header(None),
    x_ui_lang: str | None = Header(None),
):
    if not _auth_or_token_ok(authorization, token):
        raise HTTPException(401, detail="Invalid API key")

    body = await req.json()
    prompt = _extract_prompt(body)
    ui_lang = x_ui_lang or body.get("ui_lang")
    model = body.get("model") or os.getenv("OLLAMA_MODEL", "unknown")
    stream = bool(body.get("stream", False))
    allowed_tools = body.get("tools_allowed")
    if not isinstance(allowed_tools, list):
        allowed_tools = None

    logged_in = bool(token)
    user = _resolve_user(token)
    _enforce_maintenance(user)
    try:
        session_id = _resolve_session_id(user, x_session_id, logged_in)
    except HTTPException as exc:
        if isinstance(exc.detail, dict):
            return JSONResponse(status_code=exc.status_code, content=exc.detail)
        raise
    _debug(f"📨 chat: user={user['username']} session={session_id} stream={stream} prompt={prompt!r}")
    
    # Publish chat.user_message event
    message_id = f"chatcmpl-{uuid.uuid4().hex}"
    if prompt:
        text_preview = prompt[:120] if len(prompt) > 120 else prompt
        try:
            publish("chat.user_message", {
                "session_id": session_id,
                "message_id": message_id,
                "text_preview": text_preview,
                "ts": time.time(),
            })
        except Exception:
            pass
    
    if prompt and _contains_sensitive(prompt):
        if session_id:
            with get_conn() as conn:
                conn.execute(
                    "DELETE FROM messages WHERE session_id = ? AND role = ? AND content = ?",
                    (session_id, "user", prompt),
                )
                conn.commit()
        purge_user_memory(user["username"])
        reply = (
            "Jeg kan ikke hjælpe med pinkoder, kortnumre eller andre private koder. "
            "Slet dem fra chatten nu, og skift koder med det samme. "
            "Jeg har ikke gemt oplysningerne."
        )
        if session_id:
            add_message(session_id, "assistant", reply)
        if stream:
            def sensitive_gen():
                stream_id = f"chatcmpl-{uuid.uuid4().hex}"
                for chunk in _stream_chunks(reply, model, stream_id=stream_id, session_id=session_id):
                    yield chunk
                yield "data: [DONE]\n\n"
            return StreamingResponse(sensitive_gen(), media_type="text/event-stream")
        return {
            "id": f"chatcmpl-{uuid.uuid4().hex}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "server_time": datetime.now(timezone.utc).isoformat(),
            "session_id": session_id,
            "choices": [
                {"index": 0, "message": {"role": "assistant", "content": reply}, "finish_reason": "stop"}
            ],
        }
    if session_id and prompt:
        with get_conn() as conn:
            count = conn.execute(
                "SELECT COUNT(*) as c FROM messages WHERE session_id = ?",
                (session_id,),
            ).fetchone()["c"]
        if count == 0:
            name = user.get("username", "")
            try:
                prof = get_user_profile(user["username"])
                if prof and prof.get("full_name"):
                    name = prof["full_name"].split()[0]
            except Exception:
                pass
            intro = f"Hej {name}, jeg er JARVIS — din personlige assistent. Hvordan kan jeg hjælpe?"
            add_message(session_id, "assistant", intro)
        with get_conn() as conn:
            row = conn.execute(
                "SELECT content, created_at FROM messages WHERE session_id = ? AND role = ? ORDER BY id DESC LIMIT 1",
                (session_id, "user"),
            ).fetchone()
        should_add = True
        if row and row["content"] == prompt:
            try:
                last_ts = datetime.fromisoformat(row["created_at"])
                if (datetime.now(timezone.utc) - last_ts).total_seconds() < 3:
                    should_add = False
            except Exception:
                pass
        if should_add:
            add_message(session_id, "user", prompt)
        if logged_in and session_id:
            with get_conn() as conn:
                row = conn.execute(
                    "SELECT name FROM sessions WHERE id = ? AND user_id = ?",
                    (session_id, user["id"]),
                ).fetchone()
                current_name = (row["name"] if row else "") or ""
                if current_name.strip().lower() in {"", "ny chat"}:
                    auto_name = _auto_session_name(prompt, None)
                    conn.execute(
                        "UPDATE sessions SET name = ? WHERE id = ? AND user_id = ?",
                        (auto_name, session_id, user["id"]),
                    )
                    conn.commit()

    if user and is_admin_user(user) and prompt:
        banner_text = None
        lowered = prompt.strip().lower()
        if lowered.startswith("/banner"):
            banner_text = prompt.strip()[7:].strip()
        elif lowered.startswith("banner:"):
            banner_text = prompt.split(":", 1)[1].strip()
        if lowered.startswith("/system-prompt") or lowered.startswith("/systemprompt") or lowered.startswith("system prompt:"):
            _update_system_prompt_setting()
            reply = _butlerize_text("SYSTEM_PROMPT opdateret.", user)
            if session_id:
                add_message(session_id, "assistant", reply)
            if stream:
                def prompt_gen():
                    stream_id = f"chatcmpl-{uuid.uuid4().hex}"
                    for chunk in _stream_chunks(reply, model, stream_id=stream_id, session_id=session_id):
                        yield chunk
                    yield "data: [DONE]\n\n"
                return StreamingResponse(prompt_gen(), media_type="text/event-stream")
            return {
                "id": f"chatcmpl-{uuid.uuid4().hex}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": model,
                "server_time": datetime.now(timezone.utc).isoformat(),
                "session_id": session_id,
                "choices": [
                    {"index": 0, "message": {"role": "assistant", "content": reply}, "finish_reason": "stop"}
                ],
            }
        if banner_text is not None:
            if banner_text.lower() in {"clear", "ryd", "fjern"}:
                banner_text = ""
            with get_conn() as conn:
                raw = _get_setting("banner_messages", "")
                entries = _filter_banner_entries(_parse_banner_entries(raw))
                if banner_text:
                    entries.append({"text": banner_text, "ts": datetime.now(timezone.utc).isoformat()})
                else:
                    entries = []
                conn.execute(
                    "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                    ("banner_messages", json.dumps(entries)),
                )
                conn.commit()
            reply = _butlerize_text(
                "Topbanner opdateret." if banner_text else "Topbanner ryddet.", user
            )
            if session_id:
                add_message(session_id, "assistant", reply)
            if stream:
                def banner_gen():
                    stream_id = f"chatcmpl-{uuid.uuid4().hex}"
                    for chunk in _stream_chunks(reply, model, stream_id=stream_id, session_id=session_id):
                        yield chunk
                    yield "data: [DONE]\n\n"
                return StreamingResponse(banner_gen(), media_type="text/event-stream")
            return {
                "id": f"chatcmpl-{uuid.uuid4().hex}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": model,
                "server_time": datetime.now(timezone.utc).isoformat(),
                "session_id": session_id,
                "choices": [
                    {"index": 0, "message": {"role": "assistant", "content": reply}, "finish_reason": "stop"}
                ],
            }

    quota_warning = None
    expiry_warning = None
    note_reminder = None
    if user:
        _cleanup_user_assets(user)
        expiry_warning = _expiry_warning_text(user)
        note_reminder = _note_reminder_text(user)
    if user and not is_admin_user(user):
        limit_mb, credits_mb = _get_user_quota(user["id"])
        used_bytes = _monthly_usage_bytes(user["id"])
        used_mb = _bytes_to_mb(used_bytes)
        total_mb = max(0, limit_mb + credits_mb)
        if total_mb > 0 and used_mb >= total_mb:
            quota_warning = "Kvota opbrugt"
            reply = (
                "Din maanedlige kvota er opbrugt. Den nulstilles den 1. i naeste maaned. "
                "Du kan anmode om mere plads hos admin."
            )
            if note_reminder:
                reply = f"{note_reminder}\n\n{reply}"
            if expiry_warning:
                reply = f"{expiry_warning}\n\n{reply}"
            if session_id:
                add_message(session_id, "assistant", reply)
            if stream:
                def quota_gen():
                    if note_reminder:
                        yield (
                            "event: meta\n"
                            f"data: {json.dumps({'meta': {'note_reminder': note_reminder}})}\n\n"
                        )
                    if expiry_warning:
                        yield (
                            "event: meta\n"
                            f"data: {json.dumps({'meta': {'expiry_warning': expiry_warning}})}\n\n"
                        )
                    yield (
                        "event: meta\n"
                        f"data: {json.dumps({'meta': {'quota_warning': quota_warning}})}\n\n"
                    )
                    stream_id = f"chatcmpl-{uuid.uuid4().hex}"
                    for chunk in _stream_chunks(reply, model, stream_id=stream_id, session_id=session_id):
                        yield chunk
                    yield "data: [DONE]\n\n"
                return StreamingResponse(quota_gen(), media_type="text/event-stream")
            response = {
                "id": f"chatcmpl-{uuid.uuid4().hex}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": model,
                "server_time": datetime.now(timezone.utc).isoformat(),
                "session_id": session_id,
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": reply},
                        "finish_reason": "stop",
                    }
                ],
            }
            response["meta"] = {"quota_warning": quota_warning}
            if expiry_warning:
                response["meta"]["expiry_warning"] = expiry_warning
            if note_reminder:
                response["meta"]["note_reminder"] = note_reminder
            return response
        if session_id:
            quota_warning = _quota_warning(user["id"], session_id, used_mb, limit_mb, credits_mb)

    if stream:
        # EventBus-based streaming: agent emits events, server consumes them
        # This is the canonical streaming implementation - EventBus is the single source
        async def generator():
            from jarvis.events import subscribe_async
            
            trace_id = uuid.uuid4().hex
            stream_id = f"chatcmpl-{uuid.uuid4().hex}"
            deadline = time.monotonic() + MAX_STREAM_SECONDS
            done_sent = False
            agent_start_time = time.time()
            chat_start_time = time.time()
            
            # Subscribe to agent.stream events for this trace_id
            event_queue = await subscribe_async(
                ["agent.stream.start", "agent.stream.delta", "agent.stream.final", "agent.stream.error", "agent.stream.status"],
                session_filter=session_id
            )
            
            try:
                # Emit chat.start
                try:
                    publish("chat.start", {
                        "session_id": session_id,
                        "trace_id": trace_id,
                        "request_id": stream_id,
                        "model": model,
                        "ts": chat_start_time,
                    })
                except Exception:
                    pass
                # Emit agent.start event
                try:
                    publish("agent.start", {
                        "session_id": session_id,
                        "trace_id": trace_id,
                        "prompt_preview": (prompt or "")[:120] if prompt else "",
                    })
                except Exception:
                    pass  # EventBus unavailable, continue

                # Emit status via EventBus so the stream reads only from EventBus
                try:
                    publish(
                        "agent.stream.status",
                        {
                            "status": "thinking",
                            "trace_id": trace_id,
                            "session_id": session_id,
                        },
                    )
                except Exception:
                    pass
                tool_hint = choose_tool(prompt, allowed_tools=allowed_tools)
                if tool_hint in {"news", "search", "weather", "currency"}:
                    try:
                        publish(
                            "agent.stream.status",
                            {
                                "status": "using_tool",
                                "tool": tool_hint,
                                "trace_id": trace_id,
                                "session_id": session_id,
                            },
                        )
                    except Exception:
                        pass
                
                # Start agent in background task
                agent_task = None
                agent_result = None
                agent_error = None
                ui_city = req.headers.get("x-ui-city")
                
                async def run_agent_task():
                    nonlocal agent_result, agent_error
                    try:
                        # Run agent
                        result = await asyncio.to_thread(
                            run_agent,
                            user["username"],
                            prompt,
                            session_id=session_id,
                            allowed_tools=allowed_tools,
                            ui_city=ui_city,
                            ui_lang=ui_lang,
                        )
                        agent_result = result
                        
                        # Process result and emit streaming events
                        if result.get("meta", {}).get("tool_used"):
                            # Emit agent.stream.status event for tool usage
                            try:
                                publish("agent.stream.status", {
                                    "session_id": session_id,
                                    "message_id": stream_id,
                                    "trace_id": trace_id,
                                    "status": "writing",
                                    "tool": result.get("meta", {}).get("tool"),
                                })
                            except Exception:
                                pass
                        
                        text_stream = _butlerize_text(result.get("text", ""), user)
                        if note_reminder:
                            text_stream = f"{note_reminder}\n\n{text_stream}"
                        if expiry_warning:
                            text_stream = f"{expiry_warning}\n\n{text_stream}"
                        if quota_warning:
                            text_stream = f"{quota_warning}\n\n{text_stream}"
                        
                        # Emit EventBus events for streaming (canonical approach)
                        # Agent execution only emits events via EventBus - no direct streaming
                        await asyncio.to_thread(lambda: list(_stream_text_events(
                            text_stream,
                            model,
                            stream_id=stream_id,
                            trace_id=trace_id,
                            session_id=session_id,
                        )))
                        
                    except asyncio.CancelledError:
                        # CancelledError should not emit error events - it's handled by the main generator
                        raise  # Re-raise to be handled by main generator
                    except Exception as exc:
                        agent_error = exc
                        # Emit agent.error event
                        try:
                            publish("agent.error", {
                                "session_id": session_id,
                                "trace_id": trace_id,
                                "error_type": exc.__class__.__name__,
                                "error_message": str(exc),
                            })
                        except Exception:
                            pass
                        # Emit agent.stream.error
                        try:
                            publish("agent.stream.error", {
                                "session_id": session_id,
                                "message_id": stream_id,
                                "trace_id": trace_id,
                                "error_type": "ProviderError",
                                "error_message": "Provider or server error. Please retry.",
                            })
                        except Exception:
                            pass
                
                agent_task = asyncio.create_task(run_agent_task())
                
                # Process streaming events
                tokens_emitted = False
                while True:
                    try:
                        event_type, payload = await asyncio.wait_for(event_queue.get(), timeout=0.1)
                        
                        if event_type == "agent.stream.start":
                            # Yield the head chunk
                            created = int(time.time())
                            head = {
                                "id": stream_id,
                                "object": "chat.completion.chunk",
                                "created": created,
                                "model": model,
                                "trace_id": trace_id,
                                "session_id": session_id,
                                "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}],
                            }
                            yield f"data: {json.dumps(head)}\n\n"
                        
                        elif event_type == "agent.stream.delta":
                            # Yield data chunk
                            created = int(time.time())
                            data = {
                                "id": stream_id,
                                "object": "chat.completion.chunk",
                                "created": created,
                                "model": model,
                                "trace_id": trace_id,
                                "session_id": session_id,
                                "choices": [{"index": 0, "delta": {"content": payload["token"]}, "finish_reason": None}],
                            }
                            yield f"data: {json.dumps(data)}\n\n"
                            # Emit chat.token (small payload)
                            try:
                                publish("chat.token", {
                                    "session_id": session_id,
                                    "trace_id": trace_id,
                                    "request_id": stream_id,
                                    "token": payload.get("token"),
                                    "sequence": payload.get("sequence"),
                                })
                            except Exception:
                                pass
                            tokens_emitted = True
                        
                        elif event_type == "agent.stream.status":
                            # Yield status event for tool usage
                            yield _status_event(
                                payload["status"],
                                payload.get("tool"),
                                trace_id=trace_id,
                                session_id=session_id,
                            )
                        
                        elif event_type == "agent.stream.final":
                            if not tokens_emitted:
                                # Ensure at least one chat.token event for streaming (guarantees chat.token before chat.end)
                                try:
                                    publish("chat.token", {
                                        "session_id": session_id,
                                        "trace_id": trace_id,
                                        "request_id": stream_id,
                                        "token": payload.get("text") or "",
                                        "sequence": payload.get("parts"),
                                        "final": True,
                                    })
                                except Exception:
                                    pass
                            # Yield tail chunk and DONE
                            created = int(time.time())
                            tail = {
                                "id": stream_id,
                                "object": "chat.completion.chunk",
                                "created": created,
                                "model": model,
                                "trace_id": trace_id,
                                "session_id": session_id,
                                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                            }
                            yield f"data: {json.dumps(tail)}\n\n"
                            yield "data: [DONE]\n\n"
                            done_sent = True
                            try:
                                publish("chat.end", {
                                    "session_id": session_id,
                                    "trace_id": trace_id,
                                    "request_id": stream_id,
                                    "ok": True,
                                    "duration_ms": int((time.time() - chat_start_time) * 1000),
                                })
                            except Exception:
                                pass
                            break
                        
                        elif event_type == "agent.stream.error":
                            yield _stream_error_event(
                                payload.get("error_message", "Stream error"),
                                payload.get("error_type", "Error"),
                                trace_id,
                                session_id,
                            )
                            yield "data: [DONE]\n\n"
                            try:
                                publish("chat.error", {
                                    "session_id": session_id,
                                    "trace_id": trace_id,
                                    "request_id": stream_id,
                                    "error": payload,
                                })
                                publish("chat.end", {
                                    "session_id": session_id,
                                    "trace_id": trace_id,
                                    "request_id": stream_id,
                                    "ok": False,
                                    "duration_ms": int((time.time() - chat_start_time) * 1000),
                                })
                            except Exception:
                                pass
                            return
                            
                    except asyncio.TimeoutError:
                        # Check if agent task is done - if so, wait a bit more for any remaining events
                        if agent_task and agent_task.done():
                            # Wait a short time for any remaining events
                            try:
                                event_type, payload = await asyncio.wait_for(event_queue.get(), timeout=0.5)
                                # Process the event (same logic as above)
                                if event_type == "agent.stream.start":
                                    created = int(time.time())
                                    head = {
                                        "id": stream_id,
                                        "object": "chat.completion.chunk",
                                        "created": created,
                                        "model": model,
                                        "trace_id": trace_id,
                                        "session_id": session_id,
                                        "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}],
                                    }
                                    yield f"data: {json.dumps(head)}\n\n"
                                
                                elif event_type == "agent.stream.delta":
                                    created = int(time.time())
                                    data = {
                                        "id": stream_id,
                                        "object": "chat.completion.chunk",
                                        "created": created,
                                        "model": model,
                                        "trace_id": trace_id,
                                        "session_id": session_id,
                                        "choices": [{"index": 0, "delta": {"content": payload["token"]}, "finish_reason": None}],
                                    }
                                    yield f"data: {json.dumps(data)}\n\n"
                                
                                elif event_type == "agent.stream.final":
                                    created = int(time.time())
                                    tail = {
                                        "id": stream_id,
                                        "object": "chat.completion.chunk",
                                        "created": created,
                                        "model": model,
                                        "trace_id": trace_id,
                                        "session_id": session_id,
                                        "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                                    }
                                    yield f"data: {json.dumps(tail)}\n\n"
                                    yield "data: [DONE]\n\n"
                                    done_sent = True
                                    break
                                
                                elif event_type == "agent.stream.status":
                                    yield _status_event(
                                        payload["status"],
                                        payload.get("tool"),
                                        trace_id=trace_id,
                                        session_id=session_id,
                                    )
                                
                                elif event_type == "agent.stream.error":
                                    yield _stream_error_event(
                                        payload.get("error_message", "Stream error"),
                                        payload.get("error_type", "Error"),
                                        trace_id,
                                        session_id,
                                    )
                                    yield "data: [DONE]\n\n"
                                    return
                            except asyncio.TimeoutError:
                                # No more events, break
                                break
                        
                        # Check for disconnect/timeout
                        if await req.is_disconnected():
                            if agent_task and not agent_task.done():
                                agent_task.cancel()
                            try:
                                publish("agent.stream.error", {
                                    "message_id": stream_id,
                                    "session_id": session_id,
                                    "trace_id": trace_id,
                                    "error_type": "ClientDisconnected",
                                    "error_message": "Client disconnected during streaming",
                                })
                            except Exception:
                                pass
                            return
                        if time.monotonic() > deadline:
                            if agent_task and not agent_task.done():
                                agent_task.cancel()
                            try:
                                publish("agent.stream.error", {
                                    "message_id": stream_id,
                                    "session_id": session_id,
                                    "trace_id": trace_id,
                                    "error_type": "Timeout",
                                    "error_message": "Streaming timeout",
                                })
                            except Exception:
                                pass
                            yield _stream_error_event(
                                "Streaming timeout. Please retry.",
                                "Timeout",
                                trace_id,
                                session_id,
                            )
                            yield "data: [DONE]\n\n"
                            return
                
                # Wait for agent task to complete
                if agent_task:
                    try:
                        await agent_task
                        if agent_error:
                            raise agent_error
                        result = agent_result
                    except asyncio.CancelledError:
                        _req_logger.info("Streaming run_agent cancelled trace=%s", trace_id)
                        return
                    except Exception as exc:
                        _req_logger.exception("Streaming run_agent failed trace=%s", trace_id)
                        yield _stream_error_event(
                            "Provider or server error. Please retry.",
                            exc.__class__.__name__,
                            trace_id,
                            session_id,
                        )
                        yield "data: [DONE]\n\n"
                        return
                
                yield _status_event("idle", trace_id=trace_id, session_id=session_id)
                
                # Emit agent.done event
                try:
                    publish("agent.done", {
                        "session_id": session_id,
                        "trace_id": trace_id,
                        "duration_ms": int((time.time() - agent_start_time) * 1000),
                    })
                except Exception:
                    pass
                
                rendered_text_stream = result.get("rendered_text")
                payload_data_stream = result.get("data")
                payload_meta_stream = result.get("meta")
                if quota_warning:
                    payload_meta_stream = dict(payload_meta_stream or {})
                    payload_meta_stream["quota_warning"] = quota_warning
                if expiry_warning:
                    payload_meta_stream = dict(payload_meta_stream or {})
                    payload_meta_stream["expiry_warning"] = expiry_warning
                if note_reminder:
                    payload_meta_stream = dict(payload_meta_stream or {})
                    payload_meta_stream["note_reminder"] = note_reminder
                if rendered_text_stream is not None or payload_data_stream is not None or payload_meta_stream is not None:
                    payload = {
                        "rendered_text": rendered_text_stream,
                        "data": payload_data_stream,
                        "meta": payload_meta_stream,
                        "trace_id": trace_id,
                        "session_id": session_id,
                    }
                    yield (
                        "event: meta\n"
                        f"data: {json.dumps(payload)}\n\n"
                    )
                
            except Exception as exc:
                _req_logger.exception("Streaming generator failed trace=%s", trace_id)
                if not done_sent:
                    yield _stream_error_event(
                        "Internal server error",
                        "InternalError",
                        trace_id,
                        session_id,
                    )
                    yield "data: [DONE]\n\n"
            finally:
                # Cleanup
                try:
                    event_queue.cleanup()
                except Exception:
                    pass
                if agent_task and not agent_task.done():
                    agent_task.cancel()

        return StreamingResponse(generator(), media_type="text/event-stream")

    ui_city = req.headers.get("x-ui-city")
    start_time = time.time()
    trace_id = uuid.uuid4().hex
    try:
        # Emit agent.start event
        try:
            publish("agent.start", {
                "session_id": session_id,
                "trace_id": trace_id,
                "prompt_preview": (prompt or "")[:120] if prompt else "",
            })
        except Exception:
            pass  # EventBus unavailable, continue
        # Emit chat.start event for non-stream flow
        try:
            publish("chat.start", {
                "session_id": session_id,
                "request_id": message_id,
                "trace_id": trace_id,
                "model": model,
                "ts": start_time,
            })
        except Exception:
            pass
        
        try:
            result = run_agent(
                user["username"],
                prompt,
                session_id=session_id,
                allowed_tools=allowed_tools,
                ui_city=ui_city,
                ui_lang=ui_lang,
            )
        except Exception as exc:
            try:
                publish("agent.error", {
                    "session_id": session_id,
                    "trace_id": trace_id,
                    "error_type": exc.__class__.__name__,
                    "error_message": str(exc),
                })
            except Exception:
                pass
            raise
        duration_ms = int((time.time() - start_time) * 1000)
        
        # Emit agent.done event
        try:
            publish("agent.done", {
                "session_id": session_id,
                "trace_id": trace_id,
                "duration_ms": duration_ms,
            })
        except Exception:
            pass  # EventBus unavailable, continue
        
        # Process the response text
        text = _butlerize_text(result.get("text", ""), user)
        
        # Emit chat.token event with full text for non-streaming (ensures at least one chat.token before chat.end)
        try:
            publish("chat.token", {
                "session_id": session_id,
                "request_id": message_id,
                "trace_id": trace_id,
                "token": text,
            })
        except Exception:
            pass  # Never crash the request
        
        try:
            publish("chat.end", {
                "session_id": session_id,
                "request_id": message_id,
                "trace_id": trace_id,
                "ok": True,
                "duration_ms": duration_ms,
            })
        except Exception:
            pass
        
        # Publish chat.assistant_message event
        if prompt:
            publish("chat.assistant_message", {
                "session_id": session_id,
                "message_id": message_id,
                "ok": True,
                "text_preview": text_preview,
                "duration_ms": duration_ms,
            })
    except Exception as exc:
        # Emit agent.error event
        try:
            publish("agent.error", {
                "session_id": session_id,
                "trace_id": trace_id,
                "error_type": exc.__class__.__name__,
                "error_message": str(exc),
            })
        except Exception:
            pass  # EventBus unavailable, continue
        
        # Publish chat.error event
        if prompt:
            try:
                publish("chat.error", {
                    "session_id": session_id,
                    "request_id": message_id,
                    "trace_id": trace_id,
                    "error": str(exc),
                    "stage": "agent_processing",
                })
                publish("chat.end", {
                    "session_id": session_id,
                    "request_id": message_id,
                    "trace_id": trace_id,
                    "ok": False,
                    "duration_ms": int((time.time() - start_time) * 1000),
                })
            except Exception:
                pass
        raise
    if note_reminder:
        text = f"{note_reminder}\n\n{text}"
    if expiry_warning:
        text = f"{expiry_warning}\n\n{text}"
    if quota_warning:
        text = f"{quota_warning}\n\n{text}"
    
    # Emit chat.token event with full final text for non-streaming
    try:
        publish("chat.token", {
            "session_id": session_id,
            "request_id": message_id,
            "trace_id": trace_id,
            "token": text,
        })
    except Exception:
        pass  # Never crash the request
    
    rendered_text = result.get("rendered_text")
    payload_data = result.get("data")
    payload_meta = result.get("meta")
    if quota_warning:
        payload_meta = dict(payload_meta or {})
        payload_meta["quota_warning"] = quota_warning
    if expiry_warning:
        payload_meta = dict(payload_meta or {})
        payload_meta["expiry_warning"] = expiry_warning
    if note_reminder:
        payload_meta = dict(payload_meta or {})
        payload_meta["note_reminder"] = note_reminder

    response = {
        "id": f"chatcmpl-{uuid.uuid4().hex}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "server_time": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "finish_reason": "stop",
            }
        ],
    }
    if rendered_text is not None:
        response["rendered_text"] = rendered_text
    if payload_data is not None:
        response["data"] = payload_data
    if payload_meta is not None:
        response["meta"] = payload_meta
    return response


@app.get("/config")
async def config():
    return {"model": os.getenv("OLLAMA_MODEL", "local")}


@app.get("/models")
async def models():
    base = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
    try:
        resp = requests.get(f"{base}/api/tags", timeout=5)
        data = resp.json()
        items = data.get("models", []) if isinstance(data, dict) else []
        names = [m.get("name") for m in items if isinstance(m, dict) and m.get("name")]
        return {"models": names}
    except Exception:
        return {"models": [os.getenv("OLLAMA_MODEL", "local")]}


@app.get("/settings/footer")
async def footer_settings():
    settings = _get_settings(
        [
            "footer_text",
            "footer_support_url",
            "footer_contact_url",
            "footer_license_text",
            "footer_license_url",
            "system_prompt",
            "register_enabled",
            "captcha_enabled",
        ]
    )
    return {
        "text": settings.get("footer_text", f"Jarvis v.1.0.0 (build {BUILD_ID})"),
        "support_url": settings.get("footer_support_url", "#"),
        "contact_url": settings.get("footer_contact_url", "#"),
        "license_text": settings.get("footer_license_text", "Open‑source licens"),
        "license_url": settings.get("footer_license_url", "#"),
    }


@app.get("/settings/brand")
async def brand_settings():
    settings = _get_settings(["brand_top_label", "brand_core_label"])
    return {
        "name": settings.get("brand_core_label", "Jarvis"),
        "short": settings.get("brand_core_label", "Jarvis"),
        "top": settings.get("brand_top_label", "Jarvis"),
        "version": "1.0.0",
    }


@app.get("/v1/build")
async def build_info():
    """Return build information for cache busting"""
    return {"build_id": BUILD_ID}


@app.get("/account/profile")
async def account_profile(
    authorization: str | None = Header(None),
    token: str | None = Depends(_resolve_token),
):
    if not _auth_or_token_ok(authorization, token):
        raise HTTPException(401, detail="Invalid API key")
    user = get_user_by_token(token)
    if not user:
        raise HTTPException(401, detail="Missing or invalid user token")
    if user.get("is_disabled"):
        raise HTTPException(403, detail="User is disabled")
    _enforce_maintenance(user)
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, username, email, full_name, last_name, city, phone, note, created_at, last_seen, is_admin FROM users WHERE id = ?",
            (user["id"],),
        ).fetchone()
    if not row:
        raise HTTPException(404, detail="User not found")
    return dict(row)


@app.get("/account/quota")
async def account_quota(
    authorization: str | None = Header(None),
    token: str | None = Depends(_resolve_token),
):
    if not _auth_or_token_ok(authorization, token):
        raise HTTPException(401, detail="Invalid API key")
    user = get_user_by_token(token)
    if not user:
        raise HTTPException(401, detail="Missing or invalid user token")
    if user.get("is_disabled"):
        raise HTTPException(403, detail="User is disabled")
    limit_mb, credits_mb = _get_user_quota(user["id"])
    used_bytes = _monthly_usage_bytes(user["id"])
    used_mb = _bytes_to_mb(used_bytes)
    total_mb = max(0, limit_mb + credits_mb)
    remaining_mb = max(0, total_mb - used_mb)
    now = datetime.now(timezone.utc)
    next_reset = datetime(now.year + (1 if now.month == 12 else 0), 1 if now.month == 12 else now.month + 1, 1, tzinfo=timezone.utc)
    return {
        "limit_mb": limit_mb,
        "credits_mb": credits_mb,
        "used_mb": round(used_mb, 2),
        "remaining_mb": round(remaining_mb, 2),
        "total_mb": total_mb,
        "reset_at": next_reset.isoformat(),
    }


@app.patch("/account/profile")
async def update_account_profile(
    payload: AccountUpdateRequest,
    authorization: str | None = Header(None),
    token: str | None = Depends(_resolve_token),
):
    if not _auth_ok(authorization):
        raise HTTPException(401, detail="Invalid API key")
    user = get_user_by_token(token)
    if not user:
        raise HTTPException(401, detail="Missing or invalid user token")
    if user.get("is_disabled"):
        raise HTTPException(403, detail="User is disabled")
    with get_conn() as conn:
        if payload.email is not None:
            conn.execute("UPDATE users SET email = ? WHERE id = ?", (payload.email, user["id"]))
        if payload.full_name is not None:
            conn.execute("UPDATE users SET full_name = ? WHERE id = ?", (payload.full_name, user["id"]))
        if payload.last_name is not None:
            conn.execute("UPDATE users SET last_name = ? WHERE id = ?", (payload.last_name, user["id"]))
        if payload.city is not None:
            conn.execute("UPDATE users SET city = ? WHERE id = ?", (payload.city, user["id"]))
        if payload.phone is not None:
            conn.execute("UPDATE users SET phone = ? WHERE id = ?", (payload.phone, user["id"]))
        if payload.note is not None:
            conn.execute("UPDATE users SET note = ? WHERE id = ?", (payload.note, user["id"]))
        if payload.new_password:
            if not payload.current_password or not verify_user_password(user["id"], payload.current_password):
                raise HTTPException(400, detail="Nuværende password er forkert")
            from jarvis.auth import _hash_password
            conn.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?",
                (_hash_password(payload.new_password), user["id"]),
            )
        conn.commit()
    return {"ok": True}


@app.get("/settings/public")
async def public_settings(x_ui_lang: str | None = Header(None)):
    return {
        "maintenance": {
            "enabled": _maintenance_enabled(),
            "message": _maintenance_message(),
        },
        "default_lang": "da",
        "default_theme": "light",
        "features": {
            "captcha": False,
        },
        "banner": _get_setting("banner_text", ""),
        "footer": {
            "text": _get_setting("footer_text", "Jarvis v.1 @ 2026"),
            "support_url": _get_setting("footer_support_url", "#"),
            "contact_url": _get_setting("footer_contact_url", "#"),
            "license_text": _get_setting("footer_license_text", "Open‑source licens"),
            "license_url": _get_setting("footer_license_url", "#"),
        },
    }


@app.get("/v1/brand")
async def v1_brand():
    settings = _get_settings(["brand_top_label", "brand_core_label"])
    return {
        "name": settings.get("brand_core_label", "Jarvis"),
        "short": settings.get("brand_core_label", "Jarvis"),
        "top": settings.get("brand_top_label", "Jarvis"),
        "version": "1.0.0",
    }


@app.get("/v1/settings")
async def v1_settings():
    return {
        "maintenance": {
            "enabled": _maintenance_enabled(),
            "message": _maintenance_message(),
        },
        "default_lang": "da",
        "default_theme": "light",
        "features": {
            "captcha": False,
        },
    }


@app.get("/v1/captcha")
async def v1_captcha():
    return {
        "enabled": False,
    }


@app.get("/status")
async def status():
    # Return status based on application state
    return {
        "ok": app_state.demo_user_ensured and app_state.paths_logged,
        "online": True,
        "version": "1.0.0"
    }


@app.get("/v1/info")
async def v1_info():
    """Return runtime info useful for verifying which codebase is serving requests.

    - `build_id`: cache-busting id
    - `server_file`: the path to this server module
    - `project_root`: the PROJECT_ROOT being used
    - `app_html_exists`: whether ui/app.html exists at PROJECT_ROOT
    """
    try:
        return {
            "build_id": BUILD_ID,
            "server_file": __file__,
            "project_root": str(ROOT),
            "app_html_exists": APP_HTML.exists(),
        }
    except Exception:
        return {"build_id": BUILD_ID, "server_file": str(__file__), "project_root": str(ROOT), "app_html_exists": False}


@app.post("/api/tickets")
async def create_ticket_endpoint(
    payload: TicketCreateRequest,
    authorization: str | None = Header(None),
    token: str | None = Depends(_resolve_token),
):
    if not _auth_ok(authorization):
        raise HTTPException(401, detail="Invalid API key")
    user = get_user_by_token(token)
    if not user:
        raise HTTPException(401, detail="Missing or invalid user token")
    if user.get("is_disabled"):
        raise HTTPException(403, detail="User is disabled")
    priority = payload.priority or "moderat"
    created = create_ticket(user["id"], payload.title, payload.message, priority)
    return {"ticket": created}


@app.get("/api/tickets")
async def list_tickets_endpoint(
    authorization: str | None = Header(None),
    token: str | None = Depends(_resolve_token),
):
    if not _auth_ok(authorization):
        raise HTTPException(401, detail="Invalid API key")
    user = get_user_by_token(token)
    if not user:
        raise HTTPException(401, detail="Missing or invalid user token")
    if user.get("is_disabled"):
        raise HTTPException(403, detail="User is disabled")
    return {"tickets": list_tickets(user["id"])}


@app.get("/api/tickets/{ticket_id}")
async def get_ticket_endpoint(
    ticket_id: int,
    authorization: str | None = Header(None),
    token: str | None = Depends(_resolve_token),
):
    if not _auth_ok(authorization):
        raise HTTPException(401, detail="Invalid API key")
    user = get_user_by_token(token)
    if not user:
        raise HTTPException(401, detail="Missing or invalid user token")
    if user.get("is_disabled"):
        raise HTTPException(403, detail="User is disabled")
    ticket = get_ticket(user["id"], ticket_id)
    if not ticket:
        raise HTTPException(404, detail="Ticket not found")
    return {"ticket": ticket}


@app.post("/api/tickets/{ticket_id}/reply")
async def reply_ticket_endpoint(
    ticket_id: int,
    payload: TicketReplyRequest,
    authorization: str | None = Header(None),
    token: str | None = Depends(_resolve_token),
):
    if not _auth_ok(authorization):
        raise HTTPException(401, detail="Invalid API key")
    user = get_user_by_token(token)
    if not user:
        raise HTTPException(401, detail="Missing or invalid user token")
    if user.get("is_disabled"):
        raise HTTPException(403, detail="User is disabled")
    ticket = get_ticket(user["id"], ticket_id)
    if not ticket:
        raise HTTPException(404, detail="Ticket not found")
    add_ticket_message(ticket_id, user["id"], "user", payload.message)
    return {"ok": True}


@app.get("/admin/tickets")
async def admin_list_tickets(
    request: Request,
    authorization: str | None = Header(None),
    token: str | None = Depends(_resolve_token),
):
    _check_admin_auth(request, authorization, token)
    return {"tickets": list_tickets_admin()}


@app.get("/admin/tickets/{ticket_id}")
async def admin_get_ticket(
    ticket_id: int,
    request: Request,
    authorization: str | None = Header(None),
    token: str | None = Depends(_resolve_token),
):
    _check_admin_auth(request, authorization, token)
    ticket = get_ticket_admin(ticket_id)
    if not ticket:
        raise HTTPException(404, detail={"ok": False, "error": {"type": "NotFound", "message": "ticket not found"}})
    return {"ticket": ticket}


@app.patch("/admin/tickets/{ticket_id}")
async def admin_update_ticket(
    ticket_id: int,
    payload: TicketUpdateRequest,
    request: Request,
    authorization: str | None = Header(None),
    token: str | None = Depends(_resolve_token),
):
    _check_admin_auth(request, authorization, token)
    update_ticket_admin(ticket_id, payload.status, payload.priority)
    return {"ok": True}


@app.post("/admin/tickets/{ticket_id}/reply")
async def admin_reply_ticket(
    ticket_id: int,
    payload: TicketReplyRequest,
    request: Request,
    authorization: str | None = Header(None),
    token: str | None = Depends(_resolve_token),
):
    ctx = _check_admin_auth(request, authorization, token)
    user = ctx.user
    add_ticket_message(ticket_id, user["id"], "admin", payload.message)
    return {"ok": True}


@app.get("/auth/captcha")
async def captcha():
    _clean_expired_captcha()
    a = int(time.time()) % 9 + 1
    b = int(time.time() * 3) % 9 + 1
    token = uuid.uuid4().hex
    CAPCHAS[token] = {"answer": a + b, "ts": time.time()}
    return {"token": token, "question": f"Hvad er {a} + {b}?"}


@app.get("/auth/google/start")
async def google_start():
    raise HTTPException(501, detail="Google login er ikke konfigureret endnu")


@app.get("/auth/google/callback")
async def google_callback():
    raise HTTPException(501, detail="Google login er ikke konfigureret endnu")


@app.get("/admin/env")
async def admin_get_env(
    request: Request,
    authorization: str | None = Header(None),
    token: str | None = Depends(_resolve_token),
):
    _check_admin_auth(request, authorization, token)
    env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
    if not os.path.exists(env_path):
        return {"content": ""}
    with open(env_path, "r", encoding="utf-8") as f:
        return {"content": f.read()}


class EnvUpdateRequest(BaseModel):
    content: str


@app.patch("/admin/env")
async def admin_update_env(
    payload: EnvUpdateRequest,
    request: Request,
    authorization: str | None = Header(None),
    token: str | None = Depends(_resolve_token),
):
    _check_admin_auth(request, authorization, token)
    env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
    os.makedirs(os.path.dirname(env_path), exist_ok=True)
    content = payload.content.replace("\r\n", "\n")
    with open(env_path, "w", encoding="utf-8") as f:
        f.write(content)
    return {"ok": True}


class NoteCreateRequest(BaseModel):
    content: str
    title: str | None = None
    due_at: str | None = None
    remind_enabled: bool | None = False


@app.get("/notes")
async def list_notes_endpoint(
    authorization: str | None = Header(None),
    token: str | None = Depends(_resolve_token),
):
    if not _auth_or_token_ok(authorization, token):
        raise HTTPException(401, detail="Invalid API key")
    user = get_user_by_token(token)
    if not user:
        raise HTTPException(401, detail="Missing or invalid user token")
    if user.get("is_disabled"):
        raise HTTPException(403, detail="User is disabled")
    _cleanup_user_assets(user)
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, title, content, created_at, expires_at FROM notes WHERE user_id = ? ORDER BY id DESC LIMIT 20",
            (user["id"],),
        ).fetchall()
    return {"notes": [dict(r) for r in rows]}


@app.post("/notes")
async def create_note_endpoint(
    payload: NoteCreateRequest,
    authorization: str | None = Header(None),
    token: str | None = Depends(_resolve_token),
):
    if not _auth_or_token_ok(authorization, token):
        raise HTTPException(401, detail="Invalid API key")
    user = get_user_by_token(token)
    if not user:
        raise HTTPException(401, detail="Missing or invalid user token")
    if user.get("is_disabled"):
        raise HTTPException(403, detail="User is disabled")
    with get_conn() as conn:
        count = conn.execute("SELECT COUNT(*) as c FROM notes WHERE user_id = ?", (user["id"],)).fetchone()["c"]
    if count >= 40 and not is_admin_user(user):
        raise HTTPException(400, detail="Du har naet maksimum paa 40 noter.")
    item = add_note(
        user["id"],
        payload.content,
        payload.title,
        payload.due_at,
        bool(payload.remind_enabled),
    )
    return {"note": item}


@app.post("/notes/{note_id}/keep")
async def keep_note_endpoint(
    note_id: int,
    authorization: str | None = Header(None),
    token: str | None = Depends(_resolve_token),
):
    if not _auth_or_token_ok(authorization, token):
        raise HTTPException(401, detail="Invalid API key")
    user = get_user_by_token(token)
    if not user:
        raise HTTPException(401, detail="Missing or invalid user token")
    if user.get("is_disabled"):
        raise HTTPException(403, detail="User is disabled")
    _enforce_maintenance(user)
    ok = keep_note(user["id"], note_id)
    return {"ok": ok}


@app.delete("/notes/{note_id}")
async def delete_note_endpoint(
    note_id: int,
    authorization: str | None = Header(None),
    token: str | None = Depends(_resolve_token),
):
    if not _auth_or_token_ok(authorization, token):
        raise HTTPException(401, detail="Invalid API key")
    user = get_user_by_token(token)
    if not user:
        raise HTTPException(401, detail="Missing or invalid user token")
    if user.get("is_disabled"):
        raise HTTPException(403, detail="User is disabled")
    _enforce_maintenance(user)
    ok = delete_note(user["id"], note_id)
    return {"ok": ok}


@app.get("/admin/settings")
async def admin_settings(
    request: Request,
    authorization: str | None = Header(None),
    token: str | None = Depends(_resolve_token),
):
    _check_admin_auth(request, authorization, token)
    settings = _get_settings(
        [
            "footer_text",
            "footer_support_url",
            "footer_contact_url",
            "footer_license_text",
            "footer_license_url",
            "register_enabled",
            "captcha_enabled",
            "google_auth_enabled",
            "maintenance_enabled",
            "maintenance_message",
            "system_prompt",
            "updates_log",
            "quota_default_mb",
            "brand_top_label",
            "brand_core_label",
            "banner_enabled",
            "banner_messages",
            "public_base_url",
        ]
    )
    system_prompt = settings.get("system_prompt") or SYSTEM_PROMPT
    banner_entries = _parse_banner_entries(settings.get("banner_messages", ""))
    banner_lines = []
    for entry in _filter_banner_entries(banner_entries):
        try:
            ts = datetime.fromisoformat(entry["ts"]).strftime("%Y-%m-%d %H:%M")
        except Exception:
            ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
        banner_lines.append(f"{ts} | {entry['text']}")
    return {
        "footer_text": settings.get("footer_text", "Jarvis v.1 @ 2026"),
        "footer_support_url": settings.get("footer_support_url", "#"),
        "footer_contact_url": settings.get("footer_contact_url", "#"),
        "footer_license_text": settings.get("footer_license_text", "Open‑source licens"),
        "footer_license_url": settings.get("footer_license_url", "#"),
        "register_enabled": settings.get("register_enabled", "1") == "1",
        "captcha_enabled": settings.get("captcha_enabled", "1") == "1",
        "google_auth_enabled": settings.get("google_auth_enabled", "0") == "1",
        "maintenance_enabled": settings.get("maintenance_enabled", "0") == "1",
        "maintenance_message": settings.get(
            "maintenance_message",
            "Jarvis er i vedligeholdelse. Prøv igen senere.",
        ),
        "system_prompt": system_prompt,
        "updates_log": settings.get("updates_log", ""),
        "quota_default_mb": int(settings.get("quota_default_mb", "100") or 100),
        "brand_top_label": settings.get("brand_top_label", "Jarvis"),
        "brand_core_label": settings.get("brand_core_label", "Jarvis"),
        "banner_enabled": settings.get("banner_enabled", "1") == "1",
        "banner_messages": "\n".join(banner_lines),
        "public_base_url": settings.get("public_base_url", ""),
        "notify_enabled": settings.get("notify_enabled", "0") == "1",
    }


@app.patch("/admin/settings")
async def admin_update_settings(
    payload: FooterSettingsRequest,
    request: Request,
    authorization: str | None = Header(None),
    token: str | None = Depends(_resolve_token),
):
    _check_admin_auth(request, authorization, token)
    with get_conn() as conn:
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", ("footer_text", payload.text))
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            ("footer_support_url", payload.support_url),
        )
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            ("footer_contact_url", payload.contact_url),
        )
        if payload.license_text is not None:
            conn.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                ("footer_license_text", payload.license_text),
            )
        if payload.license_url is not None:
            conn.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                ("footer_license_url", payload.license_url),
            )
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            ("register_enabled", "1" if payload.register_enabled else "0"),
        )
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            ("captcha_enabled", "1" if payload.captcha_enabled else "0"),
        )
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            ("google_auth_enabled", "1" if payload.google_auth_enabled else "0"),
        )
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            ("maintenance_enabled", "1" if payload.maintenance_enabled else "0"),
        )
        if payload.maintenance_message is not None:
            conn.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                ("maintenance_message", payload.maintenance_message),
            )
        if payload.system_prompt is not None:
            conn.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                ("system_prompt", payload.system_prompt),
            )
        if payload.updates_log is not None:
            conn.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                ("updates_log", payload.updates_log),
            )
        if payload.quota_default_mb is not None:
            conn.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                ("quota_default_mb", str(int(payload.quota_default_mb))),
            )
        if payload.brand_top_label is not None:
            conn.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                ("brand_top_label", payload.brand_top_label),
            )
        if payload.brand_core_label is not None:
            conn.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                ("brand_core_label", payload.brand_core_label),
            )
        if payload.banner_enabled is not None:
            conn.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                ("banner_enabled", "1" if payload.banner_enabled else "0"),
            )
        if payload.banner_messages is not None:
            entries = _filter_banner_entries(_parse_banner_entries(payload.banner_messages))
            conn.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                ("banner_messages", json.dumps(entries)),
            )
        if payload.public_base_url is not None:
            conn.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                ("public_base_url", payload.public_base_url.strip()),
            )
        if payload.notify_enabled is not None:
            conn.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                ("notify_enabled", "1" if payload.notify_enabled else "0"),
            )
        conn.commit()
    return {"ok": True}


def _list_log_files() -> list[dict]:
    files = []
    if LOG_DIR.exists():
        for p in sorted(LOG_DIR.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
            if not p.is_file():
                continue
            files.append(
                {
                    "name": p.name,
                    "size": p.stat().st_size,
                    "modified_at": datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc).isoformat(),
                }
            )
    return files


def _safe_log_path(name: str) -> Path:
    safe = Path(name).name
    path = LOG_DIR / safe
    if not path.exists() or not path.is_file():
        raise HTTPException(404, detail="Log not found")
    return path


@app.get("/admin/logs")
async def admin_logs(
    request: Request,
    authorization: str | None = Header(None),
    token: str | None = Depends(_resolve_token),
):
    _check_admin_auth(request, authorization, token)
    _enforce_log_limits()
    return {"files": _list_log_files()}


@app.get("/admin/logs/{name}")
async def admin_log_read(
    name: str,
    request: Request,
    authorization: str | None = Header(None),
    token: str | None = Depends(_resolve_token),
):
    _check_admin_auth(request, authorization, token)
    path = _safe_log_path(name)
    try:
        with open(path, "rb") as f:
            data = f.read()
        if path.suffix == ".gz":
            data = gzip.decompress(data)
        text = data.decode("utf-8", errors="ignore")
    except Exception:
        text = ""
    lines = text.splitlines()[-500:]
    return {"name": path.name, "content": "\n".join(lines)}


@app.delete("/admin/logs/{name}")
async def admin_log_delete(
    name: str,
    request: Request,
    authorization: str | None = Header(None),
    token: str | None = Depends(_resolve_token),
):
    _check_admin_auth(request, authorization, token)
    path = _safe_log_path(name)
    path.unlink(missing_ok=True)
    return {"ok": True}


@app.get("/")
async def ui():
    return RedirectResponse(url="/login")


@app.get("/favicon.ico")
def favicon():
    return FileResponse(str(UI_DIR / "static" / "favicon.svg"))


@app.get("/login")
async def login_page():
    return FileResponse(LOGIN_PATH)


@app.get("/registere")
async def register_page():
    return FileResponse(REGISTER_PATH)


@app.get("/admin-login")
async def admin_login_page():
    return FileResponse(ADMIN_LOGIN_PATH)


@app.get("/maintenance")
async def maintenance_page():
    return FileResponse(MAINTENANCE_PATH)


@app.get("/app")
async def app_page(request: Request):
    token = request.cookies.get("jarvis_token")
    if not token or not get_user_by_token(token):
        return RedirectResponse(url="/login")
    try:
        html_content = APP_HTML.read_text(encoding="utf-8").replace("{{BUILD_ID}}", BUILD_ID)
        return HTMLResponse(content=html_content)
    except FileNotFoundError:
        _req_logger.error(f"App HTML file not found: {APP_HTML}")
        return Response(status_code=500, content=f"App HTML file not found: {APP_HTML}", media_type="text/plain")


@app.head("/app")
async def app_page_head(request: Request):
    token = request.cookies.get("jarvis_token")
    if not token or not get_user_by_token(token):
        return RedirectResponse(url="/login")
    return Response(status_code=200, headers={"content-type": "text/html; charset=utf-8"})


@app.get("/admin")
async def admin_page(request: Request):
    token = request.cookies.get("jarvis_token")
    user = get_user_by_token(token) if token else None
    if not is_admin_user(user):
        return RedirectResponse(url="/admin-login")
    return FileResponse(ADMIN_PATH)


@app.get("/docs")
async def docs_page():
    return FileResponse(DOCS_PATH)


@app.get("/tickets")
async def tickets_page():
    return FileResponse(TICKETS_PATH)


@app.get("/account")
async def account_page():
    return FileResponse(ACCOUNT_PATH)
