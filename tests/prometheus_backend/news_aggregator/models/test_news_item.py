from datetime import datetime, timedelta, timezone

import pytest

from prometheus_backend.news_aggregator.models.news_item import NewsItem, NewsItemStatus


def make_item(**overrides) -> NewsItem:
    defaults = dict(
        url="https://reuters.com/article/apple-tsmc",
        title="Apple secures TSMC capacity",
        source_id="reuters.com",
        status=NewsItemStatus.FETCHED,
        raw_content="Apple has locked in TSMC N2 node capacity through 2026.",
        creation_time=datetime.now(timezone.utc) - timedelta(minutes=5),
    )
    return NewsItem(**{**defaults, **overrides})


# --- url ---


def test_valid_url_accepted():
    make_item(url="https://reuters.com/article/apple-tsmc")


def test_url_missing_scheme_raises():
    with pytest.raises(ValueError, match="Invalid URL"):
        make_item(url="reuters.com/article/apple-tsmc")


def test_url_missing_netloc_raises():
    with pytest.raises(ValueError, match="Invalid URL"):
        make_item(url="https://")


def test_url_empty_raises():
    with pytest.raises(ValueError, match="Invalid URL"):
        make_item(url="")


# --- title ---


def test_empty_title_raises():
    with pytest.raises(ValueError, match="title"):
        make_item(title="")


def test_whitespace_only_title_raises():
    with pytest.raises(ValueError, match="title"):
        make_item(title="   ")


# --- source_id ---


def test_empty_source_id_raises():
    with pytest.raises(ValueError, match="source_id"):
        make_item(source_id="")


def test_whitespace_only_source_id_raises():
    with pytest.raises(ValueError, match="source_id"):
        make_item(source_id="   ")


# --- raw_content ---


def test_empty_raw_content_raises():
    with pytest.raises(ValueError, match="raw_content"):
        make_item(raw_content="")


def test_whitespace_only_raw_content_raises():
    with pytest.raises(ValueError, match="raw_content"):
        make_item(raw_content="   ")


def test_raw_content_none_accepted_when_pending():
    make_item(status=NewsItemStatus.PENDING, raw_content=None)


def test_raw_content_none_raises_when_fetched():
    with pytest.raises(ValueError, match="raw_content"):
        make_item(status=NewsItemStatus.FETCHED, raw_content=None)


# --- creation_time ---


def test_past_creation_time_accepted():
    make_item(creation_time=datetime.now(timezone.utc) - timedelta(seconds=1))


def test_future_creation_time_raises():
    with pytest.raises(ValueError, match="creation_time"):
        make_item(creation_time=datetime.now(timezone.utc) + timedelta(seconds=10))


# --- status ---


def test_pending_item_has_no_raw_content_by_default():
    item = make_item(status=NewsItemStatus.PENDING, raw_content=None)
    assert item.raw_content is None


def test_fetched_item_has_raw_content():
    item = make_item(status=NewsItemStatus.FETCHED)
    assert item.raw_content is not None


def test_failed_item_can_store_error():
    item = make_item(
        status=NewsItemStatus.FAILED, raw_content=None, error="Tavily timeout"
    )
    assert item.error == "Tavily timeout"


def test_processed_item_accepted():
    make_item(status=NewsItemStatus.PROCESSED)
