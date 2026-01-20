import os
from pathlib import Path

import pytest

from jarvis.triage.pytest_triage import triage_pytest_output
from jarvis.watchers import repo_watcher
from jarvis.watchers import test_watcher


def test_repo_watcher_ignores_excluded_dirs(tmp_path, monkeypatch):
    events = []

    def fake_add_event(user_id, type, title, body, severity="info", meta=None):
        events.append((type, title, body))

    monkeypatch.setattr(repo_watcher, "add_event", fake_add_event)
    repo = tmp_path / "repo"
    (repo / ".venv").mkdir(parents=True)
    excluded_file = repo / ".venv" / "skip.py"
    excluded_file.write_text("print('skip')", encoding="utf-8")
    watcher = repo_watcher.PollingRepoWatcher(repo_root=repo, user_id=1, interval_sec=1, auto_reindex=False)
    changed = watcher.scan_once()
    assert not changed
    assert not events


def test_repo_watcher_detects_change(tmp_path, monkeypatch):
    events = []

    def fake_add_event(user_id, type, title, body, severity="info", meta=None):
        events.append((type, title, body))

    monkeypatch.setattr(repo_watcher, "add_event", fake_add_event)
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    file_path = repo / "main.py"
    file_path.write_text("print('hello')\n", encoding="utf-8")
    watcher = repo_watcher.PollingRepoWatcher(repo_root=repo, user_id=1, interval_sec=1, auto_reindex=False)
    changed = watcher.scan_once()
    assert file_path in changed
    # Should emit two events: code_changed and code_index_stale
    assert len(events) == 2
    kinds = {e[0] for e in events}
    assert "code_changed" in kinds
    assert "code_index_stale" in kinds


def test_repo_watcher_detects_modified_file(tmp_path, monkeypatch):
    events = []

    def fake_add_event(user_id, type, title, body, severity="info", meta=None):
        events.append((type, title, body))

    monkeypatch.setattr(repo_watcher, "add_event", fake_add_event)
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    file_path = repo / "main.py"
    file_path.write_text("print('hello')\n", encoding="utf-8")
    watcher = repo_watcher.PollingRepoWatcher(repo_root=repo, user_id=1, interval_sec=1, auto_reindex=False)
    # First scan to establish baseline
    changed = watcher.scan_once()
    assert file_path in changed
    assert len(events) == 2
    events.clear()
    # Modify the file
    file_path.write_text("print('hello world')\n", encoding="utf-8")
    # Second scan
    changed = watcher.scan_once()
    assert file_path in changed
    assert len(events) == 2
    kinds = {e[0] for e in events}
    assert "code_changed" in kinds
    assert "code_index_stale" in kinds


def test_repo_watcher_ignores_multiple_excluded_dirs(tmp_path, monkeypatch):
    events = []

    def fake_add_event(user_id, type, title, body, severity="info", meta=None):
        events.append((type, title, body))

    monkeypatch.setattr(repo_watcher, "add_event", fake_add_event)
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    # Create excluded dirs with files
    excluded_dirs = [".venv", "__pycache__", "src/data", "tts_cache", "ui/static"]
    for d in excluded_dirs:
        (repo / d).mkdir(parents=True)
        (repo / d / "file.py").write_text("print('excluded')", encoding="utf-8")
    # Create a valid file
    valid_file = repo / "valid.py"
    valid_file.write_text("print('valid')", encoding="utf-8")
    watcher = repo_watcher.PollingRepoWatcher(repo_root=repo, user_id=1, interval_sec=1, auto_reindex=False)
    changed = watcher.scan_once()
    assert valid_file in changed
    assert len(changed) == 1  # Only the valid file
    assert len(events) == 2


def test_repo_watcher_rate_limit(monkeypatch, tmp_path):
    events = []
    now = [1000.0]

    def fake_add_event(user_id, type, title, body, severity="info", meta=None):
        events.append(type)

    def fake_time():
        return now[0]

    monkeypatch.setattr(repo_watcher, "add_event", fake_add_event)
    monkeypatch.setattr(repo_watcher, "time", fake_time)

    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    file_path = repo / "main.py"
    file_path.write_text("print('hello')\n", encoding="utf-8")
    repo_watcher._recent_events.clear()
    watcher = repo_watcher.PollingRepoWatcher(repo_root=repo, user_id=1, interval_sec=1, auto_reindex=False)
    watcher.scan_once()  # first emits
    assert events.count("code_changed") == 1
    # Second scan within rate window
    watcher.scan_once()
    assert events.count("code_changed") == 1  # no duplicate
    # Advance time beyond window and modify file to trigger change
    now[0] += 301
    file_path.write_text("print('hello2')\n", encoding="utf-8")
    watcher.scan_once()
    assert events.count("code_changed") == 2


def test_test_watcher_success(monkeypatch):
    events = []

    def fake_add_event(user_id, type, title, body, severity="info", meta=None):
        events.append((type, title, body, severity))

    monkeypatch.setattr(test_watcher, "add_event", fake_add_event)

    # Mock subprocess.run for success
    def fake_run(cmd, **kwargs):
        class FakeResult:
            returncode = 0
            stdout = "test session starts\ncollected 5 items\n\npassed 5/5\n"
            stderr = ""
        return FakeResult()

    monkeypatch.setattr(test_watcher.subprocess, "run", fake_run)

    test_watcher.run_pytest_and_notify(1, "en")

    assert len(events) == 1
    type, title, body, severity = events[0]
    assert type == "tests_passed"
    assert title == "Tests passed"
    assert body == "All tests passed"
    assert severity == "info"


def test_test_watcher_failure(monkeypatch):
    events = []

    def fake_add_event(user_id, type, title, body, severity="info", meta=None):
        events.append((type, title, body, severity, meta))

    monkeypatch.setattr(test_watcher, "add_event", fake_add_event)

    # Mock subprocess.run for failure
    def fake_run(cmd, **kwargs):
        class FakeResult:
            returncode = 1
            stdout = "FAILED test_example.py::test_func\nE   AssertionError: expected 1 == 2\nE   assert 1 == 2\n"
            stderr = ""
        return FakeResult()

    monkeypatch.setattr(test_watcher.subprocess, "run", fake_run)

    # Mock search_code
    def fake_search_code(query, limit=6):
        return [
            {"path": "src/jarvis/agent.py", "start_line": 10, "end_line": 20},
            {"path": "src/jarvis/utils.py", "start_line": 5, "end_line": 15},
            {"path": "tests/test_example.py", "start_line": 1, "end_line": 10},
            {"path": "src/jarvis/db.py", "start_line": 100, "end_line": 110},
        ][:limit]

    monkeypatch.setattr(test_watcher, "search_code", fake_search_code)

    test_watcher.run_pytest_and_notify(1, "da")

    assert len(events) == 1
    type, title, body, severity, meta = events[0]
    assert type == "tests_failed"
    assert title == "Tests fejlede (1)"
    assert "Fejlede tests:" in body
    assert "Suggestions:" in body
    assert "Refs:" in body
    assert len(meta["refs"]) == 4  # All refs in meta


def test_test_watcher_rate_limit(monkeypatch):
    events = []
    now = [2000.0]

    def fake_add_event(user_id, type, title, body, severity="info", meta=None):
        events.append(type)

    def fake_time():
        return now[0]

    monkeypatch.setattr(test_watcher, "add_event", fake_add_event)
    test_watcher._recent_events.clear()
    monkeypatch.setattr(test_watcher, "time", fake_time)

    def fake_run(cmd, **kwargs):
        class FakeResult:
            returncode = 1
            stdout = "FAILED test_example.py::test_func\nE   AssertionError: expected 1 == 2\nE   assert 1 == 2\n"
            stderr = ""
        return FakeResult()

    monkeypatch.setattr(test_watcher.subprocess, "run", fake_run)
    monkeypatch.setattr(test_watcher, "search_code", lambda *args, **kwargs: [])

    test_watcher.run_pytest_and_notify(1, "en")
    assert events.count("tests_failed") == 1
    test_watcher.run_pytest_and_notify(1, "en")
    assert events.count("tests_failed") == 1  # suppressed
    now[0] += 301
    test_watcher.run_pytest_and_notify(1, "en")
    assert events.count("tests_failed") == 2


def test_triage_pytest_output_success():
    output = "test session starts\ncollected 5 items\n\npassed 5/5\n"
    result = triage_pytest_output(output, "en")
    assert result["title"] == "Tests passed"
    assert result["body"] == "All tests passed"
    assert result["query_terms"] == []


def test_triage_pytest_output_failure():
    output = """test session starts
collected 2 items

test_example.py::test_func - AssertionError: expected 1, got 2
E   AssertionError: expected 1, got 2
E   at line 10
E   more details

FAILED test_example.py::test_func - AssertionError: expected 1, got 2
ERROR test_example.py::test_other - ImportError: no module

passed 0/2
"""
    result = triage_pytest_output(output, "en")
    assert result["title"] == "Tests failed (2)"
    assert "test_func" in result["body"]
    assert "test_other" in result["body"]
    assert "AssertionError" in result["query_terms"]
