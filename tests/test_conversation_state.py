import os

from jarvis.agent_core.conversation_state import ConversationState
from jarvis.agent import _detect_response_mode
from jarvis.session_store import set_conversation_state, get_conversation_state


def test_conversation_state_roundtrip():
    state = ConversationState()
    state.set_goal("Finish draft")
    state.add_decision("Use short mode")
    state.add_pending_question("Need more data?")
    state.update_summary("Vi besluttede at starte med planen.")
    state.set_response_mode("short")

    payload = state.to_json()
    restored = ConversationState.from_json(payload)
    assert restored.current_goal == "Finish draft"
    assert "Use short mode" in restored.decisions
    assert "Need more data?" in restored.pending_questions
    assert "besluttede" in restored.last_summary
    assert restored.response_mode == "short"


def test_detect_response_mode_da_en():
    # Short mode
    assert _detect_response_mode("kort") == "short"
    assert _detect_response_mode("kort svar") == "short"
    assert _detect_response_mode("svar kort") == "short"
    assert _detect_response_mode("short") == "short"
    assert _detect_response_mode("brief") == "short"
    
    # Deep mode
    assert _detect_response_mode("dybt") == "deep"
    assert _detect_response_mode("uddyb") == "deep"
    assert _detect_response_mode("langt") == "deep"
    assert _detect_response_mode("detaljeret") == "deep"
    assert _detect_response_mode("deep") == "deep"
    assert _detect_response_mode("detailed") == "deep"
    
    # Normal mode
    assert _detect_response_mode("normal") == "normal"
    assert _detect_response_mode("som før") == "normal"
    
    # No match
    assert _detect_response_mode("noget andet") is None


def test_update_summary_key_info():
    state = ConversationState()
    
    # Should append key info
    state.update_summary("Jeg besluttede at starte med planen.")
    assert "besluttede" in state.last_summary
    
    state.update_summary("Næste trin er at implementere.")
    assert "trin" in state.last_summary
    assert "besluttede" in state.last_summary  # Both should be there
    
    # Should not append non-key info
    state.update_summary("Det er en fin dag i dag.")
    assert "fin dag" not in state.last_summary


def test_update_summary_truncation():
    state = ConversationState()
    
    # Add text that will exceed limit
    long_text = "a" * 1100
    state.update_summary(f"Jeg skal {long_text} gøre det.")
    
    # Should be truncated
    assert len(state.last_summary) <= 1200
    # Since it starts with text, no "..."
    assert "Jeg skal" in state.last_summary
    
    # Add more to trigger truncation again
    state.update_summary("Og så næste step er at fortsætte med planen.")
    assert "step" in state.last_summary
    assert len(state.last_summary) <= 1200


def test_conversation_state_persistence(tmp_path, monkeypatch):
    db_path = tmp_path / "state.db"
    monkeypatch.setenv("JARVIS_DB_PATH", str(db_path))
    session_id = "sess1"
    state = ConversationState(current_goal="Goal", response_mode="normal")
    set_conversation_state(session_id, state.to_json())
    raw = get_conversation_state(session_id)
    assert raw
    restored = ConversationState.from_json(raw)
    assert restored.current_goal == "Goal"
