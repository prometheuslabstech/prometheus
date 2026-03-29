from datetime import datetime, timedelta, timezone

import pytest

from prometheus_backend.news_aggregator.models.news_item import (
    NewsItem,
    NewsItemStatus,
    SourceType,
)


def make_item(**overrides) -> NewsItem:
    defaults = dict(
        source_ref="https://reuters.com/article/apple-tsmc",
        source_type=SourceType.RSS,
        title="Apple secures TSMC capacity",
        source_id="reuters.com",
        status=NewsItemStatus.FETCHED,
        raw_content="Apple has locked in TSMC N2 node capacity through 2026.",
        creation_time=datetime.now(timezone.utc) - timedelta(minutes=5),
    )
    return NewsItem(**{**defaults, **overrides})


# --- source_ref ---


def test_valid_source_ref_accepted():
    make_item(source_ref="https://reuters.com/article/apple-tsmc")


def test_tweet_id_accepted_as_source_ref():
    make_item(source_ref="1234567890", source_type=SourceType.TWITTER)


def test_empty_source_ref_raises():
    with pytest.raises(ValueError, match="source_ref"):
        make_item(source_ref="")


def test_whitespace_only_source_ref_raises():
    with pytest.raises(ValueError, match="source_ref"):
        make_item(source_ref="   ")


# --- source_type ---


def test_rss_source_type_accepted():
    make_item(source_type=SourceType.RSS)


def test_twitter_source_type_accepted():
    make_item(source_ref="1234567890", source_type=SourceType.TWITTER)


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


# --- author ---


def test_author_none_by_default():
    item = make_item()
    assert item.author is None


def test_author_set_for_twitter_item():
    item = make_item(source_ref="1234567890", source_type=SourceType.TWITTER, author="@Reuters")
    assert item.author == "@Reuters"


# --- id property ---


def test_id_returns_source_ref():
    item = make_item(source_ref="https://reuters.com/article/apple-tsmc")
    assert item.id == "https://reuters.com/article/apple-tsmc"


def test_id_returns_tweet_id_for_twitter():
    item = make_item(source_ref="1234567890", source_type=SourceType.TWITTER)
    assert item.id == "1234567890"
