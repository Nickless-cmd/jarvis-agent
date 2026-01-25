"""Search utilities for the local code RAG index."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import List

import faiss
import numpy as np

from jarvis.code_rag.index import DEFAULT_INDEX_DIR, DEFAULT_REPO_ROOT, ensure_index, load_index
from jarvis.memory import _encode

logger = logging.getLogger(__name__)


@dataclass
class CodeHit:
  path: str
  start_line: int
  end_line: int
  score: float
  content: str


def _load_chunks(index_dir: Path) -> List[dict]:
  manifest_path = index_dir / "manifest.json"
  if not manifest_path.exists():
    return []
  try:
    import json

    with open(manifest_path, "r", encoding="utf-8") as f:
      manifest = json.load(f)
    return manifest.get("chunks", [])
  except Exception:
    return []


def _search_fallback(query: str, index_dir: Path) -> list[CodeHit]:
  """Simple substring search used when embeddings are disabled."""
  hits: list[CodeHit] = []
  chunks = _load_chunks(index_dir)
  q = (query or "").lower()
  if not q:
    return hits
  for entry in chunks:
    content = (entry.get("excerpt") or "").lower()
    if q in content:
      hits.append(
        CodeHit(
          path=entry.get("path", ""),
          start_line=entry.get("start_line", 0),
          end_line=entry.get("end_line", 0),
          score=0.0,
          content=entry.get("excerpt", "") or "",
        )
      )
  return hits


def search_code(
  query: str,
  repo_root: Path | str | None = None,
  index_dir: Path | str | None = None,
  k: int = 8,
  trace_id: str | None = None,
) -> list[CodeHit]:
  """Search the code index for relevant chunks. Best-effort: returns fallback on embedding errors.
  
  Args:
      trace_id: optional trace ID for cancellation-aware embeddings
  """
  root = Path(repo_root) if repo_root else DEFAULT_REPO_ROOT
  target = Path(index_dir) if index_dir else DEFAULT_INDEX_DIR

  # Check if embeddings are disabled or if we should use fallback
  if os.getenv("JARVIS_DISABLE_EMBEDDINGS") == "1" or os.getenv("DISABLE_EMBEDDINGS") == "1":
    return _search_fallback(query, target)

  existing = load_index(index_dir=target)
  if not existing:
    existing = ensure_index(repo_root=root, index_dir=target)
  if not existing:
    return []
  idx, chunks = existing

  try:
    from jarvis.memory import EmbeddingDimMismatch
    vec = _encode(query, best_effort=True, expected_dim=idx.d, trace_id=trace_id)
    vec = np.asarray(vec, dtype=np.float32).reshape(1, -1)
  except EmbeddingDimMismatch as exc:
    logger.error(
      f"embedding dimension mismatch (actual={exc.actual}, expected={exc.expected}, model={exc.model}); "
      f"skipping RAG and using fallback"
    )
    return _search_fallback(query, target)
  except Exception as e:
    logger.warning(f"Failed to encode query for search (using fallback): {e}")
    return _search_fallback(query, target)

  try:
    scores, ids = idx.search(vec, min(k, len(chunks)))
  except Exception as e:
    logger.warning(f"FAISS search failed (using fallback): {e}")
    return _search_fallback(query, target)

  hits: list[CodeHit] = []
  for score, chunk_idx in zip(scores[0], ids[0]):
    if chunk_idx < 0 or chunk_idx >= len(chunks):
      continue
    chunk = chunks[chunk_idx]
    hits.append(
      CodeHit(
        path=chunk.path if hasattr(chunk, "path") else chunk.get("path", ""),
        start_line=chunk.start_line if hasattr(chunk, "start_line") else chunk.get("start_line", 0),
        end_line=chunk.end_line if hasattr(chunk, "end_line") else chunk.get("end_line", 0),
        score=float(score),
        content=chunk.content if hasattr(chunk, "content") else chunk.get("excerpt", "") or "",
      )
    )
  return hits
