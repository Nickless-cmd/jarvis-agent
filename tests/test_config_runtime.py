import os

def test_runtime_test_mode(monkeypatch):
    import jarvis.server as server
    from jarvis import config

    # Change env after imports
    monkeypatch.setenv("JARVIS_TEST_MODE", "1")
    # Reload config should reflect env change
    assert config.is_test_mode() is True
    # Server helper should also pick up the change
    assert server.is_test_mode() is True

    # Flip back to ensure runtime read works both ways
    monkeypatch.setenv("JARVIS_TEST_MODE", "0")
    assert config.is_test_mode() is False
    assert server.is_test_mode() is False
