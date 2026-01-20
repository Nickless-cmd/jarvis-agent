"""Conversation state helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import List

MAX_ITEMS = 10
MAX_SUMMARY = 1200


@dataclass
class ConversationState:
    current_goal: str = ""
    decisions: List[str] = field(default_factory=list)
    pending_questions: List[str] = field(default_factory=list)
    last_summary: str = ""
    response_mode: str = "normal"  # short | normal | deep

    def to_json(self) -> str:
        payload = {
            "current_goal": self.current_goal or "",
            "decisions": self.decisions[:MAX_ITEMS],
            "pending_questions": self.pending_questions[:MAX_ITEMS],
            "last_summary": (self.last_summary or "")[:MAX_SUMMARY],
            "response_mode": self.response_mode or "normal",
        }
        return json.dumps(payload, ensure_ascii=False)

    @classmethod
    def from_json(cls, value: str | None) -> "ConversationState":
        if not value:
            return cls()
        try:
            data = json.loads(value)
        except Exception:
            return cls()
        return cls(
            current_goal=data.get("current_goal", "") or "",
            decisions=list(data.get("decisions", []))[:MAX_ITEMS],
            pending_questions=list(data.get("pending_questions", []))[:MAX_ITEMS],
            last_summary=(data.get("last_summary", "") or "")[:MAX_SUMMARY],
            response_mode=data.get("response_mode", "normal") or "normal",
        )

    def set_goal(self, goal: str) -> None:
        self.current_goal = (goal or "")[:200]

    def add_decision(self, decision: str) -> None:
        decision = (decision or "").strip()
        if not decision:
            return
        self.decisions = (self.decisions + [decision])[-MAX_ITEMS:]

    def add_pending_question(self, question: str) -> None:
        question = (question or "").strip()
        if not question:
            return
        self.pending_questions = (self.pending_questions + [question])[-MAX_ITEMS:]

    def clear_pending_question(self, question: str) -> None:
        self.pending_questions = [q for q in self.pending_questions if q != question]

    def update_summary(self, new_text: str) -> None:
        """Conservatively update rolling summary without LLM."""
        new_text = (new_text or "").strip()
        if not new_text:
            return
        
        # Check if it looks like a decision or plan step
        text_lower = new_text.lower()
        decision_indicators = [
            "besluttede", "beslutter", "planlægger", "skal", "vil", "næste", "step", "trin",
            "mål", "opgave", "handling", "udføre", "implementere", "starte", "afslutte"
        ]
        is_key_info = any(indicator in text_lower for indicator in decision_indicators)
        
        if not is_key_info:
            return  # Do not append non-key info
        
        # Append to existing summary
        if self.last_summary:
            combined = self.last_summary + "\n" + new_text
        else:
            combined = new_text
        
        # Truncate to MAX_SUMMARY chars, preferring to keep recent info
        if len(combined) > MAX_SUMMARY:
            # Keep the last part that fits
            combined = combined[-(MAX_SUMMARY - 3):]  # -3 for "..."
            if not combined.startswith("\n"):
                combined = "..." + combined
        
        self.last_summary = combined

    def set_response_mode(self, mode: str) -> None:
        mode = (mode or "").lower()
        if mode in {"short", "normal", "deep"}:
            self.response_mode = mode

