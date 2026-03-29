import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import tweepy  # type: ignore[import-untyped]

from prometheus_backend.news_aggregator.jobs.discovery_job import (
    DiscoveredItem,
    DiscoverySource,
    RSSDiscoverySource,
    RSSFeedConfig,
)
from prometheus_backend.news_aggregator.models.news_item import SourceType
from prometheus_backend.news_aggregator.storage.watermark_repository import WatermarkRepository

logger = logging.getLogger(__name__)


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
                "start_time": last_crawl,
            }

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
