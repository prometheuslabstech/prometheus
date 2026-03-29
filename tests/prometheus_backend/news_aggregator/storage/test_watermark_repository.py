from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from prometheus_backend.news_aggregator.storage.watermark_repository import LocalWatermarkRepository


@pytest.fixture
def repo(tmp_path: Path) -> LocalWatermarkRepository:
    return LocalWatermarkRepository(file_path=tmp_path / "watermarks.json")


def test_get_returns_48h_lookback_when_file_missing(repo):
    before = datetime.now(timezone.utc) - timedelta(hours=48)
    result = repo.get("some_source")
    after = datetime.now(timezone.utc) - timedelta(hours=48)
    assert before <= result <= after


def test_get_returns_48h_lookback_when_key_missing(repo, tmp_path):
    repo.set("other_source", datetime.now(timezone.utc))
    before = datetime.now(timezone.utc) - timedelta(hours=48)
    result = repo.get("missing_source")
    after = datetime.now(timezone.utc) - timedelta(hours=48)
    assert before <= result <= after


def test_get_returns_stored_timestamp(repo):
    ts = datetime(2026, 3, 15, 10, 0, 0, tzinfo=timezone.utc)
    repo.set("reuters.com", ts)
    assert repo.get("reuters.com") == ts


def test_set_persists_across_instances(tmp_path):
    path = tmp_path / "watermarks.json"
    ts = datetime(2026, 3, 20, 12, 0, 0, tzinfo=timezone.utc)
    LocalWatermarkRepository(file_path=path).set("reuters.com", ts)
    assert LocalWatermarkRepository(file_path=path).get("reuters.com") == ts


def test_set_preserves_other_keys(repo):
    ts1 = datetime(2026, 3, 15, 10, 0, 0, tzinfo=timezone.utc)
    ts2 = datetime(2026, 3, 16, 10, 0, 0, tzinfo=timezone.utc)
    repo.set("source_a", ts1)
    repo.set("source_b", ts2)
    assert repo.get("source_a") == ts1
    assert repo.get("source_b") == ts2
