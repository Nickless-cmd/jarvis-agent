"""
CV skill handler - thin wrapper for CV-related intents.
"""

import json


def handle_cv(
    user_id: str,
    prompt: str,
    session_id: str | None = None,
    allowed_tools: list[str] | None = None,
    ui_city: str | None = None,
    ui_lang: str | None = None,
):
    """
    Handle CV intents.
    Returns a response dict with 'text' and 'meta'.
    """
    # Local imports to avoid circular dependencies
    from jarvis.agent import _cv_intent, set_cv_state, add_message, _load_state, get_cv_state

    skip_cv_intent = False  # Assume not skipped for simplicity

    if session_id and _cv_intent(prompt) and not skip_cv_intent and not _load_state(get_cv_state(session_id)):
        set_cv_state(session_id, json.dumps({"pending_start": True, "prompt": prompt}, ensure_ascii=False))
        reply = "Vil du have, at jeg hjælper dig med et CV? Svar ja/nej."
        add_message(session_id, "assistant", reply)
        return {"text": reply, "meta": {"tool": None, "tool_used": False}}

    return None  # No CV intent or already active