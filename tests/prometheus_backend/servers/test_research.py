"""Tests for the Prometheus Research MCP server."""

import json
from unittest.mock import patch

import pytest

from prometheus_backend.servers.research import web_search

MOCK_TAVILY_RESPONSE = {
    "results": [
        {
            "title": "Apple Q4 Earnings Report",
            "url": "https://example.com/aapl-q4",
            "content": "Apple reported strong Q4 earnings with revenue of $89.5B.",
            "score": 0.95,
        },
        {
            "title": "AAPL Stock Analysis",
            "url": "https://example.com/aapl-analysis",
            "content": "Analysts remain bullish on Apple stock after earnings beat.",
            "score": 0.88,
        },
    ],
}


class TestWebSearch:
    """Tests for the web_search MCP tool."""

    @pytest.mark.asyncio
    async def test_returns_formatted_results(self):
        """Test that web_search returns properly formatted JSON."""
        with patch(
            "prometheus_backend.servers.research.search", return_value=MOCK_TAVILY_RESPONSE
        ):
            result = await web_search(search_term="AAPL earnings")

        parsed = json.loads(result)
        assert parsed["search_term"] == "AAPL earnings"
        assert len(parsed["results"]) == 2
        assert parsed["results"][0]["title"] == "Apple Q4 Earnings Report"
        assert parsed["results"][0]["url"] == "https://example.com/aapl-q4"
        assert "revenue" in parsed["results"][0]["content"]
        assert "objective" not in parsed

    @pytest.mark.asyncio
    async def test_includes_objective(self):
        """Test that objective is included in output when provided."""
        with patch(
            "prometheus_backend.servers.research.search", return_value=MOCK_TAVILY_RESPONSE
        ):
            result = await web_search(
                search_term="AAPL earnings",
                objective="Find latest quarterly results",
            )

        parsed = json.loads(result)
        assert parsed["objective"] == "Find latest quarterly results"

    @pytest.mark.asyncio
    async def test_handles_empty_results(self):
        """Test that web_search handles empty results gracefully."""
        with patch("prometheus_backend.servers.research.search", return_value={"results": []}):
            result = await web_search(search_term="obscure query")

        parsed = json.loads(result)
        assert parsed["results"] == []

    @pytest.mark.asyncio
    async def test_strips_extra_fields(self):
        """Test that only title, url, and content are kept from results."""
        with patch(
            "prometheus_backend.servers.research.search", return_value=MOCK_TAVILY_RESPONSE
        ):
            result = await web_search(search_term="AAPL earnings")

        parsed = json.loads(result)
        for r in parsed["results"]:
            assert set(r.keys()) == {"title", "url", "content"}

    @pytest.mark.asyncio
    async def test_propagates_api_errors(self):
        """Test that API errors propagate to the caller."""
        with patch(
            "prometheus_backend.servers.research.search",
            side_effect=ValueError("TAVILY_API_KEY environment variable is not set"),
        ):
            with pytest.raises(ValueError, match="TAVILY_API_KEY"):
                await web_search(search_term="test")
