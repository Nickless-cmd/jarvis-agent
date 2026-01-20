"""Code search skill backed by local code index."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Callable

from jarvis.agent_core.state_service import AgentStateService
from jarvis.agent_format.text import _shorten
from jarvis.code_rag.search import CodeHit, search_code
from jarvis.memory import add_memory


def _code_question_intent(prompt: str) -> bool:
    p = prompt.lower()
    keywords = [
        "kode",
        "code",
        "funktion",
        "function",
        "fil",
        "file",
        "linje",
        "line",
        "bug",
        "fejl",
        "traceback",
        "stacktrace",
        "test",
        "pytest",
        "hvordan i koden",
        "where in the code",
    ]
    return any(k in p for k in keywords)


def _summary_bullets(hits: list[CodeHit], ui_lang: str | None = None) -> list[str]:
    bullets = []
    for i, hit in enumerate(hits[:4]):  # 2-4 bullets
        excerpt = _shorten(hit.excerpt or "", 100)
        if ui_lang and ui_lang.lower().startswith("en"):
            bullets.append(f"- Relevant code in {hit.path}: {excerpt}")
        else:
            bullets.append(f"- Relevant kode i {hit.path}: {excerpt}")
    return bullets


def _where_in_code(hits: list[CodeHit], ui_lang: str | None = None) -> str:
    if ui_lang and ui_lang.lower().startswith("en"):
        section = "Where in code:"
    else:
        section = "Hvor i koden:"
    lines = [section]
    for hit in hits:
        lines.append(f"- {hit.path}:{hit.start_line}-{hit.end_line}")
    return "\n".join(lines)


def _next_step_suggestion(ui_lang: str | None = None) -> str:
    if ui_lang and ui_lang.lower().startswith("en"):
        return "Next step: Ask me to show the full code snippet or explain a specific part."
    return "Næste skridt: Bed mig vise hele kodeudsnittet eller forklare en bestemt del."


def _no_hits_reply(ui_lang: str | None = None) -> str:
    if ui_lang and ui_lang.lower().startswith("en"):
        return "I could not find anything relevant in the codebase right now."
    return "Jeg fandt ikke noget relevant i kodebasen lige nu."


def handle_code_question(
    prompt: str,
    state: AgentStateService,
    user_id: str,
    session_id: str | None,
    ui_lang: str | None,
    allowed_tools: list[str] | None,
    repo_root: Path | None = None,
    index_dir: Path | None = None,
    reminders_due=None,
    should_attach_reminders: Callable | None = None,
    prepend_reminders: Callable | None = None,
    user_id_int: int | None = None,
) -> dict | None:
    """Handle code questions via local code RAG. Returns response dict or None."""
    if allowed_tools is not None and "code" not in allowed_tools:
        return None
    if not _code_question_intent(prompt):
        return None

    try:
        hits = search_code(prompt, k=5, repo_root=repo_root, index_dir=index_dir)
    except Exception as exc:
        if ui_lang and ui_lang.lower().startswith("en"):
            reply = f"I could not search the codebase right now: {exc}"
        else:
            reply = f"Jeg kunne ikke søge i kodebasen lige nu: {exc}"
        add_memory("assistant", reply, user_id=user_id)
        if session_id:
            state.add_message("assistant", reply)
        return {"text": reply, "meta": {"tool": "code_search", "tool_used": False}}

    if not hits:
        reply = _no_hits_reply(ui_lang)
        if reminders_due and should_attach_reminders and should_attach_reminders(prompt):
            reply = prepend_reminders(reply, reminders_due, user_id_int)  # type: ignore[arg-type]
        add_memory("assistant", reply, user_id=user_id)
        if session_id:
            state.add_message("assistant", reply)
        return {"text": reply, "meta": {"tool": "code_search", "tool_used": True}}

    # New format
    summary = _summary_bullets(hits, ui_lang)
    where_section = _where_in_code(hits, ui_lang)
    next_step = _next_step_suggestion(ui_lang)
    reply = "\n".join(summary + [where_section, next_step])

    if reminders_due and should_attach_reminders and should_attach_reminders(prompt):
        reply = prepend_reminders(reply, reminders_due, user_id_int)  # type: ignore[arg-type]

    payload = {
        "tool": "code_search",
        "hits": [
            {
                "path": h.path,
                "start_line": h.start_line,
                "end_line": h.end_line,
                "score": h.score,
            }
            for h in hits
        ],
        "query": prompt,
    }
    if session_id:
        state.set_last_tool(json.dumps(payload, ensure_ascii=False))
        state.add_message("assistant", reply)
    add_memory("assistant", reply, user_id=user_id)
    return {"text": reply, "meta": {"tool": "code_search", "tool_used": True}}