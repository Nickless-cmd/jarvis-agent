"""
Prompt manager for loading system/admin prompts with caching and optional reload.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from jarvis.prompts import system_prompts

DEFAULT_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
ENV_RELOAD = os.getenv("JARVIS_PROMPTS_RELOAD", "0") == "1"


@dataclass
class PromptBundle:
    """Represents a prompt bundle and derived metadata."""

    name: str
    text: str

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()

    def preview(self, length: int = 200) -> str:
        if len(self.text) <= length:
            return self.text
        return self.text[:length] + "…"


class PromptManager:
    """Load and cache system prompts."""

    def __init__(self, prompts_dir: Path | None = None) -> None:
        self.prompts_dir = prompts_dir or DEFAULT_PROMPTS_DIR
        self._cache: dict[str, PromptBundle] = {}

    def _load_file(self, filename: str, fallback: str) -> str:
        path = self.prompts_dir / filename
        try:
            return path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return fallback

    def _load_prompts(self) -> None:
        if self._cache and not ENV_RELOAD:
            return
        user_prompt = self._load_file("system_user.txt", system_prompts.SYSTEM_PROMPT_USER)
        admin_prompt = self._load_file("system_admin.txt", system_prompts.SYSTEM_PROMPT_ADMIN)
        self._cache = {
            "system": PromptBundle("system", user_prompt),
            "admin_system": PromptBundle("admin_system", admin_prompt),
        }

    def get_prompt(self, name: str) -> PromptBundle:
        self._load_prompts()
        bundle = self._cache.get(name)
        if not bundle:
            raise ValueError(f"Prompt '{name}' not found")
        return bundle

    def effective_prompt(self, is_admin: bool = False) -> PromptBundle:
        """Return the effective system prompt for the user role."""
        return self.get_prompt("admin_system" if is_admin else "system")


# Singleton for convenience
_manager = PromptManager()


def get_prompt_manager() -> PromptManager:
    return _manager
