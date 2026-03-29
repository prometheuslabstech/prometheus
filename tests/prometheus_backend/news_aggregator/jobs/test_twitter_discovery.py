"""
Integration test: Twitter discovery via TwitterDiscoverySource.

Requires a valid X API bearer token set in the TWITTER_BEARER_TOKEN env var.
Skipped automatically if the env var is not set.

Run with:
    TWITTER_BEARER_TOKEN=<token> pytest tests/.../test_twitter_discovery.py -m integration -s
"""

import os

import pytest

from prometheus_backend.news_aggregator.jobs.discovery_job import DiscoveryJob
from prometheus_backend.news_aggregator.models.discovery_sources import (
    TwitterConfig,
    TwitterDiscoverySource,
)
from prometheus_backend.news_aggregator.models.news_item import NewsItemStatus, SourceType
from prometheus_backend.news_aggregator.storage.news_item_repository import LocalNewsItemRepository
from prometheus_backend.news_aggregator.storage.watermark_repository import LocalWatermarkRepository

HANDLES = ["POTUS"]


@pytest.fixture
def bearer_token():
    token = os.environ.get("TWITTER_BEARER_TOKEN")
    if not token:
        pytest.skip("TWITTER_BEARER_TOKEN not set")
    return token


@pytest.mark.integration
class TestTwitterDiscovery:
    def test_discovers_tweets_and_updates_watermark(self, tmp_path, bearer_token):
        watermark_repo = LocalWatermarkRepository(tmp_path / "watermarks.json")
        repository = LocalNewsItemRepository(tmp_path / "news_items.jsonl")

        job = DiscoveryJob(
            sources=[
                TwitterDiscoverySource(
                    config=TwitterConfig(bearer_token=bearer_token, user_handles=HANDLES),
                    watermark_repo=watermark_repo,
                )
            ],
            repository=repository,
        )
        job.run()

        items = repository.list()
        assert len(items) > 0, "Expected at least one tweet from @POTUS in the last 48h"

        for item in items:
            assert item.source_type == SourceType.TWITTER
            assert item.source_ref.isdigit(), f"source_ref should be a tweet ID: {item.source_ref}"
            assert item.title.strip()
            assert item.author == "@POTUS"
            assert item.source_id == "twitter"
            assert item.status == NewsItemStatus.PENDING

        # watermark persisted after the run
        wm = watermark_repo.get("twitter:POTUS")
        assert wm is not None

        print(f"\nDiscovered {len(items)} tweet(s) from @POTUS:")
        for item in items:
            print(f"  [{item.creation_time}] {item.title}")
            print(f"    tweet_id: {item.source_ref}")

    def test_second_run_discovers_no_new_items(self, tmp_path, bearer_token):
        watermark_repo = LocalWatermarkRepository(tmp_path / "watermarks.json")
        repository = LocalNewsItemRepository(tmp_path / "news_items.jsonl")

        job = DiscoveryJob(
            sources=[
                TwitterDiscoverySource(
                    config=TwitterConfig(bearer_token=bearer_token, user_handles=HANDLES),
                    watermark_repo=watermark_repo,
                )
            ],
            repository=repository,
        )

        job.run()
        first_count = len(repository.list())

        job.run()
        second_count = len(repository.list())

        assert second_count == first_count, (
            "Second run should discover no new items — watermark should filter them out"
        )
