from datetime import datetime
from unittest.mock import MagicMock

from prometheus_backend.deduplication.deduplicator import Deduplicator, compute_hash
from prometheus_backend.news_aggregator.models.news_item import NewsItem


def make_item(
    title: str = "Test Title",
    raw_content: str = "Test content",
    url: str = "https://example.com/article",
) -> NewsItem:
    from datetime import timezone
    from prometheus_backend.news_aggregator.models.news_item import NewsItemStatus

    return NewsItem(
        url=url,
        title=title,
        source_id="test-source",
        status=NewsItemStatus.FETCHED,
        raw_content=raw_content,
        creation_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


# --- compute_hash ---


def test_hash_is_hex_string():
    item = make_item()
    h = compute_hash(item)
    assert isinstance(h, str)
    assert len(h) == 64  # SHA-256 hex digest


def test_hash_is_stable():
    item = make_item()
    assert compute_hash(item) == compute_hash(item)


def test_hash_differs_for_different_content():
    item1 = make_item(raw_content="alpha")
    item2 = make_item(raw_content="beta")
    assert compute_hash(item1) != compute_hash(item2)


def test_normalization_case_insensitive():
    lower = make_item(title="hello world", raw_content="foo bar")
    upper = make_item(title="HELLO WORLD", raw_content="FOO BAR")
    assert compute_hash(lower) == compute_hash(upper)


def test_normalization_whitespace():
    compact = make_item(title="hello world", raw_content="foo")
    spaced = make_item(title="hello   world", raw_content="  foo  ")
    assert compute_hash(compact) == compute_hash(spaced)


def test_normalization_newlines():
    normal = make_item(title="hello world", raw_content="foo bar")
    newlined = make_item(title="hello\nworld", raw_content="foo\nbar")
    assert compute_hash(normal) == compute_hash(newlined)


# --- Deduplicator ---


def test_is_duplicate_returns_false_for_new_item():
    repo = MagicMock()
    repo.contains.return_value = False
    dedup = Deduplicator(repo)
    assert dedup.is_duplicate(make_item()) is False


def test_is_duplicate_returns_true_after_mark_seen():
    repo = MagicMock()
    item = make_item()
    h = compute_hash(item)
    repo.contains.side_effect = lambda x: x == h
    dedup = Deduplicator(repo)
    dedup.mark_seen(item)
    assert dedup.is_duplicate(item) is True


def test_mark_seen_calls_repo_add():
    repo = MagicMock()
    item = make_item()
    dedup = Deduplicator(repo)
    dedup.mark_seen(item)
    repo.add.assert_called_once_with(compute_hash(item))


def test_is_duplicate_calls_repo_contains():
    repo = MagicMock()
    repo.contains.return_value = False
    item = make_item()
    dedup = Deduplicator(repo)
    dedup.is_duplicate(item)
    repo.contains.assert_called_once_with(compute_hash(item))
