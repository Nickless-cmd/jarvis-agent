"""
Lightweight project memory store for Jarvis development context.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List

DEFAULT_PATH = os.getenv(
    "JARVIS_PROJECT_MEMORY_PATH",
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "project_memory.json"),
)

REDACT_MARKERS = ["key", "token", "password", "secret"]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_dir(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)


def _load(path: str = DEFAULT_PATH) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {"decisions": [], "conventions": [], "roadmap": [], "milestones": []}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {"decisions": [], "conventions": [], "roadmap": [], "milestones": []}
        for key in ["decisions", "conventions", "roadmap", "milestones"]:
            if key not in data or not isinstance(data[key], list):
                data[key] = []
        return data
    except Exception:
        return {"decisions": [], "conventions": [], "roadmap": [], "milestones": []}


def _save(data: Dict[str, Any], path: str = DEFAULT_PATH) -> None:
    _ensure_dir(path)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _redact(text: str) -> str | None:
    low = (text or "").lower()
    if any(marker in low for marker in REDACT_MARKERS):
        return None
    return text.strip()


def add_decision(title: str, details: str = "", path: str = DEFAULT_PATH) -> bool:
    cleaned_title = _redact(title)
    cleaned_details = _redact(details)
    if cleaned_title is None or cleaned_details is None:
        return False
    data = _load(path)
    data["decisions"].append(
        {
            "ts": _now_iso(),
            "title": cleaned_title,
            "details": cleaned_details,
        }
    )
    _save(data, path)
    return True


def add_milestone(text: str, path: str = DEFAULT_PATH) -> bool:
    cleaned = _redact(text)
    if cleaned is None:
        return False
    data = _load(path)
    data["milestones"].append({"ts": _now_iso(), "text": cleaned})
    _save(data, path)
    return True


def add_convention(text: str, path: str = DEFAULT_PATH) -> bool:
    cleaned = _redact(text)
    if cleaned is None:
        return False
    data = _load(path)
    data["conventions"].append({"ts": _now_iso(), "text": cleaned})
    _save(data, path)
    return True


def add_roadmap_item(text: str, path: str = DEFAULT_PATH) -> bool:
    cleaned = _redact(text)
    if cleaned is None:
        return False
    data = _load(path)
    data["roadmap"].append({"ts": _now_iso(), "text": cleaned})
    _save(data, path)
    return True


def list_roadmap(path: str = DEFAULT_PATH) -> List[Dict[str, Any]]:
    data = _load(path)
    return list(data.get("roadmap", []))


def summarize_project_state(max_bullets: int = 6, path: str = DEFAULT_PATH) -> List[str]:
    data = _load(path)
    bullets: List[str] = []
    for item in data.get("decisions", [])[-2:]:
        bullets.append(f"Decision: {item.get('title')}")
    for item in data.get("conventions", [])[-2:]:
        bullets.append(f"Convention: {item.get('text')}")
    for item in data.get("roadmap", [])[:2]:
        bullets.append(f"Upcoming: {item.get('text')}")
    for item in data.get("milestones", [])[-2:]:
        bullets.append(f"Done: {item.get('text')}")
    return bullets[:max_bullets]
