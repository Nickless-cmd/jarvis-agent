# Verification Guide: Embedding Dimension Fix & Stop Robustness

## Overview
This guide verifies the two critical production bug fixes:
1. **Embedding dimension auto-detection** (768 instead of 384 hardcode)
2. **Stop button robustness** (streaming cancellation in <1s)

---

## Part 1: Health Endpoint Verification

### Check Current Embedding Configuration
```bash
curl -s http://localhost:8000/health/embeddings | jq .
```

**Expected output (example):**
```json
{
  "embedding_model": "nomic-embed-text:latest",
  "embedding_dim_probed": 768,
  "embedding_dim_current": 768,
  "faiss_index_dim": 768,
  "ok": true
}
```

**Key assertions:**
- ✅ `embedding_dim_probed` should be **768** (from Ollama probe)
- ✅ `embedding_dim_current` should be **768** (cached from first embedding)
- ✅ `faiss_index_dim` should be **768** (FAISS built with correct dimension)
- ✅ `ok` should be **true**

**What to debug if failing:**
- If `embedding_dim_current` is 384: get_embedding_dim() cache not working; check `_EMBEDDING_DIM_RUNTIME` in memory.py
- If `faiss_index_dim` is 384: _current_embed_dim() not using get_embedding_dim(); check code_rag/index.py import
- If `ok` is false: Ollama endpoint unreachable; check Ollama service is running

---

## Part 2: Embedding Dimension Mismatch Logs

### Start the Jarvis Backend
```bash
cd /home/bs/vscode/jarvis-agent
python src/jarvis/server.py  # or your normal startup command
```

### Monitor Logs for Dimension Issues
In another terminal, watch the logs:
```bash
tail -f data/logs/jarvis.log | grep -i "dim\|embedding"
```

### Send a Chat Message to Trigger Embeddings
```bash
# Terminal 3: Send a streaming chat request
curl -s -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "deepseek-coder",
    "messages": [{"role": "user", "content": "What is Python?"}],
    "stream": true
  }' | head -20
```

**Expected log output (NO dimension warnings):**
```
[INFO] Embedding 10 code chunks for RAG
[DEBUG] Embedding model: nomic-embed-text:latest, response_dim: 768
[DEBUG] Successfully embedded chunks, dimension: 768
[SUCCESS] RAG search completed
```

**What to debug if failing:**
- **❌ SEE: "dim mismatch (vec=384, expected=768)"**: FAISS built with 384 but embeddings are 768
  - Solution: Rebuild FAISS index; delete `data/faiss_*` directory and restart
  - Check that _current_embed_dim() is calling get_embedding_dim()
  
- **❌ SEE: "EmbeddingDimMismatch"**: Dimension changed mid-session
  - This should not happen with caching; check that _EMBEDDING_DIM_RUNTIME is persisted
  - Restart backend to ensure fresh cache

---

## Part 3: Stop Robustness Test

### Verify /v1/chat/stop Endpoint Exists
```bash
curl -s -X OPTIONS http://localhost:8000/v1/chat/stop -v 2>&1 | grep -i "allow\|method"
```

**Expected:** POST method is available

### Test Stop During Streaming

**Terminal 1: Start backend with verbose logging**
```bash
cd /home/bs/vscode/jarvis-agent
LOGLEVEL=DEBUG python src/jarvis/server.py 2>&1 | tee backend.log
```

**Terminal 2: Start a streaming request and get its trace_id**
```bash
curl -s -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "deepseek-coder",
    "messages": [{"role": "user", "content": "Write a long Python function that takes 30 seconds to generate"}],
    "stream": true
  }' > /tmp/stream_response.txt &

# Wait 2 seconds for the trace_id to appear in the streaming response
sleep 2

# Extract trace_id from the response (look for first SSE event)
TRACE_ID=$(head -5 /tmp/stream_response.txt | grep -oP '"trace_id":\s*"\K[^"]+' | head -1)
echo "Trace ID: $TRACE_ID"
```

**Terminal 3: Send Stop Request**
```bash
# Wait ~3 seconds from start, then send stop
sleep 3

TRACE_ID="<from above>"

# Call the stop endpoint
curl -s -X POST http://localhost:8000/v1/chat/stop \
  -H "Content-Type: application/json" \
  -d "{\"trace_id\": \"$TRACE_ID\"}" | jq .

# Expected output: { "ok": true, "trace_id": "..." }
```

**Verify in Terminal 1 logs:**
```bash
grep "stream_cleanup\|is_disconnected\|set_stream_cancelled" backend.log | tail -10
```

**Expected behavior:**
- ✅ Stop request returns `{"ok": true}` immediately (<100ms)
- ✅ Backend logs show `stream_cleanup` within **<1 second**
- ✅ No further `/api/embeddings` calls after Stop
- ✅ Response stream stops outputting new data within 1s
- ✅ **No "kill -9" required** to stop the streaming

**What to debug if failing:**
- **Takes 30+ seconds to stop:** set_stream_cancelled() not being called; check /v1/chat/stop endpoint is wired to set_stream_cancelled()
- **Still making embedding calls:** ollama_request() not checking cancellation flag; verify check_stream_cancelled_sync() is called before each retry
- **trace_id not found:** SSE headers may not include trace_id; check streaming generator is sending it in event comments

---

## Part 4: Full Integration Test

### Scenario: Multiple embeddings during RAG search + Stop

**Terminal 1: Backend**
```bash
cd /home/bs/vscode/jarvis-agent
python src/jarvis/server.py 2>&1 | tee full_test.log
```

**Terminal 2: Start streaming request**
```bash
curl -s -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "deepseek-coder",
    "messages": [{"role": "user", "content": "Show me a list of 100 Python best practices"}],
    "stream": true,
    "max_tokens": 1000
  }' > /tmp/full_stream.txt 2>&1 &

# Extract trace_id
sleep 2
TRACE_ID=$(head -10 /tmp/full_stream.txt | grep -oP '"trace_id":\s*"\K[^"]+' | head -1)
echo "Trace ID: $TRACE_ID"
```

**Terminal 3: Stop after 5 seconds**
```bash
sleep 5
TRACE_ID="<from above>"
curl -X POST http://localhost:8000/v1/chat/stop \
  -H "Content-Type: application/json" \
  -d "{\"trace_id\": \"$TRACE_ID\"}"
```

**Verify in backend logs:**
```bash
# Check no dimension mismatches
grep -i "mismatch\|vec=384\|expected=768" full_test.log
# Should return NOTHING (empty)

# Check stop was called
grep "stream_cleanup\|_stream_cancellations\|cancelled=True" full_test.log | head -5

# Check timing
echo "First embedding call:"
grep "Embedding.*code chunks" full_test.log | head -1 | cut -d' ' -f1
echo "Stream cleanup:"
grep "stream_cleanup" full_test.log | head -1 | cut -d' ' -f1
```

**Expected:**
- ✅ No "dim mismatch" or "384" references in logs
- ✅ `stream_cleanup` appears within 1 second of Stop request
- ✅ Response file stops growing shortly after Stop

---

## Part 5: Regression Testing

### Verify No Breaking Changes

**Test 1: Normal completion without Stop**
```bash
curl -s -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "deepseek-coder",
    "messages": [{"role": "user", "content": "What is a Python list?"}],
    "stream": false
  }' | jq '.choices[0].message.content' | head -c 100
```
**Expected:** Full response completes without hang

**Test 2: Embeddings still work**
```bash
curl -s http://localhost:8000/health/embeddings | jq '.ok'
```
**Expected:** `true`

**Test 3: FAISS search still returns results**
```bash
curl -s -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "deepseek-coder",
    "messages": [{"role": "user", "content": "How do I read a file in Python?"}],
    "stream": false
  }' | jq '.choices[0].message'
```
**Expected:** Response includes code examples from RAG search

---

## Summary Checklist

- [ ] `embedding_dim_current` = 768 (not 384)
- [ ] `faiss_index_dim` = 768
- [ ] No "dim mismatch" logs during chat
- [ ] `/v1/chat/stop` endpoint responds in <100ms
- [ ] Stream stops within <1s of Stop request
- [ ] No "kill -9" required to stop streaming
- [ ] Normal completions still work
- [ ] FAISS search still returns results
- [ ] No regressions in other endpoints

---

## If Tests Fail

### Dimension Still 384
```bash
# Check if FAISS index exists with old dimension
find data -type d -name "dim_384"
# If found, delete it:
rm -rf data/faiss_*/dim_384

# Restart backend; it will rebuild with correct 768 dimension
```

### Stop Takes Too Long
```bash
# Check that ollama_request is using trace_id
grep -n "check_stream_cancelled_sync" src/jarvis/server.py

# Check that cancellation checks are in embedding retry loop
grep -n "check_stream_cancelled_sync\|trace_id" src/jarvis/server.py | grep -A2 "ollama_request"
```

### Dimension Keeps Changing
```bash
# Check _EMBEDDING_DIM_RUNTIME is not being reset
grep -n "_EMBEDDING_DIM_RUNTIME" src/jarvis/memory.py

# Ensure it's only reset at startup (global scope)
```

---

## Commands for Quick Testing (Copy-Paste)

```bash
# 1. Check health
curl -s http://localhost:8000/health/embeddings | jq .

# 2. Test normal chat (non-streaming)
curl -s -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"deepseek-coder","messages":[{"role":"user","content":"Hello"}]}' \
  | jq '.choices[0].message.content'

# 3. Start streaming in background
curl -s -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"deepseek-coder","messages":[{"role":"user","content":"Write 50 lines of Python"}],"stream":true}' \
  > /tmp/stream.txt 2>&1 &

# 4. Wait for trace_id
sleep 2 && TRACE_ID=$(head -10 /tmp/stream.txt | grep -oP '"trace_id":\s*"\K[^"]+' | head -1) && echo "Trace: $TRACE_ID"

# 5. Stop streaming
curl -X POST http://localhost:8000/v1/chat/stop \
  -H "Content-Type: application/json" \
  -d "{\"trace_id\": \"$TRACE_ID\"}" | jq .

# 6. Check no dimension errors
grep -i "mismatch\|384" /path/to/logs
```

Done! All modifications are syntax-correct and ready for testing.
