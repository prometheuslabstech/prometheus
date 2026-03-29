from prometheus_backend.content_processing.jobs.deduplication_job import DeduplicationJob
from prometheus_backend.news_aggregator.storage.news_item_repository import NewsItemRepository
from prometheus_backend.pipeline.base import Pipeline
from prometheus_backend.storage.hash_repository_base import HashRepository


def build_content_processing_pipeline(
    news_repo: NewsItemRepository,
    hash_repo: HashRepository,
) -> Pipeline:
    return Pipeline(
        jobs=[
            DeduplicationJob(news_repo=news_repo, hash_repo=hash_repo),
        ],
        name="content_processing",
    )
