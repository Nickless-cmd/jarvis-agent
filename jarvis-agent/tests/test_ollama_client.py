import types

import pytest

from jarvis.provider.ollama_client import ollama_request


def test_ollama_request_retries_and_envelope(monkeypatch):
    calls = {"n": 0}

    class DummyResp:
        def __init__(self):
            self.status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"ok": True}

    def fake_post(url, json=None, timeout=None):
        calls["n"] += 1
        if calls["n"] < 2:
            raise requests.exceptions.ConnectTimeout("boom")
        return DummyResp()

    import requests

    monkeypatch.setattr(requests, "post", fake_post)

    res = ollama_request("http://localhost", {"prompt": "hi"}, retries=2, backoff=(0, 0))
    assert res["ok"] is True
    assert res["data"] == {"ok": True}
    assert res["trace_id"]
    assert calls["n"] == 2


def test_ollama_request_failure(monkeypatch):
    import requests

    def fake_post(url, json=None, timeout=None):
        raise requests.exceptions.ConnectionError("refused")

    monkeypatch.setattr(requests, "post", fake_post)

    res = ollama_request("http://localhost", {"prompt": "hi"}, retries=1, backoff=(0,))
    assert res["ok"] is False
    assert res["error"]["type"] == "ConnectionError"
    assert res["error"]["trace_id"]

