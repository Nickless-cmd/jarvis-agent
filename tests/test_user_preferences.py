"""
Test user preferences functionality.
"""

import pytest
import json
import os
from pathlib import Path
from unittest.mock import patch

from jarvis.user_preferences import (
    get_user_preferences,
    set_user_preferences,
    build_persona_directive,
    parse_preference_command,
    _get_user_prefs_path
)


class TestUserPreferences:
    def test_get_default_preferences(self):
        """Test getting default preferences for new user."""
        with patch('jarvis.user_preferences._get_user_prefs_path') as mock_path:
            mock_path.return_value = Path('/tmp/nonexistent.json')
            prefs = get_user_preferences('test_user')
            
            expected = {
                'preferred_name': None,
                'preferred_language': None,
                'tone': 'neutral',
                'verbosity': 'normal'
            }
            assert prefs == expected

    def test_set_and_get_preferences(self, tmp_path):
        """Test setting and getting user preferences."""
        # Create a temporary file path
        prefs_file = tmp_path / "test_user.json"
        
        with patch('jarvis.user_preferences._get_user_prefs_path') as mock_path:
            mock_path.return_value = prefs_file
            
            # Set preferences
            set_user_preferences('test_user', {
                'preferred_name': 'TestUser',
                'tone': 'friendly',
                'verbosity': 'short'
            })
            
            # Verify file was created
            assert prefs_file.exists()
            
            # Get preferences
            prefs = get_user_preferences('test_user')
            expected = {
                'preferred_name': 'TestUser',
                'preferred_language': None,
                'tone': 'friendly',
                'verbosity': 'short'
            }
            assert prefs == expected

    def test_build_persona_directive_danish(self):
        """Test building persona directive in Danish."""
        prefs = {
            'preferred_name': 'Test',
            'preferred_language': 'da',
            'tone': 'friendly',
            'verbosity': 'short'
        }
        
        directive = build_persona_directive(prefs, 'da')
        assert 'Svar på dansk.' in directive
        assert 'Hold det kort.' in directive
        assert 'Vær venlig og imødekommende.' in directive
        assert 'Vær konkret.' in directive

    def test_build_persona_directive_english(self):
        """Test building persona directive in English."""
        prefs = {
            'preferred_name': 'Test',
            'preferred_language': 'en',
            'tone': 'technical',
            'verbosity': 'detailed'
        }
        
        directive = build_persona_directive(prefs, 'en')
        assert 'Answer in English.' in directive
        assert 'Be detailed.' in directive
        assert 'Be technical and precise.' in directive
        assert 'Be concrete.' in directive

    def test_parse_preference_command_danish_name(self):
        """Test parsing Danish name command."""
        updates = parse_preference_command('kald mig Bob', 'da')
        assert updates == {'preferred_name': 'Bob'}

    def test_parse_preference_command_english_tone(self):
        """Test parsing English tone command."""
        updates = parse_preference_command('be more technical', 'en')
        assert updates == {'tone': 'technical'}

    def test_parse_preference_command_danish_language(self):
        """Test parsing Danish language command."""
        updates = parse_preference_command('skift sprog til engelsk', 'da')
        assert updates == {'preferred_language': 'en'}

    def test_parse_preference_command_no_match(self):
        """Test parsing command that doesn't match any preference."""
        updates = parse_preference_command('hello world', 'da')
        assert updates is None

    def test_preference_validation(self, tmp_path):
        """Test that invalid preferences are corrected."""
        prefs_file = tmp_path / "test_user.json"
        
        with patch('jarvis.user_preferences._get_user_prefs_path') as mock_path:
            mock_path.return_value = prefs_file
            
            # Set invalid preferences
            set_user_preferences('test_user', {
                'tone': 'invalid_tone',
                'verbosity': 'invalid_verbosity'
            })
            
            # Get preferences and check they were corrected
            prefs = get_user_preferences('test_user')
            assert prefs['tone'] == 'neutral'
            assert prefs['verbosity'] == 'normal'