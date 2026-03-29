import logging

from prometheus_backend.jobs.base import Job
from prometheus_backend.news_aggregator.models.news_item import NewsItemStatus, SourceType
from prometheus_backend.news_aggregator.storage.news_item_repository import (
    NewsItemRepository,
)
from prometheus_backend.services import tavily_search

logger = logging.getLogger(__name__)


class PageFetchJob(Job):
    """
    Fetches full content for all PENDING NewsItems.
    Dispatches to the appropriate fetcher based on source_type.
    Updates status to FETCHED on success, FAILED on error.
    """

    def __init__(self, repository: NewsItemRepository) -> None:
        self._repository = repository

    def run(self) -> None:
        pending = self._repository.list(status=NewsItemStatus.PENDING)
        logger.info("PageFetchJob: %d PENDING items to fetch", len(pending))

        for item in pending:
            try:
                raw_content = self._fetch(item.source_ref, item.source_type)
                updated = item.model_copy(
                    update={
                        "status": NewsItemStatus.FETCHED,
                        "raw_content": raw_content,
                        "error": None,
                    }
                )
                logger.info("Fetched: %s", item.source_ref)
            except Exception as e:
                updated = item.model_copy(
                    update={
                        "status": NewsItemStatus.FAILED,
                        "error": str(e),
                    }
                )
                logger.warning("Failed to fetch %s: %s", item.source_ref, e)

            self._repository.put(updated)

    def _fetch(self, source_ref: str, source_type: SourceType) -> str:
        """Dispatch to the appropriate fetcher based on source_type."""
        if source_type == SourceType.RSS:
            return tavily_search.extract(source_ref)
        raise NotImplementedError(f"No fetcher implemented for source_type: {source_type}")
