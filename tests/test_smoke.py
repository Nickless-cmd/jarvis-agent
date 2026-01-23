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
    from jarvis.events import publish
    from jarvis.event_store import get_event_store
    
    client = TestClient(server.app)
    
    # Clear event store
    event_store = get_event_store()
    event_store.clear()
    
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
    pass


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
    
    # Clear event store
    event_store = get_event_store()
    event_store.clear()
    
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
    pass


def test_chat_token_batching():
    """Test chat token batching reduces event spam and preserves ordering."""
    from jarvis.events import publish
    import time
    
    # Collect events directly
    collected_events = []
    
    def collect_event(event_type, payload):
        collected_events.append((event_type, payload))
    
    # Subscribe to chat.token events
    from jarvis.events import subscribe
    unsubscribe = subscribe("chat.token", collect_event)
    
    request_id = "test-request-123"
    session_id = "test-session-456"
    
    # Publish many small chat.token events
    original_tokens = []
    for i in range(20):
        token = f"token{i:02d} "
        original_tokens.append(token)
        publish("chat.token", {
            "request_id": request_id,
            "session_id": session_id,
            "token": token,
            "sequence": i,
        })
    
    # Wait for batching timeout
    time.sleep(0.2)
    
    # Publish chat.end to force final flush
    publish("chat.end", {
        "request_id": request_id,
        "session_id": session_id,
    })
    
    # Check collected events
    chat_token_events = [e for e in collected_events if e[0] == "chat.token"]
    
    # Should have fewer events than original tokens (batching worked)
    assert len(chat_token_events) < len(original_tokens), f"Expected fewer than {len(original_tokens)} events, got {len(chat_token_events)}"
    
    # Reconstruct the full text from batched events
    reconstructed_text = ""
    for _, payload in chat_token_events:
        reconstructed_text += payload["token"]
    
    # Should match the original concatenation
    expected_text = "".join(original_tokens)
    assert reconstructed_text == expected_text, f"Reconstructed text doesn't match: expected '{expected_text}', got '{reconstructed_text}'"
    
    # Check that batched events have the batched flag
    for _, payload in chat_token_events:
        assert payload.get("batched") is True
    
    # Cleanup
    unsubscribe()


def test_events_stream():
    """Test SSE streaming endpoint accessibility and headers."""
    from jarvis import server
    from jarvis.events import publish
    from jarvis.event_store import get_event_store
    
    with TestClient(server.app) as client:
        # Register and login to get token
        try:
            register_user("delta", "secret", email="delta@example.com")
        except sqlite3.IntegrityError:
            pass
        
        login = login_user("delta", "secret")
        token = login["token"]
        
        # Set cookie for auth
        client.cookies.set("jarvis_token", token)
        
        # Clear event store and publish test event
        event_store = get_event_store()
        event_store.clear()
        publish("test.event", {"data": "test", "session_id": "sess1"})
        
        # Test that streaming endpoint returns correct headers and terminates
        resp = client.get("/v1/events/stream?since_id=0&max_events=1&max_ms=300")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "text/event-stream; charset=utf-8"
        assert resp.headers["cache-control"] == "no-store"
        assert resp.headers["connection"] == "keep-alive"
        # Read a few chunks to ensure SSE markers are present
        chunks = []
        for i, part in enumerate(resp.iter_text()):
            chunks.append(part)
            if i >= 2:  # Read only first few chunks
                break
        body = "".join(chunks)
        assert "data:" in body or "event:" in body or ": heartbeat" in body


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
    
    # Test that filtering parameters are accepted and stream terminates
    resp = client.get("/v1/events/stream?since_id=0&topics=agent.start,agent.done&session_id=test&max_events=1&max_ms=300")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "text/event-stream; charset=utf-8"


def test_tool_events_endpoint():
    """Test tool events endpoint returns only tool.* events and respects limit."""
    from jarvis import server
    from jarvis.events import publish
    from jarvis.event_store import get_event_store
    
    client = TestClient(server.app)
    
    # Register and login to get token
    try:
        register_user("foxtrot", "secret", email="foxtrot@example.com")
    except sqlite3.IntegrityError:
        pass
    
    login = login_user("foxtrot", "secret")
    token = login["token"]
    
    # Set cookie for auth
    client.cookies.set("jarvis_token", token)
    
    # Clear event store and set up subscription for test
    event_store = get_event_store()
    event_store.clear()
    
    # Manually subscribe event store to events for this test
    
    try:
        # Publish various events including tool events
        publish("agent.start", {"session_id": "sess1"})
        publish("tool.search.start", {"query": "test", "session_id": "sess1"})
        publish("tool.search.end", {"results": [], "session_id": "sess1"})
        publish("agent.done", {"session_id": "sess1"})
        publish("tool.weather.start", {"city": "test", "session_id": "sess1"})
        
        # Test endpoint returns 200 and only tool events
        resp = client.get("/v1/events/tool")
        assert resp.status_code == 200
        data = resp.json()
        assert "events" in data
        assert "count" in data
        assert "limit" in data
        
        # Should only contain tool.* events
        for event in data["events"]:
            assert event["type"].startswith("tool.")
        
        # Should have 3 tool events
        assert data["count"] == 3
        assert len(data["events"]) == 3
        
        # Test limit parameter
        resp = client.get("/v1/events/tool?limit=2")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["events"]) == 2
        assert data["count"] == 2
        assert data["limit"] == 2
        
        # Test limit max (200)
        resp = client.get("/v1/events/tool?limit=200")
        assert resp.status_code == 200
        
        # Test limit min (1) and max validation
        resp = client.get("/v1/events/tool?limit=0")
        assert resp.status_code == 422  # Validation error

        resp = client.get("/v1/events/tool?limit=201")
        assert resp.status_code == 422  # Validation error
    finally:
        pass


def test_events_stream_no_match_returns_fast():
    """Stream with non-matching filter should terminate within deadline and return snapshot."""
    from jarvis import server
    from jarvis.event_store import get_event_store

    client = TestClient(server.app)

    try:
        register_user("hotel", "secret", email="hotel@example.com")
    except sqlite3.IntegrityError:
        pass

    login = login_user("hotel", "secret")
    token = login["token"]
    client.cookies.set("jarvis_token", token)

    event_store = get_event_store()
    event_store.clear()

    resp = client.get("/v1/events/stream?types=no.such.type&max_ms=200&max_events=1")
    assert resp.status_code == 200
    # Snapshot path should at least include heartbeat to keep SSE format valid
    assert resp.text.startswith(": heartbeat")


def test_events_stream_filtering():
    """Test events stream filtering and deterministic termination."""
    from jarvis import server
    from jarvis.events import publish
    from jarvis.event_store import get_event_store
    
    client = TestClient(server.app)
    
    # Register and login to get token
    try:
        register_user("golf", "secret", email="golf@example.com")
    except sqlite3.IntegrityError:
        pass
    
    login = login_user("golf", "secret")
    token = login["token"]
    
    # Set cookie for auth
    client.cookies.set("jarvis_token", token)
    
    # Clear event store and set up subscription for test
    event_store = get_event_store()
    event_store.clear()
    
    # Manually subscribe event store to events for this test
    
    try:
        # Publish various events
        publish("agent.start", {"session_id": "sess1"})
        publish("tool.search.start", {"query": "test", "session_id": "sess1"})
        publish("chat.message", {"text": "hello", "session_id": "sess1"})
        publish("tool.weather.start", {"city": "test", "session_id": "sess1"})
        publish("agent.done", {"session_id": "sess1"})
        
        # Test filtering by types (prefix matching)
        with client.stream("GET", "/v1/events/stream?types=tool.,chat.&max_events=10&max_ms=1000") as resp:
            assert resp.status_code == 200
            # Collect SSE events
            events_received = []
            for line in resp.iter_lines():
                if line.startswith("event: "):
                    event_type = line.split("event: ")[1].strip()
                    events_received.append(event_type)
            
            # Should only contain tool.* and chat.* events
            assert all(et.startswith("tool.") or et.startswith("chat.") for et in events_received)
            # Should have received the matching events
            assert "tool.search.start" in events_received
            assert "chat.message" in events_received
            assert "tool.weather.start" in events_received
            # Should not have received non-matching events
            assert "agent.start" not in events_received
            assert "agent.done" not in events_received
        
        # Test termination by max_events
        with client.stream("GET", "/v1/events/stream?max_events=2&max_ms=5000") as resp:
            assert resp.status_code == 200
            events_received = []
            for line in resp.iter_lines():
                if line.startswith("event: "):
                    event_type = line.split("event: ")[1].strip()
                    events_received.append(event_type)
            # Should terminate after exactly 2 events
            assert len(events_received) == 2
        
        # Test termination by max_ms (should terminate quickly even with no new events)
        import time
        start_time = time.time()
        with client.stream("GET", "/v1/events/stream?max_ms=200&max_events=100") as resp:
            assert resp.status_code == 200
            events_received = []
            for line in resp.iter_lines():
                if line.startswith("event: "):
                    event_type = line.split("event: ")[1].strip()
                    events_received.append(event_type)
            # Should have received all events (5 total)
            assert len(events_received) == 5
        elapsed = time.time() - start_time
        # Should terminate within reasonable time (less than 1 second since max_ms=200ms and events exist)
        assert elapsed < 1.0
        
        # Test termination when filters exclude all events
        start_time = time.time()
        with client.stream("GET", "/v1/events/stream?types=none.&max_ms=200&max_events=5") as resp:
            assert resp.status_code == 200
            events_received = []
            for line in resp.iter_lines():
                if line.startswith("event: "):
                    events_received.append(line)
            # No matching events should be delivered
            assert len(events_received) == 0
        elapsed = time.time() - start_time
        assert elapsed < 1.0
        
    finally:
        pass


def test_prod_smoke_testclient():
    """Production smoke test using TestClient: register, login, sessions, chat completions."""
    from jarvis import server
    client = TestClient(server.app)
    
    # Register user
    try:
        register_user("smokeuser", "smokepass", email="smoke@example.com")
    except sqlite3.IntegrityError:
        pass
    
    # Login
    login_resp = client.post("/auth/login", json={"username": "smokeuser", "password": "smokepass", "captcha_token": "dummy", "captcha_answer": "dummy"})
    assert login_resp.status_code == 200
    token = login_resp.json()["token"]
    
    # Set cookie for auth
    client.cookies.set("jarvis_token", token)
    
    # Get sessions
    sessions_resp = client.get("/sessions")
    assert sessions_resp.status_code == 200
    sessions_data = sessions_resp.json()
    assert "sessions" in sessions_data
    assert isinstance(sessions_data["sessions"], list)
    
    # Chat completions (non-stream)
    chat_resp = client.post("/v1/chat/completions", json={
        "messages": [{"role": "user", "content": "Hello"}],
        "stream": False
    })
    assert chat_resp.status_code == 200
    chat_data = chat_resp.json()
    assert "choices" in chat_data
    assert len(chat_data["choices"]) > 0
    assert "message" in chat_data["choices"][0]
    assert "content" in chat_data["choices"][0]["message"]
