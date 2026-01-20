import json
import os
from pathlib import Path

from jarvis.code_rag.index import build_index
from jarvis.code_rag.search import search_code


def test_index_excludes_blacklist(tmp_path, monkeypatch):
    monkeypatch.setenv("DISABLE_EMBEDDINGS", "1")
    repo = tmp_path / "repo"
    (repo / "__pycache__").mkdir(parents=True, exist_ok=True)
    (repo / "__pycache__" / "skip.py").write_text("SHOULD_NOT_BE_INDEXED", encoding="utf-8")
    target = repo / "src" / "jarvis"
    target.mkdir(parents=True, exist_ok=True)
    good_file = target / "main.py"
    good_file.write_text("def foo():\n    return 'HELLO_WORLD'\n", encoding="utf-8")

    index_dir = tmp_path / "index"
    _, chunks = build_index(repo_root=repo, index_dir=index_dir, chunk_size=50, overlap=10)

    with open(index_dir / "manifest.json", "r", encoding="utf-8") as f:
        manifest = json.load(f)
    paths = [c["path"] for c in manifest.get("chunks", [])]
    assert any("main.py" in p for p in paths)
    assert not any("__pycache__" in p for p in paths)
    assert chunks


def test_search_returns_hit(tmp_path, monkeypatch):
    monkeypatch.setenv("DISABLE_EMBEDDINGS", "1")
    repo = tmp_path / "repo"
    src_dir = repo / "src" / "jarvis"
    src_dir.mkdir(parents=True, exist_ok=True)
    unique = "VERY_UNIQUE_TOKEN_123"
    (src_dir / "example.py").write_text(
        f"# example\n\ndef special():\n    return '{unique}'\n",
        encoding="utf-8",
    )

    index_dir = tmp_path / "index"
    build_index(repo_root=repo, index_dir=index_dir, chunk_size=50, overlap=10)

    hits = search_code(unique, repo_root=repo, index_dir=index_dir)
    assert hits
    assert any("example.py" in h.path for h in hits)


def test_search_no_hits(tmp_path, monkeypatch):
    monkeypatch.setenv("DISABLE_EMBEDDINGS", "1")
    repo = tmp_path / "repo"
    src_dir = repo / "src" / "jarvis"
    src_dir.mkdir(parents=True, exist_ok=True)
    (src_dir / "example.py").write_text(
        "# example\n\ndef special():\n    return 'some_code'\n",
        encoding="utf-8",
    )

    index_dir = tmp_path / "index"
    build_index(repo_root=repo, index_dir=index_dir, chunk_size=50, overlap=10)

    hits = search_code("NON_EXISTENT_TOKEN_456", repo_root=repo, index_dir=index_dir)
    assert not hits