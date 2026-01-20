"""
Files skill handler - thin wrapper for file-related intents.
"""

import json


def handle_files(
    user_id: str,
    prompt: str,
    session_id: str | None = None,
    allowed_tools: list[str] | None = None,
    ui_city: str | None = None,
    ui_lang: str | None = None,
):
    """
    Handle file-related intents: list, type check, delete by extension.
    Returns a response dict with 'text' and 'meta'.
    """
    # Local imports to avoid circular dependencies
    from jarvis.agent import (
        list_uploads, add_message, _format_dt, get_user_profile,
        _file_type_intent, _file_type_label, find_upload_by_name,
        _delete_ext_intent, delete_uploads_by_ext, _list_files_intent
    )

    profile = get_user_profile(user_id)
    user_id_int = (profile or {}).get("id")
    user_key = user_id

    # Check for list files intent
    if _list_files_intent(prompt):
        items = list_uploads(user_id_int) if user_id_int else []
        if not items:
            reply = "Du har ingen filer endnu."
        else:
            lines = [
                f"{i['id']}. {i['original_name']} — udløber {_format_dt(i.get('expires_at',''))}"
                for i in items[:10]
            ]
            reply = "Dine filer:\n" + "\n".join(lines)
        add_message(session_id, "assistant", reply)
        return {"text": reply, "meta": {"tool": None, "tool_used": False}}

    # Check for file type intent
    if file_name := _file_type_intent(prompt):
        label = _file_type_label(file_name)
        reply = f"Som De ønsker. {file_name} er en {label}."
        if user_id_int:
            info = find_upload_by_name(user_id_int, file_name)
            if info:
                reply = f"Som De ønsker. {file_name} er en {label}, og den ligger på Deres filer."
        add_message(session_id, "assistant", reply)
        return {"text": reply, "meta": {"tool": None, "tool_used": False}}

    # Check for delete ext intent
    if ext := _delete_ext_intent(prompt):
        removed = delete_uploads_by_ext(user_id_int, user_key, ext)
        delete_msg = (
            f"Som De ønsker. Jeg har slettet {removed} .{ext} filer."
            if removed > 0
            else f"Som De ønsker. Jeg fandt ingen .{ext} filer at slette."
        )
        reply = delete_msg
        add_message(session_id, "assistant", reply)
        return {"text": reply, "meta": {"tool": None, "tool_used": False}}

    # If no intent matched, return None or error
    return None