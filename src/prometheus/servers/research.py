"""Prometheus Research MCP Server."""

import logging
from contextlib import asynccontextmanager

from mcp.server.fastmcp import FastMCP

from prometheus.dagger.aws import AWSClients

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(server: FastMCP):
    """Initialize AWS clients for the server lifetime."""
    clients = AWSClients()
    clients.initialize()
    yield clients


mcp = FastMCP("prometheus-research", lifespan=lifespan)


@mcp.tool()
def research(query: str) -> str:
    """Research the provided query."""
    return f"Research results for: {query}"


def main() -> None:
    """Run the Research MCP server."""
    logger.info("Starting Prometheus Research MCP server")
    mcp.run()


if __name__ == "__main__":
    main()
