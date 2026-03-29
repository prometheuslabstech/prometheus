from unittest.mock import MagicMock

from prometheus_backend.content_processing.jobs.deduplication_job import DeduplicationJob
from prometheus_backend.content_processing.pipeline import build_content_processing_pipeline
from prometheus_backend.pipeline.base import Pipeline


def make_mock_news_repo():
    return MagicMock()


def make_mock_hash_repo():
    return MagicMock()


def test_returns_pipeline_instance():
    pipeline = build_content_processing_pipeline(
        news_repo=make_mock_news_repo(), hash_repo=make_mock_hash_repo()
    )
    assert isinstance(pipeline, Pipeline)


def test_pipeline_has_one_job():
    pipeline = build_content_processing_pipeline(
        news_repo=make_mock_news_repo(), hash_repo=make_mock_hash_repo()
    )
    assert len(pipeline.jobs) == 1


def test_first_job_is_deduplication():
    pipeline = build_content_processing_pipeline(
        news_repo=make_mock_news_repo(), hash_repo=make_mock_hash_repo()
    )
    assert isinstance(pipeline.jobs[0], DeduplicationJob)


def test_pipeline_name():
    pipeline = build_content_processing_pipeline(
        news_repo=make_mock_news_repo(), hash_repo=make_mock_hash_repo()
    )
    assert pipeline.name == "content_processing"
