import pytest
from unittest.mock import patch, MagicMock
from jarvis.provider.ollama_client import ollama_request
import requests


def test_ollama_request_success():
    """Test successful Ollama request."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"response": "test"}
    # raise_for_status does nothing if status is ok

    with patch('requests.post', return_value=mock_response) as mock_post:
        result = ollama_request("http://test", {"test": "data"})
        assert result["ok"] is True
        assert result["data"] == {"response": "test"}
        assert result["error"] is None
        mock_post.assert_called_once()


def test_ollama_request_timeout_retry_success():
    """Test that timeout triggers retry and eventually succeeds."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"response": "test"}

    with patch('requests.post', side_effect=[requests.exceptions.Timeout(), mock_response]) as mock_post:
        result = ollama_request("http://test", {"test": "data"}, retries=1)
        assert result["ok"] is True
        assert result["data"] == {"response": "test"}
        assert result["error"] is None
        assert mock_post.call_count == 2


def test_ollama_request_connection_error_classified():
    """Test that ConnectionError is classified as ProviderConnectionError."""
    with patch('requests.post', side_effect=requests.exceptions.ConnectionError("Connection failed")):
        result = ollama_request("http://test", {"test": "data"}, retries=0)
        assert result["ok"] is False
        assert result["error"]["type"] == "ProviderConnectionError"
        assert "Connection failed" in result["error"]["message"]


def test_ollama_request_timeout_classified():
    """Test that Timeout is classified as ProviderTimeout."""
    with patch('requests.post', side_effect=requests.exceptions.Timeout("Timeout")):
        result = ollama_request("http://test", {"test": "data"}, retries=0)
        assert result["ok"] is False
        assert result["error"]["type"] == "ProviderTimeout"
        assert "Timeout" in result["error"]["message"]


def test_ollama_request_json_error_classified():
    """Test that JSONDecodeError is classified as ProviderBadResponse."""
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.side_effect = requests.exceptions.JSONDecodeError("Invalid JSON", "", 0)

    with patch('requests.post', return_value=mock_response):
        result = ollama_request("http://test", {"test": "data"}, retries=0)
        assert result["ok"] is False
        assert result["error"]["type"] == "ProviderBadResponse"


def test_ollama_request_all_retries_fail():
    """Test that when all retries fail, ok=False and error is returned."""
    calls = {"n": 0}

    def _boom(*args, **kwargs):
        calls["n"] += 1
        raise requests.exceptions.ConnectionError("Fail")

    with patch('requests.post', side_effect=_boom):
        result = ollama_request("http://test", {"test": "data"}, retries=2)
        assert result["ok"] is False
        assert result["error"]["type"] == "ProviderConnectionError"
        assert result["trace_id"]
        assert calls["n"] == 3
