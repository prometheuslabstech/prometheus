"""Prometheus Research MCP Server."""

import logging

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

mcp = FastMCP("prometheus-research")


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
