"""Prometheus main entry point."""

import sys


def main() -> None:
    """Run a Prometheus MCP server by name."""
    server = sys.argv[1] if len(sys.argv) > 1 else None

    if server == "analysis":
        from prometheus.servers.analysis import main as run
    elif server == "research":
        from prometheus.servers.research import main as run
    else:
        print("Usage: prometheus <analysis|research>")
        sys.exit(1)

    run()


if __name__ == "__main__":
    main()
