"""
User preferences and persona management.
"""

import json
import os
from typing import Dict, Any, Optional
from pathlib import Path

from jarvis.db import DATA_DIR


def _get_user_prefs_path(user_id: str) -> Path:
    """Get the path to user's preferences file."""
    prefs_dir = Path(DATA_DIR) / "user_profiles"
    prefs_dir.mkdir(exist_ok=True)
    return prefs_dir / f"{user_id}.json"


def get_user_preferences(user_id: str) -> Dict[str, Any]:
    """
    Get user preferences.
    
    Returns dict with:
    - preferred_name: str or None
    - preferred_language: "da" | "en" | None
    - tone: "neutral" | "friendly" | "technical"
    - verbosity: "short" | "normal" | "detailed"
    """
    prefs_file = _get_user_prefs_path(user_id)
    if not prefs_file.exists():
        return {
            "preferred_name": None,
            "preferred_language": None,
            "tone": "neutral",
            "verbosity": "normal"
        }
    
    try:
        with open(prefs_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Validate and provide defaults
            return {
                "preferred_name": data.get("preferred_name"),
                "preferred_language": data.get("preferred_language"),
                "tone": data.get("tone", "neutral"),
                "verbosity": data.get("verbosity", "normal")
            }
    except Exception:
        return {
            "preferred_name": None,
            "preferred_language": None,
            "tone": "neutral",
            "verbosity": "normal"
        }


def set_user_preferences(user_id: str, prefs: Dict[str, Any]) -> None:
    """Set user preferences."""
    current = get_user_preferences(user_id)
    # Merge with current
    updated = {**current, **prefs}
    # Validate
    if updated.get("tone") not in ["neutral", "friendly", "technical"]:
        updated["tone"] = "neutral"
    if updated.get("verbosity") not in ["short", "normal", "detailed"]:
        updated["verbosity"] = "normal"
    if updated.get("preferred_language") not in [None, "da", "en"]:
        updated["preferred_language"] = None
    
    prefs_file = _get_user_prefs_path(user_id)
    with open(prefs_file, 'w', encoding='utf-8') as f:
        json.dump(updated, f, ensure_ascii=False, indent=2)


def build_persona_directive(prefs: Dict[str, Any], ui_lang: str = "da") -> str:
    """
    Build a short persona directive from user preferences.
    
    Args:
        prefs: User preferences dict
        ui_lang: UI language ("da" | "en")
    
    Returns:
        Short directive string to inject before LLM call
    """
    parts = []
    
    # Language override
    lang = prefs.get("preferred_language") or ui_lang
    if lang == "da":
        parts.append("Svar på dansk.")
    else:
        parts.append("Answer in English.")
    
    # Verbosity
    verbosity = prefs.get("verbosity", "normal")
    if verbosity == "short":
        if lang == "da":
            parts.append("Hold det kort.")
        else:
            parts.append("Keep it short.")
    elif verbosity == "detailed":
        if lang == "da":
            parts.append("Vær detaljeret.")
        else:
            parts.append("Be detailed.")
    
    # Tone
    tone = prefs.get("tone", "neutral")
    if tone == "friendly":
        if lang == "da":
            parts.append("Vær venlig og imødekommende.")
        else:
            parts.append("Be friendly and helpful.")
    elif tone == "technical":
        if lang == "da":
            parts.append("Vær teknisk og præcis.")
        else:
            parts.append("Be technical and precise.")
    
    # Always include concrete instruction
    if lang == "da":
        parts.append("Vær konkret.")
    else:
        parts.append("Be concrete.")
    
    return " ".join(parts)


def parse_preference_command(prompt: str, ui_lang: str = "da") -> Optional[Dict[str, Any]]:
    """
    Parse user commands for setting preferences.
    
    Returns dict of preferences to update, or None if no command found.
    """
    p = prompt.lower().strip()
    
    updates = {}
    
    # Name setting
    if ui_lang == "da":
        if p.startswith("kald mig "):
            name = prompt[9:].strip()
            if name:
                updates["preferred_name"] = name
        elif "skift sprog til dansk" in p:
            updates["preferred_language"] = "da"
        elif "skift sprog til engelsk" in p:
            updates["preferred_language"] = "en"
        elif "svar kort" in p or "vær kort" in p:
            updates["verbosity"] = "short"
        elif "svar længere" in p or "vær detaljeret" in p:
            updates["verbosity"] = "detailed"
        elif "vær mere teknisk" in p:
            updates["tone"] = "technical"
        elif "vær mere venlig" in p:
            updates["tone"] = "friendly"
    else:  # English
        if p.startswith("call me "):
            name = prompt[8:].strip()
            if name:
                updates["preferred_name"] = name
        elif "switch language to danish" in p or "speak danish" in p:
            updates["preferred_language"] = "da"
        elif "switch language to english" in p or "speak english" in p:
            updates["preferred_language"] = "en"
        elif "answer short" in p or "be short" in p:
            updates["verbosity"] = "short"
        elif "answer longer" in p or "be detailed" in p:
            updates["verbosity"] = "detailed"
        elif "be more technical" in p:
            updates["tone"] = "technical"
        elif "be more friendly" in p:
            updates["tone"] = "friendly"
    
    return updates if updates else None