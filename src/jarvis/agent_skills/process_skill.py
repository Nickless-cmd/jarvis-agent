"""
Process skill handler - thin wrapper for process-related tool.
"""

import json


def handle_process(
    user_id: str,
    prompt: str,
    session_id: str | None = None,
    allowed_tools: list[str] | None = None,
    ui_city: str | None = None,
    ui_lang: str | None = None,
):
    """
    Handle process tool actions like kill and find.
    Returns a response dict with 'text' and 'meta'.
    """
    # Local imports to avoid circular dependencies
    from jarvis.agent import (
        _process_action, _extract_pid, set_process_state, add_memory, add_message,
        get_user_profile, _should_attach_reminders, _prepend_reminders, get_due_reminders
    )
    from jarvis import tools

    profile = get_user_profile(user_id)
    user_id_int = (profile or {}).get("id")
    reminders_due = get_due_reminders(user_id_int) if session_id and user_id_int else []

    action = _process_action(prompt)
    if action == "kill":
        pid = _extract_pid(prompt)
        if not pid:
            tool_result = {"error": "missing_pid"}
            reply = "Jeg mangler proces-ID."
        elif not session_id:
            reply = "Proces-afslutning kræver en aktiv session."
            add_memory("assistant", reply, user_id=user_id)
            return {"text": reply, "meta": {"tool": "process", "tool_used": False}}
        else:
            set_process_state(session_id, json.dumps({"pid": pid}))
            reply = f"Jeg kan afslutte proces {pid}. Skriv 'bekræft' for at fortsætte."
            if reminders_due and _should_attach_reminders(prompt):
                reply = _prepend_reminders(reply, reminders_due, user_id_int)
            add_memory("assistant", reply, user_id=user_id)
            add_message(session_id, "assistant", reply)
            return {"text": reply, "meta": {"tool": "process", "tool_used": False}}
    elif action == "find":
        tool_result = tools.find_process(prompt)
        reply = f"Process søgning: {tool_result}"
    else:
        reply = "Ukendt proces handling."

    add_message(session_id, "assistant", reply)
    return {"text": reply, "meta": {"tool": "process", "tool_used": True}}