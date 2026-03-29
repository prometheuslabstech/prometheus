from datetime import datetime, timezone
from unittest.mock import MagicMock

from prometheus_backend.content_processing.jobs.deduplication_job import DeduplicationJob, compute_hash
from prometheus_backend.news_aggregator.models.news_item import NewsItem, NewsItemStatus, SourceType


def make_item(
    title: str = "Test Title",
    raw_content: str = "Test content",
    source_ref: str = "https://example.com/article",
    status: NewsItemStatus = NewsItemStatus.FETCHED,
) -> NewsItem:
    return NewsItem(
        source_ref=source_ref,
        source_type=SourceType.RSS,
        title=title,
        source_id="test-source",
        status=status,
        raw_content=raw_content if status == NewsItemStatus.FETCHED else None,
        creation_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


def make_news_repo(items: list[NewsItem]):
    repo = MagicMock()
    repo.list.return_value = items
    return repo


def make_hash_repo(seen_hashes: set[str] | None = None):
    seen = seen_hashes or set()
    repo = MagicMock()
    repo.contains.side_effect = lambda h: h in seen
    return repo


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


# --- DeduplicationJob ---


def test_unique_item_is_marked_deduplicated():
    item = make_item()
    news_repo = make_news_repo([item])
    hash_repo = make_hash_repo()
    DeduplicationJob(news_repo, hash_repo).run()
    stored = news_repo.put.call_args[0][0]
    assert stored.status == NewsItemStatus.DEDUPLICATED
    assert stored.error is None


def test_unique_item_hash_is_added_to_hash_repo():
    item = make_item()
    news_repo = make_news_repo([item])
    hash_repo = make_hash_repo()
    DeduplicationJob(news_repo, hash_repo).run()
    hash_repo.add.assert_called_once_with(compute_hash(item))


def test_duplicate_item_is_deleted():
    item = make_item()
    h = compute_hash(item)
    news_repo = make_news_repo([item])
    hash_repo = make_hash_repo(seen_hashes={h})
    DeduplicationJob(news_repo, hash_repo).run()
    news_repo.delete.assert_called_once_with(item.id)
    news_repo.put.assert_not_called()


def test_duplicate_item_does_not_add_to_hash_repo():
    item = make_item()
    h = compute_hash(item)
    news_repo = make_news_repo([item])
    hash_repo = make_hash_repo(seen_hashes={h})
    DeduplicationJob(news_repo, hash_repo).run()
    hash_repo.add.assert_not_called()


def test_job_processes_only_fetched_items():
    news_repo = make_news_repo([])
    hash_repo = make_hash_repo()
    DeduplicationJob(news_repo, hash_repo).run()
    news_repo.list.assert_called_once_with(status=NewsItemStatus.FETCHED)


def test_job_processes_multiple_items():
    item_a = make_item(source_ref="https://example.com/a", title="Story A")
    item_b = make_item(source_ref="https://example.com/b", title="Story B")
    news_repo = make_news_repo([item_a, item_b])
    hash_repo = make_hash_repo()
    DeduplicationJob(news_repo, hash_repo).run()
    assert news_repo.put.call_count == 2


def test_job_deletes_second_identical_item():
    item_a = make_item(source_ref="https://example.com/a")
    item_b = make_item(source_ref="https://example.com/b")  # same title+content
    seen: set[str] = set()

    hash_repo = MagicMock()
    hash_repo.contains.side_effect = lambda h: h in seen
    hash_repo.add.side_effect = lambda h: seen.add(h)

    news_repo = make_news_repo([item_a, item_b])
    DeduplicationJob(news_repo, hash_repo).run()

    assert news_repo.put.call_count == 1
    assert news_repo.put.call_args[0][0].status == NewsItemStatus.DEDUPLICATED
    news_repo.delete.assert_called_once_with(item_b.id)


def test_job_does_nothing_when_no_fetched_items():
    news_repo = make_news_repo([])
    hash_repo = make_hash_repo()
    DeduplicationJob(news_repo, hash_repo).run()
    news_repo.put.assert_not_called()
    hash_repo.add.assert_not_called()


# --- summary logging ---


def test_summary_logs_correct_counts(caplog):
    import logging
    item_a = make_item(source_ref="https://example.com/a", title="Story A")
    item_b = make_item(source_ref="https://example.com/b", title="Story B")
    item_c = make_item(source_ref="https://example.com/c", title="Story A")  # duplicate of item_a
    seen: set[str] = set()

    hash_repo = MagicMock()
    hash_repo.contains.side_effect = lambda h: h in seen
    hash_repo.add.side_effect = lambda h: seen.add(h)

    news_repo = make_news_repo([item_a, item_b, item_c])
    with caplog.at_level(logging.INFO):
        DeduplicationJob(news_repo, hash_repo).run()

    summary = next(r.message for r in caplog.records if "summary" in r.message)
    assert "fetched=3" in summary
    assert "deduplicated=2" in summary
    assert "deleted(duplicate)=1" in summary
