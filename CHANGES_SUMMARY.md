# Production Bug Fix: Stop/Embedding/FAISS Robustness

## Problem Statement

Production logs showed:
1. UI Stop button does not stop streaming; backend continues processing for minutes
2. Repeating "ollama_request failed ... 500 Server Error ... context length exceeds"
3. Repeating "dim mismatch (vec=384, expected=768)" without rebuilding
4. "FAISS search failed" appearing constantly, blocking RAG

Root causes:
- Embedding retries in ollama_client.py were not cancellation-aware
- RAG did not validate embedding dimensions; index rebuild was not automatic
- No dimension metadata stored; index could not detect model changes
- No trace_id propagation to embeddings for correlation

## Solution Overview

### Commit 1: Embedding Provider Enhancements

**File: `src/jarvis/provider/ollama_client.py`**

Changes:
- Added optional `trace_id` parameter to `ollama_request()`
- Implemented `_is_cancelled()` check before each retry attempt
- Check cancellation before sleep between retries
- Classify cancelled state as "ClientCancelled" error

Impact:
- Stop/abort now immediately halts embedding requests instead of running full retry loops
- Embedding calls respect cancellation flag set by streaming handler

**File: `src/jarvis/memory.py`**

Changes:
- Added `EmbeddingDimMismatch` exception class with actual/expected/model fields
- Added `_logged_embed_len_traces` set to log embedding length once per trace
- Modified `_encode()` to accept:
  - `expected_dim`: validate returned vector length; raise `EmbeddingDimMismatch` if mismatch
  - `trace_id`: pass to provider for cancellation-aware retries
- Log actual embedding length and model once per trace_id:
  ```
  logger.info("embedding_len=%s model=%s trace_id=%s", int(arr.size), model, tid)
  ```
- Catch `EmbeddingDimMismatch` separately (not best_effort) to let caller decide fallback

Impact:
- No more infinite retry loops on dimension mismatch
- Single log per trace for embedding telemetry
- Clear signal when dimensions change (typed exception)

### Commit 2: FAISS Index Metadata & Rebuild

**File: `src/jarvis/code_rag/index.py`**

Changes:
- Modified `_save_manifest()` to store:
  - `embedding_model`: current model from `_current_embed_model()`
  - `embedding_dim`: current vector dimension
- Modified `ensure_index()` to detect:
  - Model changes: `manifest_model != current_model` → rebuild
  - Dimension mismatches: compare manifest_dim, index.d, and current_dim → rebuild
  - Log detailed mismatch info including which field changed

Impact:
- FAISS indexes are now versioned by model+dim (directory already scoped this way)
- Automatic rebuild when embedding model changes (e.g., from nomic to another provider)
- No more "dim mismatch" spam; one rebuild then clean index

**File: `src/jarvis/code_rag/search.py`**

Changes:
- Updated `search_code()` signature to accept optional `trace_id`
- Catch `EmbeddingDimMismatch` separately:
  ```python
  except EmbeddingDimMismatch as exc:
      logger.error(f"embedding dimension mismatch ... skipping RAG and using fallback")
      return _search_fallback(query, target)
  ```
- Pass `trace_id` to `_encode()` for cancellation-aware embeddings

Impact:
- Clean fallback to substring search on dimension mismatch (no repeated errors)
- RAG respects cancellation and doesn't retry on Stop

### Commit 3: Cancellation Propagation Through RAG Pipeline

**File: `src/jarvis/agent_core/rag_async.py`**

Changes:
- Added optional `trace_id` parameter to `retrieve_code_rag_async()`
- Pass `trace_id` to `search_code()` call in background thread

**File: `src/jarvis/agent_core/orchestrator.py`**

Changes:
- Updated call to `retrieve_code_rag_async()` to pass `trace_id`:
  ```python
  retrieve_code_rag_async(prompt, rag_hash, trace_id=trace_id)
  ```

**File: `src/jarvis/agent_skills/code_skill.py`**

Changes:
- Updated `handle_code_question()` to pass `trace_id` to:
  - `search_code()` (line 190)
  - `search_code()` (line 284)
- Corrected indentation bug in exception handling (was under `else:` instead of at level of try)

Impact:
- trace_id flows through: orchestrator → RAG async → search → _encode → ollama_request
- All embedding calls are cancellation-aware; Stop is fast

---

## Files Modified

1. `src/jarvis/provider/ollama_client.py` — Cancellation-aware provider client
2. `src/jarvis/memory.py` — Embedding dimension validation and logging
3. `src/jarvis/code_rag/index.py` — FAISS metadata storage and rebuild logic
4. `src/jarvis/code_rag/search.py` — Graceful fallback on dimension mismatch
5. `src/jarvis/agent_core/rag_async.py` — trace_id propagation
6. `src/jarvis/agent_core/orchestrator.py` — trace_id propagation
7. `src/jarvis/agent_skills/code_skill.py` — trace_id propagation and indent fix

---

## Deployment Notes

### Backwards Compatibility

- `ollama_request(..., trace_id=None)` is optional; existing callers work unchanged
- `_encode(..., expected_dim=None, trace_id=None)` are optional kwargs; existing callers work
- `search_code(..., trace_id=None)` is optional; existing callers work
- `retrieve_code_rag_async(..., trace_id=None)` is optional; existing callers work

### Migration

- Existing FAISS indexes will be detected as having no `embedding_model` field
- On next load, `ensure_index()` detects mismatch and rebuilds silently
- No manual action needed; rebuild is automatic and non-disruptive

### Testing Recommendations

See [VERIFICATION.md](./VERIFICATION.md) for comprehensive test procedures covering:
1. Embedding vector length logging
2. FAISS metadata validation
3. Stop/cancellation breaks embedding retries
4. EmbeddingDimMismatch prevents infinite loops
5. RAG gracefully skips on mismatch
6. Full streaming stop integration test

---

## Expected Outcomes

After deployment:

| Before | After |
|--------|-------|
| Stop button → still embedding for 30+ seconds | Stop button → cleanup in <1 second |
| "dim mismatch" repeated 10+ times in logs | "dim mismatch" triggers one rebuild, then clean |
| "ollama_request failed" looping on Ollama 500 | Cancelled on Stop; no retry loop |
| FAISS index unaware of model changes | Automatic rebuild on model change |
| No embedding telemetry | Single log per trace: `embedding_len=384 model=X trace_id=Y` |

---

## Rollback Plan

If issues arise:
1. Revert commits in reverse order (3, 2, 1)
2. Existing code falls back to hash embeddings automatically if Ollama fails
3. FAISS index rebuilt on next access (automatic via existing rebuild logic)
4. No data loss; cache cleared on rollback

