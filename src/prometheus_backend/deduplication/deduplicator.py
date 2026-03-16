import hashlib
import re

from prometheus_backend.storage.hash_repository_base import HashRepository
from prometheus_backend.news_aggregator.models.news_item import NewsItem


def _normalize(text: str) -> str:
    """Lowercase and collapse all whitespace to a single space."""
    return re.sub(r"\s+", " ", text.lower()).strip()


def compute_hash(item: NewsItem) -> str:
    """Compute a SHA-256 hash of the normalized title + raw_content of a NewsItem."""
    normalized = _normalize(item.title + " " + (item.raw_content or ""))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


class Deduplicator:
    """Checks and records seen content hashes to prevent duplicate processing."""

    def __init__(self, repo: HashRepository) -> None:
        self._repo = repo

    def is_duplicate(self, item: NewsItem) -> bool:
        """Return True if this item has already been processed."""
        return self._repo.contains(compute_hash(item))

    def mark_seen(self, item: NewsItem) -> None:
        """Record this item as seen so future duplicates are skipped."""
        self._repo.add(compute_hash(item))
