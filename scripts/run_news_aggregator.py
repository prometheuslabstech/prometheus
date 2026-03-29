"""
Runs the news aggregator pipeline (discovery + fetch).

Usage:
    python scripts/run_news_aggregator.py
"""

import logging
import sys
from pathlib import Path

# Add src to path so imports work without installing the package
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from prometheus_backend.config import settings
from prometheus_backend.dagger.aws import AWSClients
from prometheus_backend.news_aggregator.models.discovery_sources import YahooFinanceDiscoverySource
from prometheus_backend.news_aggregator.pipeline import build_news_aggregator_pipeline
from prometheus_backend.news_aggregator.storage.news_item_repository import LocalNewsItemRepository
from prometheus_backend.news_aggregator.storage.watermark_repository import LocalWatermarkRepository

LOG_PATH = Path("logs/news_aggregator.log")
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_PATH),
    ],
)
logger = logging.getLogger(__name__)

NEWS_ITEMS_PATH = Path("data/news_items.jsonl")
WATERMARKS_PATH = Path("data/watermarks.json")


def main() -> None:
    aws_clients = AWSClients(region_name=settings.aws_region)
    aws_clients.initialize()
    settings.set_aws_clients(aws_clients)

    watermark_repo = LocalWatermarkRepository(file_path=WATERMARKS_PATH)
    sources = [YahooFinanceDiscoverySource(watermark_repo=watermark_repo)]
    repository = LocalNewsItemRepository(file_path=NEWS_ITEMS_PATH)

    pipeline = build_news_aggregator_pipeline(sources=sources, repository=repository)
    logger.info("Starting news aggregator pipeline")
    pipeline.run()
    logger.info("Pipeline complete")


if __name__ == "__main__":
    main()
