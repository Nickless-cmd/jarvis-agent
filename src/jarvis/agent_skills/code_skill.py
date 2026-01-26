"""Code search skill backed by local code index."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Callable

from jarvis.agent_core.state_service import AgentStateService
from jarvis.agent import _shorten
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


def _pytest_triage_intent(prompt: str) -> bool:
    """Detect if the prompt contains pytest failure output or asks for pytest triage."""
    p = prompt.lower()
    if "pytest" in p and ("fejl" in p or "fail" in p or "triage" in p or "analys" in p):
        return True
    if "failures" in prompt or "FAILED" in prompt or "ERROR" in prompt:
        if "::" in prompt or "E   " in prompt:
            return True
    return False


def _file_explain_intent(prompt: str) -> str | None:
    match = re.search(r"(?:forklar|explain)\s+fil(?:e)?(?:n)?\s+([^\s]+)", prompt, flags=re.I)
    if match:
        return match.group(1).strip()
    match = re.search(r"(?:show|vis)\s+fil(?:e)?(?:n)?\s+([^\s]+)", prompt, flags=re.I)
    if match:
        return match.group(1).strip()
    return None


def _function_intent(prompt: str) -> str | None:
    match = re.search(r"funktion(?:en)?\s+([a-zA-Z0-9_]+)", prompt, flags=re.I)
    if match:
        return match.group(1).strip()
    match = re.search(r"function\s+([a-zA-Z0-9_]+)", prompt, flags=re.I)
    if match:
        return match.group(1).strip()
    return None


def _symbol_usage_intent(prompt: str) -> str | None:
    match = re.search(r"symbol\s+([a-zA-Z0-9_/.]+).*bruges", prompt, flags=re.I)
    if match:
        return match.group(1).strip()
    match = re.search(r"bruges\s+([a-zA-Z0-9_/.]+)", prompt, flags=re.I)
    if match:
        return match.group(1).strip()
    match = re.search(r"where\s+([a-zA-Z0-9_/.]+)\s+is\s+used", prompt, flags=re.I)
    if match:
        return match.group(1).strip()
    return None


def _test_fail_intent(prompt: str) -> str | None:
    match = re.search(r"test\s+([a-zA-Z0-9_/.:-]+)", prompt, flags=re.I)
    if match and ("fejl" in prompt.lower() or "fail" in prompt.lower()):
        return match.group(1).strip()
    return None


def _fix_suggestion_intent(prompt: str) -> str | None:
    if any(k in prompt.lower() for k in ["forslag til fix", "suggest fix", "how to fix", "hvordan løser jeg"]):
        match = re.search(r"fix\s+for\s+(.+)", prompt, flags=re.I)
        if match:
            return match.group(1).strip()
        return prompt
    return None


def _safe_read_file(path_str: str, repo_root: Path | None = None, max_bytes: int = 65536) -> tuple[str | None, str | None]:
    """Safely read a file within repo_root."""
    if not path_str:
        return None, "No path provided."
    root = (repo_root or Path(".")).resolve()
    candidate = (root / path_str).resolve()
    try:
        candidate.relative_to(root)
    except Exception:
        return None, "Path outside repository."
    if not candidate.is_file():
        return None, "File not found."
    if candidate.stat().st_size > max_bytes:
        return None, "File too large to read."
    try:
        text = candidate.read_text(encoding="utf-8", errors="ignore")
        return text, None
    except Exception as exc:  # pragma: no cover
        return None, str(exc)


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
    rag_hash: str | None = None,
    trace_id: str | None = None,
) -> dict | None:
    """
    Handle code questions via local code RAG. Returns response dict or None.
    
    Args:
        rag_hash: Pre-computed hash from retrieve_code_rag_async (for non-blocking RAG)
        trace_id: Optional trace ID for cancellation checking
    """
    if allowed_tools is not None and "code" not in allowed_tools:
        return None

    # Pytest triage flow
    if _pytest_triage_intent(prompt):
        from jarvis.triage.pytest_triage import parse_pytest_output, suggest_next_queries

        parsed = parse_pytest_output(prompt)
        queries = suggest_next_queries(parsed)
        hits: list[CodeHit] = []
        if queries:
            try:
                hits = search_code(" ".join(queries), k=5, repo_root=repo_root, index_dir=index_dir, trace_id=trace_id)
            except Exception as exc:
                reply = (
                    f"I could not search the codebase right now: {exc}"
                    if ui_lang and ui_lang.lower().startswith("en")
                    else f"Jeg kunne ikke søge i kodebasen lige nu: {exc}"
                )
                add_memory("assistant", reply, user_id=user_id)
                if session_id and state:
                    state.add_message("assistant", reply)
                return {"text": reply, "meta": {"tool": "pytest_triage", "tool_used": False}}

        # Build response
        lang_en = ui_lang and ui_lang.lower().startswith("en")
        header = "Hypothesis" if lang_en else "Hypotese"
        etype = parsed.get("error_type") or ("pytest failure" if lang_en else "pytest-fejl")
        emsg = parsed.get("error_message")
        lines = [f"{header}: {etype}"]
        if emsg:
            lines.append(emsg[:200])

        if hits:
            lines.append("Where:" if lang_en else "Hvor:")
            for hit in hits[:3]:
                snippet = _shorten(hit.excerpt or "", 120)
                lines.append(f"- {hit.path}:{hit.start_line}-{hit.end_line} — {snippet}")
        else:
            lines.append("No code references yet; try sharing the failing test file.")

        suggestions: list[str] = []
        if parsed.get("error_type") == "ModuleNotFoundError":
            suggestions.append("Check imports and ensure dependencies/modules are installed.")
        if parsed.get("error_type") in {"AssertionError", "TypeError"}:
            suggestions.append("Inspect the failing assertion and input types.")
        suggestions.append("Re-run the single failing test with: pytest -q -k <name> -vv")
        if lang_en:
            lines.append("Next steps:")
            lines.extend(f"- {s}" for s in suggestions[:3])
        else:
            lines.append("Næste skridt:")
            lines.extend(f"- {s}" for s in suggestions[:3])

        reply = "\n".join(lines)
        if reminders_due and should_attach_reminders and should_attach_reminders(prompt):
            reply = prepend_reminders(reply, reminders_due, user_id_int)  # type: ignore[arg-type]

        payload = {"tool": "pytest_triage", "queries": queries, "parsed": parsed}
        if session_id and state:
            state.set_last_tool(json.dumps(payload, ensure_ascii=False))
            state.add_message("assistant", reply)
        add_memory("assistant", reply, user_id=user_id)
        return {"text": reply, "meta": {"tool": "pytest_triage", "tool_used": True}}

    query = prompt
    short_answer = None

    path_intent = _file_explain_intent(prompt)
    func_intent = _function_intent(prompt)
    symbol_intent = _symbol_usage_intent(prompt)
    test_intent = _test_fail_intent(prompt)
    fix_intent = _fix_suggestion_intent(prompt)

    if path_intent:
        text, err = _safe_read_file(path_intent, repo_root=repo_root)
        if text:
            short_answer = _shorten(text, 240)
            query = f"{path_intent} {prompt}"
        else:
            if ui_lang and ui_lang.lower().startswith("en"):
                reply = f"I could not read {path_intent}: {err}"
            else:
                reply = f"Jeg kunne ikke læse {path_intent}: {err}"
            return {"text": reply, "meta": {"tool": "code_search", "tool_used": False}}
    elif func_intent:
        query = f"function {func_intent}"
    elif symbol_intent:
        query = f"usage of {symbol_intent}"
    elif test_intent:
        query = f"test {test_intent} failure"
    elif fix_intent:
        query = f"fix suggestion {fix_intent}"
    elif not _code_question_intent(prompt):
        return None

    # Try to get cached RAG results first (non-blocking, with short timeout) - only if enabled
    hits = []
    if rag_hash and os.getenv("JARVIS_ENABLE_RAG") == "1":
        from jarvis.agent_core.rag_async import get_code_rag_results
        hits = get_code_rag_results(rag_hash, max_wait=0.5, trace_id=trace_id)

    
    # If no cached results and RAG is enabled, do blocking search
    if not hits and os.getenv("JARVIS_ENABLE_RAG") == "1":
        try:
            hits = search_code(query, k=5, repo_root=repo_root, index_dir=index_dir, trace_id=trace_id)
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
    summary = []
    if short_answer:
        if ui_lang and ui_lang.lower().startswith("en"):
            summary.append(f"Short answer: {short_answer}")
        else:
            summary.append(f"Kort svar: {short_answer}")
    else:
        if ui_lang and ui_lang.lower().startswith("en"):
            summary.append("Short answer: Found relevant code.")
        else:
            summary.append("Kort svar: Fandt relevant kode.")

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
