"""Tests for the Prometheus MCP servers."""

from prometheus.analysis import analyze
from prometheus.research import research


def test_analyze():
    """Test the analyze tool."""
    assert analyze("test input") == "Analysis of: test input"


def test_research():
    """Test the research tool."""
    assert research("test query") == "Research results for: test query"
