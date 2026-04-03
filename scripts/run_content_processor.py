"""
Runs the content processing pipeline (deduplication + content processing).

Usage:
    python scripts/run_content_processor.py
"""

import logging
import sys
from pathlib import Path

# Add src to path so imports work without installing the package
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from prometheus_backend.config import settings
from prometheus_backend.content_processing.pipeline import build_content_processing_pipeline
from prometheus_backend.dagger.aws import AWSClients
from prometheus_backend.news_aggregator.storage.news_item_repository import LocalNewsItemRepository
from prometheus_backend.services.gemini import GeminiClient
from prometheus_backend.storage.hash_repository_base import LocalHashRepository
from prometheus_backend.storage.local_file_system.content_item_store import ContentItemStore

LOG_PATH = Path("logs/content_processor.log")
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
HASHES_PATH = Path("data/news_items_hashes.txt")
CONTENT_ITEMS_PATH = Path("data/content_items.jsonl")


def main() -> None:
    aws_clients = AWSClients(region_name=settings.aws_region)
    aws_clients.initialize()
    settings.set_aws_clients(aws_clients)

    news_repo = LocalNewsItemRepository(file_path=NEWS_ITEMS_PATH)
    hash_repo = LocalHashRepository(file_path=str(HASHES_PATH))
    content_store = ContentItemStore(file_path=CONTENT_ITEMS_PATH)
    gemini = GeminiClient(api_key=settings.gemini_api_key)

    pipeline = build_content_processing_pipeline(
        news_repo=news_repo,
        hash_repo=hash_repo,
        content_store=content_store,
        gemini=gemini,
    )
    logger.info("Starting content processing pipeline")
    pipeline.run()
    logger.info("Pipeline complete")


if __name__ == "__main__":
    main()
