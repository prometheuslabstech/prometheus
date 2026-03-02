"""Tavily web search service."""

import os

from tavily import TavilyClient  # type: ignore[import-untyped]


def search(
    query: str,
    search_depth: str = "basic",
    max_results: int = 5,
) -> dict:
    """Execute a web search using the Tavily API.

    Args:
        query: The search query string.
        search_depth: Search depth - "basic" or "advanced".
        max_results: Maximum number of results to return.

    Returns:
        Raw Tavily response dict containing search results.

    Raises:
        ValueError: If TAVILY_API_KEY environment variable is not set.
    """
    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        raise ValueError(
            "TAVILY_API_KEY environment variable is not set. "
            "Get an API key at https://tavily.com"
        )

    client = TavilyClient(api_key=api_key)
    response = client.search(
        query=query,
        search_depth=search_depth,
        max_results=max_results,
    )

    return dict(response)
