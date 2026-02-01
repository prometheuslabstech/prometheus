"""Prometheus Analysis MCP Server."""

import logging
from contextlib import asynccontextmanager

from mcp.server.fastmcp import Context, FastMCP

from prometheus.dagger.aws import AWSClients
from prometheus.prompts.extract_research_keywords_prompt import (
    EXTRACT_RESEARCH_KEYWORDS_PROMPT,
)
from prometheus.services.aws_bedrock import converse

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(server: FastMCP):
    """Initialize AWS clients for the server lifetime."""
    clients = AWSClients()
    clients.initialize()
    yield clients


mcp = FastMCP(
    "prometheus-analysis",
    instructions=(
        "Financial analysis tools for investment research and decision-making. "
        "Provides text analysis capabilities for processing news articles, "
        "earnings reports, analyst notes, and other financial documents."
    ),
    lifespan=lifespan,
)


@mcp.tool()
async def extract_research_keywords(
    text: str,
    context: str | None = None,
    ctx: Context | None = None,
) -> str:
    """Extract structured financial keywords and topics from text for deeper research.

    Use this as a first step before calling a deep research or search tool.
    Returns a JSON object with keywords grouped into: securities, financial_terms,
    policy_and_regulation, economic_indicators, and market_sentiment.

    Args:
        text: The source text to extract keywords from (article, report, filing, etc.)
        context: Optional additional context such as a security ticker or sector
                 to help focus the extraction.
    """
    user_message = text
    if context is not None:
        user_message = f"Context: {context}\n\n{text}"

    assert ctx is not None, "Context is required"
    clients: AWSClients = ctx.request_context.lifespan_context
    bedrock = clients.get_bedrock_runtime_client()

    return converse(
        client=bedrock,
        user_message=user_message,
        system_prompt=EXTRACT_RESEARCH_KEYWORDS_PROMPT,
    )


def main() -> None:
    """Run the Analysis MCP server."""
    logger.info("Starting Prometheus Analysis MCP server")
    mcp.run()


if __name__ == "__main__":
    main()
