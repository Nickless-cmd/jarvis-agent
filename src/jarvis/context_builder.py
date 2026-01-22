"""
Deterministic conversation context builder for the agent.

Centralizes context construction, history trimming, and summarization hooks.
"""

import time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass

from jarvis.events import publish
from jarvis.memory import search_memory
from jarvis.session_store import get_recent_messages, get_custom_prompt
from jarvis.performance_metrics import ContextBudget, get_budget
from jarvis.personality import SYSTEM_PROMPT
from jarvis.user_preferences import get_user_preferences, build_persona_directive
from jarvis.context_utils import (
    get_system_prompt,
    first_name,
    get_project_context_block,
    get_user_profile,
    inject_time_context,
)


@dataclass
class ContextResult:
    """Result of context building."""
    messages: List[Dict[str, str]]
    context_counts: Dict[str, int]
    budget_exceeded: bool
    items_trimmed: int
    summary_created: bool


class ConversationContextBuilder:
    """Centralized builder for conversation context with deterministic trimming."""

    def __init__(self):
        self.budget = get_budget()

    def build_context(
        self,
        user_id: str,
        prompt: str,
        session_id: Optional[str] = None,
        ui_lang: Optional[str] = None,
        allowed_tools: Optional[List[str]] = None,
        tool_result: Optional[Any] = None,
        is_admin: bool = False,
    ) -> ContextResult:
        """
        Build conversation context deterministically.

        Args:
            user_id: User identifier
            prompt: Current user prompt
            session_id: Session identifier (optional)
            ui_lang: UI language preference
            allowed_tools: List of allowed tools
            tool_result: Result from tool execution (optional)
            is_admin: Whether user is admin

        Returns:
            ContextResult with messages and metadata
        """
        # Get base components
        profile = get_user_profile(user_id)
        display_name = first_name(profile, user_id)
        user_prefs = get_user_preferences(user_id)
        effective_name = user_prefs.get("preferred_name") or display_name

        # Get conversation history
        session_hist = get_recent_messages(session_id, limit=self.budget.max_history_messages * 2) if session_id else []

        # Get memory
        mem = search_memory(prompt, user_id=user_id)

        # Apply budget trimming
        trimmed_hist, trimmed_mem, context_counts, budget_exceeded, items_trimmed = self.budget.enforce_budget(session_hist, mem)

        # Emit trimming event if needed
        summary_created = False
        if items_trimmed > 0:
            try:
                publish("memory.trim", {
                    "session_id": session_id,
                    "before_count": len(session_hist) + len(mem),
                    "after_count": len(trimmed_hist) + len(trimmed_mem),
                    "items_trimmed": items_trimmed,
                })
            except Exception:
                pass  # EventBus unavailable

            # Create summary placeholder (don't call LLM)
            if len(trimmed_hist) < len(session_hist):
                summary_text = f"[Conversation trimmed: {items_trimmed} messages removed for context budget]"
                # Prepend summary to history
                trimmed_hist.insert(0, {"role": "system", "content": summary_text})
                summary_created = True

                try:
                    publish("memory.summary", {
                        "session_id": session_id,
                        "summary_len": len(summary_text),
                    })
                except Exception:
                    pass

        # Build system prompt
        sys_prompt = get_system_prompt(is_admin=is_admin)
        if session_id:
            override = get_custom_prompt(session_id)
            if override:
                sys_prompt = override

        # Add persona directive
        persona_directive = build_persona_directive(user_prefs, ui_lang or "da")
        if persona_directive:
            sys_prompt = f"{sys_prompt}\n{persona_directive}"

        # Build system content parts
        name_hint = f"Brugerens navn er {effective_name}."
        time_context = inject_time_context(ui_lang)
        project_context = get_project_context_block(prompt, ui_lang)

        # Determine mode hint (simplified - could be passed in)
        mode_hint = "Mode normal: balanceret længde og dybde."

        sys_content_parts = [sys_prompt, name_hint, mode_hint, time_context]
        if project_context:
            sys_content_parts.append(project_context)

        # Construct messages
        messages = [{"role": "system", "content": "\n".join(sys_content_parts)}]

        # Add memory
        if trimmed_mem:
            messages.append({"role": "assistant", "content": "\n".join(trimmed_mem)})

        # Add history
        messages.extend(self._format_history(trimmed_hist))

        # Add current user message
        messages.append({"role": "user", "content": prompt})

        # Add tool result if present
        if tool_result is not None:
            tool_summary = self._summarize_tool_result(tool_result)
            messages.append({"role": "assistant", "content": f"Tool result: {tool_summary}"})

        return ContextResult(
            messages=messages,
            context_counts=context_counts,
            budget_exceeded=budget_exceeded,
            items_trimmed=items_trimmed,
            summary_created=summary_created,
        )

    def _format_history(self, history: List[Dict]) -> List[Dict[str, str]]:
        """Format conversation history for context."""
        formatted = []
        for msg in history:
            if isinstance(msg, dict) and "role" in msg and "content" in msg:
                formatted.append({"role": msg["role"], "content": msg["content"]})
        return formatted

    def _summarize_tool_result(self, tool_result: Any) -> str:
        """Create a summary of tool result for context."""
        if isinstance(tool_result, dict):
            if "text" in tool_result:
                return tool_result["text"][:200] + "..." if len(tool_result["text"]) > 200 else tool_result["text"]
            return str(tool_result)[:200] + "..." if len(str(tool_result)) > 200 else str(tool_result)
        return str(tool_result)[:200] + "..." if len(str(tool_result)) > 200 else str(tool_result)


# Global instance
_context_builder: Optional[ConversationContextBuilder] = None


def get_context_builder() -> ConversationContextBuilder:
    """Get the global context builder instance."""
    global _context_builder
    if _context_builder is None:
        _context_builder = ConversationContextBuilder()
    return _context_builder
