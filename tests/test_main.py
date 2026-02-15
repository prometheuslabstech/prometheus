"""Tests for the Prometheus MCP servers."""

from unittest.mock import patch

import pytest

from prometheus.servers.research import web_search


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
