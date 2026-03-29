import logging
from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import feedparser
import tweepy  # type: ignore[import-untyped]

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

    source_ref: str             # URL for RSS; tweet ID for Twitter
    source_type: SourceType
    title: str
    source_id: str              # platform/feed label, e.g. "reuters.com", "twitter"
    creation_time: datetime
    author: Optional[str] = None  # None for RSS; "@Reuters" for Twitter


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
        crawl_time = datetime.now(timezone.utc)
        feed = feedparser.parse(self._config.feed_url)
        items = []
        for entry in feed.entries:
            url = entry.get("link", "")
            title = entry.get("title", "")
            if not url or not title:
                continue
            published = entry.get("published_parsed")
            if not published:
                logger.error("Article missing publish time, skipping: %s", url)
                continue
            creation_time = datetime(
                published[0],
                published[1],
                published[2],
                published[3],
                published[4],
                published[5],
                tzinfo=timezone.utc,
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
        self._watermark_repo.set(self._config.source_id, crawl_time)
        return items


@dataclass
class TwitterConfig:
    bearer_token: str
    user_handles: list[str]          # e.g. ["Reuters", "WSJ", "markets"]
    source_id: str = "twitter"
    max_results_per_user: int = 10   # X API: 5–100 per request


class TwitterDiscoverySource(DiscoverySource):
    """Discovers tweets from a list of subscribed Twitter/X user handles.

    Watermark key is "{source_id}:{handle}" per user, so each handle tracks
    its own crawl position independently.
    start_time is passed directly to the X API to avoid client-side filtering.
    """

    def __init__(
        self,
        config: TwitterConfig,
        watermark_repo: WatermarkRepository,
    ) -> None:
        self._config = config
        self._watermark_repo = watermark_repo
        self._client = tweepy.Client(bearer_token=config.bearer_token)

    def discover(self) -> list[DiscoveredItem]:
        items = []
        for handle in self._config.user_handles:
            watermark_key = f"{self._config.source_id}:{handle}"
            last_crawl = self._watermark_repo.get(watermark_key)
            crawl_time = datetime.now(timezone.utc)

            user_response = self._client.get_user(username=handle)
            if not user_response.data:
                logger.warning("Twitter user not found: @%s", handle)
                continue

            kwargs: dict = {
                "max_results": self._config.max_results_per_user,
                "tweet_fields": ["created_at"],
            }
            if last_crawl:
                kwargs["start_time"] = last_crawl

            response = self._client.get_users_tweets(user_response.data.id, **kwargs)
            if not response.data:
                self._watermark_repo.set(watermark_key, crawl_time)
                continue

            for tweet in response.data:
                creation_time = tweet.created_at or datetime.now(timezone.utc)
                items.append(
                    DiscoveredItem(
                        source_ref=str(tweet.id),
                        source_type=SourceType.TWITTER,
                        title=tweet.text[:120],
                        source_id=self._config.source_id,
                        author=f"@{handle}",
                        creation_time=creation_time,
                    )
                )

            self._watermark_repo.set(watermark_key, crawl_time)
            logger.info("Discovered %d tweets from @%s", len(response.data), handle)

        return items


class DiscoveryJob(Job):
    """
    Runs all configured DiscoverySource(s) and stores new items as PENDING NewsItems.
    Skips items already present in the repository as a secondary dedup guard.
    Time-window filtering is handled by each DiscoverySource via its watermark.
    """

    def __init__(
        self,
        sources: Sequence[DiscoverySource],
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
                    author=item.author,
                    status=NewsItemStatus.PENDING,
                    creation_time=item.creation_time,
                )
                self._repository.put(news_item)
                logger.info("Discovered: %s", item.source_ref)
