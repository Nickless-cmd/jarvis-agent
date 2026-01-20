"""
Notes skill handler - thin wrapper for note-related intents.
"""

import json


def handle_notes(
    user_id: str,
    prompt: str,
    session_id: str | None = None,
    allowed_tools: list[str] | None = None,
    ui_city: str | None = None,
    ui_lang: str | None = None,
):
    """
    Handle note-related intents.
    Returns a response dict with 'text' and 'meta'.
    """
    # Local imports to avoid circular dependencies
    from jarvis.agent import add_note, set_pending_note, add_message, _format_dt, get_user_profile

    profile = get_user_profile(user_id)
    user_id_int = (profile or {}).get("id")

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