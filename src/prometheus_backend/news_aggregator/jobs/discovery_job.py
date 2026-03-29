import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone

import feedparser

from prometheus_backend.jobs.base import Job
from prometheus_backend.news_aggregator.models.news_item import NewsItem, NewsItemStatus
from prometheus_backend.news_aggregator.storage.news_item_repository import (
    NewsItemRepository,
)

logger = logging.getLogger(__name__)


@dataclass
class DiscoveredItem:
    """Raw discovery result from a source before it becomes a NewsItem."""

    url: str
    title: str
    source_id: str
    creation_time: datetime


class DiscoverySource(ABC):
    """Abstract source that discovers URLs without fetching full content."""

    @abstractmethod
    def discover(self) -> list[DiscoveredItem]: ...


@dataclass
class RSSFeedConfig:
    source_id: str  # publisher domain, e.g. "reuters.com"
    feed_url: str  # e.g. "https://feeds.reuters.com/reuters/businessNews"


class RSSDiscoverySource(DiscoverySource):
    """Discovers news items from RSS/Atom feeds."""

    def __init__(self, config: RSSFeedConfig) -> None:
        self._config = config

    def discover(self) -> list[DiscoveredItem]:
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
                )  # noqa: E501
                if published
                else datetime.now(timezone.utc)
            )
            items.append(
                DiscoveredItem(
                    url=url,
                    title=title,
                    source_id=self._config.source_id,
                    creation_time=creation_time,
                )
            )
        return items


class DiscoveryJob(Job):
    """
    Runs all configured DiscoverySource(s) and stores new URLs as PENDING NewsItems.
    Skips URLs already present in the repository.
    If since is provided, items published before that time are ignored.
    """

    def __init__(
        self,
        sources: list[DiscoverySource],
        repository: NewsItemRepository,
        since: datetime | None = None,
    ) -> None:
        self._sources = sources
        self._repository = repository
        self._since = since

    def run(self) -> None:
        for source in self._sources:
            discovered = source.discover()
            for item in discovered:
                if self._since and item.creation_time < self._since:
                    logger.debug("Skipping item outside time window: %s", item.url)
                    continue
                if self._repository.get(item.url) is not None:
                    logger.debug("Skipping already-known URL: %s", item.url)
                    continue
                news_item = NewsItem(
                    url=item.url,
                    title=item.title,
                    source_id=item.source_id,
                    status=NewsItemStatus.PENDING,
                    creation_time=item.creation_time,
                )
                self._repository.put(news_item)
                logger.info("Discovered: %s", item.url)
