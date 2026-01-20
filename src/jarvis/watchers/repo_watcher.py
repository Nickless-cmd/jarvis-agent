"""Polling repository watcher that emits notification events on changes."""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from typing import Dict, Iterable, Set

from jarvis.notifications.store import add_event
from jarvis.code_rag.index import build_index, DEFAULT_INDEX_DIR, DEFAULT_REPO_ROOT

RELEVANT_EXT = {".py", ".md", ".txt", ".sh", ".toml", ".yml", ".yaml", ".ini"}
EXCLUDE_DIRS = {".venv", "__pycache__", ".pytest_cache", "src/data", "data", "tts_cache", "ui/static"}
EXCLUDE_EXT = {".pyc"}
MAX_SIZE_BYTES = 2 * 1024 * 1024


class PollingRepoWatcher:
    """Simple mtime-based polling watcher."""

    def __init__(self, repo_root: Path, user_id: int, interval_sec: int = 5, auto_reindex: bool = False):
        self.repo_root = repo_root
        self.interval_sec = max(1, interval_sec)
        self.user_id = user_id
        self.auto_reindex = auto_reindex
        self._mtimes: Dict[Path, float] = {}
        self._stop = threading.Event()
        self._reindex_lock = threading.Lock()

    def _iter_files(self) -> Iterable[Path]:
        exclude_set = set(EXCLUDE_DIRS)
        for root, dirs, files in os.walk(self.repo_root):
            root_path = Path(root)
            rel_root = root_path.relative_to(self.repo_root)
            # Exclude dirs if their relative path is in exclude
            dirs[:] = [d for d in dirs if str(rel_root / d) not in exclude_set]
            for name in files:
                p = root_path / name
                rel_p = p.relative_to(self.repo_root)
                if str(rel_p.parent) in exclude_set:
                    continue
                if p.suffix.lower() not in RELEVANT_EXT:
                    continue
                if p.suffix.lower() in EXCLUDE_EXT:
                    continue
                try:
                    if p.stat().st_size > MAX_SIZE_BYTES:
                        continue
                except OSError:
                    continue
                yield p

    def _detect_changes(self) -> Set[Path]:
        changed: Set[Path] = set()
        current: Dict[Path, float] = {}
        for path in self._iter_files():
            try:
                mtime = path.stat().st_mtime
            except OSError:
                continue
            current[path] = mtime
            old = self._mtimes.get(path)
            if old is None or mtime > old:
                changed.add(path)
        # Detect deletions
        for old_path in set(self._mtimes.keys()) - set(current.keys()):
            changed.add(old_path)
        self._mtimes = current
        return changed

    def _emit_change_events(self, changed: Set[Path]) -> None:
        if not changed:
            return
        paths_preview = ", ".join(sorted(p.as_posix() for p in list(changed)[:3]))
        count = len(changed)
        add_event(
            self.user_id,
            type="code_changed",
            severity="info",
            title="Code changed",
            body=f"{count} file(s) changed: {paths_preview}",
        )
        add_event(
            self.user_id,
            type="code_index_stale",
            severity="warning",
            title="Code index needs rebuild",
            body="Repository changes detected. Rebuild index when convenient.",
        )
        if self.auto_reindex:
            self._trigger_reindex()

    def _trigger_reindex(self) -> None:
        if not self._reindex_lock.acquire(blocking=False):
            return

        def _worker():
            try:
                build_index(repo_root=self.repo_root, index_dir=DEFAULT_INDEX_DIR)
                add_event(
                    self.user_id,
                    type="code_index_rebuilt",
                    severity="info",
                    title="Code index rebuilt",
                    body="Rebuild completed successfully.",
                )
            except Exception as exc:  # pragma: no cover - defensive
                add_event(
                    self.user_id,
                    type="code_index_rebuild_failed",
                    severity="error",
                    title="Code index rebuild failed",
                    body=str(exc)[:8000],
                )
            finally:
                self._reindex_lock.release()

        threading.Thread(target=_worker, daemon=True).start()

    def scan_once(self) -> Set[Path]:
        """Run a single scan and emit events if changes detected."""
        changed = self._detect_changes()
        self._emit_change_events(changed)
        return changed

    def start(self) -> None:
        """Start background polling."""

        def _loop():
            while not self._stop.is_set():
                self.scan_once()
                self._stop.wait(self.interval_sec)

        threading.Thread(target=_loop, daemon=True).start()

    def stop(self) -> None:
        self._stop.set()


def start_repo_watcher_if_enabled() -> None:
    """Start watcher if env flag is enabled."""
    if os.getenv("JARVIS_ENABLE_WATCHERS") != "1":
        return
    repo_root = Path(os.getenv("JARVIS_REPO_ROOT") or DEFAULT_REPO_ROOT)
    interval = int(os.getenv("JARVIS_WATCHER_INTERVAL_SEC", "5") or 5)
    auto_reindex = os.getenv("JARVIS_AUTO_REINDEX") == "1"
    user_id = int(os.getenv("JARVIS_WATCHER_USER_ID", "1"))
    watcher = PollingRepoWatcher(repo_root=repo_root, user_id=user_id, interval_sec=interval, auto_reindex=auto_reindex)
    watcher.start()

