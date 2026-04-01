from unittest.mock import MagicMock

from prometheus_backend.content_processing.jobs.content_processing_job import ContentProcessingJob
from prometheus_backend.content_processing.jobs.deduplication_job import DeduplicationJob
from prometheus_backend.content_processing.pipeline import build_content_processing_pipeline
from prometheus_backend.pipeline.base import Pipeline


def make_pipeline():
    return build_content_processing_pipeline(
        news_repo=MagicMock(),
        hash_repo=MagicMock(),
        content_store=MagicMock(),
        gemini=MagicMock(),
    )


def test_returns_pipeline_instance():
    assert isinstance(make_pipeline(), Pipeline)


def test_pipeline_has_two_jobs():
    assert len(make_pipeline().jobs) == 2


def test_first_job_is_deduplication():
    assert isinstance(make_pipeline().jobs[0], DeduplicationJob)


def test_second_job_is_content_processing():
    assert isinstance(make_pipeline().jobs[1], ContentProcessingJob)


def test_pipeline_name():
    assert make_pipeline().name == "content_processing"
