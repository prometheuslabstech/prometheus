from unittest.mock import MagicMock

from prometheus_backend.news_aggregator.pipeline import build_news_aggregator_pipeline
from prometheus_backend.news_aggregator.jobs.discovery_job import DiscoveryJob
from prometheus_backend.news_aggregator.jobs.page_fetch_job import PageFetchJob
from prometheus_backend.pipeline.base import Pipeline


def make_mock_sources():
    return [MagicMock()]


def make_mock_repo():
    return MagicMock()


def test_returns_pipeline_instance():
    pipeline = build_news_aggregator_pipeline(
        sources=make_mock_sources(), repository=make_mock_repo()
    )
    assert isinstance(pipeline, Pipeline)


def test_pipeline_has_two_jobs():
    pipeline = build_news_aggregator_pipeline(
        sources=make_mock_sources(), repository=make_mock_repo()
    )
    assert len(pipeline.jobs) == 2


def test_first_job_is_discovery():
    pipeline = build_news_aggregator_pipeline(
        sources=make_mock_sources(), repository=make_mock_repo()
    )
    assert isinstance(pipeline.jobs[0], DiscoveryJob)


def test_second_job_is_page_fetch():
    pipeline = build_news_aggregator_pipeline(
        sources=make_mock_sources(), repository=make_mock_repo()
    )
    assert isinstance(pipeline.jobs[1], PageFetchJob)
