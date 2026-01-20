"""Run pytest on demand and emit notification events."""

from __future__ import annotations

import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Optional

from jarvis.code_rag import search_code
from jarvis.notifications.store import add_event
from jarvis.triage.pytest_triage import triage_pytest_output
from jarvis.code_rag.index import DEFAULT_REPO_ROOT


def _truncate(text: str, limit: int = 8000) -> str:
    return (text or "")[:limit]


def _format_body(stdout: str, stderr: str) -> str:
    parts = []
    if stdout:
        parts.append(stdout.strip())
    if stderr:
        parts.append(stderr.strip())
    body = "\n".join(parts).strip()
    return _truncate(body, 8000)


_recent_events: dict[str, float] = {}
RATE_WINDOW_SEC = 300  # 5 minutes


def _fingerprint_from_triage(triage: dict) -> str:
    parsed = triage.get("parsed") or {}
    etype = parsed.get("error_type") or "unknown"
    first_test = (parsed.get("failing_tests") or ["none"])[0]
    first_file = (parsed.get("file_paths") or ["none"])[0]
    return f"{etype}:{first_test}:{first_file}"


def _should_emit(fingerprint: str, now_ts: float | None = None, window: int = RATE_WINDOW_SEC) -> bool:
    ts_provider = time.time if hasattr(time, "time") else time
    ts = now_ts if now_ts is not None else ts_provider()
    last = _recent_events.get(fingerprint)
    if last is not None and ts - last < window:
        return False
    _recent_events[fingerprint] = ts
    return True


def run_pytest_and_notify(user_id: int, ui_lang: Optional[str] = None) -> int:
    """
    Run pytest -q and emit notification events.
    Returns the pytest exit code.
    """
    ui_lang = (ui_lang or "da").lower()
    title_ok = "Tests passed" if ui_lang.startswith("en") else "Tests bestået"
    title_fail = "Tests failed" if ui_lang.startswith("en") else "Tests fejlede"
    cmd = ["pytest", "-q"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except Exception as exc:  # pragma: no cover - defensive
        add_event(
            user_id,
            type="tests_failed",
            severity="error",
            title=title_fail,
            body=_truncate(str(exc), 8000),
        )
        return 1

    body = _format_body(result.stdout or "", result.stderr or "")
    if result.returncode == 0:
        add_event(
            user_id,
            type="tests_passed",
            severity="info",
            title=title_ok,
            body="All tests passed",
        )
    else:
        triage = triage_pytest_output(body, ui_lang)
        fingerprint = _fingerprint_from_triage(triage)
        if not _should_emit(fingerprint):
            return result.returncode
        # Get code refs for query terms
        refs = []
        if triage["query_terms"]:
            try:
                # Check if code index exists by attempting search
                query = " ".join(triage["query_terms"])
                results = search_code(query, limit=6)
                refs = results[:6]  # Up to 6 refs
            except Exception:
                pass
        top_refs = refs[:3]  # Top 3 for body
        suggestions = ["Review the failing test code for logic errors.", "Check if dependencies or fixtures are missing.", "Run the test with --tb=short for more details."]
        body_parts = [triage["body"]]
        if suggestions:
            body_parts.append("Suggestions:\n" + "\n".join(f"- {s}" for s in suggestions[:3]))
        if top_refs:
            body_parts.append("Refs:\n" + "\n".join(f"- {r['path']}:{r['start_line']}-{r['end_line']}" for r in top_refs))
        final_body = "\n\n".join(body_parts)
        add_event(
            user_id,
            type="tests_failed",
            severity="error",
            title=triage["title"],
            body=_truncate(final_body, 8000),
            meta={"refs": refs, "fingerprint": fingerprint, "parsed": triage.get("parsed")},
        )
    return result.returncode


class PollingTestWatcher:
    """Simple polling test runner."""

    def __init__(self, repo_root: Path, user_id: int, interval_sec: int = 60):
        self.repo_root = repo_root
        self.interval_sec = max(10, interval_sec)  # Min 10 sec
        self.user_id = user_id
        self._stop = threading.Event()

    def _run_tests(self) -> tuple[int, str]:
        """Run pytest -q and return (returncode, output)."""
        try:
            result = subprocess.run(
                ["python", "-m", "pytest", "-q"],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=300,  # 5 min timeout
            )
            output = result.stdout + result.stderr
            return result.returncode, output
        except subprocess.TimeoutExpired:
            return -1, "Test run timed out after 5 minutes"
        except Exception as exc:
            return -1, f"Failed to run tests: {exc}"

    def _extract_summary(self, returncode: int, output: str) -> str:
        """Extract short summary from output."""
        if returncode == 0:
            return "All tests passed"
        triage = triage_pytest_output(output)
        return triage["summary"]

    def scan_once(self) -> None:
        """Run tests once and emit event."""
        returncode, output = self._run_tests()
        triage = triage_pytest_output(output, "da")  # Assume da for watcher
        fingerprint = _fingerprint_from_triage(triage)
        if returncode == 0:
            add_event(
                self.user_id,
                type="test_run_success",
                severity="info",
                title="Tests passed",
                body=triage["body"],
            )
        else:
            # Rate limit identical failures
            if not _should_emit(fingerprint):
                return
            # Get code refs for query terms
            refs = []
            if triage["query_terms"]:
                try:
                    # Check if code index exists by attempting search
                    query = " ".join(triage["query_terms"])
                    results = search_code(query, limit=6)
                    refs = results[:6]  # Up to 6 refs
                except Exception:
                    pass
            top_refs = refs[:3]  # Top 3 for body
            suggestions = ["Review the failing test code for logic errors.", "Check if dependencies or fixtures are missing.", "Run the test with --tb=short for more details."]
            body = f"{triage['body']}\n\nSuggestions:\n" + "\n".join(f"- {s}" for s in suggestions[:3])
            if top_refs:
                body += "\n\nRefs:\n" + "\n".join(f"- {r['path']}:{r['start_line']}-{r['end_line']}" for r in top_refs)
            meta = {"refs": refs, "fingerprint": fingerprint}  # Full refs in meta
            add_event(
                self.user_id,
                type="test_run_failed",
                severity="error",
                title=triage["title"],
                body=body,
                meta=meta,
            )

    def start(self) -> None:
        """Start background polling."""

        def _loop():
            while not self._stop.is_set():
                self.scan_once()
                self._stop.wait(self.interval_sec)

        threading.Thread(target=_loop, daemon=True).start()

    def stop(self) -> None:
        self._stop.set()


def start_test_watcher_if_enabled() -> None:
    """Start test watcher if env flag is enabled."""
    if os.getenv("JARVIS_ENABLE_TEST_WATCHER") != "1":
        return
    repo_root = Path(os.getenv("JARVIS_REPO_ROOT") or DEFAULT_REPO_ROOT)
    interval = int(os.getenv("JARVIS_TEST_WATCHER_INTERVAL_SEC", "60") or 60)
    user_id = int(os.getenv("JARVIS_WATCHER_USER_ID", "1"))
    watcher = PollingTestWatcher(repo_root=repo_root, user_id=user_id, interval_sec=interval)
    watcher.start()
