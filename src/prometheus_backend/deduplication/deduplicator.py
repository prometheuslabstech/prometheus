import hashlib
import re

from prometheus_backend.deduplication.hash_repository import ContentHashRepository
from prometheus_backend.news_ingestion.models import RawNewsItem


def _normalize(text: str) -> str:
    """Lowercase and collapse all whitespace to a single space."""
    return re.sub(r"\s+", " ", text.lower()).strip()


def compute_hash(item: RawNewsItem) -> str:
    """Compute a SHA-256 hash of the normalized title + raw_content of a RawNewsItem."""
    normalized = _normalize(item.title + " " + item.raw_content)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


class Deduplicator:
    """Checks and records seen content hashes to prevent duplicate processing."""

    def __init__(self, repo: ContentHashRepository) -> None:
        self._repo = repo

    def is_duplicate(self, item: RawNewsItem) -> bool:
        """Return True if this item has already been processed."""
        return self._repo.contains(compute_hash(item))

    def mark_seen(self, item: RawNewsItem) -> None:
        """Record this item as seen so future duplicates are skipped."""
        self._repo.add(compute_hash(item))
