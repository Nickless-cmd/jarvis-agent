"""
Session-scoped state management to eliminate state leaks across sessions.
"""

import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from threading import Lock

from jarvis.events import publish
from jarvis.agent_core.conversation_state import ConversationState


@dataclass
class SessionState:
    """Session-scoped state that should not leak between sessions."""

    # User profile data (computed once per session)
    profile: Optional[Dict[str, Any]] = None
    display_name: Optional[str] = None
    user_id_int: Optional[int] = None
    user_key: Optional[str] = None
    is_admin_user: bool = False

    # Pending states (transient, should be reset on session switch)
    pending_weather: Dict[str, Any] = field(default_factory=dict)
    pending_note: Dict[str, Any] = field(default_factory=dict)
    pending_reminder: Dict[str, Any] = field(default_factory=dict)
    pending_file: Dict[str, Any] = field(default_factory=dict)
    pending_image_preview: Dict[str, Any] = field(default_factory=dict)
    pending_city: Optional[str] = None
    pending_scope: Optional[str] = None
    pending_prompt: Optional[str] = None

    # Conversation and mode state
    conversation_state: ConversationState = field(default_factory=ConversationState)
    mode: str = "balanced"
    model_profile: str = "balanced"

    # Cached results (can persist but should be session-specific)
    last_city: Optional[str] = None
    last_news: Optional[Dict[str, Any]] = None
    last_search: Optional[Dict[str, Any]] = None
    last_tool: Optional[Dict[str, Any]] = None
    last_image_prompt: Optional[str] = None

    # Process state
    process_state: Dict[str, Any] = field(default_factory=dict)

    # CV and story states
    cv_state: Dict[str, Any] = field(default_factory=dict)
    story_state: Dict[str, Any] = field(default_factory=dict)

    # Ticket and reminder states
    ticket_state: Dict[str, Any] = field(default_factory=dict)
    reminder_state: Dict[str, Any] = field(default_factory=dict)

    # Creation and access tracking
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)

    def reset_transient_state(self, reason: str = "session_switch") -> None:
        """Reset transient state fields that should not persist across sessions."""
        # Reset pending states
        self.pending_weather = {}
        self.pending_note = {}
        self.pending_reminder = {}
        self.pending_file = {}
        self.pending_image_preview = {}
        self.pending_city = None
        self.pending_scope = None
        self.pending_prompt = None

        # Reset conversation state to defaults
        self.conversation_state = ConversationState()

        # Reset process state
        self.process_state = {}

        # Emit reset event
        try:
            publish("session.reset", {
                "session_id": getattr(self, '_session_id', None),
                "reason": reason,
                "reset_at": time.time()
            })
        except Exception:
            pass  # EventBus may not be available

    def update_access_time(self) -> None:
        """Update the last accessed timestamp."""
        self.last_accessed = time.time()

    def is_expired(self, max_age_seconds: int = 3600) -> bool:
        """Check if session state is expired."""
        return time.time() - self.last_accessed > max_age_seconds


class SessionStateManager:
    """Manages session-scoped state objects."""

    def __init__(self):
        self._states: Dict[str, SessionState] = {}
        self._lock = Lock()
        self._max_age_seconds = 3600  # 1 hour
        self._last_session_id: Optional[str] = None

    def get_or_create(self, session_id: str) -> SessionState:
        """Get existing session state or create new one."""
        if not session_id:
            # For non-session requests, return a temporary state
            return SessionState()

        with self._lock:
            # Clean up expired states periodically
            self._cleanup_expired()

            if session_id not in self._states:
                state = SessionState()
                state._session_id = session_id  # Store session_id for events
                self._states[session_id] = state

                try:
                    publish("session.created", {
                        "session_id": session_id,
                        "created_at": state.created_at
                    })
                except Exception:
                    pass

            state = self._states[session_id]
            state.update_access_time()
            return state

    def get_for_request(self, session_id: str) -> SessionState:
        """
        Convenience helper for per-request access that handles session switching.
        """
        state = self.switch_session(self._last_session_id, session_id)
        self._last_session_id = session_id
        return state

    def reset(self, session_id: str, reason: str = "manual_reset") -> None:
        """Reset transient state for a session."""
        if session_id in self._states:
            self._states[session_id].reset_transient_state(reason)

    def delete(self, session_id: str) -> None:
        """Delete session state."""
        with self._lock:
            if session_id in self._states:
                try:
                    publish("session.deleted", {
                        "session_id": session_id,
                        "deleted_at": time.time()
                    })
                except Exception:
                    pass
                del self._states[session_id]

    def switch_session(self, from_session: Optional[str], to_session: str) -> SessionState:
        """Handle session switching with proper cleanup."""
        # Reset transient state in the old session if it exists
        if from_session and from_session != to_session:
            self.reset(from_session, "session_switch")

            try:
                publish("session.switch", {
                    "from_session": from_session,
                    "to_session": to_session,
                    "switched_at": time.time()
                })
            except Exception:
                pass

        # Get or create the new session state
        self._last_session_id = to_session
        return self.get_or_create(to_session)

    def _cleanup_expired(self) -> None:
        """Clean up expired session states."""
        expired = [sid for sid, state in self._states.items() if state.is_expired(self._max_age_seconds)]
        for sid in expired:
            self.delete(sid)

    def _reset_for_tests(self) -> None:
        """Testing helper to clear all session state."""
        with self._lock:
            self._states.clear()
            self._last_session_id = None


# Global instance
_session_state_manager: Optional[SessionStateManager] = None


def get_session_state_manager() -> SessionStateManager:
    """Get the global session state manager instance."""
    global _session_state_manager
    if _session_state_manager is None:
        _session_state_manager = SessionStateManager()
    return _session_state_manager
