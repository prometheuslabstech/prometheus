from collections.abc import Sequence

from prometheus_backend.jobs.base import Job


class Pipeline:
    """Runs a fixed sequence of jobs in order."""

    def __init__(self, jobs: Sequence[Job], name: str = "pipeline") -> None:
        self.jobs = jobs
        self.name = name

    def run(self) -> None:
        for job in self.jobs:
            job.run()
