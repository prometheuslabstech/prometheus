from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from prometheus_backend.news_aggregator.jobs.discovery_job import (
    DiscoveredItem,
    DiscoveryJob,
    DiscoverySource,
    RSSDiscoverySource,
    RSSFeedConfig,
)
from prometheus_backend.news_aggregator.models.news_item import NewsItemStatus, SourceType

# ── helpers ───────────────────────────────────────────────────────────────────

FEED_URL = "https://feeds.reuters.com/reuters/businessNews"
CONFIG = RSSFeedConfig(source_id="reuters.com", feed_url=FEED_URL)

PUBLISHED = (2026, 3, 15, 10, 30, 0, 0, 0, 0)
CREATION_TIME = datetime(2026, 3, 15, 10, 30, 0, tzinfo=timezone.utc)
# Watermark older than CREATION_TIME — used to let test items pass through
WATERMARK_BEFORE = datetime(2026, 3, 15, 9, 0, 0, tzinfo=timezone.utc)


def make_entry(
    link="https://reuters.com/article/1",
    title="Test Title",
    published_parsed=PUBLISHED,
):
    entry = {"link": link, "title": title}
    if published_parsed is not None:
        entry["published_parsed"] = published_parsed
    return entry


def make_mock_feed(entries):
    feed = MagicMock()
    feed.entries = entries
    return feed


def make_mock_source(items: list[DiscoveredItem]):
    source = MagicMock(spec=DiscoverySource)
    source.discover.return_value = items
    return source


def make_mock_repo(existing_refs: set[str] | None = None):
    repo = MagicMock()
    existing_refs = existing_refs or set()
    repo.get.side_effect = lambda ref: MagicMock() if ref in existing_refs else None
    return repo


def make_watermark_repo(last_crawl: datetime | None = None):
    repo = MagicMock()
    # Default mirrors LocalWatermarkRepository: 48h lookback when no watermark exists
    repo.get.return_value = last_crawl or (datetime.now(timezone.utc) - timedelta(hours=48))
    return repo


def make_discovered_item(
    source_ref="https://reuters.com/article/1",
    source_type=SourceType.RSS,
    title="Test Title",
    source_id="reuters.com",
    author=None,
):
    return DiscoveredItem(
        source_ref=source_ref,
        source_type=source_type,
        title=title,
        source_id=source_id,
        author=author,
        creation_time=CREATION_TIME,
    )


# ── DiscoverySource ABC ───────────────────────────────────────────────────────


def test_cannot_instantiate_discovery_source_without_implementing_discover():
    with pytest.raises(TypeError):
        DiscoverySource()


# ── RSSDiscoverySource ────────────────────────────────────────────────────────


@patch("prometheus_backend.news_aggregator.jobs.discovery_job.feedparser.parse")
def test_rss_returns_discovered_item_for_valid_entry(mock_parse):
    mock_parse.return_value = make_mock_feed([make_entry()])
    items = RSSDiscoverySource(CONFIG, make_watermark_repo(last_crawl=WATERMARK_BEFORE)).discover()
    assert len(items) == 1
    assert items[0].source_ref == "https://reuters.com/article/1"
    assert items[0].source_type == SourceType.RSS
    assert items[0].title == "Test Title"
    assert items[0].source_id == "reuters.com"


@patch("prometheus_backend.news_aggregator.jobs.discovery_job.feedparser.parse")
def test_rss_skips_entry_missing_url(mock_parse):
    mock_parse.return_value = make_mock_feed([make_entry(link="")])
    items = RSSDiscoverySource(CONFIG, make_watermark_repo()).discover()
    assert items == []


@patch("prometheus_backend.news_aggregator.jobs.discovery_job.feedparser.parse")
def test_rss_skips_entry_missing_title(mock_parse):
    mock_parse.return_value = make_mock_feed([make_entry(title="")])
    items = RSSDiscoverySource(CONFIG, make_watermark_repo()).discover()
    assert items == []


@patch("prometheus_backend.news_aggregator.jobs.discovery_job.feedparser.parse")
def test_rss_skips_entry_missing_publish_time(mock_parse):
    mock_parse.return_value = make_mock_feed([make_entry(published_parsed=None)])
    items = RSSDiscoverySource(CONFIG, make_watermark_repo()).discover()
    assert items == []


@patch("prometheus_backend.news_aggregator.jobs.discovery_job.feedparser.parse")
def test_rss_logs_error_for_missing_publish_time(mock_parse, caplog):
    import logging
    mock_parse.return_value = make_mock_feed([make_entry(published_parsed=None)])
    with caplog.at_level(logging.ERROR):
        RSSDiscoverySource(CONFIG, make_watermark_repo()).discover()
    assert any("missing publish time" in r.message for r in caplog.records)


@patch("prometheus_backend.news_aggregator.jobs.discovery_job.feedparser.parse")
def test_rss_uses_published_parsed_for_creation_time(mock_parse):
    mock_parse.return_value = make_mock_feed([make_entry(published_parsed=PUBLISHED)])
    items = RSSDiscoverySource(CONFIG, make_watermark_repo(last_crawl=WATERMARK_BEFORE)).discover()
    assert items[0].creation_time == CREATION_TIME


@patch("prometheus_backend.news_aggregator.jobs.discovery_job.feedparser.parse")
def test_rss_returns_empty_list_when_feed_has_no_entries(mock_parse):
    mock_parse.return_value = make_mock_feed([])
    assert RSSDiscoverySource(CONFIG, make_watermark_repo()).discover() == []


@patch("prometheus_backend.news_aggregator.jobs.discovery_job.feedparser.parse")
def test_rss_returns_multiple_items(mock_parse):
    mock_parse.return_value = make_mock_feed(
        [
            make_entry(link="https://reuters.com/1", title="Story One"),
            make_entry(link="https://reuters.com/2", title="Story Two"),
        ]
    )
    items = RSSDiscoverySource(CONFIG, make_watermark_repo(last_crawl=WATERMARK_BEFORE)).discover()
    assert len(items) == 2


# ── RSSDiscoverySource watermark ──────────────────────────────────────────────


@patch("prometheus_backend.news_aggregator.jobs.discovery_job.feedparser.parse")
def test_rss_returns_items_within_default_lookback_when_no_watermark(mock_parse):
    # When no watermark exists, repo returns now-48h; items within that window are included.
    # Use WATERMARK_BEFORE so CREATION_TIME passes the filter.
    mock_parse.return_value = make_mock_feed([make_entry()])
    items = RSSDiscoverySource(CONFIG, make_watermark_repo(last_crawl=WATERMARK_BEFORE)).discover()
    assert len(items) == 1


@patch("prometheus_backend.news_aggregator.jobs.discovery_job.feedparser.parse")
def test_rss_includes_item_published_after_watermark(mock_parse):
    watermark = datetime(2026, 3, 15, 10, 0, 0, tzinfo=timezone.utc)
    # CREATION_TIME (10:30) is after watermark (10:00)
    mock_parse.return_value = make_mock_feed([make_entry()])
    items = RSSDiscoverySource(CONFIG, make_watermark_repo(last_crawl=watermark)).discover()
    assert len(items) == 1


@patch("prometheus_backend.news_aggregator.jobs.discovery_job.feedparser.parse")
def test_rss_excludes_item_published_at_watermark(mock_parse):
    # CREATION_TIME == watermark → should be filtered (<=)
    mock_parse.return_value = make_mock_feed([make_entry()])
    items = RSSDiscoverySource(CONFIG, make_watermark_repo(last_crawl=CREATION_TIME)).discover()
    assert items == []


@patch("prometheus_backend.news_aggregator.jobs.discovery_job.feedparser.parse")
def test_rss_excludes_item_published_before_watermark(mock_parse):
    watermark = datetime(2026, 3, 15, 11, 0, 0, tzinfo=timezone.utc)
    # CREATION_TIME (10:30) is before watermark (11:00)
    mock_parse.return_value = make_mock_feed([make_entry()])
    items = RSSDiscoverySource(CONFIG, make_watermark_repo(last_crawl=watermark)).discover()
    assert items == []


@patch("prometheus_backend.news_aggregator.jobs.discovery_job.datetime")
@patch("prometheus_backend.news_aggregator.jobs.discovery_job.feedparser.parse")
def test_rss_sets_watermark_to_crawl_time_not_publish_time(mock_parse, mock_datetime):
    crawl_time = datetime(2026, 3, 15, 12, 0, 0, tzinfo=timezone.utc)
    mock_datetime.now.return_value = crawl_time
    mock_datetime.side_effect = lambda *a, **kw: datetime(*a, **kw)
    mock_parse.return_value = make_mock_feed([make_entry()])
    watermark_repo = make_watermark_repo()
    RSSDiscoverySource(CONFIG, watermark_repo).discover()
    watermark_repo.set.assert_called_once_with("reuters.com", crawl_time)


@patch("prometheus_backend.news_aggregator.jobs.discovery_job.feedparser.parse")
def test_rss_sets_watermark_even_when_no_items_found(mock_parse):
    mock_parse.return_value = make_mock_feed([])
    watermark_repo = make_watermark_repo()
    RSSDiscoverySource(CONFIG, watermark_repo).discover()
    watermark_repo.set.assert_called_once()


# ── DiscoveryJob ──────────────────────────────────────────────────────────────


def test_discovery_job_stores_new_item_as_pending():
    repo = make_mock_repo()
    DiscoveryJob(sources=[make_mock_source([make_discovered_item()])], repository=repo).run()
    repo.put.assert_called_once()
    assert repo.put.call_args[0][0].status == NewsItemStatus.PENDING


def test_discovery_job_skips_existing_ref():
    ref = "https://reuters.com/article/1"
    repo = make_mock_repo(existing_refs={ref})
    DiscoveryJob(
        sources=[make_mock_source([make_discovered_item(source_ref=ref)])],
        repository=repo,
    ).run()
    repo.put.assert_not_called()


def test_discovery_job_calls_discover_on_all_sources():
    source_a = make_mock_source([make_discovered_item(source_ref="https://reuters.com/1")])
    source_b = make_mock_source([make_discovered_item(source_ref="https://ft.com/1")])
    DiscoveryJob(sources=[source_a, source_b], repository=make_mock_repo()).run()
    source_a.discover.assert_called_once()
    source_b.discover.assert_called_once()


def test_discovery_job_stores_nothing_when_source_returns_empty():
    repo = make_mock_repo()
    DiscoveryJob(sources=[make_mock_source([])], repository=repo).run()
    repo.put.assert_not_called()


def test_discovery_job_stores_items_from_multiple_sources():
    source_a = make_mock_source([make_discovered_item(source_ref="https://reuters.com/1")])
    source_b = make_mock_source([make_discovered_item(source_ref="https://ft.com/1")])
    repo = make_mock_repo()
    DiscoveryJob(sources=[source_a, source_b], repository=repo).run()
    assert repo.put.call_count == 2


def test_discovery_job_stores_correct_fields():
    item = make_discovered_item(
        source_ref="https://reuters.com/1",
        source_type=SourceType.RSS,
        title="Apple news",
        source_id="reuters.com",
    )
    repo = make_mock_repo()
    DiscoveryJob(sources=[make_mock_source([item])], repository=repo).run()
    stored = repo.put.call_args[0][0]
    assert stored.source_ref == "https://reuters.com/1"
    assert stored.source_type == SourceType.RSS
    assert stored.title == "Apple news"
    assert stored.source_id == "reuters.com"
    assert stored.status == NewsItemStatus.PENDING


def test_discovery_job_stores_author_for_twitter_item():
    item = make_discovered_item(
        source_ref="1234567890",
        source_type=SourceType.TWITTER,
        source_id="twitter",
        author="@Reuters",
    )
    repo = make_mock_repo()
    DiscoveryJob(sources=[make_mock_source([item])], repository=repo).run()
    stored = repo.put.call_args[0][0]
    assert stored.author == "@Reuters"


def test_discovery_job_author_is_none_for_rss_item():
    item = make_discovered_item(author=None)
    repo = make_mock_repo()
    DiscoveryJob(sources=[make_mock_source([item])], repository=repo).run()
    stored = repo.put.call_args[0][0]
    assert stored.author is None
