"""Tavily web search service."""

from tavily import TavilyClient  # type: ignore[import-untyped]

from prometheus_backend.config import settings


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
    """
    client = TavilyClient(api_key=settings.tavily_api_key)
    response = client.search(
        query=query,
        search_depth=search_depth,
        max_results=max_results,
    )

    return dict(response)


def extract(url: str) -> str:
    """Extract the full content of a webpage by URL.

    Args:
        url: The URL to extract content from.

    Returns:
        Raw markdown content of the page.
    """
    client = TavilyClient(api_key=settings.tavily_api_key)
    response = client.extract(urls=url, format="markdown")
    return response["results"][0]["raw_content"]
