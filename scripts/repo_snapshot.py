#!/usr/bin/env python3
"""
Repository snapshot and status report generator.
Outputs JSON report with git status, file stats, and module inventory.
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, Any, List


def run_git_command(args: List[str], cwd: str = None) -> str:
    """Run a git command safely and return output."""
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            return ""
    except (subprocess.TimeoutExpired, subprocess.SubprocessError, FileNotFoundError):
        return ""


def get_git_info() -> Dict[str, Any]:
    """Get git repository information."""
    # Current branch
    branch = run_git_command(["rev-parse", "--abbrev-ref", "HEAD"])
    if not branch:
        branch = "unknown"

    # HEAD commit
    head_commit = run_git_command(["rev-parse", "HEAD"])
    if not head_commit:
        head_commit = "unknown"

    # Status summary
    status_output = run_git_command(["status", "--porcelain"])
    status_lines = status_output.split('\n') if status_output else []
    changed_files = len([line for line in status_lines if line.strip()])
    is_clean = changed_files == 0

    # Recent commits (last 10)
    log_output = run_git_command([
        "log", "--oneline", "-10",
        "--pretty=format:%H %s"
    ])
    recent_commits = []
    if log_output:
        for line in log_output.split('\n'):
            if line.strip():
                parts = line.split(' ', 1)
                if len(parts) == 2:
                    recent_commits.append({
                        "hash": parts[0],
                        "subject": parts[1]
                    })

    return {
        "branch": branch,
        "head_commit": head_commit,
        "status": {
            "is_clean": is_clean,
            "changed_files_count": changed_files
        },
        "recent_commits": recent_commits
    }


def count_lines_in_file(filepath: Path) -> int:
    """Count lines in a file, excluding empty lines."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            return sum(1 for line in f if line.strip())
    except (OSError, UnicodeDecodeError):
        return 0


def get_file_stats() -> Dict[str, Any]:
    """Get key file statistics."""
    base_path = Path(__file__).parent.parent / "src" / "jarvis"

    # Line count for agent.py
    agent_py = base_path / "agent.py"
    agent_lines = count_lines_in_file(agent_py)

    # Total lines in src/jarvis
    total_lines = 0
    if base_path.exists():
        for py_file in base_path.rglob("*.py"):
            # Skip certain directories for safety
            if any(skip in str(py_file) for skip in ["__pycache__", ".git"]):
                continue
            total_lines += count_lines_in_file(py_file)

    return {
        "agent_py_lines": agent_lines,
        "total_src_jarvis_lines": total_lines
    }


def list_modules_in_directory(dir_path: Path) -> List[str]:
    """List Python modules in a directory."""
    modules = []
    if dir_path.exists() and dir_path.is_dir():
        for item in dir_path.iterdir():
            if item.is_file() and item.suffix == ".py" and not item.name.startswith("__"):
                modules.append(item.stem)
    return sorted(modules)


def get_module_inventory() -> Dict[str, Any]:
    """Get inventory of skills and core modules."""
    base_path = Path(__file__).parent.parent / "src" / "jarvis"

    skills_dir = base_path / "agent_skills"
    core_dir = base_path / "agent_core"

    return {
        "skills_modules": list_modules_in_directory(skills_dir),
        "core_modules": list_modules_in_directory(core_dir)
    }


def generate_snapshot() -> Dict[str, Any]:
    """Generate complete repository snapshot."""
    return {
        "git_info": get_git_info(),
        "file_stats": get_file_stats(),
        "module_inventory": get_module_inventory(),
        "timestamp": "2026-01-21T00:00:00Z"  # Will be set by calling code
    }


def main():
    """Main entry point for command line usage."""
    import datetime

    snapshot = generate_snapshot()
    snapshot["timestamp"] = datetime.datetime.now().isoformat() + "Z"

    print(json.dumps(snapshot, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()