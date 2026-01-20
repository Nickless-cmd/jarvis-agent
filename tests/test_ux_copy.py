"""
Unit tests for ux_copy.
"""

import pytest
from jarvis.agent_format.ux_copy import ux_error, ux_notice


class TestUXCopy:
    def test_ux_error_da(self):
        # Test Danish error messages
        msg = ux_error("model_timeout", "da")
        assert "Modellen tog for lang tid" in msg
        assert "kortere spørgsmål" in msg

        msg = ux_error("empty_reply", "da")
        assert "tomt svar" in msg

        msg = ux_error("tool_failed", "da", tool="weather")
        assert "weather fejlede" in msg

    def test_ux_error_en(self):
        # Test English error messages
        msg = ux_error("model_timeout", "en")
        assert "took too long" in msg
        assert "shorter question" in msg

        msg = ux_error("empty_reply", "en")
        assert "empty response" in msg

        msg = ux_error("tool_failed", "en", tool="search")
        assert "search failed" in msg

    def test_ux_notice_da(self):
        # Test Danish notices
        msg = ux_notice("farewell", "da")
        assert "Vi ses snart" in msg

        msg = ux_notice("memory_remembered", "da")
        assert "Jeg husker det" in msg

    def test_ux_notice_en(self):
        # Test English notices
        msg = ux_notice("farewell", "en")
        assert "See you soon" in msg

        msg = ux_notice("memory_remembered", "en")
        assert "I'll remember that" in msg

    def test_fallback(self):
        # Test unknown key
        msg = ux_error("unknown_key", "da")
        assert "Error: unknown_key" in msg

        msg = ux_notice("unknown_key", "en")
        assert "Notice: unknown_key" in msg

    def test_lang_fallback(self):
        # Test invalid lang defaults to da
        msg = ux_error("model_timeout", "invalid")
        assert "Modellen tog for lang tid" in msg