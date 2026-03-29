from prometheus_backend.news_aggregator.jobs.discovery_job import RSSDiscoverySource, RSSFeedConfig
from prometheus_backend.news_aggregator.storage.watermark_repository import WatermarkRepository


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
