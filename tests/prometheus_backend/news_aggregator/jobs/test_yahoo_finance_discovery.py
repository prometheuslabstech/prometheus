"""Integration test: Yahoo Finance RSS discovery via RSSDiscoverySource."""

from datetime import datetime, timedelta, timezone

import pytest

from prometheus_backend.news_aggregator.jobs.discovery_job import (
    DiscoveryJob,
    RSSDiscoverySource,
    RSSFeedConfig,
)
from prometheus_backend.news_aggregator.storage.news_item_repository import (
    LocalNewsItemRepository,
)

YAHOO_FINANCE_RSS_URL = "https://finance.yahoo.com/news/rssindex"


@pytest.mark.integration
class TestYahooFinanceRSSDiscovery:
    def test_discovers_items_within_time_window(self, tmp_path):
        since = datetime.now(timezone.utc) - timedelta(hours=48)
        repository = LocalNewsItemRepository(tmp_path / "news_items.jsonl")

        job = DiscoveryJob(
            sources=[RSSDiscoverySource(RSSFeedConfig(
                source_id="yahoo_finance",
                feed_url=YAHOO_FINANCE_RSS_URL,
            ))],
            repository=repository,
            since=since,
        )
        job.run()

        items = repository.list()
        assert len(items) > 0, "Expected at least one item within the last 24 hours"

        for item in items:
            assert item.creation_time >= since, (
                f"Item outside time window: {item.title} at {item.creation_time}"
            )
            assert item.url.startswith("http"), f"Invalid URL: {item.url}"
            assert item.title.strip()

        print(f"\nDiscovered {len(items)} items from Yahoo Finance RSS (last 48h)")
        for item in items[:10]:
            print(f"  [{item.creation_time}] {item.title}")
            print(f"    {item.url}")
