"""Integration tests: full deduplication round-trip using LocalHashRepository."""

from datetime import datetime

from prometheus_backend.deduplication.deduplicator import Deduplicator, compute_hash
from prometheus_backend.storage.hash_repository_base import LocalHashRepository
from prometheus_backend.news_aggregator.models.news_item import NewsItem


def make_item(
    title: str, raw_content: str, source_ref: str = "https://example.com/article"
) -> NewsItem:
    from datetime import timezone
    from prometheus_backend.news_aggregator.models.news_item import NewsItemStatus, SourceType

    return NewsItem(
        source_ref=source_ref,
        source_type=SourceType.RSS,
        title=title,
        source_id="test-source",
        status=NewsItemStatus.FETCHED,
        raw_content=raw_content,
        creation_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


def test_two_distinct_items_and_one_duplicate(tmp_path):
    hash_file = tmp_path / "content_hashes.txt"
    repo = LocalHashRepository(str(hash_file))
    dedup = Deduplicator(repo)

    item_a = make_item(
        "Fed raises rates",
        "The Federal Reserve raised interest rates by 25bps.",
        source_ref="https://reuters.com/fed",
    )
    item_b = make_item(
        "Apple earnings beat",
        "Apple reported record Q4 earnings above consensus.",
        source_ref="https://reuters.com/apple",
    )
    item_a_dup = make_item(
        "Fed raises rates",
        "The Federal Reserve raised interest rates by 25bps.",
        source_ref="https://ft.com/fed",
    )

    # Nothing seen yet
    assert dedup.is_duplicate(item_a) is False
    assert dedup.is_duplicate(item_b) is False

    # Process item_a
    dedup.mark_seen(item_a)
    assert dedup.is_duplicate(item_a) is True
    assert dedup.is_duplicate(item_b) is False  # item_b still new

    # Process item_b
    dedup.mark_seen(item_b)
    assert dedup.is_duplicate(item_b) is True

    # Duplicate of item_a is correctly detected
    assert dedup.is_duplicate(item_a_dup) is True


def test_hash_file_contains_exactly_two_hashes(tmp_path):
    hash_file = tmp_path / "content_hashes.txt"
    repo = LocalHashRepository(str(hash_file))
    dedup = Deduplicator(repo)

    item_a = make_item("Story one", "Content one", source_ref="https://reuters.com/one")
    item_b = make_item("Story two", "Content two", source_ref="https://reuters.com/two")

    dedup.mark_seen(item_a)
    dedup.mark_seen(item_b)

    lines = [line for line in hash_file.read_text().splitlines() if line]
    assert len(lines) == 2
    assert compute_hash(item_a) in lines
    assert compute_hash(item_b) in lines


def test_state_restored_after_reinitialisation(tmp_path):
    hash_file = tmp_path / "content_hashes.txt"
    item = make_item("Persistent story", "Some content that was processed.")

    # First run: process the item
    repo1 = LocalHashRepository(str(hash_file))
    dedup1 = Deduplicator(repo1)
    dedup1.mark_seen(item)

    # Second run: new instances, same file
    repo2 = LocalHashRepository(str(hash_file))
    dedup2 = Deduplicator(repo2)
    assert dedup2.is_duplicate(item) is True


def test_mark_seen_not_called_on_duplicate_leaves_file_unchanged(tmp_path):
    hash_file = tmp_path / "content_hashes.txt"
    repo = LocalHashRepository(str(hash_file))
    dedup = Deduplicator(repo)

    item = make_item("Some title", "Some content")
    dedup.mark_seen(item)

    content_before = hash_file.read_text()

    # Attempting to mark the same item again should be idempotent
    dedup.mark_seen(item)

    assert hash_file.read_text() == content_before
