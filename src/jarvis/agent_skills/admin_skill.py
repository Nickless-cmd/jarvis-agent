"""
Admin skill handler - thin wrapper for admin-related intents.
"""

import os
import re
import sqlite3


def _admin_create_user_from_prompt(prompt: str) -> tuple[dict | None, str | None]:
    lowered = prompt.lower().strip()
    if not (lowered.startswith("/opret bruger") or lowered.startswith("/opret-bruger") or lowered.startswith("opret bruger")):
        return None, None
    fields = _parse_kv_fields(prompt)
    username = fields.get("brugernavn") or fields.get("username")
    email = fields.get("email")
    password = fields.get("password") or fields.get("kode")
    full_name = fields.get("navn") or fields.get("fulde navn")
    city = fields.get("by") or fields.get("city")
    is_admin_raw = (fields.get("admin") or "").lower()
    is_admin = is_admin_raw in {"ja", "true", "1", "yes"}
    missing = []
    if not username:
        missing.append("brugernavn")
    if not email:
        missing.append("email")
    if not password:
        missing.append("password")
    if not full_name:
        missing.append("navn")
    if missing:
        return None, (
            "Jeg kan oprette en bruger. Send fx:\\n"
            "/opret bruger\\n"
            "brugernavn: ...\\n"
            "email: ...\\n"
            "password: ...\\n"
            "navn: ...\\n"
            "by: ... (valgfri)\\n"
            "admin: ja/nej (valgfri)"
        )
    if "@" not in email:
        return None, "Email ser ugyldig ud. Prøv igen."
    payload = {
        "username": username,
        "password": password,
        "email": email,
        "full_name": full_name,
        "city": city,
        "is_admin": is_admin,
    }
    return payload, None


def _admin_log_intent(prompt: str) -> bool:
    p = prompt.lower()
    return any(k in p for k in ["server log", "serverlog", "logfil", "logs"])


def _ticket_analyze_intent(prompt: str) -> int | None:
    match = re.search(r"\b(analy[sz]er|vurdér|vurder)\s+ticket\s+(\d+)\b", prompt.lower())
    if match:
        return int(match.group(2))
    return None


def _ticket_reply_intent(prompt: str) -> tuple[int, str] | None:
    match = re.search(r"\bsvar\s+p[åa]\s+ticket\s+(\d+)\s*:\s*(.+)$", prompt, re.I)
    if match:
        return int(match.group(1)), match.group(2).strip()
    return None


def _parse_kv_fields(prompt: str) -> dict[str, str]:
    fields = {}
    lines = prompt.split("\n")
    for line in lines[1:]:  # Skip the command line
        if ":" in line:
            key, value = line.split(":", 1)
            fields[key.strip().lower()] = value.strip()
    return fields


def handle_admin(
    user_id: str,
    prompt: str,
    session_id: str | None = None,
    allowed_tools: list[str] | None = None,
    ui_city: str | None = None,
    ui_lang: str | None = None,
    user_id_int: int | None = None,
):
    """
    Handle admin intents like creating users, log access, ticket management.
    Returns a response dict with 'text' and 'meta', or None if not handled.
    """
    # Local imports to avoid circular dependencies
    from jarvis.agent import (
        register_user, add_memory, add_message, get_user_profile, call_ollama, get_ticket_admin, add_ticket_message
    )

    profile = get_user_profile(user_id)
    is_admin_user = bool((profile or {}).get("is_admin"))

    if not is_admin_user:
        return None  # Not admin, skip

    # Admin user creation
    payload, ask = _admin_create_user_from_prompt(prompt)
    if ask:
        add_memory("assistant", ask, user_id=user_id)
        if session_id:
            add_message(session_id, "assistant", ask)
        return {"text": ask, "meta": {"tool_used": False}}
    if payload:
        try:
            created = register_user(
                payload["username"],
                payload["password"],
                1 if payload["is_admin"] else 0,
                email=payload["email"],
                full_name=payload["full_name"],
                city=payload.get("city"),
            )
            reply = f"Bruger oprettet: {created['username']}."
        except sqlite3.IntegrityError:
            reply = "Brugernavn findes allerede. Vælg et andet."
        except Exception:
            reply = "Kunne ikke oprette brugeren lige nu."
        add_memory("assistant", reply, user_id=user_id)
        if session_id:
            add_message(session_id, "assistant", reply)
        return {"text": reply, "meta": {"tool_used": False}}

    # Admin log access
    if _admin_log_intent(prompt):
        log_path = os.getenv("JARVIS_LOG_PATH", "data/server.log")
        if not os.path.exists(log_path):
            reply = "Logfilen findes ikke endnu."
            add_message(session_id, "assistant", reply)
            return {"text": reply, "meta": {"tool": None, "tool_used": False}}
        try:
            with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()[-200:]
            log_text = "".join(lines).strip()
        except Exception:
            log_text = ""
        if not log_text:
            reply = "Logfilen er tom lige nu."
            add_message(session_id, "assistant", reply)
            return {"text": reply, "meta": {"tool": None, "tool_used": False}}
        if "analyser" in prompt.lower() or "find fejl" in prompt.lower():
            messages = [
                {"role": "system", "content": "Analyser loggen og peg på fejl og næste skridt. Dansk, kort."},
                {"role": "assistant", "content": log_text},
                {"role": "user", "content": "Hvad er de vigtigste fejl og hvad bør jeg gøre?"},
            ]
            res = call_ollama(messages)
            reply = res.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            if not reply:
                reply = "Jeg kan ikke analysere loggen lige nu."
        else:
            reply = f"Seneste loglinjer:\n{log_text}"
        add_message(session_id, "assistant", reply)
        return {"text": reply, "meta": {"tool": None, "tool_used": False}}

    # Ticket reply
    ticket_reply = _ticket_reply_intent(prompt)
    if ticket_reply is not None and user_id_int:
        ticket_id, message = ticket_reply
        add_ticket_message(ticket_id, user_id_int, "admin", message)
        reply = f"Svar sendt på ticket #{ticket_id}."
        add_message(session_id, "assistant", reply)
        return {"text": reply, "meta": {"tool": None, "tool_used": False}}

    # Ticket analyze
    ticket_id = _ticket_analyze_intent(prompt)
    if ticket_id is not None and user_id_int:
        ticket = get_ticket_admin(ticket_id)
        if not ticket:
            reply = "Jeg kan ikke finde den ticket."
            add_message(session_id, "assistant", reply)
            return {"text": reply, "meta": {"tool": None, "tool_used": False}}
        thread = "\n".join([f"{m['role']}: {m['content']}" for m in ticket.get("messages", [])])
        messages = [
            {"role": "system", "content": "Analyser ticket og foreslå et kort svar. Dansk."},
            {"role": "assistant", "content": thread},
            {"role": "user", "content": "Giv et forslag til svar og næste skridt."},
        ]
        res = call_ollama(messages)
        reply = res.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        if not reply:
            reply = "Jeg kan ikke analysere ticketen lige nu."
        add_message(session_id, "assistant", reply)
        return {"text": reply, "meta": {"tool": None, "tool_used": False}}

    return None  # No admin intent matched