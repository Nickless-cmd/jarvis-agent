import subprocess

from jarvis.watchers import test_watcher


class DummyResult:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_run_pytest_success(monkeypatch):
    events = []

    def fake_run(cmd, capture_output, text, check):
        return DummyResult(returncode=0, stdout="all good", stderr="")

    def fake_add_event(user_id, type, severity, title, body, meta=None):
        events.append((type, severity, title, body))

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(test_watcher, "add_event", fake_add_event)
    code = test_watcher.run_pytest_and_notify(user_id=1, ui_lang="en")
    assert code == 0
    assert events
    assert events[0][0] == "tests_passed"
    assert "passed" in events[0][2].lower()


def test_run_pytest_failure(monkeypatch):
    events = []

    def fake_run(cmd, capture_output, text, check):
        return DummyResult(returncode=1, stdout="test_example.py::test_func FAILED\ntraceback\nline2", stderr="")

    def fake_add_event(user_id, type, severity, title, body, meta=None):
        events.append((type, severity, title, body))

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(test_watcher, "add_event", fake_add_event)
    code = test_watcher.run_pytest_and_notify(user_id=1, ui_lang="da")
    assert code == 1
    assert events
    assert events[0][0] == "tests_failed"
    assert "Fejlede tests" in events[0][3]
