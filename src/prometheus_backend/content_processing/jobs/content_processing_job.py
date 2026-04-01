import logging
from datetime import datetime, timezone

from appdevcommons.unique_id import UniqueIdGenerator

from prometheus_backend.jobs.base import Job
from prometheus_backend.models.content import ContentItem, LLMContentItemOutput
from prometheus_backend.news_aggregator.models.news_item import NewsItem, NewsItemStatus
from prometheus_backend.news_aggregator.storage.news_item_repository import NewsItemRepository
from prometheus_backend.prompts.content_processing_prompt import SYSTEM_INSTRUCTION, user_message
from prometheus_backend.services.gemini import GeminiClient
from prometheus_backend.storage.local_file_system.content_item_store import ContentItemStore

logger = logging.getLogger(__name__)

_MAX_ANALYSIS_CHARS = 20_000


def _to_content_item(item: NewsItem, gemini: GeminiClient) -> ContentItem:
    response = gemini.client.models.generate_content(
        model=gemini.model_id,
        contents=user_message((item.raw_content or "")[:_MAX_ANALYSIS_CHARS]),
        config={
            "system_instruction": SYSTEM_INSTRUCTION,
            "response_mime_type": "application/json",
            "response_schema": LLMContentItemOutput,
        },
    )
    llm_output = LLMContentItemOutput.model_validate_json(response.text or "")
    return ContentItem(
        id=UniqueIdGenerator.generate_id(),
        url=item.source_ref,
        source_id=item.source_id,
        created_at=datetime.now(timezone.utc),
        content=item.raw_content or "",
        **llm_output.model_dump(),
    )


class ContentProcessingJob(Job):
    """Converts DEDUPLICATED NewsItems into ContentItems via Gemini and persists them."""

    def __init__(
        self,
        news_repo: NewsItemRepository,
        content_store: ContentItemStore,
        gemini: GeminiClient,
    ) -> None:
        self._news_repo = news_repo
        self._content_store = content_store
        self._gemini = gemini

    def run(self) -> None:
        items = self._news_repo.list(status=NewsItemStatus.DEDUPLICATED)
        total = len(items)
        processed = 0
        failed = 0

        for item in items:
            try:
                content_item = _to_content_item(item, self._gemini)
                self._content_store.put(content_item)
                self._news_repo.put(item.model_copy(update={"status": NewsItemStatus.PROCESSED}))
                logger.info("content_processing_job: processed source_ref=%s", item.source_ref)
                processed += 1
            except Exception as e:
                logger.warning(
                    "content_processing_job: failed source_ref=%s error=%s",
                    item.source_ref,
                    e,
                )
                self._news_repo.put(
                    item.model_copy(update={"status": NewsItemStatus.FAILED, "error": str(e)})
                )
                failed += 1

        logger.info(
            "content_processing_job summary: total=%d processed=%d failed=%d",
            total,
            processed,
            failed,
        )
