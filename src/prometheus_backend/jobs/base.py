from abc import ABC, abstractmethod


class Job(ABC):
    """Abstract base for all aggregator jobs."""

    @abstractmethod
    def run(self) -> None: ...
