import json

from jarvis.agent_core.conversation_state import ConversationState


def test_pending_tool_roundtrip():
    state = ConversationState()
    state.set_pending_tool("kill_process", {"pid": 123}, risk_level="high")
    serialized = state.to_json()
    data = json.loads(serialized)
    assert data["pending_tool_action"]["name"] == "kill_process"
    assert data["pending_tool_action"]["args"]["pid"] == 123
    assert data["pending_tool_action"]["risk_level"] == "high"

    restored = ConversationState.from_json(serialized)
    assert restored.pending_tool_action == {
        "name": "kill_process",
        "args": {"pid": 123},
        "risk_level": "high",
    }

    restored.clear_pending_tool()
    assert restored.pending_tool_action is None
