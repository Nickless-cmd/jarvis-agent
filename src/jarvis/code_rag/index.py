"""Code indexing utilities for local RAG."""

from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List
from datetime import datetime

import faiss
import numpy as np

from jarvis.memory import DIM, _encode

logger = logging.getLogger(__name__)

DEFAULT_REPO_ROOT = Path(os.getenv("CODE_RAG_REPO_ROOT") or Path(__file__).resolve().parents[2])
DEFAULT_INDEX_DIR = Path(
    os.getenv("CODE_RAG_INDEX_DIR")
    or DEFAULT_REPO_ROOT / "data" / "code_index" / "default"
)


def _current_embed_dim() -> int:
    """Get current embedding dimension from runtime cache.
    This ensures consistent dimension across all FAISS operations."""
    try:
        from jarvis.memory import get_embedding_dim
        return get_embedding_dim()
    except Exception:
        try:
            return _probe_embedding_dim()
        except Exception:
            return DIM

def _index_dir_for_model(base_dir: Path) -> Path:
    """Return a model+dim-scoped index dir to avoid dim mismatches after model changes."""
    model_slug = _slug(_current_embed_model())
    dim = _current_embed_dim()
    return base_dir / f"model_{model_slug}" / f"dim_{dim}"


def _current_embed_model() -> str:
    return os.getenv("OLLAMA_EMBED_MODEL") or "nomic-embed-text:latest"


def get_index_dim(index_dir: Path | str | None = None) -> int | None:
    """Return the FAISS index dimension if available, else None."""
    base_target = Path(index_dir) if index_dir else DEFAULT_INDEX_DIR
    target = _index_dir_for_model(base_target)
    existing = load_index(index_dir=target)
    if not existing:
        return None
    idx, _ = existing
    try:
        return int(getattr(idx, "d", 0))
    except Exception:
        return None


def _slug(text: str) -> str:
    return (
        text.replace(":", "_")
        .replace("/", "_")
        .replace(" ", "_")
        .strip("_")
        or "default"
    )

EXCLUDE_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    "node_modules",
    "build",
    "dist",
    "data",
    "tts_cache",
    "ui/build",
    "ui/dist",
    "ui/.svelte-kit",
}

INCLUDE_EXT = {".py", ".md", ".sh", ".txt", ".ini", ".cfg"}


@dataclass
class CodeChunk:
    path: str
    start_line: int
    end_line: int
    content: str
    sha: str
    mtime: float


def _should_index(path: Path, repo_root: Path) -> bool:
    rel = path.relative_to(repo_root).as_posix()
    parts = rel.split("/")
    if any(part in EXCLUDE_DIRS for part in parts):
        return False
    if rel.startswith("src/data") or rel.startswith("data/"):
        return False
    if rel.startswith("tts_cache") or rel.startswith("ui/static"):
        return False
    if rel.startswith("comfyui"):
        return False
    if rel.startswith("src/jarvis/") and path.suffix == ".py":
        return True
    if rel.startswith("docs/") and path.suffix == ".md":
        return True
    if rel.startswith("scripts/") and path.suffix == ".sh":
        return True
    if path.name.lower().startswith("readme"):
        return True
    if path.name in {"pytest.ini", "requirements.txt"}:
        return True
    return path.suffix in INCLUDE_EXT


def _iter_files(repo_root: Path) -> Iterable[Path]:
    for root, dirs, files in os.walk(repo_root):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for name in files:
            p = Path(root) / name
            if _should_index(p, repo_root):
                yield p


def _chunk_lines(text: str, chunk_size: int = 200, overlap: int = 40) -> list[tuple[int, int, str]]:
    lines = text.splitlines()
    chunks: list[tuple[int, int, str]] = []
    if not lines:
        return chunks
    step = max(1, chunk_size - overlap)
    for start in range(0, len(lines), step):
        end = min(len(lines), start + chunk_size)
        chunk = "\n".join(lines[start:end])
        chunks.append((start + 1, end, chunk))
        if end == len(lines):
            break
    return chunks


def _hash_content(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _compute_repo_hash(repo_root: Path) -> str:
    """Compute a hash of file paths and mtimes for change detection."""
    files = sorted(_iter_files(repo_root))
    hasher = hashlib.sha256()
    for path in files:
        stat = path.stat()
        hasher.update(str(path.relative_to(repo_root)).encode())
        hasher.update(str(stat.st_mtime).encode())
    return hasher.hexdigest()


def _load_manifest(index_dir: Path) -> dict | None:
    manifest_path = index_dir / "manifest.json"
    if not manifest_path.exists():
        return None
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _save_manifest(index_dir: Path, chunks: List[CodeChunk], repo_root: Path, embedding_dim: int | None, embedding_model: str | None = None) -> None:
    manifest_path = index_dir / "manifest.json"
    payload = {
        "repo_root": str(repo_root),
        "repo_hash": _compute_repo_hash(repo_root),
        "build_timestamp": datetime.now().isoformat(),
        "embedding_dim": embedding_dim,
        "embedding_model": embedding_model or _current_embed_model(),
        "chunks": [
            {
                "path": c.path,
                "start_line": c.start_line,
                "end_line": c.end_line,
                "sha": c.sha,
                "mtime": c.mtime,
                "excerpt": (c.content.replace("\n", " ")[:800] + "…") if len(c.content) > 800 else c.content.replace("\n", " "),
            }
            for c in chunks
        ],
    }
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def build_index(
    repo_root: Path | str | None = None,
    index_dir: Path | str | None = None,
    chunk_size: int = 200,
    overlap: int = 40,
) -> tuple[faiss.Index, list[CodeChunk]]:
    root = Path(repo_root) if repo_root else DEFAULT_REPO_ROOT
    base_target = Path(index_dir) if index_dir else DEFAULT_INDEX_DIR
    target = _index_dir_for_model(base_target)
    os.makedirs(target, exist_ok=True)

    files = list(_iter_files(root))
    chunks: list[CodeChunk] = []
    index: faiss.Index | None = None
    embedding_dim: int | None = None

    for path in files:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for start, end, content in _chunk_lines(text, chunk_size=chunk_size, overlap=overlap):
            sha = _hash_content(content)
            rel = path.relative_to(root).as_posix()
            chunk = CodeChunk(path=rel, start_line=start, end_line=end, content=content, sha=sha, mtime=path.stat().st_mtime)
            try:
                # Enforce max chars per embedding to avoid backend 500 errors
                max_chars = int(os.getenv("EMBEDDING_MAX_CHARS", "8000") or 8000)
                content_safe = content[:max_chars] if len(content) > max_chars else content
                if len(content) > max_chars:
                    logger.debug(
                        "Chunk truncated for embedding: %s:%s-%s from %s to %s chars",
                        rel, start, end, len(content), len(content_safe)
                    )
                vec = _encode(content_safe, best_effort=True)
                if embedding_dim is None:
                    embedding_dim = int(vec.size)
                    index = faiss.IndexFlatL2(embedding_dim)
                if vec.size != embedding_dim:
                    logger.warning(
                        "Skipping chunk for %s:%s-%s due to dim mismatch (vec=%s, expected=%s)",
                        rel,
                        start,
                        end,
                        vec.size,
                        embedding_dim,
                    )
                    continue
                vec = np.asarray(vec, dtype=np.float32).reshape(1, -1)
                index.add(vec)
                chunks.append(chunk)
            except Exception as exc:
                logger.warning(f"Skipping chunk for {rel}:{start}-{end}: {exc}")
                continue

    if index is None:
        # No embeddings succeeded; build an empty index with fallback dim
        embedding_dim = embedding_dim or DIM
        index = faiss.IndexFlatL2(embedding_dim)

    faiss.write_index(index, str(target / "index.faiss"))
    _save_manifest(target, chunks, root, embedding_dim)
    return index, chunks


def load_index(index_dir: Path | str | None = None) -> tuple[faiss.Index, list[CodeChunk]] | None:
    base_target = Path(index_dir) if index_dir else DEFAULT_INDEX_DIR
    target = _index_dir_for_model(base_target)
    manifest = _load_manifest(target)
    index_path = target / "index.faiss"
    if not manifest or not index_path.exists():
        return None
    try:
        idx = faiss.read_index(str(index_path))
    except Exception:
        return None
    chunks = [
        CodeChunk(
            path=entry["path"],
            start_line=entry["start_line"],
            end_line=entry["end_line"],
            content=entry.get("excerpt", ""),
            sha=entry.get("sha", ""),
            mtime=entry.get("mtime", 0.0),
        )
        for entry in manifest.get("chunks", [])
    ]
    return idx, chunks


def _probe_embedding_dim() -> int:
    """Probe current embedding dimension from encoder. Falls back to DIM on error."""
    try:
        vec = _encode("dim-probe", best_effort=True)
        if hasattr(vec, "size") and int(vec.size) > 0:
            return int(vec.size)
    except Exception:
        pass
    return DIM


def ensure_index(
    repo_root: Path | str | None = None,
    index_dir: Path | str | None = None,
) -> tuple[faiss.Index, list[CodeChunk]]:
    root = Path(repo_root) if repo_root else DEFAULT_REPO_ROOT
    base_target = Path(index_dir) if index_dir else DEFAULT_INDEX_DIR
    target = _index_dir_for_model(base_target)
    manifest = _load_manifest(target)
    idx_tuple = load_index(index_dir=target)

    # If nothing exists, build fresh
    if not manifest or not idx_tuple:
        return build_index(repo_root=root, index_dir=target)

    idx, chunks = idx_tuple
    repo_hash_ok = manifest.get("repo_hash") == _compute_repo_hash(root)
    manifest_dim = manifest.get("embedding_dim")
    manifest_model = manifest.get("embedding_model")
    current_dim = _probe_embedding_dim()
    current_model = _current_embed_model()

    dim_mismatch = False
    model_mismatch = False

    # Check model mismatch
    if manifest_model is not None and manifest_model != current_model:
        model_mismatch = True
        logger.warning(f"embedding_model changed (was={manifest_model}, now={current_model}); will rebuild")

    # Check dimension mismatch
    if manifest_dim is not None and manifest_dim != current_dim:
        dim_mismatch = True
        logger.warning(f"embedding_dim changed (was={manifest_dim}, now={current_dim}); will rebuild")
    if idx.d != current_dim:
        dim_mismatch = True
        logger.warning(f"index.d mismatch (index.d={idx.d}, current={current_dim}); will rebuild")

    if repo_hash_ok and not dim_mismatch and not model_mismatch:
        return idx, chunks

    logger.info(
        "Rebuilding code index (repo_hash_ok=%s, dim_mismatch=%s, model_mismatch=%s, current_dim=%s, manifest_dim=%s, index_dim=%s, manifest_model=%s, current_model=%s)",
        repo_hash_ok,
        dim_mismatch,
        model_mismatch,
        current_dim,
        manifest_dim,
        idx.d,
        manifest_model,
        current_model,
    )
    return build_index(repo_root=root, index_dir=target)
