import os
import pytest
import sqlite3
import unittest.mock as mock
from fastapi.testclient import TestClient

# Sørg for at appen bruger test-data (valgfrit, men rart)
os.environ.setdefault("API_BEARER_TOKEN", "devkey")
os.environ.setdefault("JARVIS_TEST_MODE", "1")
os.environ.setdefault("JARVIS_DB_PATH", "/tmp/jarvis_test.db")
os.environ.setdefault("JARVIS_LOG_DIR", "/tmp/jarvis_logs")
os.environ.setdefault("DISABLE_EMBEDDINGS", "1")
os.environ.setdefault("TTS", "false")

# Import app efter env
from jarvis.auth import register_user, login_user, get_user_by_token
from jarvis.session_store import create_session, list_sessions
from jarvis.agent import run_agent, should_use_wiki
from jarvis.index_excludes import should_exclude

@pytest.fixture(autouse=True)
def _mock_llm(monkeypatch):
    """
    IMPORTANT:
    Smoke tests må ikke lave rigtige LLM/Ollama-kald (det tager minutter og kan fejle).
    Vi monkeypatcher call_ollama() til at returnere et deterministisk svar med det samme.
    """
    import jarvis.agent as agent_mod

    def fake_call_ollama(messages, model_profile=None):
        # Returnér samme struktur som din agent forventer (her antager vi res er en tekst)
        # return "OK (mock)"
        return {"choices": [{"message": {"content": "OK (mock)"}}]}

    monkeypatch.setattr(agent_mod, "call_ollama", fake_call_ollama)

def test_register_login_sessions_and_chat():
    # Register
    try:
        register_user(
            "alice",
            "secret",
            email="alice@example.com",
            full_name="Alice Test",
        )
    except sqlite3.IntegrityError:
        pass

    # Login (token)
    login = login_user("alice", "secret")
    assert login and login.get("token")
    token = login["token"]
    user = get_user_by_token(token)
    assert user and user.get("id")

    # Create session
    session_id = create_session(user["id"], name="Min session")
    assert session_id

    # List sessions
    sessions = list_sessions(user["id"])
    assert sessions

    # Chat (non-stream) — må ikke trigge tools og må ikke lave netkald
    res = run_agent("alice", "Sig hej kort.", session_id=session_id)
    assert res["text"]
    assert "OK (mock)" in res["text"]


def test_time_query_da():
    """Test Danish time query with mocked deterministic time."""
    with mock.patch('jarvis.tools.time_now', return_value='2023-10-01T14:30:00+00:00'):
        res = run_agent("alice", "hvad er klokken", session_id="test_session")
        assert "Klokken er 14:30" in res["text"]


def test_time_query_en():
    """Test English time query with mocked deterministic time."""
    with mock.patch('jarvis.tools.time_now', return_value='2023-10-01T14:30:00+00:00'):
        res = run_agent("alice", "what time is it", session_id="test_session")
        assert "The time is 14:30" in res["text"]


def test_date_query_da():
    """Test Danish date query with mocked deterministic time."""
    with mock.patch('jarvis.tools.time_now', return_value='2023-10-01T14:30:00+00:00'):
        res = run_agent("alice", "hvad er datoen", session_id="test_session")
        assert "I dag er det 01.10.2023" in res["text"]


def test_date_query_en():
    """Test English date query with mocked deterministic time."""
    with mock.patch('jarvis.tools.time_now', return_value='2023-10-01T14:30:00+00:00'):
        res = run_agent("alice", "what is the date", session_id="test_session")
        assert "Today is 01.10.2023" in res["text"]


def test_index_excludes():
    """Test repo scanning exclude list."""
    assert should_exclude(".venv")
    assert should_exclude("__pycache__")
    assert should_exclude(".pytest_cache")
    assert should_exclude("src/data")
    assert should_exclude("tts_cache")
    assert should_exclude("ui/static")
    assert should_exclude("large.bin")
    assert should_exclude("file.zip")
    assert not should_exclude("src/jarvis/agent.py")
    assert not should_exclude("README.md")


def test_should_use_wiki():
    """Test wiki heuristic for various prompts."""
    # True cases: encyclopedic/factual
    assert should_use_wiki("What is Python?")
    assert should_use_wiki("Who is Einstein?")
    assert should_use_wiki("How does photosynthesis work?")
    assert should_use_wiki("Explain quantum physics")
    assert should_use_wiki("Hvad er fotosyntese?")
    assert should_use_wiki("Hvem er Einstein?")
    assert should_use_wiki("Hvordan virker kvantefysik?")
    assert should_use_wiki("Forklar evolution")

    # False cases: code questions
    assert not should_use_wiki("How to code a function?")
    assert not should_use_wiki("What is a bug in my code?")
    assert not should_use_wiki("Explain this traceback")

    # False cases: tool commands
    assert not should_use_wiki("Search for Python tutorials")
    assert not should_use_wiki("Find files")
    assert not should_use_wiki("Ping google.com")

    # False cases: freshness/news
    assert not should_use_wiki("What time is it?")
    assert not should_use_wiki("Hvad er klokken?")
    assert not should_use_wiki("Latest news")
    assert not should_use_wiki("Weather forecast")

    # Default False
    assert not should_use_wiki("Hello world")


def test_admin_endpoints_require_auth():
    """Test that admin endpoints require proper auth."""
    from jarvis import server
    client = TestClient(server.app)
    
    # Public endpoint should work without auth
    resp = client.get("/status")
    assert resp.status_code == 200
    
    # Admin endpoint without auth should fail
    resp = client.get("/admin/users")
    assert resp.status_code == 401
    data = resp.json()
    assert data["detail"]["ok"] is False
    assert data["detail"]["error"]["type"] == "AuthRequired"
    
    # Admin endpoint with Bearer devkey should work
    resp = client.get("/admin/users", headers={"Authorization": "Bearer devkey"})
    assert resp.status_code == 200
    assert "users" in resp.json()
    
    # Admin endpoint with invalid Bearer should fail
    resp = client.get("/admin/users", headers={"Authorization": "Bearer invalid"})
    assert resp.status_code == 401


def test_user_endpoints_work_with_cookie():
    """Test that user endpoints work with cookie auth."""
    from jarvis import server
    client = TestClient(server.app)
    
    # Register and login to get token
    try:
        register_user("bob", "secret", email="bob@example.com")
    except sqlite3.IntegrityError:
        pass
    
    login = login_user("bob", "secret")
    token = login["token"]
    
    # User endpoint with cookie should work
    resp = client.get("/sessions", cookies={"jarvis_token": token})
    assert resp.status_code == 200
    assert "sessions" in resp.json()
    
    # Without cookie should fail
    resp = client.get("/sessions")
    assert resp.status_code == 401
