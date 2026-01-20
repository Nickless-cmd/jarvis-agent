"""
Unit tests for freshness policy.
"""

import pytest
from jarvis.agent_policy.freshness import is_time_sensitive, detect_date_query, inject_time_context


class TestFreshness:
    def test_is_time_sensitive_da(self):
        assert is_time_sensitive("Seneste nyheder", "da") == True
        assert is_time_sensitive("Pris nu", "da") == True
        assert is_time_sensitive("Hvad er 2+2", "da") == False
        assert is_time_sensitive("Hvilken dato er det", "da") == True
        assert is_time_sensitive("CEO nu", "da") == True
        assert is_time_sensitive("Valg resultater", "da") == True

    def test_is_time_sensitive_en(self):
        assert is_time_sensitive("Latest news", "en") == True
        assert is_time_sensitive("Current price", "en") == True
        assert is_time_sensitive("What is 2+2", "en") == False
        assert is_time_sensitive("What is the date", "en") == True
        assert is_time_sensitive("CEO now", "en") == True
        assert is_time_sensitive("Election results", "en") == True

    def test_detect_date_query(self):
        assert detect_date_query("Hvilken dato er det") == True
        assert detect_date_query("What is the date") == True
        assert detect_date_query("Hvad er klokken") == True
        assert detect_date_query("What time is it") == True
        assert detect_date_query("Hello world") == False

    def test_inject_time_context(self):
        context = inject_time_context("da")
        assert "i dag er det" in context.lower()
        assert "europa/københavn" in context.lower()
        
        context_en = inject_time_context("en")
        assert "today is" in context_en.lower()
        assert "europe/copenhagen" in context_en.lower()