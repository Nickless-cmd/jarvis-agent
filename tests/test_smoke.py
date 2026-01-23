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
    client.cookies.set("jarvis_token", token)
    resp = client.get("/sessions")
    assert resp.status_code == 200
    assert "sessions" in resp.json()
    
    # Without cookie should fail
    client.cookies.clear()
    resp = client.get("/sessions")
    assert resp.status_code == 401


def test_events_endpoint():
    """Test /v1/events endpoint returns EventBus events."""
    from jarvis import server
    from jarvis.events import publish, subscribe_all
    from jarvis.event_store import get_event_store
    
    client = TestClient(server.app)
    
    # Clear event store and manually subscribe (in case lifespan doesn't run in TestClient)
    event_store = get_event_store()
    event_store.clear()
    unsubscribe = subscribe_all(lambda event_type, payload: event_store.append(event_type, payload))
    
    # Register and login to get token
    try:
        register_user("charlie", "secret", email="charlie@example.com")
    except sqlite3.IntegrityError:
        pass
    
    login = login_user("charlie", "secret")
    token = login["token"]
    
    # Set cookie for auth
    client.cookies.set("jarvis_token", token)
    
    # First request should return empty
    resp = client.get("/v1/events")
    assert resp.status_code == 200
    data = resp.json()
    assert "events" in data
    assert "last_id" in data
    initial_last_id = data["last_id"]
    
    # Publish a test event
    publish("test.event", {"message": "hello world"})
    
    # Get events again
    resp = client.get("/v1/events")
    assert resp.status_code == 200
    
    data = resp.json()
    assert "events" in data
    assert "last_id" in data
    assert len(data["events"]) == 1
    assert data["events"][0]["type"] == "test.event"
    assert data["events"][0]["payload"]["message"] == "hello world"
    
    # Test pagination with after parameter
    last_id = data["last_id"]
    publish("test.event2", {"message": "second event"})
    
    resp = client.get(f"/v1/events?after={last_id}")
    assert resp.status_code == 200
    
    data2 = resp.json()
    assert len(data2["events"]) == 1
    assert data2["events"][0]["type"] == "test.event2"
    
    # Cleanup
    unsubscribe()


def test_chat_events():
    """Test chat lifecycle events are published to EventBus."""
    from jarvis import server
    from jarvis.events import publish, subscribe
    from jarvis.event_store import get_event_store
    
    client = TestClient(server.app)
    
    # Register and login to get token
    try:
        register_user("charlie", "secret", email="charlie@example.com")
    except sqlite3.IntegrityError:
        pass
    
    login = login_user("charlie", "secret")
    token = login["token"]
    
    # Set cookie for auth
    client.cookies.set("jarvis_token", token)
    
    # Clear event store and manually subscribe
    event_store = get_event_store()
    event_store.clear()
    unsubscribe = subscribe("*", lambda event_type, payload: event_store.append(event_type, payload))
    
    # Test the subscription
    publish("test.event", {"test": "data"})
    assert len(event_store.get_events()["events"]) == 1
    
    # Make a chat request
    resp = client.post("/v1/chat/completions", json={
        "messages": [{"role": "user", "content": "Hello, how are you?"}],
        "model": "test",
        "stream": False
    })
    assert resp.status_code == 200
    
    # Check events
    resp = client.get("/v1/events")
    assert resp.status_code == 200
    
    data = resp.json()
    events = data["events"]
    
    # Should have test.event, chat.user_message and chat.assistant_message
    event_types = [e["type"] for e in events]
    assert "test.event" in event_types
    assert "chat.user_message" in event_types
    assert "chat.assistant_message" in event_types
    
    user_event = next(e for e in events if e["type"] == "chat.user_message")
    assert "session_id" in user_event["payload"]
    assert "message_id" in user_event["payload"]
    assert user_event["payload"]["text_preview"] == "Hello, how are you?"
    
    assistant_event = next(e for e in events if e["type"] == "chat.assistant_message")
    assert assistant_event["payload"]["ok"] is True
    assert "text_preview" in assistant_event["payload"]
    assert "duration_ms" in assistant_event["payload"]
    
    # Cleanup
    unsubscribe()
    
    user_event = next(e for e in events if e["type"] == "chat.user_message")
    assert "session_id" in user_event["payload"]
    assert "message_id" in user_event["payload"]
    assert user_event["payload"]["text_preview"] == "Hello, how are you?"
    
    assistant_event = next(e for e in events if e["type"] == "chat.assistant_message")
    assert assistant_event["payload"]["ok"] is True
    assert "text_preview" in assistant_event["payload"]
    assert "duration_ms" in assistant_event["payload"]
    
    # Cleanup
    unsubscribe()


@pytest.mark.skip(reason="SSE streaming test hangs - needs investigation")
def test_events_stream():
    """Test SSE streaming endpoint accessibility and headers."""
    pass


def test_events_stream_filtering():
    """Test SSE streaming endpoint with filtering parameters."""
    from jarvis import server
    from jarvis.events import publish
    from jarvis.event_store import get_event_store
    
    client = TestClient(server.app)
    
    # Register and login to get token
    try:
        register_user("echo", "secret", email="echo@example.com")
    except sqlite3.IntegrityError:
        pass
    
    login = login_user("echo", "secret")
    token = login["token"]
    
    # Set cookie for auth
    client.cookies.set("jarvis_token", token)
    
    # Clear event store
    event_store = get_event_store()
    event_store.clear()
    
    # Test that filtering parameters are accepted
    resp = client.get("/v1/events/stream?since_id=0&topics=agent.start,agent.done&session_id=test")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "text/event-stream; charset=utf-8"
