import hashlib
import json
import os
import re
from dataclasses import dataclass

import numpy as np
from jarvis.provider.ollama_client import ollama_request
from jarvis.agent_core.cache import TTLCache

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

DIM = 384
_EMBEDDER = None

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


def _encode(text: str):
    embedder = _get_embedder()
    if os.getenv("DISABLE_EMBEDDINGS") == "1":
        return _to_vec(_hash_embed(text))
    backend = os.getenv("EMBEDDINGS_BACKEND", "ollama")
    if backend == "ollama":
        url = os.getenv("OLLAMA_EMBED_URL", "http://127.0.0.1:11434/api/embeddings")
        model = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
        resp = ollama_request(
            url,
            {"model": model, "prompt": text},
            connect_timeout=3.0,
            read_timeout=30.0,
            retries=2,
        )
        if resp.get("ok"):
            data = resp.get("data") or {}
            vec = data.get("embedding")
            if not vec:
                raise RuntimeError("Missing embedding from Ollama")
            return _to_vec(vec)
        error = resp.get("error") or {}
        raise RuntimeError(
            f"Ollama embeddings failed ({error.get('type')}): {error.get('message')} [trace_id={error.get('trace_id')}]"
        )
    return _to_vec(embedder.encode([text])[0])


def _ensure_index_dim(store: MemoryStore, dim: int) -> None:
    if store.index.d == dim:
        return
    print(f"⚠ Embedding dim mismatch (index={store.index.d}, vec={dim}); rebuilding index")
    new_index = faiss.IndexFlatL2(dim)
    new_memories = []
    for entry in store.memories:
        try:
            vec = _encode(entry)
            if vec.size != dim:
                continue
            new_index.add(vec.reshape(1, -1))
            new_memories.append(entry)
        except Exception as exc:
            print(f"⚠ Embedding rebuild skipped: {exc!r}")
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
    store = _get_store(user_id)
    _search_cache.clear()
    try:
        vec = _encode(entry)
        _ensure_index_dim(store, vec.size)
        store.index.add(vec.reshape(1, -1))
    except Exception as exc:
        print(f"⚠ Embedding add skipped: {exc!r}")
        return
    store.memories.append(entry)
    store.save()


def search_memory(query: str, k: int = 3, user_id: str | None = None) -> list[str]:
    global _last_cache_status
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
        qvec = _encode(query)
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
        print(f"⚠ Embedding search skipped: {exc!r}")
        return []


def get_last_cache_status() -> str | None:
    """Return last search_memory cache status."""
    return _last_cache_status
