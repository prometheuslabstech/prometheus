from prometheus_backend.content_processing.jobs.content_processing_job import ContentProcessingJob
from prometheus_backend.content_processing.jobs.deduplication_job import DeduplicationJob
from prometheus_backend.news_aggregator.storage.news_item_repository import NewsItemRepository
from prometheus_backend.pipeline.base import Pipeline
from prometheus_backend.services.gemini import GeminiClient
from prometheus_backend.storage.hash_repository_base import HashRepository
from prometheus_backend.storage.local_file_system.content_item_store import ContentItemStore


def build_content_processing_pipeline(
    news_repo: NewsItemRepository,
    hash_repo: HashRepository,
    content_store: ContentItemStore,
    gemini: GeminiClient,
) -> Pipeline:
    return Pipeline(
        jobs=[
            DeduplicationJob(news_repo=news_repo, hash_repo=hash_repo),
            ContentProcessingJob(news_repo=news_repo, content_store=content_store, gemini=gemini),
        ],
        name="content_processing",
    )
