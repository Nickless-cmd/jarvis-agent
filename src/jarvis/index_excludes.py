"""
Repo scanning exclude list for code indexing.
Configurable patterns to exclude directories/files from indexing.
"""

import os
from pathlib import Path

# Configurable exclude patterns (glob-style)
EXCLUDE_PATTERNS = [
    ".venv",
    "__pycache__",
    ".pytest_cache",
    "src/data",
    "tts_cache",
    "ui/static",
    "*.bin",  # large binaries
    "*.exe",
    "*.dll",
    "*.so",
    "*.dylib",
    "*.zip",
    "*.tar.gz",
    "*.tar.bz2",
    "*.tar.xz",
    "*.rar",
    "*.7z",
    "*.iso",
    "*.img",
    "*.dmg",
    "*.deb",
    "*.rpm",
    "*.apk",
    "*.jar",
    "*.war",
    "*.ear",
    "*.class",
    "*.pyc",
    "*.pyo",
    "*.pyd",
    "*.whl",
    "*.egg",
    "*.egg-info",
    "dist",
    "build",
    "*.log",
    "*.tmp",
    "*.swp",
    "*.bak",
    "*.old",
    ".git",
    ".svn",
    ".hg",
    ".DS_Store",
    "Thumbs.db",
]

def should_exclude(path: str) -> bool:
    """
    Check if a path should be excluded from indexing.
    path: relative path from repo root.
    """
    path_obj = Path(path)
    for pattern in EXCLUDE_PATTERNS:
        if path_obj.match(pattern):
            return True
        for part in path_obj.parts:
            if Path(part).match(pattern):
                return True
    return False
