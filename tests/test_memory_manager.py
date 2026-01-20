"""
Unit tests for memory_manager.
"""

import pytest
from jarvis.agent_core.memory_manager import redact_sensitive, should_write_memory, should_retrieve_memory, retrieve_context, handle_memory_commands, MemoryItem


class TestMemoryManager:
    def test_redact_sensitive(self):
        # Test API key redaction
        text = "My API key is api_key: sk-1234567890abcdef"
        redacted = redact_sensitive(text)
        assert "[REDACTED]" in redacted
        assert "sk-1234567890abcdef" not in redacted

        # Test token redaction
        text = "Bearer token: abc123def456"
        redacted = redact_sensitive(text)
        assert "[REDACTED]" in redacted

        # Test password redaction
        text = "Password: mysecret123"
        redacted = redact_sensitive(text)
        assert "[REDACTED]" in redacted

        # Test email redaction
        text = "Contact me at user@example.com"
        redacted = redact_sensitive(text)
        assert "[EMAIL]" in redacted

        # Test phone redaction
        text = "Call me at 12345678"
        redacted = redact_sensitive(text)
        assert "[PHONE]" in redacted

        # Test card redaction
        text = "Card: 1234 5678 9012 3456"
        redacted = redact_sensitive(text)
        assert "[CARD]" in redacted

        # Test no sensitive data
        text = "This is a normal message"
        redacted = redact_sensitive(text)
        assert redacted == text

    def test_should_write_memory(self):
        # Test preference detection
        items = should_write_memory("Jeg kan godt lide kaffe", "Jeg husker at du kan lide kaffe og det er en god præference at have.", "da")
        assert len(items) == 1
        assert items[0].category == "preference"

        # Test project detection
        items = should_write_memory("Jeg arbejder på et nyt projekt", "Det lyder spændende. Fortæl mig mere om dit projekt og hvad du arbejder på.", "da")
        assert len(items) >= 1  # May have multiple categories
        assert any(item.category == "project" for item in items)

        # Test identity detection
        items = should_write_memory("Jeg hedder John", "Hej John, hvordan kan jeg hjælpe dig i dag med dine opgaver?", "da")
        assert len(items) == 1
        assert items[0].category == "identity-lite"

        # Test TODO detection
        items = should_write_memory("Påmind mig om mødet", "Jeg sætter en påmindelse om mødet så du ikke glemmer det.", "da")
        assert len(items) == 1
        assert items[0].category == "todo"

        # Test short reply (should not store)
        items = should_write_memory("Hej", "Hej!", "da")
        assert len(items) == 0

    def test_should_retrieve_memory(self):
        # Test retrieval triggers
        assert should_retrieve_memory("Husker du mit navn?", "da") == True
        assert should_retrieve_memory("Hvad sagde jeg før?", "da") == True
        assert should_retrieve_memory("Fortsæt hvor vi slap", "da") == True
        assert should_retrieve_memory("Hvad kan du lide?", "da") == True

        # Test no retrieval
        assert should_retrieve_memory("Hvad er vejret?", "da") == False

    def test_retrieve_context(self):
        # This would require mocking search_memory, but for now just test the function exists
        context = retrieve_context("test_user", "test prompt")
        assert isinstance(context, str)

    def test_handle_memory_commands(self):
        # Test remember command
        response = handle_memory_commands("husk dette: jeg elsker pizza", "test_user")
        assert response == "Jeg husker det."

        # Test show memory command
        response = handle_memory_commands("vis hvad du husker om mig", "test_user")
        assert "hvad jeg husker" in response.lower()

        # Test clear memory command
        response = handle_memory_commands("ryd hukommelse", "test_user")
        assert response == "Din hukommelse er ryddet."

        # Test no command
        response = handle_memory_commands("Hej hvordan går det?", "test_user")
        assert response is None

    def test_memory_item(self):
        item = MemoryItem("test content", "test_category", "2024-01-01T12:00:00")
        assert item.content == "test content"
        assert item.category == "test_category"
        assert item.timestamp == "2024-01-01T12:00:00"