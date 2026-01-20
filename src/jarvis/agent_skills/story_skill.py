"""
Story skill handler - thin wrapper for story-related intents.
"""

import json
import re

STORY_QUESTIONS = [
    ("topic", "Hvad skal historien/stilen handle om?"),
    ("genre", "Hvilken genre eller type ønsker du? (fx realistisk, humor, sci‑fi, essay)"),
    ("length", "Hvor lang skal den være? (kort/mellem/lang)"),
    ("tone", "Hvilken tone skal den have? (fx varm, neutral, dramatisk)"),
    ("audience", "Hvem er målgruppen?"),
]


def _story_prompt_from_state(state: dict) -> str:
    answers = state.get("answers", {})
    lines = []
    for key, label in STORY_QUESTIONS:
        value = answers.get(key)
        if value:
            lines.append(f"{label} {value}")
    return "\n".join(lines)


def handle_story(
    user_id: str,
    prompt: str,
    session_id: str | None = None,
    allowed_tools: list[str] | None = None,
    ui_city: str | None = None,
    ui_lang: str | None = None,
    user_id_int: int | None = None,
    reminders_due: list | None = None,
    profile: dict | None = None,
):
    """
    Handle story intents and flow.
    Returns a response dict with 'text' and 'meta', or None if not handled.
    """
    # Local imports to avoid circular dependencies
    from jarvis.agent import (
        _story_intent, _load_state, get_story_state, _extract_story_topic,
        _story_needs_questions, _detect_format, _save_text_intent, _save_permanent_intent,
        set_story_state, add_message, _update_state, _next_question, call_ollama, _summarize_text,
        tools, _write_text_file, _make_download_link, _download_notice, _wrap_download_link,
        _save_permanent_intent, _save_later_intent, _finalize_intent, _should_attach_reminders, _prepend_reminders
    )

    # Cancel story intent
    if session_id and prompt.lower().strip().startswith("annuller historie"):
        set_story_state(session_id, json.dumps({}))
        reply = "Historie-flow annulleret."
        if reminders_due and _should_attach_reminders(prompt):
            reply = _prepend_reminders(reply, reminders_due, user_id_int)
        add_message(session_id, "assistant", reply)
        return {"text": reply, "meta": {"tool": None, "tool_used": False}}

    # Initial story intent
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
            system = (
                "Du skriver en kort dansk historie. Brug kun info i prompten. "
                "Skriv flydende og sammenhængende."
            )
            story_messages = [
                {"role": "system", "content": system},
                {"role": "assistant", "content": story_prompt},
                {"role": "user", "content": "Skriv historien."},
            ]
            res = call_ollama(story_messages)
            story_text = res.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            if not story_text:
                story_text = "Jeg kunne ikke skrive historien lige nu."
            story_state["draft"] = story_text
            story_state["done"] = True
            set_story_state(session_id, json.dumps(story_state))
            if story_state.get("auto_finalize") and story_state.get("format"):
                fmt = story_state.get("format") or "txt"
                temp = not story_state.get("persist")
                filename = _write_text_file(user_id, story_text, fmt, "tekst", temp=temp)
                if filename:
                    url = _make_download_link(user_id_int, session_id, filename, temp)
                    reply = f"{story_text}\n\nHer er din tekst: {_wrap_download_link(url)}\n{_download_notice()}"
                    if temp:
                        reply += "\nFilen slettes automatisk efter download, medmindre du beder mig gemme den."
                    data = {"type": "file", "title": "Tekst", "label": "Download tekst", "url": url}
                    add_message(session_id, "assistant", reply)
                    return {"text": reply, "data": data, "meta": {"tool": None, "tool_used": False}}
            reply = story_text + "\n\nVil du have den gemt som pdf, docx eller txt?"
            if reminders_due and _should_attach_reminders(prompt):
                reply = _prepend_reminders(reply, reminders_due, user_id_int)
            add_message(session_id, "assistant", reply)
            return {"text": reply, "meta": {"tool": None, "tool_used": False}}
        first_q = _next_question(story_state, STORY_QUESTIONS)
        reply = "Jeg kan skrive en historie eller en stil. Jeg stiller et par spørgsmål."
        if first_q:
            reply += f"\n{first_q}"
        if reminders_due and _should_attach_reminders(prompt):
            reply = _prepend_reminders(reply, reminders_due, user_id_int)
        add_message(session_id, "assistant", reply)
        return {"text": reply, "meta": {"tool": None, "tool_used": False}}

    # Story state handling
    story_state = _load_state(get_story_state(session_id)) if session_id else None
    if story_state:
        if story_state.get("draft") and not story_state.get("finalized"):
            if _save_permanent_intent(prompt):
                story_state["persist"] = True
                set_story_state(session_id, json.dumps(story_state))
                reply = "Forstået. Jeg gemmer teksten permanent, når du beder om download."
                if reminders_due and _should_attach_reminders(prompt):
                    reply = _prepend_reminders(reply, reminders_due, user_id_int)
                add_message(session_id, "assistant", reply)
                return {"text": reply, "meta": {"tool": None, "tool_used": False}}
            if _save_later_intent(prompt):
                reply = "Fint. Jeg gemmer kladden til senere. Skriv 'vis tekst' for at få den igen."
                if reminders_due and _should_attach_reminders(prompt):
                    reply = _prepend_reminders(reply, reminders_due, user_id_int)
                add_message(session_id, "assistant", reply)
                return {"text": reply, "meta": {"tool": None, "tool_used": False}}
            if prompt.lower().strip().startswith("vis tekst"):
                reply = story_state.get("draft", "")
                reply += "\n\nVil du have den gemt som pdf, docx eller txt?"
                if reminders_due and _should_attach_reminders(prompt):
                    reply = _prepend_reminders(reply, reminders_due, user_id_int)
                add_message(session_id, "assistant", reply)
                return {"text": reply, "meta": {"tool": None, "tool_used": False}}
            fmt = _detect_format(prompt)
            if fmt:
                story_state["format"] = fmt
                set_story_state(session_id, json.dumps(story_state))
                reply = f"Format sat til {fmt.upper()}. Skriv 'gem' når du vil have download-link."
                if reminders_due and _should_attach_reminders(prompt):
                    reply = _prepend_reminders(reply, reminders_due, user_id_int)
                add_message(session_id, "assistant", reply)
                return {"text": reply, "meta": {"tool": None, "tool_used": False}}
            if _finalize_intent(prompt):
                fmt = story_state.get("format") or "txt"
                temp = not story_state.get("persist")
                filename = _write_text_file(user_id, story_state.get("draft", ""), fmt, "tekst", temp=temp)
                if not filename:
                    reply = "Jeg kan ikke gemme i det format. Vælg pdf, docx eller txt."
                    if reminders_due and _should_attach_reminders(prompt):
                        reply = _prepend_reminders(reply, reminders_due, user_id_int)
                    add_message(session_id, "assistant", reply)
                    return {"text": reply, "meta": {"tool": None, "tool_used": False}}
                url = _make_download_link(user_id_int, session_id, filename, temp)
                story_state["finalized"] = True
                story_state["file"] = filename
                set_story_state(session_id, json.dumps(story_state))
                reply = f"Her er din tekst: {_wrap_download_link(url)}\n{_download_notice()}"
                if temp:
                    reply += "\nFilen slettes automatisk efter download, medmindre du beder mig gemme den."
                data = {"type": "file", "title": "Tekst", "label": "Download tekst", "url": url}
                if reminders_due and _should_attach_reminders(prompt):
                    reply = _prepend_reminders(reply, reminders_due, user_id_int)
                add_message(session_id, "assistant", reply)
                return {"text": reply, "data": data, "meta": {"tool": None, "tool_used": False}}
        if story_state.get("step", 0) >= 0 and not story_state.get("done"):
            story_state = _update_state(story_state, prompt, STORY_QUESTIONS)
            next_q = _next_question(story_state, STORY_QUESTIONS)
            if next_q:
                set_story_state(session_id, json.dumps(story_state))
                reply = next_q
                if reminders_due and _should_attach_reminders(prompt):
                    reply = _prepend_reminders(reply, reminders_due, user_id_int)
                add_message(session_id, "assistant", reply)
                return {"text": reply, "meta": {"tool": None, "tool_used": False}}
            story_state["done"] = True
            set_story_state(session_id, json.dumps(story_state))
            story_prompt = _story_prompt_from_state(story_state)
            research = ""
            if story_state.get("needs_research"):
                topic = story_state.get("answers", {}).get("topic")
                if topic:
                    search_result = tools.search_combined(topic, max_items=5)
                    facts = []
                    for item in (search_result or {}).get("items", [])[:3]:
                        url = item.get("url")
                        if url:
                            article = tools.read_article(url)
                            summary = _summarize_text((article or {}).get("text") or "", sentences=1)
                            if summary:
                                facts.append(summary)
                    if facts:
                        research = "Fakta (fra søgning): " + " ".join(facts)
            system = (
                "Du skriver en dansk historie eller stil. Brug kun info i prompten. "
                "Hvis der er fakta, brug kun dem. Skriv flydende og sammenhængende."
            )
            story_messages = [
                {"role": "system", "content": system},
                {"role": "assistant", "content": f"{story_prompt}\n{research}".strip()},
                {"role": "user", "content": "Skriv teksten."},
            ]
            res = call_ollama(story_messages)
            story_text = res.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            if not story_text:
                story_text = "Jeg kunne ikke skrive teksten lige nu."
            story_state["draft"] = story_text
            story_state["finalized"] = False
            set_story_state(session_id, json.dumps(story_state))
            if story_state.get("auto_finalize") and story_state.get("format"):
                fmt = story_state.get("format") or "txt"
                temp = not story_state.get("persist")
                filename = _write_text_file(user_id, story_text, fmt, "tekst", temp=temp)
                if filename:
                    url = _make_download_link(user_id_int, session_id, filename, temp)
                    reply = f"{story_text}\n\nHer er din tekst: {_wrap_download_link(url)}\n{_download_notice()}"
                    if temp:
                        reply += "\nFilen slettes automatisk efter download, medmindre du beder mig gemme den."
                    data = {"type": "file", "title": "Tekst", "label": "Download tekst", "url": url}
                    if reminders_due and _should_attach_reminders(prompt):
                        reply = _prepend_reminders(reply, reminders_due, user_id_int)
                    add_message(session_id, "assistant", reply)
                    return {"text": reply, "data": data, "meta": {"tool": None, "tool_used": False}}
            reply = story_text + "\n\nVil du have den gemt som pdf, docx eller txt?"
            if reminders_due and _should_attach_reminders(prompt):
                reply = _prepend_reminders(reply, reminders_due, user_id_int)
            add_message(session_id, "assistant", reply)
            return {"text": reply, "meta": {"tool": None, "tool_used": False}}

    return None  # No story intent handled