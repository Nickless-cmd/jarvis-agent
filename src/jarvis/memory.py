import hashlib
import json
import logging
import os
import re
from dataclasses import dataclass

import numpy as np
from jarvis.provider.ollama_client import ollama_request
from jarvis.agent_core.cache import TTLCache

logger = logging.getLogger(__name__)


class EmbeddingDimMismatch(Exception):
    def __init__(self, actual: int, expected: int, model: str):
        super().__init__(f"EmbeddingDimMismatch(actual={actual}, expected={expected}, model={model})")
        self.actual = actual
        self.expected = expected
        self.model = model

# Ensure we only log embedding length once per trace
_logged_embed_len_traces: set[str] = set()

try:
    import faiss  # type: ignore
except ImportError:  # pragma: no cover - fallback for environments without faiss
    class _DummyIndex:
        def __init__(self, d: int):
            self.d = d
            self.vectors: list[np.ndarray] = []

        @property
        def ntotal(self) -> int:
            return len(self.vectors)

        def add(self, mat: np.ndarray) -> None:
            for row in mat:
                self.vectors.append(np.asarray(row, dtype=np.float32).reshape(-1))

        def search(self, mat: np.ndarray, k: int):
            if not self.vectors:
                return np.array([[]], dtype=np.float32), np.array([[]], dtype=int)
            data = np.stack(self.vectors)
            query = np.asarray(mat, dtype=np.float32)
            # Simple L2 distance
            diffs = data[None, :, :] - query[:, None, :]
            dists = np.sum(diffs ** 2, axis=2)
            idx = np.argsort(dists, axis=1)[:, :k]
            dist_sorted = np.take_along_axis(dists, idx, axis=1)
            return dist_sorted, idx

    class _DummyFaiss:
        IndexFlatL2 = _DummyIndex
        Index = _DummyIndex

        @staticmethod
        def write_index(index: _DummyIndex, path: str) -> None:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            arr = np.stack(index.vectors) if index.vectors else np.zeros((0, index.d), dtype=np.float32)
            np.save(path, arr)

        @staticmethod
        def read_index(path: str) -> _DummyIndex:
            arr = np.load(path) if os.path.exists(path) else np.zeros((0, DIM), dtype=np.float32)
            dim = arr.shape[1] if arr.size else DIM
            idx = _DummyIndex(dim)
            for row in arr:
                idx.vectors.append(np.asarray(row, dtype=np.float32).reshape(-1))
            return idx

    faiss = _DummyFaiss()

# Default embedding dimension - may be overridden by provider
# This is just a fallback; the actual dimension comes from probing
DIM = 384
_EMBEDDER = None
_EMBEDDING_DIM_RUNTIME: int | None = None  # Cache the probed dimension from Ollama
DATA_DIR = os.path.abspath(
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "data", "memory")
)


def _safe_user_id(user_id: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "_", user_id)
    return cleaned or "default"


@dataclass
class MemoryStore:
    index: faiss.Index
    memories: list[str]
    index_file: str
    data_file: str

    def save(self) -> None:
        os.makedirs(DATA_DIR, exist_ok=True)
        faiss.write_index(self.index, self.index_file)
        with open(self.data_file, "w", encoding="utf-8") as f:
            json.dump(self.memories, f, ensure_ascii=False, indent=2)


_stores: dict[str, MemoryStore] = {}
_search_cache = TTLCache(default_ttl=float(os.getenv("MEMORY_CACHE_TTL", "60") or 60))
_last_cache_status: str | None = None


def _hash_embed(text: str, dim: int = DIM):
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    seed = int.from_bytes(digest[:4], "little")
    # Deterministic best-effort embedding to ensure fallback never raises
    rng = np.random.default_rng(seed)
    vec = rng.random(dim, dtype=np.float32)
    return vec


def _get_embedder():
    global _EMBEDDER
    if _EMBEDDER is not None:
        return _EMBEDDER
    if os.getenv("DISABLE_EMBEDDINGS") == "1":
        _EMBEDDER = _hash_embed
        return _EMBEDDER
    backend = os.getenv("EMBEDDINGS_BACKEND", "ollama")
    if backend == "sentence_transformers":
        from sentence_transformers import SentenceTransformer

        device = os.getenv("EMBEDDINGS_DEVICE", "cpu")
        model_name = os.getenv("EMBEDDINGS_MODEL", "all-MiniLM-L6-v2")
        try:
            _EMBEDDER = SentenceTransformer(model_name, device=device)
        except Exception as exc:
            raise RuntimeError("Embeddings-model mangler lokalt") from exc
        return _EMBEDDER
    _EMBEDDER = "ollama"
    return _EMBEDDER


def _to_vec(x) -> np.ndarray:
    vec = np.asarray(x, dtype=np.float32).reshape(-1)
    if vec.size == 0:
        raise ValueError("empty embedding")
    return vec


def get_embedding_dim() -> int:
    """Get the current embedding dimension (cached after first probe).
    This ensures we use the actual dimension from the embedding provider (e.g., 768 from Ollama nomic-embed-text)."""
    global _EMBEDDING_DIM_RUNTIME
    if _EMBEDDING_DIM_RUNTIME is not None:
        return _EMBEDDING_DIM_RUNTIME
    # Probe once and cache
    try:
        # Try a tiny probe to get the dimension without full encoding
        from jarvis.provider.ollama_client import ollama_request
        model = os.getenv("OLLAMA_EMBED_MODEL") or "nomic-embed-text:latest"
        url = os.getenv("OLLAMA_EMBED_URL", "http://127.0.0.1:11434/api/embeddings")
        resp = ollama_request(url, {"model": model, "prompt": "."}, connect_timeout=2.0, read_timeout=10.0, retries=1)
        if resp.get("ok"):
            data = resp.get("data") or {}
            vec = data.get("embedding", [])
            if vec:
                _EMBEDDING_DIM_RUNTIME = len(vec)
                logger.info(f"Embedding dimension auto-detected from {model}: {_EMBEDDING_DIM_RUNTIME}")
                return _EMBEDDING_DIM_RUNTIME
    except Exception as e:
        logger.warning(f"Failed to auto-probe embedding dimension: {e}")
    
    # Fallback
    _EMBEDDING_DIM_RUNTIME = DIM
    logger.warning(f"Using fallback embedding dimension: {DIM}")
    return DIM


def _encode(text: str, best_effort: bool = True, *, expected_dim: int | None = None, trace_id: str | None = None):
    """Encode text to embedding. Falls back to hash-embed on error if best_effort=True.
    
    Respects cancellation signal from streaming. If trace_id provided and stream is cancelled,
    raises early to prevent wasted computation.

    Args:
        expected_dim: If provided, validate returned vector length and raise EmbeddingDimMismatch on mismatch.
        trace_id: Optional trace id to log once and support cancellation-aware provider retries.
    """
    # Check if embeddings are disabled
    if os.getenv("JARVIS_DISABLE_EMBEDDINGS") == "1" or os.getenv("DISABLE_EMBEDDINGS") == "1":
        return _to_vec(_hash_embed(text))

    # Cancellation check BEFORE starting expensive operation
    if trace_id:
        try:
            from jarvis.server import check_stream_cancelled_sync  # type: ignore
            if check_stream_cancelled_sync(trace_id):
                logger.info(f"[EMBED] Cancelled before request (trace_id={trace_id})")
                raise RuntimeError(f"Embedding cancelled by stream stop (trace_id={trace_id})")
        except RuntimeError:
            raise  # Re-raise cancellation
        except Exception:
            pass  # Server module not available, continue

    embedder = _get_embedder()
    backend = os.getenv("EMBEDDINGS_BACKEND", "ollama")

    try:
        if backend == "ollama":
            url = os.getenv("OLLAMA_EMBED_URL", "http://127.0.0.1:11434/api/embeddings")
            # Force known-good embedding model
            model = os.getenv("OLLAMA_EMBED_MODEL") or "nomic-embed-text:latest"
            resp = ollama_request(
                url,
                {"model": model, "prompt": text},
                connect_timeout=3.0,
                read_timeout=30.0,
                retries=2,
                trace_id=trace_id,
            )
            if resp.get("ok"):
                data = resp.get("data") or {}
                vec = data.get("embedding")
                if not vec:
                    logger.warning("Missing embedding from Ollama response (trace_id=%s); using hash fallback", resp.get("trace_id"))
                    if best_effort:
                        return _to_vec(_hash_embed(text))
                    raise RuntimeError("Missing embedding from Ollama")
                try:
                    arr = _to_vec(vec)
                    # Cache the actual embedding dimension from provider
                    global _EMBEDDING_DIM_RUNTIME
                    if _EMBEDDING_DIM_RUNTIME is None:
                        _EMBEDDING_DIM_RUNTIME = int(arr.size)
                        logger.info(f"Embedding dimension locked from {model}: {_EMBEDDING_DIM_RUNTIME}")
                    # Log actual embedding length once per trace
                    tid = resp.get("trace_id") or trace_id
                    if tid and tid not in _logged_embed_len_traces:
                        logger.info("embedding_len=%s model=%s trace_id=%s", int(arr.size), model, tid)
                        # bound the set size; avoid unbounded growth
                        if len(_logged_embed_len_traces) > 1024:
                            _logged_embed_len_traces.clear()
                        _logged_embed_len_traces.add(tid)
                    if expected_dim is not None and int(arr.size) != int(expected_dim):
                        raise EmbeddingDimMismatch(int(arr.size), int(expected_dim), model)
                    
                    # Cancellation check AFTER response received (before returning to caller)
                    if trace_id:
                        try:
                            from jarvis.server import check_stream_cancelled_sync  # type: ignore
                            if check_stream_cancelled_sync(trace_id):
                                logger.info(f"[EMBED] Cancelled after response (trace_id={trace_id})")
                                raise RuntimeError(f"Embedding cancelled after response (trace_id={trace_id})")
                        except RuntimeError:
                            raise  # Re-raise cancellation
                        except Exception:
                            pass  # Server module not available, continue
                    
                    return arr
                except EmbeddingDimMismatch:
                    raise
                except Exception as exc:
                    logger.warning("Invalid embedding shape (%s); using hash fallback", exc)
                    if best_effort:
                        return _to_vec(_hash_embed(text))
                    raise
            error = resp.get("error") or {}
            # If cancelled, short-circuit without retry loops
            if (error.get("type") or "").lower() == "clientcancelled".lower():
                logger.info(f"[EMBED] Cancelled during request (trace_id={trace_id})")
                raise RuntimeError(f"Embedding cancelled during request (trace_id={trace_id})")
            msg = f"Ollama embeddings failed ({error.get('type')}): {error.get('message')} [trace_id={error.get('trace_id')}]"
            logger.warning(msg)
            if best_effort:
                return _to_vec(_hash_embed(text))
            raise RuntimeError(msg)
        else:
            # sentence_transformers or other backend
            arr = _to_vec(embedder.encode([text])[0])
            model = os.getenv("EMBEDDINGS_MODEL", "all-MiniLM-L6-v2")
            if expected_dim is not None and int(arr.size) != int(expected_dim):
                raise EmbeddingDimMismatch(int(arr.size), int(expected_dim), model)
            return arr
    except (TimeoutError, ConnectionError, OSError) as e:
        logger.warning(f"Embedding timeout/connection error (best-effort fallback): {type(e).__name__}: {e}")
        if best_effort:
            return _to_vec(_hash_embed(text))
        raise
    except EmbeddingDimMismatch:
        # propagate, let caller decide on fallback (e.g., skip RAG)
        raise
    except Exception as e:
        logger.warning(f"Embedding error (best-effort fallback): {type(e).__name__}: {e}")
        if best_effort:
            return _to_vec(_hash_embed(text))
        raise


def _ensure_index_dim(store: MemoryStore, dim: int) -> None:
    if store.index.d == dim:
        return
    logger.info(f"⚠ Embedding dim mismatch (index={store.index.d}, vec={dim}); rebuilding index")
    new_index = faiss.IndexFlatL2(dim)
    new_memories = []
    for entry in store.memories:
        try:
            vec = _encode(entry, best_effort=True)
            if vec.size != dim:
                continue
            new_index.add(vec.reshape(1, -1))
            new_memories.append(entry)
        except Exception as exc:
            logger.warning(f"Embedding rebuild skipped for entry: {exc!r}")
            continue
    store.index = new_index
    store.memories = new_memories
    store.save()


def _load_store(user_id: str) -> MemoryStore:
    safe_id = _safe_user_id(user_id)
    index_file = os.path.join(DATA_DIR, f"{safe_id}.faiss")
    data_file = os.path.join(DATA_DIR, f"{safe_id}.json")

    if os.path.exists(index_file):
        index = faiss.read_index(index_file)
    else:
        index = faiss.IndexFlatL2(DIM)

    if os.path.exists(data_file):
        with open(data_file, "r", encoding="utf-8") as f:
            memories = json.load(f)
    else:
        memories = []

    return MemoryStore(index=index, memories=memories, index_file=index_file, data_file=data_file)


def _get_store(user_id: str) -> MemoryStore:
    if user_id not in _stores:
        _stores[user_id] = _load_store(user_id)
    return _stores[user_id]


def purge_user_memory(user_id: str) -> None:
    safe_id = _safe_user_id(user_id)
    index_file = os.path.join(DATA_DIR, f"{safe_id}.faiss")
    data_file = os.path.join(DATA_DIR, f"{safe_id}.json")
    _stores.pop(user_id, None)
    _search_cache.clear()
    for path in (index_file, data_file):
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception:
            pass


def add_memory(role: str, text: str, user_id: str = "default") -> None:
    entry = f"{role}: {text}"
    if len(text) < 20:
        return
    
    # Memory indexing uses embeddings - only enable if RAG is enabled
    if os.getenv("JARVIS_ENABLE_RAG") != "1":
        logger.debug(f"Memory add skipped (JARVIS_ENABLE_RAG not set)")
        return
    
    store = _get_store(user_id)
    _search_cache.clear()
    try:
        vec = _encode(entry, best_effort=True)
        _ensure_index_dim(store, vec.size)
        store.index.add(vec.reshape(1, -1))
    except Exception as exc:
        logger.warning(f"Embedding add skipped: {exc!r}")
        return
    store.memories.append(entry)
    store.save()


def search_memory(query: str, k: int = 3, user_id: str | None = None, trace_id: str | None = None) -> list[str]:
    global _last_cache_status
    
    # Memory search uses embeddings - only enable if RAG is enabled
    if os.getenv("JARVIS_ENABLE_RAG") != "1":
        logger.debug(f"search_memory skipped (JARVIS_ENABLE_RAG not set)")
        return []
    
    # Check if stream has been cancelled
    if trace_id:
        try:
            from jarvis.server import check_stream_cancelled_sync
            if check_stream_cancelled_sync(trace_id):
                logger.debug(f"search_memory cancelled: trace={trace_id}")
                return []
        except Exception:
            pass
    
    cache_key = (user_id or "default", query, k)
    cached = _search_cache.get(cache_key)
    if cached is not None:
        _last_cache_status = "hit"
        return cached
    _last_cache_status = "miss"

    store = _get_store(user_id)
    if store.index.ntotal == 0:
        return []
    try:
        qvec = _encode(query, best_effort=True, expected_dim=store.index.d, trace_id=trace_id)
        _ensure_index_dim(store, qvec.size)
        qmat = qvec.reshape(1, -1)
        limit = min(k, store.index.ntotal)
        if limit <= 0:
            return []
        _, ids = store.index.search(qmat, limit)
        hits = [store.memories[i] for i in ids[0] if i < len(store.memories)]
        _search_cache.set(cache_key, hits)
        return hits
    except Exception as exc:
        logger.warning(f"Embedding search skipped: {exc!r}")
        return []


def get_last_cache_status() -> str | None:
    """Return last search_memory cache status."""
    return _last_cache_status
