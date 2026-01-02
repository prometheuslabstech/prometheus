"""Main entry point for the Prometheus application."""

import logging
from typing import Optional

from prometheus.utils import greet

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main(name: Optional[str] = None) -> None:
    """
    Main function to run the application.

    Args:
        name: Optional name to greet. Defaults to None.
    """
    logger.info("Starting Prometheus application")
    
    if name:
        message = greet(name)
    else:
        message = greet("World")
    
    print(message)
    logger.info("Application completed")


if __name__ == "__main__":
    main()

