"""
Tests for the centralized conversation context builder.
"""

import pytest
from unittest.mock import patch, MagicMock

from jarvis.context_builder import ConversationContextBuilder, ContextResult, get_context_builder


class TestConversationContextBuilder:
    """Test the ConversationContextBuilder class."""

    def test_build_context_basic(self):
        """Test basic context building functionality."""
        with patch('jarvis.context_builder.get_user_profile') as mock_profile, \
             patch('jarvis.context_utils.get_user_preferences') as mock_prefs, \
             patch('jarvis.context_builder.get_recent_messages') as mock_history, \
             patch('jarvis.context_builder.search_memory') as mock_memory, \
             patch('jarvis.context_builder.get_budget') as mock_budget:

            # Mock dependencies
            mock_profile.return_value = {"name": "Test User"}
            mock_prefs.return_value = {}
            mock_history.return_value = [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there"}
            ]
            mock_memory.return_value = ["User likes coffee"]

            # Mock budget
            mock_budget_instance = MagicMock()
            mock_budget_instance.enforce_budget.return_value = (
                [{"role": "user", "content": "Hello"}],  # trimmed_hist
                ["User likes coffee"],  # trimmed_mem
                {"history_messages": 1, "memory_snippets": 1, "total_chars": 17},  # context_counts
                False,  # budget_exceeded
                1  # items_trimmed
            )
            mock_budget.return_value = mock_budget_instance

            builder = ConversationContextBuilder()
            result = builder.build_context(
                user_id="test_user",
                prompt="What's the weather?",
                session_id="test_session"
            )

            assert isinstance(result, ContextResult)
            assert len(result.messages) >= 3  # system + memory + history + user
            assert result.context_counts == {"history_messages": 1, "memory_snippets": 1, "total_chars": 17}
            assert result.budget_exceeded is False
            assert result.items_trimmed == 1

    def test_context_builder_singleton(self):
        """Test that get_context_builder returns a singleton."""
        builder1 = get_context_builder()
        builder2 = get_context_builder()

        assert builder1 is builder2
        assert isinstance(builder1, ConversationContextBuilder)

    def test_memory_trim_event_emission(self):
        """Test that memory.trim events are emitted when items are trimmed."""
        with patch('jarvis.context_builder.get_user_profile'), \
             patch('jarvis.context_utils.get_user_preferences'), \
             patch('jarvis.context_builder.get_recent_messages'), \
             patch('jarvis.context_builder.search_memory'), \
             patch('jarvis.context_builder.get_budget') as mock_budget, \
             patch('jarvis.context_builder.publish') as mock_publish:

            # Mock budget to return trimmed results
            mock_budget_instance = MagicMock()
            mock_budget_instance.enforce_budget.return_value = (
                [],  # trimmed_hist (empty)
                [],  # trimmed_mem (empty)
                {"messages": 0, "memory": 0},  # context_counts
                True,  # budget_exceeded
                5  # items_trimmed
            )
            mock_budget.return_value = mock_budget_instance

            builder = ConversationContextBuilder()
            result = builder.build_context(
                user_id="test_user",
                prompt="Test",
                session_id="test_session"
            )

            # Verify event was published
            mock_publish.assert_any_call("memory.trim", {
                "session_id": "test_session",
                "before_count": 0,  # No history/memory in this mock
                "after_count": 0,
                "items_trimmed": 5,
            })

    def test_summary_creation(self):
        """Test that summary is created when history is trimmed."""
        with patch('jarvis.context_builder.get_user_profile'), \
             patch('jarvis.context_utils.get_user_preferences'), \
             patch('jarvis.context_builder.get_recent_messages') as mock_history, \
             patch('jarvis.context_builder.search_memory'), \
             patch('jarvis.context_builder.get_budget') as mock_budget, \
             patch('jarvis.context_builder.publish') as mock_publish:

            # Mock history with multiple messages
            mock_history.return_value = [
                {"role": "user", "content": "First message"},
                {"role": "assistant", "content": "First response"},
                {"role": "user", "content": "Second message"},
                {"role": "assistant", "content": "Second response"},
            ]

            # Mock budget to trim history
            mock_budget_instance = MagicMock()
            mock_budget_instance.enforce_budget.return_value = (
                [{"role": "user", "content": "Second message"}],  # Only keep last user message
                [],  # no memory
                {"messages": 1, "memory": 0},  # context_counts
                True,  # budget_exceeded
                3  # items_trimmed
            )
            mock_budget.return_value = mock_budget_instance

            builder = ConversationContextBuilder()
            result = builder.build_context(
                user_id="test_user",
                prompt="Test",
                session_id="test_session"
            )

            # Verify summary was created
            assert result.summary_created is True
            assert len(result.messages) >= 2  # system + summary + user
            assert "trimmed" in result.messages[1]["content"].lower()

            # Verify summary event was published
            mock_publish.assert_any_call("memory.summary", {
                "session_id": "test_session",
                "summary_len": pytest.approx(50, abs=20),  # Approximate length
            })

    def test_tool_result_integration(self):
        """Test that tool results are properly integrated into context."""
        with patch('jarvis.context_builder.get_user_profile'), \
             patch('jarvis.context_utils.get_user_preferences'), \
             patch('jarvis.context_builder.get_recent_messages'), \
             patch('jarvis.context_builder.search_memory'), \
             patch('jarvis.context_builder.get_budget') as mock_budget:

            # Mock budget
            mock_budget_instance = MagicMock()
            mock_budget_instance.enforce_budget.return_value = ([], [], {}, False, 0)
            mock_budget.return_value = mock_budget_instance

            builder = ConversationContextBuilder()
            tool_result = {"text": "Weather is sunny", "temperature": 25}

            result = builder.build_context(
                user_id="test_user",
                prompt="What's the weather?",
                tool_result=tool_result
            )

            # Verify tool result is in the last message
            last_message = result.messages[-1]
            assert last_message["role"] == "assistant"
            assert "Tool result:" in last_message["content"]
            assert "Weather is sunny" in last_message["content"]
