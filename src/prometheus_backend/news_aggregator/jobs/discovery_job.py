import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone

import feedparser

from prometheus_backend.jobs.base import Job
from prometheus_backend.news_aggregator.models.news_item import (
    NewsItem,
    NewsItemStatus,
    SourceType,
)
from prometheus_backend.news_aggregator.storage.news_item_repository import (
    NewsItemRepository,
)
from prometheus_backend.news_aggregator.storage.watermark_repository import WatermarkRepository

logger = logging.getLogger(__name__)


@dataclass
class DiscoveredItem:
    """Raw discovery result from a source before it becomes a NewsItem."""

    source_ref: str       # URL for RSS; tweet ID for Twitter
    source_type: SourceType
    title: str
    source_id: str
    creation_time: datetime


class DiscoverySource(ABC):
    """Abstract source that discovers items without fetching full content.

    Implementations must:
    1. Load last_crawl_timestamp from WatermarkRepository and filter to items
       published after it (watermark check).
    2. Normalize native format (XML/JSON/HTML) into DiscoveredItem.
    3. Persist the new last_crawl_timestamp via WatermarkRepository after
       a successful discover().
    """

    @abstractmethod
    def discover(self) -> list[DiscoveredItem]: ...


@dataclass
class RSSFeedConfig:
    source_id: str  # publisher label, e.g. "reuters.com"
    feed_url: str   # e.g. "https://feeds.reuters.com/reuters/businessNews"


class RSSDiscoverySource(DiscoverySource):
    """Discovers news items from RSS/Atom feeds.

    Uses WatermarkRepository to track the last crawl timestamp per source.
    Only items published after the watermark are returned. The watermark is
    updated to the latest publication time after each successful discover().
    """

    def __init__(
        self,
        config: RSSFeedConfig,
        watermark_repo: WatermarkRepository,
    ) -> None:
        self._config = config
        self._watermark_repo = watermark_repo

    def discover(self) -> list[DiscoveredItem]:
        last_crawl = self._watermark_repo.get(self._config.source_id)
        feed = feedparser.parse(self._config.feed_url)
        items = []
        for entry in feed.entries:
            url = entry.get("link", "")
            title = entry.get("title", "")
            if not url or not title:
                continue
            published = entry.get("published_parsed")
            creation_time = (
                datetime(
                    published[0],
                    published[1],
                    published[2],
                    published[3],
                    published[4],
                    published[5],
                    tzinfo=timezone.utc,
                )
                if published
                else datetime.now(timezone.utc)
            )
            if last_crawl and creation_time <= last_crawl:
                continue
            items.append(
                DiscoveredItem(
                    source_ref=url,
                    source_type=SourceType.RSS,
                    title=title,
                    source_id=self._config.source_id,
                    creation_time=creation_time,
                )
            )
        if items:
            self._watermark_repo.set(
                self._config.source_id,
                max(item.creation_time for item in items),
            )
        return items


class YahooFinanceDiscoverySource(RSSDiscoverySource):
    """Discovers news from Yahoo Finance RSS."""

    RSS_URL = "https://finance.yahoo.com/news/rssindex"

    def __init__(self, watermark_repo: WatermarkRepository) -> None:
        super().__init__(
            config=RSSFeedConfig(
                source_id="yahoo_finance",
                feed_url=self.RSS_URL,
            ),
            watermark_repo=watermark_repo,
        )


class DiscoveryJob(Job):
    """
    Runs all configured DiscoverySource(s) and stores new items as PENDING NewsItems.
    Skips items already present in the repository as a secondary dedup guard.
    Time-window filtering is handled by each DiscoverySource via its watermark.
    """

    def __init__(
        self,
        sources: list[DiscoverySource],
        repository: NewsItemRepository,
    ) -> None:
        self._sources = sources
        self._repository = repository

    def run(self) -> None:
        for source in self._sources:
            discovered = source.discover()
            for item in discovered:
                if self._repository.get(item.source_ref) is not None:
                    logger.debug("Skipping already-known item: %s", item.source_ref)
                    continue
                news_item = NewsItem(
                    source_ref=item.source_ref,
                    source_type=item.source_type,
                    title=item.title,
                    source_id=item.source_id,
                    status=NewsItemStatus.PENDING,
                    creation_time=item.creation_time,
                )
                self._repository.put(news_item)
                logger.info("Discovered: %s", item.source_ref)
