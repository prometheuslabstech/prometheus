"""Integration test: Yahoo Finance RSS discovery via YahooFinanceDiscoverySource."""

import pytest

from prometheus_backend.news_aggregator.jobs.discovery_job import (
    DiscoveryJob,
    YahooFinanceDiscoverySource,
)
from prometheus_backend.news_aggregator.storage.news_item_repository import (
    LocalNewsItemRepository,
)
from prometheus_backend.news_aggregator.storage.watermark_repository import LocalWatermarkRepository


@pytest.mark.integration
class TestYahooFinanceRSSDiscovery:
    def test_discovers_items_and_updates_watermark(self, tmp_path):
        watermark_repo = LocalWatermarkRepository(tmp_path / "watermarks.json")
        repository = LocalNewsItemRepository(tmp_path / "news_items.jsonl")

        job = DiscoveryJob(
            sources=[YahooFinanceDiscoverySource(watermark_repo)],
            repository=repository,
        )
        job.run()

        items = repository.list()
        assert len(items) > 0, "Expected at least one item from Yahoo Finance RSS"

        for item in items:
            assert item.url.startswith("http"), f"Invalid URL: {item.url}"
            assert item.title.strip()
            assert item.source_id == "yahoo_finance"

        # watermark should be persisted after the run
        assert watermark_repo.get("yahoo_finance") is not None

        print(f"\nDiscovered {len(items)} items from Yahoo Finance RSS")
        for item in items[:10]:
            print(f"  [{item.creation_time}] {item.title}")
            print(f"    {item.url}")

    def test_second_run_skips_already_seen_items(self, tmp_path):
        watermark_repo = LocalWatermarkRepository(tmp_path / "watermarks.json")
        repository = LocalNewsItemRepository(tmp_path / "news_items.jsonl")

        job = DiscoveryJob(
            sources=[YahooFinanceDiscoverySource(watermark_repo)],
            repository=repository,
        )

        job.run()
        first_count = len(repository.list())

        job.run()
        second_count = len(repository.list())

        assert second_count == first_count, (
            "Second run should discover no new items — watermark should filter them out"
        )
