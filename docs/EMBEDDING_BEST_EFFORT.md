# Embedding Best-Effort Configuration

## Overview
Jarvis has been updated to provide best-effort embedding/RAG handling. If embeddings fail (timeout, connection error, etc.), the system automatically falls back to:
1. **Memory search**: Falls back to substring matching instead of vector search
2. **Code RAG**: Falls back to substring search in code chunks
3. **Index building**: Skips chunks that fail to embed, continues with successful ones

**Key guarantee**: Chat will **never crash or stop responding** due to embedding failures. RAG will gracefully degrade to substring search.

## Environment Variables

### `JARVIS_DISABLE_EMBEDDINGS=1` (NEW)
Completely disables embeddings and uses fast hash-based embeddings throughout:
- Skips Ollama embedding API calls entirely
- Uses deterministic SHA256-based hash embeddings instead
- Forces all RAG searches to use substring matching (fallback search)
- Useful for: Testing, offline environments, or when Ollama is unavailable

### `DISABLE_EMBEDDINGS=1` (legacy)
Also supported for backward compatibility. Has same effect as `JARVIS_DISABLE_EMBEDDINGS=1`.

### Standard Ollama Configuration (unchanged)
- `OLLAMA_EMBED_URL`: Default `http://127.0.0.1:11434/api/embeddings`
- `OLLAMA_EMBED_MODEL`: Default `nomic-embed-text`
- `EMBEDDINGS_BACKEND`: Default `ollama` (also supports `sentence_transformers`)

## Error Handling

### Timeout/Connection Errors
If embedding requests timeout or fail to connect:
- **Logged as WARNING**: `"Embedding timeout/connection error (best-effort fallback): [error type]"`
- **Behavior**: Automatically falls back to hash-embed + substring search
- **Result**: Chat continues, RAG quality degrades but doesn't fail

### General Embedding Errors
If embedding fails for any other reason:
- **Logged as WARNING**: `"Embedding error (best-effort fallback): [error type]"`
- **Behavior**: Falls back to hash-embed
- **Result**: Chat continues with degraded RAG

### Memory/Code Index Rebuilds
When embedding dimension mismatches or chunk encoding fails:
- **Logged as WARNING**: Specific chunk/entry skipped
- **Behavior**: Continues indexing other chunks
- **Result**: Index builds successfully with subset of chunks, no failures

## Examples

### Disable embeddings entirely (fastest, for testing)
```bash
JARVIS_DISABLE_EMBEDDINGS=1 python -m jarvis
```

### Use custom Ollama instance
```bash
OLLAMA_EMBED_URL=http://192.168.1.100:11434/api/embeddings python -m jarvis
```

### Use sentence_transformers with GPU
```bash
EMBEDDINGS_BACKEND=sentence_transformers \
EMBEDDINGS_MODEL=all-MiniLM-L6-v2 \
EMBEDDINGS_DEVICE=cuda \
python -m jarvis
```

## Implementation Details

### `_encode(text: str, best_effort: bool = True)`
Updated in `src/jarvis/memory.py`:
- `best_effort=True`: Catches all embedding errors and falls back to hash-embed (new default)
- `best_effort=False`: Raises exceptions (for strict validation)
- Catches: `TimeoutError`, `ConnectionError`, `OSError`, and general `Exception`
- Logs all errors with appropriate level (WARNING/ERROR)

### `search_code(query, ...)`
Updated in `src/jarvis/code_rag/search.py`:
- Checks `JARVIS_DISABLE_EMBEDDINGS` env var
- Encodes query with `best_effort=True` (automatic hash-embed fallback on error)
- Falls back to `_search_fallback()` if encoding fails (substring matching)
- Falls back to substring search if FAISS index search fails
- **Never raises exceptions** - always returns list (possibly empty)

### Memory Operations
Updated in `src/jarvis/memory.py`:
- `add_memory()`: Uses `best_effort=True`, logs warnings on failure, continues
- `search_memory()`: Uses `best_effort=True`, falls back to empty results on error
- `_ensure_index_dim()`: Rebuilds index with `best_effort=True`, skips failed chunks

### Index Building
Updated in `src/jarvis/code_rag/index.py`:
- `build_index()`: Encodes chunks with `best_effort=True`
- Skips individual chunks that fail, continues with others
- Index builds successfully even if some chunks fail to encode

## Logging
All embedding warnings are logged using Python's `logging` module to `jarvis.memory`, `jarvis.code_rag.search`, and `jarvis.code_rag.index`:

```
jarvis.memory - WARNING - Embedding timeout/connection error (best-effort fallback): ConnectionError: [...]
jarvis.code_rag.search - WARNING - Failed to encode query for search (using fallback): [...]
```

Check logs with:
```bash
grep -i "embedding\|rag" <logfile>
```

## Testing
Run chat normally. If Ollama is down/unavailable:
1. First code search: Takes slightly longer (embedding timeout + fallback)
2. Subsequent searches: Use substring matching (fast)
3. Chat responses: Continue normally, may have less context from code RAG

Test with:
```bash
JARVIS_DISABLE_EMBEDDINGS=1 python -m pytest tests/test_code_skill.py -v
```
