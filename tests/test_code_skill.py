import tempfile
from pathlib import Path

from jarvis.agent_skills import code_skill


def test_safe_read_file_allows_repo_root(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    target = repo / "file.txt"
    target.write_text("hello", encoding="utf-8")
    text, err = code_skill._safe_read_file("file.txt", repo_root=repo)
    assert err is None
    assert text == "hello"


def test_safe_read_file_blocks_escape(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    text, err = code_skill._safe_read_file("../secret.txt", repo_root=repo)
    assert text is None
    assert "outside" in (err or "").lower()


def test_intent_detection_danish_and_english():
    assert code_skill._file_explain_intent("forklar fil src/app.py") == "src/app.py"
    assert code_skill._file_explain_intent("explain file src/app.py") == "src/app.py"
    assert code_skill._function_intent("hvad gør funktionen run_agent?") == "run_agent"
    assert code_skill._function_intent("what does function handler do?") == "handler"
    assert code_skill._symbol_usage_intent("find hvor symbol foo bruges") == "foo"
    assert code_skill._symbol_usage_intent("where bar is used") == "bar"
