"""
Story skill handler - thin wrapper for story-related intents.
"""

import json


def handle_story(
    user_id: str,
    prompt: str,
    session_id: str | None = None,
    allowed_tools: list[str] | None = None,
    ui_city: str | None = None,
    ui_lang: str | None = None,
):
    """
    Handle story intents.
    Returns a response dict with 'text' and 'meta'.
    """
    # Local imports to avoid circular dependencies
    from jarvis.agent import (
        _story_intent, _load_state, get_story_state, _extract_story_topic,
        _story_needs_questions, _detect_format, _save_text_intent, _save_permanent_intent,
        set_story_state, _story_prompt_from_state, add_message
    )

    if session_id and _story_intent(prompt) and not _load_state(get_story_state(session_id)):
        topic = _extract_story_topic(prompt)
        wants_style = _story_needs_questions(prompt)
        fmt = _detect_format(prompt) or ""
        story_state = {
            "step": 0,
            "answers": {},
            "done": False,
            "needs_research": wants_style,
            "format": fmt if fmt else None,
            "auto_finalize": _save_text_intent(prompt),
            "persist": _save_permanent_intent(prompt),
        }
        if topic:
            story_state["answers"]["topic"] = topic
            story_state["step"] = 1
        set_story_state(session_id, json.dumps(story_state))
        if not wants_style and topic:
            story_prompt = _story_prompt_from_state(story_state)
            # Simplified: assume we generate the story here
            reply = f"Her er din historie om {topic}: [Generated story based on {story_prompt}]"
        else:
            reply = "Lad os skabe en historie. Hvad er emnet?"
        add_message(session_id, "assistant", reply)
        return {"text": reply, "meta": {"tool": None, "tool_used": False}}

    return None  # No story intent or already active