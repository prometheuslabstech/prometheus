import hashlib
import logging
import re

from prometheus_backend.jobs.base import Job
from prometheus_backend.news_aggregator.models.news_item import NewsItem, NewsItemStatus
from prometheus_backend.news_aggregator.storage.news_item_repository import NewsItemRepository
from prometheus_backend.storage.hash_repository_base import HashRepository

logger = logging.getLogger(__name__)


def _normalize(text: str) -> str:
    """Lowercase and collapse all whitespace to a single space."""
    return re.sub(r"\s+", " ", text.lower()).strip()


def compute_hash(item: NewsItem) -> str:
    """Compute a SHA-256 hash of the normalized title + raw_content of a NewsItem."""
    normalized = _normalize(item.title + " " + (item.raw_content or ""))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


class DeduplicationJob(Job):
    """Marks FETCHED items as DEDUPLICATED or FAILED (duplicate) based on content hash."""

    def __init__(self, news_repo: NewsItemRepository, hash_repo: HashRepository) -> None:
        self._news_repo = news_repo
        self._hash_repo = hash_repo

    def run(self) -> None:
        items = self._news_repo.list(status=NewsItemStatus.FETCHED)
        total = len(items)
        deduplicated = 0
        deleted = 0

        for item in items:
            h = compute_hash(item)
            if self._hash_repo.contains(h):
                logger.info("deduplication_job: duplicate detected, deleting source_ref=%s", item.source_ref)
                self._news_repo.delete(item.id)
                deleted += 1
            else:
                self._hash_repo.add(h)
                self._news_repo.put(item.model_copy(update={"status": NewsItemStatus.DEDUPLICATED}))
                deduplicated += 1

        logger.info(
            "deduplication_job summary: fetched=%d deduplicated=%d deleted(duplicate)=%d",
            total, deduplicated, deleted,
        )
