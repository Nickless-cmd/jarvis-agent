"""Non-blocking RAG retrieval for streaming responses."""

import os
import logging
import threading
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class NonBlockingRAGCache:
    """Simple thread-safe cache for RAG results."""
    def __init__(self):
        self.results = {}
        self.lock = threading.Lock()
    
    def get(self, key: str):
        with self.lock:
            return self.results.get(key)
    
    def set(self, key: str, value):
        with self.lock:
            self.results[key] = value
    
    def clear(self, key: str) -> None:
        with self.lock:
            self.results.pop(key, None)


_rag_cache = NonBlockingRAGCache()


def retrieve_code_rag_async(
    prompt: str,
    prompt_hash: str,
    timeout: float = 1.0,
    repo_root: Optional[Path] = None,
    index_dir: Optional[Path] = None,
    trace_id: str | None = None,
) -> None:
    """
    Retrieve code RAG results in background thread with timeout.
    Results are stored in cache keyed by prompt_hash.
    
    Args:
        trace_id: optional trace ID for cancellation-aware embeddings
    """
    # Check if RAG is disabled
    if os.getenv("JARVIS_DISABLE_EMBEDDINGS") == "1":
        logger.debug(f"Skipping RAG (JARVIS_DISABLE_EMBEDDINGS=1) for prompt_hash={prompt_hash}")
        _rag_cache.set(prompt_hash, [])
        return

    def _retrieve():
        try:
            from jarvis.code_rag.search import search_code

            logger.debug(f"RAG retrieval starting for prompt_hash={prompt_hash}")
            start = time.time()

            hits = search_code(
                prompt,
                repo_root=repo_root,
                index_dir=index_dir,
                k=5,
                trace_id=trace_id,
            )
            
            _rag_cache.set(prompt_hash, hits)
        except Exception as e:
            logger.warning(
                f"RAG retrieval failed for prompt_hash={prompt_hash}: {type(e).__name__}: {e}"
            )
            _rag_cache.set(prompt_hash, [])
    
    thread = threading.Thread(target=_retrieve, daemon=True)
    thread.start()


def get_code_rag_results(
    prompt_hash: str,
    max_wait: float = 0.1,
    trace_id: str | None = None,
):
    """Get RAG results if available (non-blocking)."""
    start = time.time()
    
    while time.time() - start < max_wait:
        # Check if stream has been cancelled
        if trace_id:
            try:
                from jarvis.server import check_stream_cancelled_sync
                if check_stream_cancelled_sync(trace_id):
                    logger.debug(f"RAG cancelled: trace={trace_id}")
                    _rag_cache.clear(prompt_hash)
                    return []
            except Exception:
                pass
        
        results = _rag_cache.get(prompt_hash)
        if results is not None:
            _rag_cache.clear(prompt_hash)  # Clean up
            return results
        time.sleep(0.01)
    
    logger.debug(f"RAG timeout for prompt_hash={prompt_hash} (waited {max_wait:.2f}s)")
    _rag_cache.clear(prompt_hash)
    return []


def wait_for_code_rag_results(
    prompt_hash: str,
    timeout: float = 1.0,
):
    """Wait for RAG results with timeout."""
    start = time.time()
    
    while time.time() - start < timeout:
        results = _rag_cache.get(prompt_hash)
        if results is not None:
            _rag_cache.clear(prompt_hash)
            return results
        time.sleep(0.05)
    
    logger.debug(f"RAG timeout for prompt_hash={prompt_hash} (waited {timeout:.2f}s)")
    _rag_cache.clear(prompt_hash)
    return []
