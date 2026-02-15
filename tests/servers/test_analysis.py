"""Tests for the Prometheus Analysis MCP server."""

import json
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from prometheus.servers.analysis import extract_research_keywords


class TestExtractResearchKeywords:
    """Tests for the extract_research_keywords tool."""

    @pytest.mark.asyncio
    async def test_calls_bedrock_and_returns_validated_response(self):
        """Test extract_research_keywords calls Bedrock and returns validated response."""
        mock_ctx = MagicMock()
        mock_bedrock = MagicMock()
        mock_ctx.request_context.lifespan_context.get_bedrock_runtime_client.return_value = (
            mock_bedrock
        )

        expected = {"keywords": [{"security": "Apple", "theme": "earnings", "context": "Apple reported strong revenue growth"}]}
        mock_bedrock_response = {
            "output": {"message": {"content": [{"text": json.dumps(expected)}]}}
        }

        with patch(
            "prometheus.servers.analysis.converse", return_value=mock_bedrock_response
        ) as mock_converse:
            result = await extract_research_keywords(
                "AAPL reported strong revenue growth.", ctx=mock_ctx
            )

        assert json.loads(result) == expected
        mock_converse.assert_called_once()

    @pytest.mark.asyncio
    async def test_prepends_context_to_user_message(self):
        """Test extract_research_keywords prepends context to user message."""
        mock_ctx = MagicMock()
        mock_bedrock = MagicMock()
        mock_ctx.request_context.lifespan_context.get_bedrock_runtime_client.return_value = (
            mock_bedrock
        )

        mock_bedrock_response = {"output": {"message": {"content": [{"text": '{"keywords": []}'}]}}}

        with patch(
            "prometheus.servers.analysis.converse", return_value=mock_bedrock_response
        ) as mock_converse:
            await extract_research_keywords(
                "revenue grew 20%", additional_context="TSLA", ctx=mock_ctx
            )

        call_kwargs = mock_converse.call_args.kwargs
        assert "TSLA" in call_kwargs["user_message"]
        assert "revenue grew 20%" in call_kwargs["user_message"]

    @pytest.mark.asyncio
    async def test_raises_validation_error_on_malformed_response(self):
        """Test extract_research_keywords raises ValidationError on malformed LLM output."""
        mock_ctx = MagicMock()
        mock_bedrock = MagicMock()
        mock_ctx.request_context.lifespan_context.get_bedrock_runtime_client.return_value = (
            mock_bedrock
        )

        mock_bedrock_response = {
            "output": {"message": {"content": [{"text": '{"keywords": [{"wrong_field": "bad"}]}'}]}}
        }

        with patch(
            "prometheus.servers.analysis.converse", return_value=mock_bedrock_response
        ):
            with pytest.raises(ValidationError):
                await extract_research_keywords("some text", ctx=mock_ctx)
