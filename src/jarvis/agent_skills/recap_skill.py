"""
Recap skill: analyze chatlogs/milestone text files to summarize progress and gaps.
"""

from __future__ import annotations

import re
from typing import Dict, List, Tuple

from jarvis.files import read_upload_text
from jarvis.agent_core.project_memory import add_milestone as pm_add_milestone, add_roadmap_item as pm_add_roadmap_item


def _recap_intent(prompt: str) -> Tuple[bool, int | None, int | None]:
    """
    Detect recap intent and optional file ids.
    Returns (is_recap, chatlog_id, snapshot_id)
    """
    p = prompt.lower()
    is_recap = any(
        k in p
        for k in [
            "analysér chatlog",
            "analysér chat log",
            "analyser chatlog",
            "analyser chat log",
            "where were we",
            "hvor var vi",
            "hvad mangler vi",
            "project recap",
        ]
    )
    chatlog_id = None
    snapshot_id = None
    match_chat = re.search(r"chatlog\s*(\d+)", p)
    if match_chat:
        chatlog_id = int(match_chat.group(1))
    match_snap = re.search(r"snapshot\s*(\d+)", p)
    if match_snap:
        snapshot_id = int(match_snap.group(1))
    return is_recap, chatlog_id, snapshot_id


def _extract_items(lines: List[str], keywords: List[str]) -> List[str]:
    found = []
    for line in lines:
        lower = line.lower()
        if any(k in lower for k in keywords):
            cleaned = line.strip("•-– ").strip()
            if cleaned:
                found.append(cleaned)
    return found


def _analyze_text(text: str) -> Dict[str, List[str]]:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    completed = _extract_items(lines, ["done", "tests pass", "merged", "commit", "wired", "implemented", "completed"])
    pending = _extract_items(lines, ["next", "todo", "missing", "phase", "pending", "unwired", "not wired"])
    risks = _extract_items(
        lines,
        ["not green", "test fail", "error", "exception", "traceback", "warning", "not working"],
    )
    return {"completed": completed, "pending": pending, "risks": risks}


def _format_report(completed: List[str], pending: List[str], risks: List[str], ui_lang: str | None) -> str:
    en = (ui_lang or "").lower().startswith("en")
    parts = []
    if completed:
        header = "Completed:" if en else "Færdigt:"
        parts.append(header)
        parts.extend([f"- {c}" for c in completed[:6]])
    if pending:
        header = "Missing/Next:" if en else "Mangler/Næste:"
        parts.append(header)
        parts.extend([f"- {p}" for p in pending[:6]])
    if risks:
        header = "Risks:" if en else "Risici:"
        parts.append(header)
        parts.extend([f"- {r}" for r in risks[:4]])
    if pending:
        header = "Suggested order:" if en else "Forslået rækkefølge:"
        parts.append(header)
        parts.extend([f"- {p}" for p in pending[:3]])
    if not parts:
        return "Jeg kunne ikke finde relevante punkter." if not en else "I could not find relevant items."
    return "\n".join(parts)


def handle_recap(
    user_id: str,
    prompt: str,
    session_id: str | None,
    user_id_int: int | None,
    user_key: str | None,
    ui_lang: str | None = None,
):
    """
    Handle recap intent. Returns TurnResult-like dict or None.
    """
    from jarvis.agent import TurnResult  # local import to avoid cycle

    is_recap, chatlog_id, snapshot_id = _recap_intent(prompt)
    if not is_recap or not session_id or not user_id_int:
        return None

    if chatlog_id is None:
        reply = "Angiv chatlog fil-id, fx 'analysér chatlog 12'." if not (ui_lang or "").startswith("en") else "Please specify chatlog file id, e.g. 'analyze chatlog 12'."
        return TurnResult(reply_text=reply, meta={"tool_used": False, "tool": None})

    info = read_upload_text(user_id_int, user_key, chatlog_id, max_chars=20000)
    if not info or info.get("error"):
        reply = info.get("detail", "Jeg kunne ikke læse filen.") if info else "Jeg kunne ikke læse filen."
        return TurnResult(reply_text=reply, meta={"tool_used": False, "tool": None})

    analysis = _analyze_text(info.get("text", ""))
    report = _format_report(analysis["completed"], analysis["pending"], analysis["risks"], ui_lang)

    if snapshot_id:
        snap = read_upload_text(user_id_int, user_key, snapshot_id, max_chars=10000)
        if snap and not snap.get("error"):
            report += "\n" + ("Snapshot loaded." if (ui_lang or "").startswith("en") else "Snapshot indlæst.")

    save_hint = (
        "\n\nVil du gemme status som milestone/roadmap? Svar 'gem milestone' eller 'gem roadmap'."
        if not (ui_lang or "").startswith("en")
        else "\n\nSave as milestone/roadmap? Reply 'save milestone' or 'save roadmap'."
    )
    return TurnResult(
        reply_text=report + save_hint,
        meta={"tool": "recap", "tool_used": False},
        data={"completed": analysis["completed"], "pending": analysis["pending"], "risks": analysis["risks"]},
    )


def maybe_store_confirmation(prompt: str, data: Dict[str, List[str]], ui_lang: str | None = None):
    """Store recap results into project memory on confirmation."""
    p = prompt.lower().strip()
    save_m = p in {"gem milestone", "save milestone"}
    save_r = p in {"gem roadmap", "save roadmap"}
    if not data or not (save_m or save_r):
        return None
    if save_m and data.get("completed"):
        for item in data["completed"][:3]:
            pm_add_milestone(item)
    if save_r and data.get("pending"):
        for item in data["pending"][:3]:
            pm_add_roadmap_item(item)
    en = (ui_lang or "").lower().startswith("en")
    return "Gemt." if not en else "Saved."
