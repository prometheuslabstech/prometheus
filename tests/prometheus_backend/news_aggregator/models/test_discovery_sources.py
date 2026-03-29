from unittest.mock import MagicMock, patch

from prometheus_backend.news_aggregator.models.discovery_sources import YahooFinanceDiscoverySource


def make_watermark_repo():
    repo = MagicMock()
    repo.get.return_value = None
    return repo


def test_source_id_is_yahoo_finance():
    source = YahooFinanceDiscoverySource(watermark_repo=make_watermark_repo())
    assert source._config.source_id == "yahoo_finance"


def test_feed_url_is_yahoo_finance_rss():
    source = YahooFinanceDiscoverySource(watermark_repo=make_watermark_repo())
    assert source._config.feed_url == YahooFinanceDiscoverySource.RSS_URL


def test_watermark_repo_is_passed_through():
    watermark_repo = make_watermark_repo()
    source = YahooFinanceDiscoverySource(watermark_repo=watermark_repo)
    assert source._watermark_repo is watermark_repo
