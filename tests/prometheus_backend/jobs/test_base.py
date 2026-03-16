import pytest

from prometheus_backend.jobs.base import Job


def test_cannot_instantiate_job_without_implementing_run():
    with pytest.raises(TypeError):
        Job()


def test_concrete_subclass_can_be_instantiated_and_run():
    class ConcreteJob(Job):
        def run(self) -> None:
            pass

    job = ConcreteJob()
    job.run()  # should not raise


def test_run_is_called():
    class ConcreteJob(Job):
        def __init__(self):
            self.ran = False

        def run(self) -> None:
            self.ran = True

    job = ConcreteJob()
    job.run()
    assert job.ran is True
