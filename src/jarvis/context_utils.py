"""
Shared utilities for context building and agent functionality.
"""

from jarvis.session_store import get_custom_prompt
from jarvis.user_preferences import get_user_preferences, build_persona_directive
from jarvis.personality import SYSTEM_PROMPT
from jarvis.agent_policy.freshness import inject_time_context
from jarvis.agent_core.project_memory import summarize_project_state as pm_summarize
from jarvis.auth import get_user_profile


from jarvis.prompt_manager import get_prompt_manager
from jarvis.db import get_conn


def get_system_prompt(is_admin: bool = False) -> str:
    """Get the system prompt for the agent."""
    pm = get_prompt_manager()
    try:
        return pm.effective_prompt(is_admin=is_admin).text
    except Exception:
        with get_conn() as conn:
            row = conn.execute("SELECT value FROM settings WHERE key = ?", ("system_prompt",)).fetchone()
        if row and row["value"]:
            return row["value"]
        return pm.effective_prompt(is_admin=is_admin).text


def first_name(profile, user_id: str) -> str:
    """Get the first name from profile or user_id."""
    if profile and profile.get("name"):
        return profile["name"].split()[0]
    return user_id.split("@")[0] if "@" in user_id else user_id


from jarvis.agent_core.project_memory import summarize_project_state as pm_summarize


def get_project_context_block(prompt: str, ui_lang: str = None) -> str | None:
    """Return a short project context block when prompt is repo/dev related."""
    p = prompt.lower()
    dev_markers = [
        "kode", "repo", "pull request", "commit", "test", "pytest", "fejl", "bug",
        "jarvis", "orchestrator", "skill", "module", "modul", "refactor", "build", "pipeline",
        "ci", "cd", "log", "stacktrace", "traceback",
    ]
    if not any(m in p for m in dev_markers):
        return None
    bullets = pm_summarize()
    if not bullets:
        return None
    header = "Project context" if (ui_lang or "").lower().startswith("en") else "Projektkontekst"
    return header + ":\n" + "\n".join(f"- {b}" for b in bullets)