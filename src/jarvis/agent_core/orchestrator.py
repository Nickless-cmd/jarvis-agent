"""
Agent orchestrator - coordinates agent execution.
"""

def handle_turn(
    user_id: str,
    prompt: str,
    session_id: str | None = None,
    allowed_tools: list[str] | None = None,
    ui_city: str | None = None,
    ui_lang: str | None = None,
):
    """
    Handle a single turn of agent interaction.
    Performs initial setup and calls the internal agent implementation.
    """
    from jarvis.agent import (
        search_memory, get_recent_messages, _debug, _session_prompt_intent,
        get_user_profile, _first_name, get_due_reminders, _load_state,
        get_pending_weather, get_pending_note, get_pending_reminder,
        get_pending_file, get_pending_image_preview, _detect_response_mode
    )
    from jarvis.conversation_state import ConversationState
    from jarvis.agent import get_conversation_state, set_conversation_state

    mem = search_memory(prompt, user_id=user_id)
    session_hist = get_recent_messages(session_id, limit=8) if session_id else []
    _debug(f"🧭 run_agent: user={user_id} session={session_id} prompt={prompt!r}")
    if session_id:
        wants_prompt, custom = _session_prompt_intent(prompt)
        if wants_prompt:
            if custom.lower() in {"nulstil", "reset", "standard", "default"}:
                from jarvis.agent import set_custom_prompt
                set_custom_prompt(session_id, None)
                return {
                    "text": "Session‑personlighed nulstillet. Jeg bruger standarden igen.",
                    "meta": {"tool_used": False},
                }
            if not custom:
                return {
                    "text": "Skriv den ønskede personlighed efter kommandoen, fx: /personlighed Kort, varm og praktisk.",
                    "meta": {"tool_used": False},
                }
            from jarvis.agent import set_custom_prompt
            set_custom_prompt(session_id, custom)
            return {
                "text": "Session‑personlighed opdateret.",
                "meta": {"tool_used": False},
            }
    profile = get_user_profile(user_id)
    display_name = _first_name(profile, user_id)
    user_id_int = (profile or {}).get("id")
    user_key = user_id
    is_admin_user = bool((profile or {}).get("is_admin"))
    reminders_due = get_due_reminders(user_id_int) if session_id and user_id_int else []
    pending_weather = _load_state(get_pending_weather(session_id)) if session_id else {}
    pending_note = _load_state(get_pending_note(session_id)) if session_id else {}
    pending_reminder = _load_state(get_pending_reminder(session_id)) if session_id else {}
    pending_file = _load_state(get_pending_file(session_id)) if session_id else {}
    pending_image_preview = _load_state(get_pending_image_preview(session_id)) if session_id else {}
    conversation_state = (
        ConversationState.from_json(get_conversation_state(session_id)) if session_id else ConversationState()
    )
    if session_id and get_conversation_state(session_id) is None:
        set_conversation_state(session_id, conversation_state.to_json())
    mode_request = _detect_response_mode(prompt)
    if mode_request and mode_request != conversation_state.response_mode:
        conversation_state.response_mode = mode_request

    preloaded = {
        "mem": mem,
        "session_hist": session_hist,
        "profile": profile,
        "display_name": display_name,
        "user_id_int": user_id_int,
        "user_key": user_key,
        "is_admin_user": is_admin_user,
        "reminders_due": reminders_due,
        "pending_weather": pending_weather,
        "pending_note": pending_note,
        "pending_reminder": pending_reminder,
        "pending_file": pending_file,
        "pending_image_preview": pending_image_preview,
        "conversation_state": conversation_state,
        "mode_request": mode_request,
    }

    from jarvis.agent import _run_agent_impl
    return _run_agent_impl(
        user_id=user_id,
        prompt=prompt,
        session_id=session_id,
        allowed_tools=allowed_tools,
        ui_city=ui_city,
        ui_lang=ui_lang,
        preloaded=preloaded,
    )