import os

from jarvis import memory


def test_embedding_failure_returns_gracefully(monkeypatch, tmp_path):
    # isolate stores
    monkeypatch.setattr(memory, "_stores", {})
    monkeypatch.setattr(memory, "DATA_DIR", tmp_path)
    monkeypatch.setenv("EMBEDDINGS_BACKEND", "ollama")
    monkeypatch.setenv("DISABLE_EMBEDDINGS", "0")

    def fake_request(url, payload, **kwargs):
        return {"ok": False, "error": {"type": "ProviderTimeout", "message": "timeout", "trace_id": "abc123"}}

    monkeypatch.setattr(memory, "ollama_request", fake_request)

    # Should not raise; add_memory swallows embedding errors
    memory.add_memory("assistant", "Dette er en test for embedding fejl", user_id="embed-test")
    store = memory._get_store("embed-test")
    # nothing should be added
    assert store.index.ntotal == 0
