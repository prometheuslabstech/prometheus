"""Prometheus Analysis MCP Server."""

import logging
from contextlib import asynccontextmanager

from mcp.server.fastmcp import Context, FastMCP

from prometheus.dagger.aws import AWSClients
from prometheus.prompts.extract_research_keywords_prompt import (
    EXTRACT_RESEARCH_KEYWORDS_PROMPT,
)
from prometheus.prompts.generate_research_plan_prompt import (
    GENERATE_RESEARCH_PLAN_PROMPT,
)
from prometheus.models.extract_research_keywords import ExtractResearchKeywordsResponse
from prometheus.services.aws_bedrock import converse
from prometheus.services.helpers.aws_bedrock_helper import parse_converse_response

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
    source_text: str,
    additional_context: str | None = None,
    ctx: Context | None = None,
) -> str:
    """Extract structured financial keywords and topics from text for deeper research.

    Use this as a first step before calling a deep research or search tool.
    Returns a JSON object with a "keywords" key containing a list of objects,
    each with "security", "theme", and "context" fields pairing a company
    with a relevant theme and brief explanation.

    Args:
        source_text: The source text to extract keywords from (article, report, filing, etc.)
        additional_context: Optional additional context such as a security or sector
                            to help focus the extraction.
    """
    user_message = source_text
    if additional_context is not None:
        user_message = f"Context: {additional_context}\n\n{source_text}"

    assert ctx is not None, "Context is required"
    clients: AWSClients = ctx.request_context.lifespan_context
    bedrock = clients.get_bedrock_runtime_client()

    response = converse(
        client=bedrock,
        user_message=user_message,
        system_prompt=EXTRACT_RESEARCH_KEYWORDS_PROMPT,
    )
    raw = parse_converse_response(response)

    validated = ExtractResearchKeywordsResponse.model_validate_json(raw)
    return validated.model_dump_json()


@mcp.tool()
async def generate_research_plan(
    prompt: str,
    context: str | None = None,
    ctx: Context | None = None,
) -> str:
    """Generate a structured research plan with web search terms and objectives.

    Given a research prompt and optional context (as of Feb 12, this is a string
    blob.  In the future, it can be a text file or image document or a URL),
    returns a JSON list of searches to perform. Each entry has a "search_term" and
    an "objective".

    Args:
        prompt: The research question or topic to plan searches for.
        context: Optional supporting context such as a document body, article
                 text, or background information.
    """
    user_message = prompt
    if context is not None:
        user_message = f"Context:\n{context}\n\nResearch prompt: {prompt}"

    assert ctx is not None, "Context is required"
    clients: AWSClients = ctx.request_context.lifespan_context
    bedrock = clients.get_bedrock_runtime_client()

    response = converse(
        client=bedrock,
        user_message=user_message,
        system_prompt=GENERATE_RESEARCH_PLAN_PROMPT,
        model_id="us.anthropic.claude-sonnet-4-5-20250929-v1:0",
    )
    return parse_converse_response(response)


def main() -> None:
    """Run the Analysis MCP server."""
    logger.info("Starting Prometheus Analysis MCP server")
    mcp.run()


if __name__ == "__main__":
    main()
