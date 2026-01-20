"""
Notes skill handler - handles note and reminder intents.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, time, timezone
from typing import Any, Callable, Dict, List, Tuple
from zoneinfo import ZoneInfo

from jarvis.notes import (
    add_note,
    add_reminder,
    delete_note,
    get_note,
    keep_note,
    list_notes,
    list_notes_since,
    list_reminders,
    set_note_remind,
    update_note_content,
    update_note_due,
)
from jarvis.session_store import (
    add_message,
    clear_pending_note,
    clear_pending_reminder,
    set_pending_note,
    set_pending_reminder,
    set_reminder_state,
)


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


def _analyze_note_intent(prompt: str) -> int | None:
    match = re.search(r"\banaly[sz]er\s+note\s+(\d+)\b", prompt.lower())
    if match:
        return int(match.group(1))
    return None


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
    prompt: str,
    session_id: str | None,
    user_id_int: int | None,
    session_hist: List[Dict[str, Any]],
    reminders_due,
    format_dt: Callable[[str], str],
    format_note_brief: Callable[[dict], str],
    should_attach_reminders: Callable[[str], bool],
    prepend_reminders: Callable[[str, Any, Any], str],
) -> Dict[str, Any] | None:
    """
    Handle note and reminder intents. Returns response dict or None.
    """

    # List notes (with optional since)
    if session_id and _list_notes_intent(prompt):
        since_dt = _note_list_since_intent(prompt)
        if since_dt and user_id_int:
            items = list_notes_since(user_id_int, since_dt.astimezone(timezone.utc).isoformat())
        else:
            items = list_notes(user_id_int, limit=10) if user_id_int else []
        if not items:
            reply = "Du har ingen noter endnu."
        else:
            lines = [
                f"{i['id']}. {i.get('title','Note')} — udløber {format_dt(i.get('expires_at',''))}"
                for i in items
            ]
            reply = "Dine noter (seneste først):\n" + "\n".join(lines)
        add_message(session_id, "assistant", reply)
        return {"text": reply, "meta": {"tool": None, "tool_used": False}}

    # Short description of notes
    if session_id and "kort beskrivelse" in prompt.lower():
        notes_context = any(
            m.get("role") == "assistant" and "note" in (m.get("content") or "").lower()
            for m in session_hist[-2:]
        )
        if _note_describe_intent(prompt) or notes_context:
            items = list_notes(user_id_int, limit=10) if user_id_int else []
            if not items:
                reply = "Du har ingen noter endnu."
            else:
                lines = [f"{i['id']}. {format_note_brief(i)}" for i in items[:10]]
                reply = "Kort beskrivelse af dine noter:\n" + "\n".join(lines)
            add_message(session_id, "assistant", reply)
            return {"text": reply, "meta": {"tool": None, "tool_used": False}}

    # List reminders
    if session_id and _list_reminders_intent(prompt):
        items = list_reminders(user_id_int, include_done=False, limit=10) if user_id_int else []
        if not items:
            reply = "Du har ingen aktive påmindelser."
        else:
            lines = [f"{i['id']}. {i['content']} — {format_dt(i['remind_at'])}" for i in items]
            reply = "Aktive påmindelser:\n" + "\n".join(lines)
        add_message(session_id, "assistant", reply)
        return {"text": reply, "meta": {"tool": None, "tool_used": False}}

    # Edit note
    if session_id:
        edit_note = _note_edit_intent(prompt)
        if edit_note is not None:
            note_id, content = edit_note
            ok = update_note_content(user_id_int, note_id, content) if user_id_int else False
            reply = "Noten er opdateret." if ok else "Kunne ikke opdatere noten."
            add_message(session_id, "assistant", reply)
            return {"text": reply, "meta": {"tool": None, "tool_used": False}}

        note_id = _delete_note_intent(prompt)
        if note_id is not None:
            ok = delete_note(user_id_int, note_id) if user_id_int else False
            reply = "Note slettet." if ok else "Kunne ikke finde den note."
            add_message(session_id, "assistant", reply)
            return {"text": reply, "meta": {"tool": None, "tool_used": False}}

        remind_id = _note_remind_enable_intent(prompt)
        if remind_id is not None:
            ok = set_note_remind(user_id_int, remind_id, True) if user_id_int else False
            reply = "Påmindelser er slået til for noten." if ok else "Kunne ikke finde den note."
            add_message(session_id, "assistant", reply)
            return {"text": reply, "meta": {"tool": None, "tool_used": False}}

        stop_id = _note_remind_stop_intent(prompt)
        if stop_id is not None:
            ok = set_note_remind(user_id_int, stop_id, False) if user_id_int else False
            reply = "Påmindelser er slået fra for noten." if ok else "Kunne ikke finde den note."
            add_message(session_id, "assistant", reply)
            return {"text": reply, "meta": {"tool": None, "tool_used": False}}

        due_update = _note_update_due_intent(prompt)
        if due_update is not None:
            note_id, due_dt, remind_flag = due_update
            ok = (
                update_note_due(
                    user_id_int,
                    note_id,
                    due_dt.astimezone(timezone.utc).isoformat(),
                    remind_flag,
                )
                if user_id_int
                else False
            )
            reply = "Dato og tid er opdateret for noten." if ok else "Kunne ikke opdatere noten."
            add_message(session_id, "assistant", reply)
            return {"text": reply, "meta": {"tool": None, "tool_used": False}}

        keep_id = _keep_note_intent(prompt)
        if keep_id is not None:
            ok = keep_note(user_id_int, keep_id) if user_id_int else False
            reply = "Noten er fornyet i 30 dage." if ok else "Kunne ikke finde den note."
            add_message(session_id, "assistant", reply)
            return {"text": reply, "meta": {"tool": None, "tool_used": False}}

        analyze_note_id = _analyze_note_intent(prompt)
        if analyze_note_id is not None:
            note = get_note(user_id_int, analyze_note_id) if user_id_int else None
            if not note:
                reply = "Jeg kan ikke finde den note."
                add_message(session_id, "assistant", reply)
                return {"text": reply, "meta": {"tool": None, "tool_used": False}}
            messages = [
                {"role": "system", "content": "Analyser teksten kort og præcist på dansk. Ingen gæt."},
                {"role": "assistant", "content": note.get("content", "")},
                {"role": "user", "content": "Lav en kort analyse."},
            ]
            from jarvis import tools

            res = tools.call_ollama(messages)  # type: ignore[attr-defined]
            reply = res.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            if not reply:
                reply = "Jeg kunne ikke analysere noten lige nu."
            add_message(session_id, "assistant", reply)
            return {"text": reply, "meta": {"tool": None, "tool_used": False}}

    return None
