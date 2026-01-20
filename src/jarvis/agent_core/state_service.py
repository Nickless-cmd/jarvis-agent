"""Lightweight state wrapper around session_store.

Provides scoped helpers so skills can read/write session state without
importing session_store directly.
"""

from __future__ import annotations

from typing import List, Optional

from jarvis import session_store


class AgentStateService:
    """Scoped state helper for a single user/session."""

    def __init__(self, user_id: str, session_id: str):
        self.user_id = user_id
        self.session_id = session_id

    # Message helpers
    def add_message(self, role: str, content: str) -> None:
        """Persist a chat message for this session."""
        if self.session_id:
            session_store.add_message(self.session_id, role, content)

    def get_recent_messages(self, limit: int = 8) -> List[dict]:
        """Fetch recent messages for this session."""
        if not self.session_id:
            return []
        return session_store.get_recent_messages(self.session_id, limit=limit)

    def get_all_messages(self) -> List[dict]:
        """Fetch all messages for this session."""
        if not self.session_id:
            return []
        return session_store.get_all_messages(self.session_id)

    # Tool helpers
    def set_last_tool(self, payload: str) -> None:
        """Store last tool payload for this session."""
        if self.session_id:
            session_store.set_last_tool(self.session_id, payload)

    def get_last_tool(self) -> Optional[str]:
        """Return last tool payload for this session."""
        if not self.session_id:
            return None
        return session_store.get_last_tool(self.session_id)

    # Mode / prompt helpers
    def get_mode(self) -> str:
        if not self.session_id:
            return "balanced"
        return session_store.get_mode(self.session_id)

    def set_mode(self, mode: str) -> None:
        if self.session_id:
            session_store.set_mode(self.session_id, mode)

    def get_custom_prompt(self) -> Optional[str]:
        if not self.session_id:
            return None
        return session_store.get_custom_prompt(self.session_id)

    def set_custom_prompt(self, prompt: Optional[str]) -> None:
        if self.session_id:
            session_store.set_custom_prompt(self.session_id, prompt)
