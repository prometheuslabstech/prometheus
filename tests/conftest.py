"""Pytest configuration and fixtures."""

import pytest


def pytest_addoption(parser):
    """Add custom command line options."""
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="Run integration tests that make real API calls",
    )


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "integration: mark test as integration test (requires --run-integration flag)",
    )


def pytest_collection_modifyitems(config, items):
    """Skip integration tests unless --run-integration is passed."""
    if config.getoption("--run-integration"):
        return

    skip_integration = pytest.mark.skip(reason="Need --run-integration flag to run")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)
