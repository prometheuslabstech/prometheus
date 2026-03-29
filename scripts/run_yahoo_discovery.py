"""Run Yahoo Finance discovery job and print results to stdout."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

from prometheus_backend.news_aggregator.jobs.discovery_job import (
    DiscoveryJob,
    RSSDiscoverySource,
    RSSFeedConfig,
)
from prometheus_backend.news_aggregator.storage.news_item_repository import (
    LocalNewsItemRepository,
)

OUTPUT_FILE = Path(__file__).parent / "yahoo_news_items.jsonl"

if __name__ == "__main__":
    since = datetime.now(timezone.utc) - timedelta(hours=48)
    repository = LocalNewsItemRepository(OUTPUT_FILE)

    job = DiscoveryJob(
        sources=[RSSDiscoverySource(RSSFeedConfig(
            source_id="yahoo_finance",
            feed_url="https://finance.yahoo.com/news/rssindex",
        ))],
        repository=repository,
        since=since,
    )
    job.run()

    items = repository.list()
    print(f"Discovered {len(items)} items\n")
    for item in items:
        print(f"[{item.creation_time}] {item.title}")
        print(f"  {item.url}")
        print(f"  status={item.status}")
        print()

    print(f"Saved to: {OUTPUT_FILE}")
