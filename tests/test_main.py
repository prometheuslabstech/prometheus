"""Tests for the Prometheus MCP servers."""

from unittest.mock import MagicMock, patch

import pytest

from prometheus.servers.analysis import extract_research_keywords
from prometheus.servers.research import web_search


@pytest.mark.asyncio
async def test_extract_research_keywords():
    """Test extract_research_keywords calls Bedrock and returns response."""
    mock_ctx = MagicMock()
    mock_bedrock = MagicMock()
    mock_ctx.request_context.lifespan_context.get_bedrock_runtime_client.return_value = (
        mock_bedrock
    )

    mock_bedrock_response = {
        "output": {"message": {"content": [{"text": '{"securities": ["AAPL"]}'}]}}
    }

    with patch(
        "prometheus.servers.analysis.converse", return_value=mock_bedrock_response
    ) as mock_converse:
        result = await extract_research_keywords(
            "AAPL reported strong revenue growth.", ctx=mock_ctx
        )

    assert result == '{"securities": ["AAPL"]}'
    mock_converse.assert_called_once()


@pytest.mark.asyncio
async def test_extract_research_keywords_with_context():
    """Test extract_research_keywords prepends context to user message."""
    mock_ctx = MagicMock()
    mock_bedrock = MagicMock()
    mock_ctx.request_context.lifespan_context.get_bedrock_runtime_client.return_value = (
        mock_bedrock
    )

    mock_bedrock_response = {"output": {"message": {"content": [{"text": "{}"}]}}}

    with patch(
        "prometheus.servers.analysis.converse", return_value=mock_bedrock_response
    ) as mock_converse:
        await extract_research_keywords(
            "revenue grew 20%", context="TSLA", ctx=mock_ctx
        )

    call_kwargs = mock_converse.call_args.kwargs
    assert "TSLA" in call_kwargs["user_message"]
    assert "revenue grew 20%" in call_kwargs["user_message"]


@pytest.mark.asyncio
async def test_web_search():
    """Test the web_search tool returns structured JSON."""
    mock_response = {
        "results": [
            {
                "title": "Test Result",
                "url": "https://example.com",
                "content": "Test content",
            }
        ]
    }

    with patch("prometheus.servers.research.search", return_value=mock_response):
        result = await web_search("test query")

    import json

    parsed = json.loads(result)
    assert parsed["search_term"] == "test query"
    assert len(parsed["results"]) == 1
    assert parsed["results"][0]["title"] == "Test Result"
