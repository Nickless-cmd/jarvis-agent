"""
Test repo snapshot functionality.
"""

import json
import pytest
from unittest.mock import patch, mock_open
from pathlib import Path
import sys
import os

# Add src to path for testing
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from jarvis.agent import _is_repo_snapshot_command, _handle_repo_snapshot


class TestRepoSnapshot:
    def test_is_repo_snapshot_command_danish(self):
        """Test Danish repo snapshot command detection."""
        assert _is_repo_snapshot_command("lav repo snapshot", "da") == True
        assert _is_repo_snapshot_command("repo snapshot", "da") == True
        assert _is_repo_snapshot_command("repository snapshot", "da") == True
        assert _is_repo_snapshot_command("hello world", "da") == False

    def test_is_repo_snapshot_command_english(self):
        """Test English repo snapshot command detection."""
        assert _is_repo_snapshot_command("make repo snapshot", "en") == True
        assert _is_repo_snapshot_command("repo snapshot", "en") == True
        assert _is_repo_snapshot_command("repository snapshot", "en") == True
        assert _is_repo_snapshot_command("hello world", "en") == False

    @patch('subprocess.run')
    @patch('jarvis.agent.create_download_token')
    @patch('pathlib.Path.mkdir')
    @patch('builtins.open', new_callable=mock_open)
    @patch('jarvis.auth.get_user_profile')
    def test_handle_repo_snapshot_success(self, mock_get_profile, mock_file, mock_mkdir, mock_create_token, mock_subprocess):
        """Test successful repo snapshot handling."""
        # Mock user profile
        mock_get_profile.return_value = {"id": 123}
        
        # Mock subprocess output
        mock_result = mock_subprocess.return_value
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({
            "git_info": {
                "branch": "main",
                "head_commit": "abc123",
                "status": {"is_clean": True, "changed_files_count": 0},
                "recent_commits": [{"hash": "abc123", "subject": "Test commit"}]
            },
            "file_stats": {"agent_py_lines": 1000, "total_src_jarvis_lines": 5000},
            "module_inventory": {"skills_modules": ["test"], "core_modules": ["core"]},
            "timestamp": "2026-01-21T00:00:00Z"
        })
        
        mock_create_token.return_value = "test_token"
        
        result = _handle_repo_snapshot("user123", "da")
        
        assert "Repository snapshot genereret" in result.reply_text
        assert "main branch" in result.reply_text
        assert "ren" in result.reply_text
        assert "/download/" in result.reply_text
        assert result.meta["tool"] == "repo_snapshot"
        assert result.meta["tool_used"] == True

    @patch('subprocess.run')
    @patch('jarvis.auth.get_user_profile')
    def test_handle_repo_snapshot_subprocess_error(self, mock_get_profile, mock_subprocess):
        """Test repo snapshot handling when subprocess fails."""
        mock_get_profile.return_value = {"id": 123}
        mock_result = mock_subprocess.return_value
        mock_result.returncode = 1
        
        result = _handle_repo_snapshot("user123", "da")
        
        assert "Kunne ikke generere repo snapshot" in result.reply_text
        assert result.meta["tool_used"] == False

    @patch('subprocess.run')
    @patch('jarvis.auth.get_user_profile')
    def test_handle_repo_snapshot_exception(self, mock_get_profile, mock_subprocess):
        """Test repo snapshot handling when exception occurs."""
        mock_get_profile.return_value = {"id": 123}
        mock_subprocess.side_effect = Exception("Test error")
        
        result = _handle_repo_snapshot("user123", "en")
        
        assert "Error generating snapshot" in result.reply_text
        assert result.meta["tool_used"] == False

    def test_is_model_profile_command_danish(self):
        """Test Danish model profile command detection."""
        from jarvis.agent import _is_model_profile_command
        
        is_cmd, profile = _is_model_profile_command("skift til hurtig", "da")
        assert is_cmd == True
        assert profile == "fast"
        
        is_cmd, profile = _is_model_profile_command("skift til balanceret", "da")
        assert is_cmd == True
        assert profile == "balanced"
        
        is_cmd, profile = _is_model_profile_command("skift model til kvalitet", "da")
        assert is_cmd == True
        assert profile == "quality"
        
        is_cmd, profile = _is_model_profile_command("hello world", "da")
        assert is_cmd == False
        assert profile == ""

    def test_is_model_profile_command_english(self):
        """Test English model profile command detection."""
        from jarvis.agent import _is_model_profile_command
        
        is_cmd, profile = _is_model_profile_command("switch to fast", "en")
        assert is_cmd == True
        assert profile == "fast"
        
        is_cmd, profile = _is_model_profile_command("set profile to quality", "en")
        assert is_cmd == True
        assert profile == "quality"
        
        is_cmd, profile = _is_model_profile_command("change to balanced", "en")
        assert is_cmd == True
        assert profile == "balanced"
        
        is_cmd, profile = _is_model_profile_command("hello world", "en")
        assert is_cmd == False
        assert profile == ""