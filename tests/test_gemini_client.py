"""Tests for the Gemini client."""

import os
from unittest.mock import MagicMock, patch

import pytest

from prometheus.services.gemini import GeminiClient, converse


class TestGeminiClient:
    """Tests for GeminiClient class."""

    def test_init_with_api_key(self):
        """Test client initialization with explicit API key."""
        with patch("prometheus.services.gemini.genai") as mock_genai:
            client = GeminiClient(api_key="test-key")
            mock_genai.Client.assert_called_once_with(api_key="test-key")
            assert client.api_key == "test-key"
            assert client.model_id == "gemini-2.0-flash"

    def test_init_with_env_var(self):
        """Test client initialization with environment variable."""
        with patch.dict(os.environ, {"GEMINI_API_KEY": "env-key"}, clear=False):
            with patch("prometheus.services.gemini.genai") as mock_genai:
                client = GeminiClient()
                mock_genai.Client.assert_called_once_with(api_key="env-key")
                assert client.api_key == "env-key"

    def test_init_with_google_api_key_env_var(self):
        """Test client initialization with GOOGLE_API_KEY environment variable."""
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "google-key"}, clear=False):
            # Make sure GEMINI_API_KEY is not set
            env = os.environ.copy()
            env.pop("GEMINI_API_KEY", None)
            env["GOOGLE_API_KEY"] = "google-key"
            with patch.dict(os.environ, env, clear=True):
                with patch("prometheus.services.gemini.genai") as mock_genai:
                    client = GeminiClient()
                    mock_genai.Client.assert_called_once_with(api_key="google-key")
                    assert client.api_key == "google-key"

    def test_init_without_key_raises(self):
        """Test that initialization without API key raises ValueError."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="Gemini API key is required"):
                GeminiClient()

    def test_converse(self):
        """Test the converse method."""
        with patch("prometheus.services.gemini.genai") as mock_genai:
            mock_response = MagicMock()
            mock_response.text = "Test response"
            mock_client_instance = MagicMock()
            mock_client_instance.models.generate_content.return_value = mock_response
            mock_genai.Client.return_value = mock_client_instance

            client = GeminiClient(api_key="test-key")
            result = client.converse(
                user_message="Hello",
                system_prompt="Be helpful",
                max_tokens=100,
            )

            assert result == "Test response"
            mock_client_instance.models.generate_content.assert_called_once_with(
                model="gemini-2.0-flash",
                contents="Hello",
                config={
                    "system_instruction": "Be helpful",
                    "max_output_tokens": 100,
                },
            )

    def test_custom_model_id(self):
        """Test client initialization with custom model ID."""
        with patch("prometheus.services.gemini.genai") as mock_genai:
            client = GeminiClient(api_key="test-key", model_id="gemini-2.0-flash")
            assert client.model_id == "gemini-2.0-flash"


class TestConverseFunction:
    """Tests for the standalone converse function."""

    def test_converse_function(self):
        """Test the converse helper function."""
        mock_client = MagicMock(spec=GeminiClient)
        mock_client.converse.return_value = "Function response"

        result = converse(
            client=mock_client,
            user_message="Test message",
            system_prompt="Test prompt",
            max_tokens=512,
        )

        assert result == "Function response"
        mock_client.converse.assert_called_once_with(
            user_message="Test message",
            system_prompt="Test prompt",
            max_tokens=512,
        )
