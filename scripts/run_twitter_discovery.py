"""
Runs Twitter discovery for @POTUS and prints discovered tweets.

Usage:
    TWITTER_BEARER_TOKEN=<token> python scripts/run_twitter_discovery.py

On first run: no watermark exists — fetches the most recent tweets.
On subsequent runs: only tweets published after the last crawl are returned.
"""

import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from prometheus_backend.news_aggregator.models.discovery_sources import (
    TwitterConfig,
    TwitterDiscoverySource,
)
from prometheus_backend.news_aggregator.storage.watermark_repository import LocalWatermarkRepository

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

WATERMARKS_PATH = Path("data/watermarks.json")
HANDLES = ["POTUS"]


def main() -> None:
    bearer_token = os.environ.get("TWITTER_BEARER_TOKEN")
    if not bearer_token:
        logger.error("TWITTER_BEARER_TOKEN environment variable not set")
        sys.exit(1)

    watermark_repo = LocalWatermarkRepository(file_path=WATERMARKS_PATH)

    # Log watermark state before crawl
    for handle in HANDLES:
        key = f"twitter:{handle}"
        logger.info("Watermark for %s: %s", key, watermark_repo.get(key).isoformat())

    source = TwitterDiscoverySource(
        config=TwitterConfig(
            bearer_token=bearer_token,
            user_handles=HANDLES,
            max_results_per_user=10,
        ),
        watermark_repo=watermark_repo,
    )

    items = source.discover()

    if not items:
        logger.info("No new tweets discovered")
        return

    logger.info("Discovered %d tweet(s):", len(items))
    for item in items:
        print(f"\n  author:       {item.author}")
        print(f"  source_ref:   {item.source_ref}")
        print(f"  title:        {item.title}")
        print(f"  creation_time:{item.creation_time.isoformat()}")

    # Log updated watermark
    for handle in HANDLES:
        key = f"twitter:{handle}"
        updated = watermark_repo.get(key)
        if updated:
            logger.info("Watermark updated for %s: %s", key, updated.isoformat())


if __name__ == "__main__":
    main()
