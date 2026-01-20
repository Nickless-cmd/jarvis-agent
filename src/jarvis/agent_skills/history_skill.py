"""
History skill handler - thin wrapper for history-related intents.
"""

from datetime import datetime, time
from zoneinfo import ZoneInfo
import re


def _history_intent(prompt: str) -> bool:
    p = prompt.lower()
    return any(
        phrase in p
        for phrase in [
            "hvad sagde jeg",
            "hvad snakkede vi om",
            "hvad talte vi om",
            "hvad snakkede vi",
            "hvad sagde du",
            "hvad spurgte jeg",
        ]
    )


def _summary_intent(prompt: str) -> bool:
    p = prompt.lower().strip()
    if p.startswith("/summary") or p.startswith("/opsummer"):
        return True
    return any(
        k in p
        for k in [
            "opsummer chat",
            "opsummer samtalen",
            "opsummer vores samtale",
            "kort resume",
            "resume af chatten",
            "opsummering",
        ]
    )


def _summary_detail(prompt: str) -> str:
    p = prompt.lower()
    if any(k in p for k in ["dybdegående", "lang", "mere detaljeret", "uddyb"]):
        return "long"
    return "short"


def _time_window(prompt: str) -> tuple[time | None, time | None]:
    p = prompt.lower()
    if "formiddag" in p:
        return time(6, 0), time(12, 0)
    if "eftermiddag" in p:
        return time(12, 0), time(17, 0)
    if "aften" in p:
        return time(17, 0), time(22, 0)
    if "morgen" in p:
        return time(6, 0), time(10, 0)
    if "i dag" in p:
        return time(0, 0), time(23, 59)
    return None, None


def _extract_time_point(prompt: str) -> time | None:
    match = re.search(r"\b(?:kl\.?\s*)?(\d{1,2})[:.](\d{2})\b", prompt.lower())
    if not match:
        return None
    hh = int(match.group(1))
    mm = int(match.group(2))
    if hh > 23 or mm > 59:
        return None
    return time(hh, mm)


def _history_reply(session_id: str, prompt: str) -> str | None:
    # Local imports to avoid circular dependencies
    from jarvis.session_store import get_all_messages

    messages = get_all_messages(session_id)
    if not messages:
        return "Jeg har ingen historik i denne session."
    zone = ZoneInfo("Europe/Copenhagen")
    start, end = _time_window(prompt)
    point = _extract_time_point(prompt)
    filtered = []
    for m in messages:
        created = m.get("created_at")
        if not created:
            continue
        try:
            dt = datetime.fromisoformat(created.replace("Z", "+00:00")).astimezone(zone)
        except Exception:
            continue
        if point:
            filtered.append((dt, m))
            continue
        if start and end:
            if start <= dt.time() <= end:
                filtered.append((dt, m))
        else:
            filtered.append((dt, m))
    if not filtered:
        return "Jeg kunne ikke finde noget i det tidsrum."
    if point:
        filtered.sort(key=lambda x: abs((datetime.combine(x[0].date(), point, tzinfo=zone) - x[0]).total_seconds()))
        nearest = filtered[0][1]
        who = "du" if nearest.get("role") == "user" else "jeg"
        return f"Klods på tidspunktet sagde {who}: {nearest.get('content','')}"
    user_msgs = [m for _, m in filtered if m.get("role") == "user"]
    if not user_msgs:
        return "Jeg kan ikke finde hvad du sagde i det tidsrum."
    lines = []
    for m in user_msgs[-5:]:
        lines.append(f"• {m.get('content','')}")
    return "Det du sagde:\n" + "\n".join(lines)


def handle_history(
    user_id: str,
    prompt: str,
    session_id: str | None = None,
    allowed_tools: list[str] | None = None,
    ui_city: str | None = None,
    ui_lang: str | None = None,
    reminders_due: list | None = None,
    user_id_int: int | None = None,
):
    """
    Handle history and summary intents.
    Returns a response dict with 'text' and 'meta'.
    """
    # Local imports to avoid circular dependencies
    from jarvis.session_store import get_all_messages, add_message
    from jarvis.agent import call_ollama, _should_attach_reminders, _prepend_reminders, _dedupe_repeated_words

    if session_id and _history_intent(prompt):
        reply = _history_reply(session_id, prompt)
        add_message(session_id, "assistant", reply)
        return {"text": reply, "meta": {"tool": None, "tool_used": False}}

    if _summary_intent(prompt):
        if not session_id:
            reply = "Opsummering kræver en aktiv chat."
            return {"text": reply, "meta": {"tool": None, "tool_used": False}}
        detail = _summary_detail(prompt)
        messages = get_all_messages(session_id)
        if not messages:
            reply = "Der er ingen beskeder at opsummere endnu."
            return {"text": reply, "meta": {"tool": None, "tool_used": False}}
        max_chars = 12000 if detail == "long" else 8000
        parts = []
        total = 0
        for m in reversed(messages):
            line = f"{'Bruger' if m['role']=='user' else 'Jarvis'}: {m['content']}"
            if total + len(line) > max_chars:
                break
            parts.append(line)
            total += len(line)
        transcript = "\n".join(reversed(parts))
        bullets = "8 punkter" if detail == "long" else "5 punkter"
        system = (
            "Du opsummerer samtaler på dansk. Vær kort og præcis. "
            f"Returnér {bullets} i punktform. Ingen gæt."
        )
        summary_messages = [
            {"role": "system", "content": system},
            {"role": "assistant", "content": transcript},
            {"role": "user", "content": "Giv en opsummering."},
        ]
        res = call_ollama(summary_messages)
        reply = res.get("choices", [{}])[0].get("message", {}).get("content", "")
        reply = _dedupe_repeated_words(reply).strip()
        if not reply:
            reply = "Jeg kan ikke opsummere samtalen lige nu."
        if reminders_due and _should_attach_reminders(prompt):
            reply = _prepend_reminders(reply, reminders_due, user_id_int)
        add_message(session_id, "assistant", reply)
        return {"text": reply, "meta": {"tool": None, "tool_used": False}}

    return None  # No history or summary intent