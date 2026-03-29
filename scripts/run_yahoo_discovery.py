"""Run Yahoo Finance discovery job and print results to stdout."""

from pathlib import Path

from prometheus_backend.news_aggregator.jobs.discovery_job import (
    DiscoveryJob,
    YahooFinanceDiscoverySource,
)
from prometheus_backend.news_aggregator.storage.news_item_repository import (
    LocalNewsItemRepository,
)
from prometheus_backend.storage.watermark_repository import LocalWatermarkRepository

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

if __name__ == "__main__":
    watermark_repo = LocalWatermarkRepository(DATA_DIR / "watermarks.json")
    repository = LocalNewsItemRepository(DATA_DIR / "yahoo_news_items.jsonl")

    job = DiscoveryJob(
        sources=[YahooFinanceDiscoverySource(watermark_repo)],
        repository=repository,
    )
    job.run()

    items = repository.list()
    print(f"Discovered {len(items)} items\n")
    for item in items:
        print(f"[{item.creation_time}] {item.title}")
        print(f"  {item.url}")
        print(f"  status={item.status.value}")
        print()

    watermark = watermark_repo.get("yahoo_finance")
    print(f"Watermark saved: {watermark}")
    print(f"Items saved to: {DATA_DIR / 'yahoo_news_items.jsonl'}")
