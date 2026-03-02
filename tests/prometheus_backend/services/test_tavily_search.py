"""Tests for the tavily_search service."""

from unittest.mock import patch

from prometheus_backend.services.tavily_search import search

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


class TestTavilySearch:
    """Tests for the tavily_search service."""

    def test_search_calls_tavily_client(self):
        """Test that search correctly calls the Tavily client."""
        with patch(
            "prometheus_backend.services.tavily_search.settings"
        ) as mock_settings:
            mock_settings.tavily_api_key = "test-key"
            with patch(
                "prometheus_backend.services.tavily_search.TavilyClient"
            ) as mock_client_cls:
                mock_client = mock_client_cls.return_value
                mock_client.search.return_value = MOCK_TAVILY_RESPONSE

                result = search(
                    query="AAPL earnings", search_depth="advanced", max_results=3
                )

                mock_client_cls.assert_called_once_with(api_key="test-key")
                mock_client.search.assert_called_once_with(
                    query="AAPL earnings",
                    search_depth="advanced",
                    max_results=3,
                )
                assert result == MOCK_TAVILY_RESPONSE
