"""Integration tests: full deduplication round-trip using LocalContentHashRepository."""
from datetime import datetime

from prometheus_backend.deduplication.deduplicator import Deduplicator, compute_hash
from prometheus_backend.deduplication.hash_repository import LocalContentHashRepository
from prometheus_backend.news_ingestion.models import RawNewsItem


def make_item(title: str, raw_content: str) -> RawNewsItem:
    return RawNewsItem(
        url="https://example.com",
        title=title,
        source_id="test-source",
        raw_content=raw_content,
        fetched_at=datetime(2026, 1, 1),
    )


def test_two_distinct_items_and_one_duplicate(tmp_path):
    hash_file = tmp_path / "content_hashes.txt"
    repo = LocalContentHashRepository(str(hash_file))
    dedup = Deduplicator(repo)

    item_a = make_item("Fed raises rates", "The Federal Reserve raised interest rates by 25bps.")
    item_b = make_item("Apple earnings beat", "Apple reported record Q4 earnings above consensus.")
    item_a_dup = make_item("Fed raises rates", "The Federal Reserve raised interest rates by 25bps.")

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
    repo = LocalContentHashRepository(str(hash_file))
    dedup = Deduplicator(repo)

    item_a = make_item("Story one", "Content one")
    item_b = make_item("Story two", "Content two")

    dedup.mark_seen(item_a)
    dedup.mark_seen(item_b)

    lines = [l for l in hash_file.read_text().splitlines() if l]
    assert len(lines) == 2
    assert compute_hash(item_a) in lines
    assert compute_hash(item_b) in lines


def test_state_restored_after_reinitialisation(tmp_path):
    hash_file = tmp_path / "content_hashes.txt"
    item = make_item("Persistent story", "Some content that was processed.")

    # First run: process the item
    repo1 = LocalContentHashRepository(str(hash_file))
    dedup1 = Deduplicator(repo1)
    dedup1.mark_seen(item)

    # Second run: new instances, same file
    repo2 = LocalContentHashRepository(str(hash_file))
    dedup2 = Deduplicator(repo2)
    assert dedup2.is_duplicate(item) is True


def test_mark_seen_not_called_on_duplicate_leaves_file_unchanged(tmp_path):
    hash_file = tmp_path / "content_hashes.txt"
    repo = LocalContentHashRepository(str(hash_file))
    dedup = Deduplicator(repo)

    item = make_item("Some title", "Some content")
    dedup.mark_seen(item)

    content_before = hash_file.read_text()

    # Attempting to mark the same item again should be idempotent
    dedup.mark_seen(item)

    assert hash_file.read_text() == content_before
