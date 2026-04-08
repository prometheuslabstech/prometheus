"""Prometheus main entry point."""

import sys

from prometheus_backend.config import settings


def main() -> None:
    """Run a Prometheus MCP server by name."""
    settings.init_aws()

    server = sys.argv[1] if len(sys.argv) > 1 else None

    if server == "analysis":
        from prometheus_backend.servers.analysis import main as run
    elif server == "research":
        from prometheus_backend.servers.research import main as run
    elif server == "profile":
        from prometheus_backend.servers.profile import main as run
    else:
        print("Usage: prometheus <analysis|research|profile>")
        sys.exit(1)

    run()


if __name__ == "__main__":
    main()
