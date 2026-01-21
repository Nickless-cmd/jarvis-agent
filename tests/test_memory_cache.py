import numpy as np

import jarvis.memory as mem


def test_memory_search_uses_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("DISABLE_EMBEDDINGS", "1")
    mem.DATA_DIR = tmp_path / "memory"
    mem._stores.clear()
    mem._search_cache.clear()

    call_count = {"n": 0}

    def fake_encode(text):
        call_count["n"] += 1
        return np.ones(mem.DIM, dtype=np.float32)

    monkeypatch.setattr(mem, "_encode", fake_encode)

    mem.add_memory("user", "This is a memory entry that is long enough.", user_id="u1")
    call_count["n"] = 0

    res1 = mem.search_memory("memory entry", user_id="u1")
    assert res1
    assert call_count["n"] == 1  # first search encoded

    res2 = mem.search_memory("memory entry", user_id="u1")
    assert res2 == res1
    assert call_count["n"] == 1  # cached result, no extra encode

    mem._search_cache.clear()
    mem.search_memory("memory entry", user_id="u1")
    assert call_count["n"] == 2  # cache cleared triggers encode again
