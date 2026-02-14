"""Tests for the Gemini client."""

import json
import os
from unittest.mock import MagicMock, patch

import pytest

from prometheus.services.gemini import GeminiClient, converse
from prometheus.prompts.extract_research_keywords_prompt import (
    EXTRACT_RESEARCH_KEYWORDS_PROMPT,
)


class TestGeminiClient:
    """Tests for GeminiClient class."""

    def test_init_with_api_key(self):
        """Test client initialization with explicit API key."""
        with patch("prometheus.services.gemini.genai") as mock_genai:
            client = GeminiClient(api_key="test-key")
            mock_genai.Client.assert_called_once_with(api_key="test-key")
            assert client.api_key == "test-key"
            assert client.model_id == "gemini-2.5-flash-lite"

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
                model="gemini-2.5-flash-lite",
                contents="Hello",
                config={
                    "system_instruction": "Be helpful",
                    "max_output_tokens": 100,
                },
            )

    def test_custom_model_id(self):
        """Test client initialization with custom model ID."""
        with patch("prometheus.services.gemini.genai"):
            client = GeminiClient(api_key="test-key", model_id="gemini-2.5-flash-lite")
            assert client.model_id == "gemini-2.5-flash-lite"


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


@pytest.mark.integration
class TestGeminiIntegration:
    """Integration tests that make real API calls to Gemini.

    Run with: pytest --run-integration
    Requires GEMINI_API_KEY environment variable to be set.

    Rate limits (gemini-2.5-flash-lite): 20 requests per minute.
    Tests include delays and retry logic to handle rate limiting.
    """

    # Delay between API calls to respect rate limits (20 req/min = 3s between calls)
    RATE_LIMIT_DELAY = 4  # seconds
    MAX_RETRIES = 3
    RETRY_DELAY = 10  # seconds to wait on rate limit error

    @pytest.fixture
    def client(self):
        """Create a real Gemini client."""
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            pytest.skip("GEMINI_API_KEY environment variable not set")
        return GeminiClient(api_key=api_key)

    def _call_with_retry(self, func, *args, **kwargs):
        """Call a function with retry logic for rate limit errors."""
        import time
        from google.genai.errors import ClientError

        for attempt in range(self.MAX_RETRIES):
            try:
                return func(*args, **kwargs)
            except ClientError as e:
                if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                    if attempt < self.MAX_RETRIES - 1:
                        wait_time = self.RETRY_DELAY * (attempt + 1)
                        print(f"\nRate limited, waiting {wait_time}s before retry...")
                        time.sleep(wait_time)
                    else:
                        raise
                else:
                    raise

    def test_simple_response(self, client):
        """Test that we can get a simple response from Gemini."""
        import time

        response = self._call_with_retry(
            client.converse,
            user_message="What is 2 + 2? Reply with just the number.",
            system_prompt="You are a helpful assistant. Be concise.",
            max_tokens=10,
        )

        assert response is not None
        assert len(response) > 0
        assert "4" in response

        time.sleep(self.RATE_LIMIT_DELAY)

    def _extract_json(self, response: str) -> dict:
        """Extract JSON from response, handling markdown code blocks."""
        import re

        # Try to extract JSON from markdown code blocks
        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", response)
        if json_match:
            json_str = json_match.group(1).strip()
        else:
            json_str = response.strip()

        return json.loads(json_str)

    def test_extract_keywords_response_format(self, client):
        """Test that Gemini returns valid JSON for keyword extraction."""
        import time

        test_text = """
            Apple (AAPL) reported Q4 earnings beating EPS estimates. The Fed signaled
            a potential rate cut amid falling CPI. Investors remain bullish on tech stocks.
        """

        response = self._call_with_retry(
            client.converse,
            user_message=test_text,
            system_prompt=EXTRACT_RESEARCH_KEYWORDS_PROMPT,
            max_tokens=1024,
        )

        # Should be valid JSON (may be wrapped in markdown code blocks)
        parsed = self._extract_json(response)

        # Should have the required keys
        required_keys = {
            "securities",
            "financial_terms",
            "policy_and_regulation",
            "economic_indicators",
            "market_sentiment",
        }
        assert required_keys <= set(parsed.keys()), f"Missing keys: {required_keys - set(parsed.keys())}"

        # Each value should be a list
        for key in required_keys:
            assert isinstance(parsed[key], list), f"{key} should be a list"

        time.sleep(self.RATE_LIMIT_DELAY)
