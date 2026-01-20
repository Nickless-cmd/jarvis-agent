"""
Notes skill handler - handles note and reminder intents.
"""

import json
import re
from datetime import datetime, timedelta, time
from typing import Tuple
from zoneinfo import ZoneInfo


def _note_intent(prompt: str) -> bool:
    p = prompt.lower()
    return p.startswith("note") or p.startswith("noter") or "opret note" in p


def _list_notes_intent(prompt: str) -> bool:
    p = prompt.lower()
    return any(k in p for k in ["vis noter", "mine noter", "liste noter"])


def _delete_note_intent(prompt: str) -> int | None:
    match = re.search(r"\bslet note\s+(\d+)\b", prompt.lower())
    if match:
        return int(match.group(1))
    return None


def _keep_note_intent(prompt: str) -> int | None:
    match = re.search(r"\b(behold|forny)\s+note\s+(\d+)\b", prompt.lower())
    if match:
        return int(match.group(2))
    return None


def _note_remind_enable_intent(prompt: str) -> int | None:
    match = re.search(r"\b(mind mig om|påmind)\s+note\s+(\d+)\b", prompt.lower())
    if match:
        return int(match.group(2))
    return None


def _note_remind_stop_intent(prompt: str) -> int | None:
    match = re.search(
        r"\b(stop|slut|afslut)\s+(påmindelser|påmindelse|med at minde om)\s+note\s+(\d+)\b",
        prompt.lower(),
    )
    if match:
        return int(match.group(3))
    return None


def _note_update_due_intent(prompt: str) -> Tuple[int, datetime, bool | None] | None:
    match = re.search(r"\b(note)\s+(\d+)\b", prompt.lower())
    if not match:
        return None
    note_id = int(match.group(2))
    dt = _parse_time(prompt)
    if not dt:
        return None
    remind = None
    if "mind mig om" in prompt.lower() or "påmind" in prompt.lower():
        remind = True
    return note_id, dt, remind


def _note_list_since_intent(prompt: str) -> datetime | None:
    if "efter" not in prompt.lower() and "fra" not in prompt.lower():
        return None
    dt = _parse_time(prompt)
    return dt


def _note_edit_intent(prompt: str) -> Tuple[int, str] | None:
    match = re.search(r"\b(opdater|rediger)\s+note\s+(\d+)\s*:\s*(.+)$", prompt, re.I)
    if not match:
        return None
    return int(match.group(2)), match.group(3).strip()


def _note_describe_intent(prompt: str) -> bool:
    p = prompt.lower()
    return "kort beskrivelse" in p and ("note" in p or "noter" in p)


def _remind_intent(prompt: str) -> bool:
    p = prompt.lower()
    return "mind mig" in p or "påmind" in p or "timer" in p


def _list_reminders_intent(prompt: str) -> bool:
    p = prompt.lower()
    return any(k in p for k in ["vis påmindelser", "mine påmindelser", "liste påmindelser", "hvad skal jeg huske"])


def _parse_time(prompt: str) -> datetime | None:
    tz = ZoneInfo("Europe/Copenhagen")
    now = datetime.now(tz)
    match = re.search(r"\bkl\.?\s*(\d{1,2})[:.](\d{2})\b", prompt.lower())
    if match:
        hh = int(match.group(1))
        mm = int(match.group(2))
        dt = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if "i morgen" in prompt.lower() or "imorgen" in prompt.lower():
            dt = dt + timedelta(days=1)
        if dt < now:
            dt = dt + timedelta(days=1)
        return dt
    match = re.search(r"\b(\d{1,2})[./-](\d{1,2})(?:[./-](\d{2,4}))?\b", prompt)
    if match:
        day = int(match.group(1))
        month = int(match.group(2))
        year = int(match.group(3) or now.year)
        if year < 100:
            year += 2000
        dt = datetime(year, month, day, tzinfo=tz)
        return dt
    return None


def _parse_timer_minutes(prompt: str) -> int | None:
    match = re.search(r"\b(\d{1,3})\s*(min|minutter)\b", prompt.lower())
    if match:
        return int(match.group(1))
    match = re.search(r"\b(\d{1,3})\s*(sek|sekunder)\b", prompt.lower())
    if match:
        seconds = int(match.group(1))
        return max(1, round(seconds / 60))
    return None


def handle_notes(
    user_id: str,
    prompt: str,
    session_id: str | None = None,
    allowed_tools: list[str] | None = None,
    ui_city: str | None = None,
    ui_lang: str | None = None,
):
    """
    Handle note and reminder intents.
    Returns a response dict with 'text' and 'meta'.
    """
    # Local imports to avoid circular dependencies
    from jarvis.agent import (
        add_note, set_pending_note, add_message, _format_dt, get_user_profile,
        add_reminder, set_reminder_state, set_pending_reminder, get_due_reminders, _should_attach_reminders, _prepend_reminders
    )
    import re
    from datetime import datetime, timedelta, timezone

    profile = get_user_profile(user_id)
    user_id_int = (profile or {}).get("id")
    reminders_due = get_due_reminders(user_id_int) if session_id and user_id_int else []

    # Handle note intent
    if session_id and _note_intent(prompt):
        content = prompt.split(":", 1)[-1].strip() if ":" in prompt else prompt.replace("note", "", 1).strip()
        if not content:
            reply = "Hvad skal jeg gemme som note?"
            if session_id:
                set_pending_note(session_id, json.dumps({"awaiting_note": True}, ensure_ascii=False))
        else:
            item = add_note(user_id_int, content) if user_id_int else None
            reply = f"Note gemt ({item['id']}) — {_format_dt(item['created_at'])}." if item else "Jeg kunne ikke gemme noten."
        add_message(session_id, "assistant", reply)
        return {"text": reply, "meta": {"tool": None, "tool_used": False}}

    # Handle remind intent
    if session_id and _remind_intent(prompt):
        state = {}  # Simplified, assuming no state
        if state.get("awaiting_time"):
            when = _parse_time(prompt)
            if not when:
                reply = "Jeg mangler tidspunktet. Skriv fx 'i morgen kl 10:00'."
                if session_id:
                    set_pending_reminder(session_id, json.dumps({"awaiting_reminder": True}, ensure_ascii=False))
                add_message(session_id, "assistant", reply)
                return {"text": reply, "meta": {"tool": None, "tool_used": False}}
            item = add_reminder(user_id_int, state.get("content", "Påmindelse"), when.astimezone(timezone.utc).isoformat()) if user_id_int else None
            set_reminder_state(session_id, json.dumps({}))
            clear_pending_reminder(session_id)
            reply = f"Påmindelse sat til {_format_dt(item['remind_at'])}." if item else "Jeg kunne ikke gemme påmindelsen."
            add_message(session_id, "assistant", reply)
            return {"text": reply, "meta": {"tool": None, "tool_used": False}}
        when = _parse_time(prompt)
        timer_minutes = _parse_timer_minutes(prompt)
        content = prompt
        content = re.sub(r"\bmind mig om\b", "", content, flags=re.I).strip()
        if not content:
            reply = "Hvad skal jeg minde dig om?"
            add_message(session_id, "assistant", reply)
            return {"text": reply, "meta": {"tool": None, "tool_used": False}}
        if not when and timer_minutes:
            tz = ZoneInfo("Europe/Copenhagen")
            when = datetime.now(tz) + timedelta(minutes=timer_minutes)
        if not when:
            set_reminder_state(session_id, json.dumps({"awaiting_time": True, "content": content}))
            set_pending_reminder(session_id, json.dumps({"awaiting_reminder": True}, ensure_ascii=False))
            reply = "Hvornår skal jeg minde dig om det?"
            add_message(session_id, "assistant", reply)
            return {"text": reply, "meta": {"tool": None, "tool_used": False}}
        item = add_reminder(user_id_int, content, when.astimezone(timezone.utc).isoformat()) if user_id_int else None
        reply = f"Påmindelse sat til {_format_dt(item['remind_at'])}." if item else "Jeg kunne ikke gemme påmindelsen."
        add_message(session_id, "assistant", reply)
        return {"text": reply, "meta": {"tool": None, "tool_used": False}}

    return None  # No note or remind intent