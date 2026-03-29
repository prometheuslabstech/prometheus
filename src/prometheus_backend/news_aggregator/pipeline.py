from collections.abc import Sequence

from prometheus_backend.news_aggregator.jobs.discovery_job import DiscoveryJob, DiscoverySource
from prometheus_backend.news_aggregator.jobs.page_fetch_job import PageFetchJob
from prometheus_backend.news_aggregator.storage.news_item_repository import NewsItemRepository
from prometheus_backend.pipeline.base import Pipeline


def build_news_aggregator_pipeline(
    sources: Sequence[DiscoverySource],
    repository: NewsItemRepository,
) -> Pipeline:
    return Pipeline(
        jobs=[
            DiscoveryJob(sources=sources, repository=repository),
            PageFetchJob(repository=repository),
        ],
        name="news_aggregator",
    )
