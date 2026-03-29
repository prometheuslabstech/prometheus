import pytest
from unittest.mock import MagicMock, call

from prometheus_backend.pipeline.base import Pipeline


def make_mock_job():
    job = MagicMock()
    job.run = MagicMock()
    return job


def test_runs_all_jobs():
    job_a, job_b = make_mock_job(), make_mock_job()
    Pipeline(jobs=[job_a, job_b]).run()
    job_a.run.assert_called_once()
    job_b.run.assert_called_once()


def test_runs_jobs_in_order():
    call_order = []
    job_a = MagicMock()
    job_a.run.side_effect = lambda: call_order.append("a")
    job_b = MagicMock()
    job_b.run.side_effect = lambda: call_order.append("b")
    Pipeline(jobs=[job_a, job_b]).run()
    assert call_order == ["a", "b"]


def test_empty_job_list_runs_without_error():
    Pipeline(jobs=[]).run()  # should not raise


def test_exception_from_job_propagates():
    job = make_mock_job()
    job.run.side_effect = RuntimeError("job failed")
    with pytest.raises(RuntimeError, match="job failed"):
        Pipeline(jobs=[job]).run()
