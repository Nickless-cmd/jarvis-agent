"""
History skill handler - thin wrapper for history-related intents.
"""


def handle_history(
    user_id: str,
    prompt: str,
    session_id: str | None = None,
    allowed_tools: list[str] | None = None,
    ui_city: str | None = None,
    ui_lang: str | None = None,
):
    """
    Handle history intents.
    Returns a response dict with 'text' and 'meta'.
    """
    # Local imports to avoid circular dependencies
    from jarvis.agent import _history_intent, _history_reply, add_message

    if session_id and _history_intent(prompt):
        reply = _history_reply(session_id, prompt)
        add_message(session_id, "assistant", reply)
        return {"text": reply, "meta": {"tool": None, "tool_used": False}}

    return None  # No history intent