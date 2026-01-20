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
    user_id_int: int | None = None,
    reminders_due: list | None = None,
    profile: dict | None = None,
):
    """
    Handle CV intents and flow.
    Returns a response dict with 'text' and 'meta', or None if not handled.
    """
    # Local imports to avoid circular dependencies
    from jarvis.agent import (
        _cv_intent, _cv_cancel_intent, _cancel_with_followup, _cv_own_intent, _cv_example_intent,
        _cv_help_intent, _show_cv_intent, _continue_cv_intent, _save_permanent_intent, _save_later_intent,
        _finalize_intent, _detect_format, _write_cv_file, _make_download_link, _download_notice, _wrap_download_link,
        _should_attach_reminders, _prepend_reminders, _affirm_intent, _deny_intent, _load_state, get_cv_state,
        set_cv_state, add_message, _init_cv_state, _update_state, _next_question, CV_QUESTIONS, _cv_prompt_from_state,
        _extract_cv_query, call_ollama, _summarize_text, tools, JARVIS_CV, CV_STRUCTURE_TEMPLATE
    )

    skip_cv_intent = False

    # CV cancel intent
    if session_id and _cv_cancel_intent(prompt):
        set_cv_state(session_id, json.dumps({}))
        has_followup, stripped = _cancel_with_followup(prompt)
        if stripped:
            prompt = stripped
        if has_followup:
            skip_cv_intent = True
        else:
            if _cv_own_intent(prompt):
                reply = JARVIS_CV + "\nVil du have, at vi fortsætter og laver dit CV?"
            elif _cv_example_intent(prompt):
                reply = CV_STRUCTURE_TEMPLATE + "\nVil du have, at vi fortsætter og laver dit CV?"
            else:
                reply = "Forstået. Jeg lægger CV‑arbejdet på is. Hvad vil du i stedet?"
            if reminders_due and _should_attach_reminders(prompt):
                reply = _prepend_reminders(reply, reminders_due, user_id_int)
            add_message(session_id, "assistant", reply)
            return {"text": reply, "meta": {"tool": None, "tool_used": False}}

    # CV help/example/own intents
    if _cv_help_intent(prompt):
        reply = (
            "CV‑kommandoer:\n"
            "• /cv eksempel — viser CV‑struktur + kort eksempel\n"
            "• /cv jarvis — viser JARVIS‑CV (eksempel)\n"
            "\n"
            "Vil du have, at vi fortsætter og laver dit CV?"
        )
        if reminders_due and _should_attach_reminders(prompt):
            reply = _prepend_reminders(reply, reminders_due, user_id_int)
        add_message(session_id, "assistant", reply)
        return {"text": reply, "meta": {"tool": None, "tool_used": False}}
    if _cv_example_intent(prompt):
        reply = CV_STRUCTURE_TEMPLATE + "\nVil du have, at vi fortsætter og laver dit CV?"
        if reminders_due and _should_attach_reminders(prompt):
            reply = _prepend_reminders(reply, reminders_due, user_id_int)
        add_message(session_id, "assistant", reply)
        return {"text": reply, "meta": {"tool": None, "tool_used": False}}
    if _cv_own_intent(prompt):
        reply = JARVIS_CV + "\n\n" + CV_STRUCTURE_TEMPLATE + "\nVil du have, at vi fortsætter og laver dit CV?"
        if reminders_due and _should_attach_reminders(prompt):
            reply = _prepend_reminders(reply, reminders_due, user_id_int)
        add_message(session_id, "assistant", reply)
        return {"text": reply, "meta": {"tool": None, "tool_used": False}}

    # Affirm/deny for CV
    cv_state_active = _load_state(get_cv_state(session_id)) if session_id else None
    if session_id and _deny_intent(prompt):
        if cv_state_active:
            set_cv_state(session_id, json.dumps({}))
            reply = (
                "Som De ønsker. Vi parkerer CV‑arbejdet for nu. "
                "Skal vi kigge på noget andet — fx noter, vejret eller en kort opsummering?"
            )
            add_message(session_id, "assistant", reply)
            return {"text": reply, "meta": {"tool": None, "tool_used": False}}
    if session_id and _affirm_intent(prompt):
        if cv_state_active and cv_state_active.get("pending_start"):
            start_prompt = cv_state_active.get("prompt") or prompt
            cv_state = _init_cv_state(start_prompt)
            set_cv_state(session_id, json.dumps(cv_state))
            guidance = ""
            query = _extract_cv_query(start_prompt)
            search_result = tools.search_combined(query, max_items=5)
            if isinstance(search_result, dict) and search_result.get("items"):
                snippets = []
                for item in search_result["items"][:3]:
                    url = item.get("url")
                    if url:
                        article = tools.read_article(url)
                        summary = _summarize_text((article or {}).get("text") or "", sentences=1)
                        if summary:
                            snippets.append(summary)
                if snippets:
                    candidate = _summarize_text(" ".join(snippets), sentences=1)
                    if candidate and len(candidate) >= 40 and "send teksten" not in candidate.lower():
                        guidance = candidate
            first_q = _next_question(cv_state, CV_QUESTIONS)
            reply = "Fint. Jeg stiller et par korte spørgsmål."
            if guidance:
                reply += f"\nKort råd (fra søgning): {guidance}"
            if first_q:
                reply += f"\n{first_q}"
            add_message(session_id, "assistant", reply)
            return {"text": reply, "meta": {"tool": None, "tool_used": False}}
        if cv_state_active and not cv_state_active.get("done"):
            next_q = _next_question(cv_state_active, CV_QUESTIONS)
            reply = f"Naturligvis. {next_q}" if next_q else "Naturligvis. Hvad vil du tilføje?"
            add_message(session_id, "assistant", reply)
            return {"text": reply, "meta": {"tool": None, "tool_used": False}}

    # Initial CV intent
    if session_id and _cv_intent(prompt) and not skip_cv_intent and not _load_state(get_cv_state(session_id)):
        set_cv_state(session_id, json.dumps({"pending_start": True, "prompt": prompt}, ensure_ascii=False))
        reply = "Vil du have, at jeg hjælper dig med et CV? Svar ja/nej."
        add_message(session_id, "assistant", reply)
        return {"text": reply, "meta": {"tool": None, "tool_used": False}}

    # CV state handling
    cv_state = _load_state(get_cv_state(session_id)) if session_id else None
    if cv_state:
        if cv_state.get("draft") and not cv_state.get("finalized"):
            if _save_permanent_intent(prompt):
                cv_state["persist"] = True
                set_cv_state(session_id, json.dumps(cv_state))
                reply = "Forstået. Jeg gemmer CV'et permanent, når du beder om download."
                add_message(session_id, "assistant", reply)
                return {"text": reply, "meta": {"tool": None, "tool_used": False}}
            if _save_later_intent(prompt):
                reply = "Fint. Jeg gemmer kladden til senere. Skriv 'vis cv' når du vil se den igen."
                add_message(session_id, "assistant", reply)
                return {"text": reply, "meta": {"tool": None, "tool_used": False}}
            if _show_cv_intent(prompt):
                reply = cv_state.get("draft", "")
                reply += "\n\nVil du have den gemt som pdf, docx eller txt?"
                add_message(session_id, "assistant", reply)
                return {"text": reply, "meta": {"tool": None, "tool_used": False}}
            fmt = _detect_format(prompt)
            if fmt:
                cv_state["format"] = fmt
                set_cv_state(session_id, json.dumps(cv_state))
                reply = f"Format sat til {fmt.upper()}. Skriv 'gem' når du vil have download-link."
                add_message(session_id, "assistant", reply)
                return {"text": reply, "meta": {"tool": None, "tool_used": False}}
            if _finalize_intent(prompt):
                fmt = cv_state.get("format") or "txt"
                temp = not cv_state.get("persist")
                filename = _write_cv_file(user_id, cv_state.get("draft", ""), fmt, temp=temp)
                if not filename:
                    reply = "Jeg kan ikke gemme i det format. Vælg pdf, docx eller txt."
                    add_message(session_id, "assistant", reply)
                    return {"text": reply, "meta": {"tool": None, "tool_used": False}}
                url = _make_download_link(user_id_int, session_id, filename, temp)
                cv_state["finalized"] = True
                cv_state["file"] = filename
                set_cv_state(session_id, json.dumps(cv_state))
                reply = f"Her er dit CV: {_wrap_download_link(url)}\n{_download_notice()}"
                if temp:
                    reply += "\nFilen slettes automatisk efter download, medmindre du beder mig gemme den."
                data = {"type": "file", "title": "CV", "label": "Download CV", "url": url}
                add_message(session_id, "assistant", reply)
                return {"text": reply, "data": data, "meta": {"tool": None, "tool_used": False}}
            if _continue_cv_intent(prompt):
                cv_state["edit_mode"] = True
                set_cv_state(session_id, json.dumps(cv_state))
                reply = "Skriv hvad du vil ændre eller tilføje."
                add_message(session_id, "assistant", reply)
                return {"text": reply, "meta": {"tool": None, "tool_used": False}}
            if cv_state.get("edit_mode"):
                extra = cv_state.setdefault("answers", {}).get("other", "")
                cv_state["answers"]["other"] = (extra + "\n" + prompt).strip()
                cv_state["edit_mode"] = False
                set_cv_state(session_id, json.dumps(cv_state))
                reply = "Noteret. Skriv 'gem' for download-link eller vælg format (pdf/docx/txt)."
                add_message(session_id, "assistant", reply)
                return {"text": reply, "meta": {"tool": None, "tool_used": False}}
        if cv_state.get("step", 0) >= 0 and not cv_state.get("done"):
            cv_state = _update_state(cv_state, prompt, CV_QUESTIONS)
            next_q = _next_question(cv_state, CV_QUESTIONS)
            if next_q:
                set_cv_state(session_id, json.dumps(cv_state))
                reply = next_q
                add_message(session_id, "assistant", reply)
                return {"text": reply, "meta": {"tool": None, "tool_used": False}}
            cv_state["done"] = True
            profile_name = (profile or {}).get("full_name") or user_id
            cv_prompt = _cv_prompt_from_state(cv_state)
            system = (
                "Du skriver et professionelt dansk CV. Brug kun info i prompten. "
                "Formatér med overskrifter og punktform. Vær kort og præcis."
            )
            cv_messages = [
                {"role": "system", "content": system},
                {"role": "assistant", "content": f"Navn: {profile_name}\n{cv_prompt}"},
                {"role": "user", "content": "Skriv et CV-kladdetekst."},
            ]
            res = call_ollama(cv_messages)
            cv_text = res.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            if not cv_text:
                cv_text = "Jeg kunne ikke generere et CV lige nu."
            cv_state["draft"] = cv_text
            cv_state["finalized"] = False
            set_cv_state(session_id, json.dumps(cv_state))
            if cv_state.get("auto_finalize") and cv_state.get("format"):
                fmt = cv_state.get("format") or "txt"
                temp = not cv_state.get("persist")
                filename = _write_cv_file(user_id, cv_text, fmt, temp=temp)
                if filename:
                    url = _make_download_link(user_id_int, session_id, filename, temp)
                    cv_state["finalized"] = True
                    cv_state["file"] = filename
                    set_cv_state(session_id, json.dumps(cv_state))
                    reply = f"{cv_text}\n\nHer er dit CV: {_wrap_download_link(url)}\n{_download_notice()}"
                    if temp:
                        reply += "\nFilen slettes automatisk efter download, medmindre du beder mig gemme den."
                    data = {"type": "file", "title": "CV", "label": "Download CV", "url": url}
                    add_message(session_id, "assistant", reply)
                    return {"text": reply, "data": data, "meta": {"tool": None, "tool_used": False}}
            reply = cv_text + "\n\nVil du have det gemt som pdf, docx eller txt?"
            add_message(session_id, "assistant", reply)
            return {"text": reply, "meta": {"tool": None, "tool_used": False}}

    # Show CV intent outside state
    if _show_cv_intent(prompt):
        reply = "Jeg har ingen CV-kladde endnu. Start med at skrive, at du vil lave et CV."
        add_message(session_id, "assistant", reply)
        return {"text": reply, "meta": {"tool": None, "tool_used": False}}

    return None  # No CV intent handled