import logging

from prometheus_backend.jobs.base import Job
from prometheus_backend.news_aggregator.models.news_item import NewsItemStatus
from prometheus_backend.news_aggregator.storage.news_item_repository import (
    NewsItemRepository,
)
from prometheus_backend.services import tavily_search

logger = logging.getLogger(__name__)


class PageFetchJob(Job):
    """
    Fetches full page content for all PENDING NewsItems.
    Updates status to FETCHED on success, FAILED on error.
    """

    def __init__(self, repository: NewsItemRepository) -> None:
        self._repository = repository

    def run(self) -> None:
        pending = self._repository.list(status=NewsItemStatus.PENDING)
        logger.info("PageFetchJob: %d PENDING items to fetch", len(pending))

        for item in pending:
            try:
                raw_content = tavily_search.extract(item.url)
                updated = item.model_copy(
                    update={
                        "status": NewsItemStatus.FETCHED,
                        "raw_content": raw_content,
                        "error": None,
                    }
                )
                logger.info("Fetched: %s", item.url)
            except Exception as e:
                updated = item.model_copy(
                    update={
                        "status": NewsItemStatus.FAILED,
                        "error": str(e),
                    }
                )
                logger.warning("Failed to fetch %s: %s", item.url, e)

            self._repository.put(updated)
