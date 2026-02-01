"""Prometheus Analysis MCP Server."""

import logging

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

mcp = FastMCP("prometheus-analysis")


@mcp.tool()
def analyze(text: str) -> str:
    """Analyze the provided text."""
    return f"Analysis of: {text}"


def main() -> None:
    """Run the Analysis MCP server."""
    logger.info("Starting Prometheus Analysis MCP server")
    mcp.run()


if __name__ == "__main__":
    main()
