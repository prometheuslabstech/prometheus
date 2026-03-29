"""
Runs the content processing pipeline (deduplication).

Usage:
    python scripts/run_content_processor.py
"""

import logging
import sys
from pathlib import Path

# Add src to path so imports work without installing the package
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from prometheus_backend.content_processing.pipeline import build_content_processing_pipeline
from prometheus_backend.news_aggregator.storage.news_item_repository import LocalNewsItemRepository
from prometheus_backend.storage.hash_repository_base import LocalHashRepository

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


def main() -> None:
    news_repo = LocalNewsItemRepository(file_path=NEWS_ITEMS_PATH)
    hash_repo = LocalHashRepository(file_path=str(HASHES_PATH))

    pipeline = build_content_processing_pipeline(news_repo=news_repo, hash_repo=hash_repo)
    logger.info("Starting content processing pipeline")
    pipeline.run()
    logger.info("Pipeline complete")


if __name__ == "__main__":
    main()
