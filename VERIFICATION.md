# Verification Guide for Production Bug Fixes

## Summary of Changes

### Commit 1: Embedding dimension truth + validation
- Added `EmbeddingDimMismatch` exception in `src/jarvis/memory.py`
- Added logging of actual embedding vector length once per trace_id
- Modified `_encode()` to accept `expected_dim` and `trace_id` parameters
- Implemented cancellation awareness in `src/jarvis/provider/ollama_client.py`

### Commit 2: FAISS index rebuild / metadata
- Store `embedding_model` in index metadata alongside `embedding_dim`
- Detect model changes automatically in `ensure_index()`
- Rebuild index without spamming errors when dimensions mismatch

### Commit 3: Stop/cancellation propagation
- Pass `trace_id` through embedding calls to `ollama_request()`
- Check `check_stream_cancelled_sync(trace_id)` before each retry attempt and sleep
- Propagate cancellation through RAG pipeline: `retrieve_code_rag_async()` and `search_code()`

---

## Verification Commands

### Test 1: Embedding Vector Length Logging

Start the backend server and check that embedding calls log the actual vector length:

```bash
# Terminal 1: Backend
cd /home/bs/vscode/jarvis-agent
source .venv/bin/activate
python3 src/jarvis/server.py
```

In another terminal, make a direct embedding request:

```bash
# Terminal 2: Curl embedding endpoint
curl -X POST http://127.0.0.1:11434/api/embeddings \
  -H "Content-Type: application/json" \
  -d '{"model": "nomic-embed-text:latest", "prompt": "test embedding"}' | jq '.embedding | length'
```

**Expected output**: An integer (e.g., `384` or `768`).

Then verify the backend logs show the embedding length:

```bash
# Terminal 2 (continued): Check backend logs
tail -20 /home/bs/vscode/jarvis-agent/data/logs/jarvis.log | grep embedding_len
```

**Expected log line**: `embedding_len=384 model=nomic-embed-text:latest trace_id=xxxxxxxx`

---

### Test 2: FAISS Metadata and Index Rebuild

Check that the FAISS index metadata is stored and respected:

```bash
# Terminal 2: Check manifest contains model and dim
find /home/bs/vscode/jarvis-agent/src/data/code_index -name "manifest.json" -type f | head -1 | xargs cat | jq '.embedding_dim, .embedding_model'
```

**Expected output**:
```json
768
"nomic-embed-text:latest"
```

If you change the embedding model or dimension, the index should rebuild automatically without spamming errors. Test by modifying an environment variable:

```bash
# Terminal 2: Simulate model change
export OLLAMA_EMBED_MODEL="another-model:latest"
# The next RAG search should trigger a rebuild silently
```

---

### Test 3: Stop/Cancellation Breaks Embedding Retries

Start a chat with streaming, then click **Stop** immediately before the response completes:

```bash
# Terminal 1: Ensure backend is running with debugging
export JARVIS_DEBUG=1
cd /home/bs/vscode/jarvis-agent
python3 src/jarvis/server.py 2>&1 | tee /tmp/backend.log &
BACKEND_PID=$!
```

In the UI (or via curl), start a streaming chat:

```bash
# Terminal 2: Start a streaming request
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Authorization: Bearer $YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "local",
    "prompt": "tell me about the code in jarvis",
    "stream": true
  }' > /tmp/stream.log &
STREAM_PID=$!
sleep 0.5

# Extract trace_id from logs
TRACE_ID=$(tail -20 /tmp/backend.log | grep "stream_start" | head -1 | grep -o "trace=[^ ]*" | cut -d= -f2)
echo "Stream trace_id: $TRACE_ID"

# Now kill the curl to simulate Stop
kill $STREAM_PID 2>/dev/null || true
sleep 1

# Check logs for stream_cleanup and NO further embedding calls
echo "=== Cleanup logs ==="
tail -30 /tmp/backend.log | grep -E "(stream_cleanup|ollama_request)" | grep "$TRACE_ID"
```

**Expected output**:
- Line with `stream_cleanup trace=$TRACE_ID`: confirms stream stopped cleanly
- NO `ollama_request` lines for that trace_id AFTER `stream_cleanup`

---

### Test 4: EmbeddingDimMismatch Prevents Infinite Retries

Manually trigger a dimension mismatch and verify the error is caught without looping:

```python
# Terminal 2: Python test
cd /home/bs/vscode/jarvis-agent
python3 << 'EOF'
import sys
sys.path.insert(0, 'src')

from jarvis.memory import _encode, EmbeddingDimMismatch

# Mock a scenario where expected_dim doesn't match actual
try:
    # This should raise EmbeddingDimMismatch if dims don't match
    vec = _encode("test", expected_dim=999, best_effort=False)
except EmbeddingDimMismatch as e:
    print(f"✓ Caught mismatch: {e}")
    print(f"  actual={e.actual}, expected={e.expected}, model={e.model}")
except Exception as e:
    print(f"Other error (OK for fallback mode): {type(e).__name__}: {e}")
EOF
```

**Expected output**:
```
✓ Caught mismatch: EmbeddingDimMismatch(actual=384, expected=999, model=nomic-embed-text:latest)
  actual=384, expected=999, model=nomic-embed-text:latest
```

---

### Test 5: RAG Gracefully Skips on Dimension Mismatch

Query the code RAG index and verify it falls back to substring search if dims mismatch:

```python
# Terminal 2: Test code search with trace_id
cd /home/bs/vscode/jarvis-agent
python3 << 'EOF'
import sys
sys.path.insert(0, 'src')
import uuid

from jarvis.code_rag.search import search_code

trace_id = uuid.uuid4().hex[:8]
print(f"Test with trace_id={trace_id}")

# Normal search (should work)
results = search_code("async def", trace_id=trace_id)
print(f"✓ Found {len(results)} results")
for r in results[:2]:
    print(f"  - {r.path}:{r.start_line}")
EOF
```

**Expected output**: Search completes without error, returning substring matches.

---

### Test 6: Comprehensive Streaming Stop Test

Use this comprehensive script to test the full Stop flow:

```bash
cat > /tmp/test_stop.sh << 'BASHEOF'
#!/bin/bash
set -e

cd /home/bs/vscode/jarvis-agent
source .venv/bin/activate

echo "=== Test 6: Comprehensive Streaming Stop ==="

# Start fresh backend with clean logs
rm -f /tmp/backend_test.log
python3 src/jarvis/server.py > /tmp/backend_test.log 2>&1 &
BACKEND_PID=$!
sleep 2

# Get a token (if needed)
TOKEN="${JARVIS_TEST_TOKEN:-test-token}"

# Start a streaming chat
echo "Starting streaming chat..."
REQUEST_ID=$(uuidgen)
curl -X POST http://localhost:8080/v1/chat/completions \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "local",
    "prompt": "explain the code architecture",
    "stream": true
  }' > /tmp/stream_output.log 2>&1 &
CURL_PID=$!

# Wait a moment then kill it
sleep 1
kill $CURL_PID 2>/dev/null || true
wait $CURL_PID 2>/dev/null || true

# Check logs
echo ""
echo "=== Backend Log Analysis ==="
echo "Stream starts:"
grep "stream_start" /tmp/backend_test.log | tail -1

echo "Stream cleanup:"
grep "stream_cleanup" /tmp/backend_test.log | tail -1

echo "Final embeddings check (should be empty if no further calls):"
TRACE_ID=$(grep "stream_start" /tmp/backend_test.log | tail -1 | grep -o "trace=[^ ]*" | cut -d= -f2 | head -1)
if [ -n "$TRACE_ID" ]; then
  echo "Last trace_id: $TRACE_ID"
  CLEANUP_TIME=$(grep "stream_cleanup" /tmp/backend_test.log | tail -1 | awk '{print $1}')
  echo "Embeddings after cleanup for $TRACE_ID:"
  awk -v trace="$TRACE_ID" -v cleanup_time="$CLEANUP_TIME" \
    '$0 ~ trace && $0 ~ /ollama_request/ { if ($1 > cleanup_time) print }' \
    /tmp/backend_test.log | wc -l | xargs echo "Count (should be 0):"
fi

# Cleanup
kill $BACKEND_PID 2>/dev/null || true

echo ""
echo "✓ Test complete"
BASHEOF
chmod +x /tmp/test_stop.sh
/tmp/test_stop.sh
```

---

## Log Keys to Monitor

When running in production, watch for these log entries:

| Log Entry | Meaning |
|-----------|---------|
| `embedding_len=384 model=nomic-embed-text:latest trace_id=abc123` | Successful embedding with length logged once |
| `EmbeddingDimMismatch(actual=384, expected=768, ...)` | Dimension mismatch detected; RAG will skip |
| `stream_disconnected trace=abc123` | Client disconnected |
| `stream_cleanup trace=abc123` | Streaming generator cleaned up; no further work for this trace |
| `ollama_request cancelled` | Request was cancelled before being sent |
| `embedding dimension mismatch; skipping RAG and using fallback` | Search fell back to substring search |
| `Rebuilding code index ... model_mismatch=True` | Index rebuilt due to model change |

---

## Expected Behavior After Fix

1. **No infinite embedding retries**: When user clicks Stop, embeddings cease immediately.
2. **Single embedding log per trace**: Each trace_id logs embedding length exactly once.
3. **Automatic FAISS rebuild**: Model/dimension changes trigger silent index rebuild.
4. **No dimension mismatch spam**: Fallback to substring search without repeating error logs.
5. **Clean SSE termination**: Client always receives `[DONE]` when stream stops.

