"""
Agent orchestrator - coordinates agent execution.
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional

from jarvis.agent_core.state_service import AgentStateService
from jarvis.notifications import add_notification
import time

last_turn_metrics: Dict[str, Any] | None = None

@dataclass
class TurnResult:
    reply_text: str
    meta: Dict[str, Any]
    data: Optional[Dict[str, Any]] = None
    audio: Optional[str] = None
    rendered_text: Optional[str] = None
    download_info: Optional[Dict[str, Any]] = None
    reminders_already_prepended: bool = False
    message_already_added: bool = False


def set_last_metric(key: str, value: Any) -> None:
    global last_turn_metrics
    if last_turn_metrics is None:
        last_turn_metrics = {}
    last_turn_metrics[key] = value


def get_last_metrics() -> Dict[str, Any] | None:
    return last_turn_metrics.copy() if last_turn_metrics else None

def coerce_to_turn_result(result: Dict[str, Any]) -> TurnResult:
    """Convert a legacy result dict to TurnResult."""
    return TurnResult(
        reply_text=result.get("text", ""),
        meta=result.get("meta", {}),
        data=result.get("data"),
        audio=result.get("audio"),
        rendered_text=result.get("rendered_text"),
        download_info=result.get("download_info"),
        reminders_already_prepended=False,
        message_already_added=False,
    )

def build_response(
    turn_result: TurnResult,
    session_id: str | None,
    reminders_due: list,
    user_id_int: int | None,
    prompt: str,
    user_id: str,
    memory_used: bool = False,
    resume_hint: str | None = None,
    ui_lang: str | None = None,
) -> Dict[str, Any]:
    """Apply final packaging: reminders, optional resume hint/transparency, persistence."""
    from jarvis.agent import _should_attach_reminders, _prepend_reminders, add_message
    from jarvis.agent_core.memory_manager import should_write_memory

    reply_text = turn_result.reply_text

    if resume_hint:
        reply_text = f"{resume_hint}\n{reply_text}"

    if not turn_result.reminders_already_prepended and reminders_due and _should_attach_reminders(prompt):
        reply_text = _prepend_reminders(reply_text, reminders_due, user_id_int)
    if session_id and not turn_result.message_already_added:
        add_message(session_id, "assistant", reply_text)

    # Memory transparency
    if memory_used:
        if ui_lang and ui_lang.lower().startswith("en"):
            reply_text += "\n(I used something you told me earlier.)"
        else:
            reply_text += "\n(Jeg brugte noget, du har fortalt mig før.)"

    # Memory writing
    memory_items = should_write_memory(prompt, reply_text)
    for item in memory_items:
        from jarvis.memory import add_memory
        add_memory("assistant", f"[{item.category}] {item.content}", user_id)

    return {
        "text": reply_text,
        "meta": turn_result.meta,
        "data": turn_result.data,
        "audio": turn_result.audio,
        "rendered_text": turn_result.rendered_text,
        "download_info": turn_result.download_info,
    }

def emit_notification(user_id: str, level: str, title: str, body: str, meta: Dict[str, Any] = None):
    """
    Helper function for skills to emit notifications.
    
    Args:
        user_id: The user ID to send the notification to
        level: Notification level ('info', 'warning', 'error', 'success')
        title: Short notification title
        body: Notification body text
        meta: Optional metadata dictionary
    """
    try:
        add_notification(user_id, level, title, body, meta or {})
    except Exception as e:
        # Log error but don't fail the calling operation
        print(f"Failed to emit notification: {e}")

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
    from jarvis.agent_core.conversation_state import ConversationState
    from jarvis.agent import get_conversation_state, set_conversation_state
    import time

    timings = {}
    start_total = time.time()

    def _finish(resp):
        timings.setdefault("total_ms", (time.time() - start_total) * 1000)
        set_last_metric("timings", timings)
        return resp

    start = time.time()
    mem = search_memory(prompt, user_id=user_id)
    try:
        from jarvis.memory import get_last_cache_status
        timings["memory_cache"] = get_last_cache_status()
    except Exception:
        pass
    timings["memory_ms"] = (time.time() - start) * 1000
    memory_used_flag = bool(mem)
    session_hist = get_recent_messages(session_id, limit=8) if session_id else []
    _debug(f"🧭 run_agent: user={user_id} session={session_id} prompt={prompt!r}")
    if session_id:
        wants_prompt, custom = _session_prompt_intent(prompt)
        if wants_prompt:
            if custom.lower() in {"nulstil", "reset", "standard", "default"}:
                from jarvis.agent import set_custom_prompt
                set_custom_prompt(session_id, None)
                result = {
                    "text": "Session‑personlighed nulstillet. Jeg bruger standarden igen.",
                    "meta": {"tool_used": False},
                }
                turn_result = coerce_to_turn_result(result)
                return _finish(build_response(turn_result, session_id, [], None, prompt, user_id, memory_used=False, resume_hint=None, ui_lang=ui_lang))
            if not custom:
                result = {
                    "text": "Skriv den ønskede personlighed efter kommandoen, fx: /personlighed Kort, varm og praktisk.",
                    "meta": {"tool_used": False},
                }
                turn_result = coerce_to_turn_result(result)
                return _finish(build_response(turn_result, session_id, [], None, prompt, user_id, memory_used=False, resume_hint=None, ui_lang=ui_lang))
            from jarvis.agent import set_custom_prompt
            set_custom_prompt(session_id, custom)
            result = {
                "text": "Session‑personlighed opdateret.",
                "meta": {"tool_used": False},
            }
            turn_result = coerce_to_turn_result(result)
            return _finish(build_response(turn_result, session_id, [], None, prompt, user_id, memory_used=False, resume_hint=None, ui_lang=ui_lang))
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
        "memory_used": memory_used_flag,
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

    # Memory retrieval
    from jarvis.agent_core.memory_manager import retrieve_context, handle_memory_commands
    memory_context = ""
    memory_command_response = handle_memory_commands(prompt, user_id, ui_lang)
    if memory_command_response:
        result = {
            "text": memory_command_response,
            "meta": {"tool_used": False},
        }
        turn_result = coerce_to_turn_result(result)
        resp = build_response(turn_result, session_id, preloaded["reminders_due"], preloaded["user_id_int"], prompt, user_id, memory_used=preloaded["memory_used"], resume_hint=preloaded.get("resume_hint"), ui_lang=ui_lang)
        timings["total_ms"] = (time.time() - start_total) * 1000
        set_last_metric("timings", timings)
        return resp
    
    from jarvis.agent_core.memory_manager import should_retrieve_memory
    if should_retrieve_memory(prompt, ui_lang):
        start_mem = time.time()
        memory_context = retrieve_context(user_id, prompt)
        timings["memory_retrieve_ms"] = (time.time() - start_mem) * 1000
        if memory_context:
            preloaded["mem"].append(f"assistant: {memory_context}")
            preloaded["memory_used"] = True

    # Pending resolution
    pending_city = None
    pending_scope = None
    pending_prompt = None
    if isinstance(preloaded["pending_weather"], dict) and preloaded["pending_weather"].get("awaiting_city"):
        from jarvis.agent import extract_location, _simple_city
        pending_city = extract_location(prompt) or _simple_city(prompt)
        if pending_city:
            pending_scope = preloaded["pending_weather"].get("scope") or "today"
            pending_prompt = preloaded["pending_weather"].get("prompt") or prompt
            from jarvis.agent import clear_pending_weather
            clear_pending_weather(session_id)
            preloaded["pending_weather"] = {}
    if isinstance(preloaded["pending_note"], dict) and preloaded["pending_note"].get("awaiting_note"):
        from jarvis.agent import _is_note_related
        if _is_note_related(prompt):
            from jarvis.agent import clear_pending_note
            clear_pending_note(session_id)
            preloaded["pending_note"] = {}
    if isinstance(preloaded["pending_reminder"], dict) and preloaded["pending_reminder"].get("awaiting_reminder"):
        from jarvis.agent import _is_reminder_related
        if _is_reminder_related(prompt):
            from jarvis.agent import clear_pending_reminder
            clear_pending_reminder(session_id)
            preloaded["pending_reminder"] = {}

    preloaded["pending_city"] = pending_city
    preloaded["pending_scope"] = pending_scope
    preloaded["pending_prompt"] = pending_prompt

    # Pending tool approval
    pending_tool = preloaded["conversation_state"].pending_tool_action if preloaded.get("conversation_state") else None
    if pending_tool:
        from jarvis.agent import _affirm_intent, _deny_intent
        if _affirm_intent(prompt):
            # Execute stored tool
            from jarvis.agent_core.tool_registry import call_tool
            try:
                result = call_tool(pending_tool["name"], pending_tool.get("args", {}), user_id, session_id)
                reply = result if isinstance(result, str) else str(result)
                if isinstance(result, dict) and "text" in result:
                    reply = result["text"]
                preloaded["conversation_state"].pending_tool_action = None
                set_conversation_state(session_id, preloaded["conversation_state"].to_json())
                return build_response(
                    TurnResult(reply_text=reply, meta={"tool": pending_tool["name"], "tool_used": True}),
                    session_id,
                    preloaded["reminders_due"],
                    preloaded["user_id_int"],
                    prompt,
                    user_id,
                    memory_used=preloaded["memory_used"],
                    resume_hint=preloaded.get("resume_hint"),
                    ui_lang=ui_lang,
                )
            except Exception as exc:
                preloaded["conversation_state"].pending_tool_action = None
                set_conversation_state(session_id, preloaded["conversation_state"].to_json())
                return {
                    "text": f"Tool '{pending_tool['name']}' failed: {exc}",
                    "meta": {"tool": pending_tool["name"], "tool_used": False},
                }
        if _deny_intent(prompt):
            preloaded["conversation_state"].pending_tool_action = None
            set_conversation_state(session_id, preloaded["conversation_state"].to_json())
            cancel_msg = "Forstår. Jeg kører ikke værktøjet." if not ui_lang or not ui_lang.startswith("en") else "Understood. I will not run the tool."
            return {
                "text": cancel_msg,
                "meta": {"tool": None, "tool_used": False},
            }

    # Resume hint (only once after inactivity)
    resume_hint_text = None
    if session_id:
        from datetime import datetime, timezone
        now_dt = datetime.now(timezone.utc)
        from jarvis.agent_core.conversation_state import should_show_resume_hint
        from jarvis.agent import _load_state, get_cv_state, get_story_state, _resume_context_reply

        cv_state_hint = _load_state(get_cv_state(session_id))
        story_state_hint = _load_state(get_story_state(session_id))
        if should_show_resume_hint(session_hist, now_dt, threshold_minutes=45, already_shown=conversation_state.resume_hint_shown):
            if cv_state_hint and not cv_state_hint.get("done"):
                resume_hint_text = "We were working on your CV. Want to continue?" if ui_lang and ui_lang.lower().startswith("en") else "Vi var i gang med at arbejde på dit CV. Vil du fortsætte?"
            elif story_state_hint and not story_state_hint.get("done"):
                resume_hint_text = "We were working on your story. Want to continue?" if ui_lang and ui_lang.lower().startswith("en") else "Vi var i gang med din historie. Vil du fortsætte?"
            elif preloaded["pending_note"]:
                resume_hint_text = "We were editing a note. Want to continue?" if ui_lang and ui_lang.lower().startswith("en") else "Vi var i gang med en note. Vil du fortsætte?"
            elif preloaded["pending_reminder"]:
                resume_hint_text = "We were setting a reminder. Want to continue?" if ui_lang and ui_lang.lower().startswith("en") else "Vi var i gang med en påmindelse. Vil du fortsætte?"
            elif preloaded["pending_weather"]:
                resume_hint_text = "We were fetching the weather. Want to continue?" if ui_lang and ui_lang.lower().startswith("en") else "Vi var i gang med vejret. Vil du fortsætte?"
            else:
                resume_hint_text = "We were mid-conversation. Want to continue?" if ui_lang and ui_lang.lower().startswith("en") else "Vi var i gang med en samtale. Vil du fortsætte?"
            conversation_state.resume_hint_shown = True
            set_conversation_state(session_id, conversation_state.to_json())

    preloaded["resume_hint"] = resume_hint_text

    # Dispatch
    from jarvis.agent_skills.files_skill import handle_files
    from jarvis.agent import _should_attach_reminders, _prepend_reminders, _affirm_intent, _deny_intent, _wants_previous_prompt
    file_response = handle_files(
        prompt=prompt,
        session_id=session_id,
        user_id=user_id,
        user_id_int=preloaded["user_id_int"],
        user_key=preloaded["user_key"],
        display_name=preloaded["display_name"],
        allowed_tools=allowed_tools,
        pending_file=preloaded["pending_file"],
        pending_image_preview=preloaded["pending_image_preview"],
        reminders_due=preloaded["reminders_due"],
        should_attach_reminders=_should_attach_reminders,
        prepend_reminders=_prepend_reminders,
        affirm_intent=_affirm_intent,
        deny_intent=_deny_intent,
        wants_previous_prompt=_wants_previous_prompt,
    )
    if file_response:
        return file_response

    if session_id:
        from jarvis.agent import _resume_context_intent, _load_state, get_cv_state, _resume_context_reply, add_message
        if _resume_context_intent(prompt):
            cv_state_active = _load_state(get_cv_state(session_id))
            reply = _resume_context_reply(cv_state_active, None, preloaded["pending_note"], preloaded["pending_reminder"], preloaded["pending_weather"])
            if preloaded["reminders_due"] and _should_attach_reminders(prompt):
                reply = _prepend_reminders(reply, preloaded["reminders_due"], preloaded["user_id_int"])
            add_message(session_id, "assistant", reply)
            turn_result = TurnResult(reply_text=reply, meta={"tool": None, "tool_used": False}, reminders_already_prepended=True, message_already_added=True)
            resp = build_response(turn_result, session_id, preloaded["reminders_due"], preloaded["user_id_int"], prompt, user_id, memory_used=preloaded["memory_used"], resume_hint=preloaded.get("resume_hint"), ui_lang=ui_lang)
            timings["total_ms"] = (time.time() - start_total) * 1000
            set_last_metric("timings", timings)
            return resp

    from jarvis.agent_skills.admin_skill import handle_admin
    admin_response = handle_admin(user_id, prompt, session_id, allowed_tools, ui_city, ui_lang, user_id_int=preloaded["user_id_int"])
    if admin_response:
        return admin_response

    from jarvis.agent_skills.cv_skill import handle_cv
    cv_response = handle_cv(user_id, prompt, session_id, allowed_tools, ui_city, ui_lang, preloaded["user_id_int"], preloaded["reminders_due"], preloaded["profile"])
    if cv_response:
        return cv_response

    from jarvis.agent import get_mode
    mode = get_mode(session_id) if session_id else "balanced"
    preloaded["mode"] = mode
    from jarvis.agent_skills.history_skill import handle_history
    history_response = handle_history(user_id, prompt, session_id, allowed_tools, ui_city, ui_lang, preloaded["reminders_due"], preloaded["user_id_int"])
    if history_response:
        return history_response

    from jarvis.agent_skills.process_skill import handle_process
    process_response = handle_process(user_id, prompt, session_id, allowed_tools, ui_city, ui_lang, reminders_due=preloaded["reminders_due"], user_id_int=preloaded["user_id_int"], display_name=preloaded["display_name"])
    if process_response:
        return process_response

    # Code skill (code RAG)
    try:
        from jarvis.agent_skills.code_skill import handle_code_question
        code_state = AgentStateService(user_id, session_id) if session_id else None
        code_response = handle_code_question(
            prompt=prompt,
            state=code_state,
            user_id=user_id,
            session_id=session_id,
            ui_lang=ui_lang,
            allowed_tools=allowed_tools,
            user_id_int=preloaded["user_id_int"],
        )
        if code_response:
            return code_response
    except Exception:
        pass

    from jarvis.agent_skills.story_skill import handle_story
    story_response = handle_story(user_id, prompt, session_id, allowed_tools, ui_city, ui_lang, preloaded["user_id_int"], preloaded["reminders_due"], preloaded["profile"])
    if story_response:
        timings["total_ms"] = (time.time() - start_total) * 1000
        set_last_metric("timings", timings)
        return story_response

    # Fallback
    from jarvis.agent import _run_agent_core_fallback
    turn_result = _run_agent_core_fallback(
        user_id=user_id,
        prompt=prompt,
        session_id=session_id,
        allowed_tools=allowed_tools,
        ui_city=ui_city,
        ui_lang=ui_lang,
        preloaded=preloaded,
    )
    resp = build_response(turn_result, session_id, preloaded["reminders_due"], preloaded["user_id_int"], prompt, user_id, memory_used=preloaded["memory_used"], resume_hint=preloaded.get("resume_hint"), ui_lang=ui_lang)
    timings["total_ms"] = (time.time() - start_total) * 1000
    set_last_metric("timings", timings)
    return resp
