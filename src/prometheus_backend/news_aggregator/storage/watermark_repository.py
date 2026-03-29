import json
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from pathlib import Path


class WatermarkRepository(ABC):
    """Persists last_crawl_timestamp per source_id.

    When no watermark exists for a source, get() returns now() minus
    default_lookback_hours so that the first crawl fetches a bounded window
    rather than the full history.

    Swap the implementation (local file, Redis, DynamoDB, etc.) without
    touching any discovery source logic.
    """

    DEFAULT_LOOKBACK_HOURS = 48

    @abstractmethod
    def get(self, source_id: str) -> datetime:
        """Return the last crawl timestamp for source_id.

        Falls back to now() - DEFAULT_LOOKBACK_HOURS if never crawled.
        """
        ...

    @abstractmethod
    def set(self, source_id: str, timestamp: datetime) -> None:
        """Persist timestamp as the last crawl time for source_id."""
        ...


class LocalWatermarkRepository(WatermarkRepository):
    """JSON file-backed implementation: { "source_id": "2026-03-27T21:54:03+00:00" }"""

    def __init__(self, file_path: Path) -> None:
        self._path = file_path
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def get(self, source_id: str) -> datetime:
        if self._path.exists():
            data = json.loads(self._path.read_text())
            raw = data.get(source_id)
            if raw is not None:
                return datetime.fromisoformat(raw)
        return datetime.now(timezone.utc) - timedelta(hours=self.DEFAULT_LOOKBACK_HOURS)

    def set(self, source_id: str, timestamp: datetime) -> None:
        data = json.loads(self._path.read_text()) if self._path.exists() else {}
        data[source_id] = timestamp.isoformat()
        self._path.write_text(json.dumps(data, indent=2))
