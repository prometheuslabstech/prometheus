from datetime import datetime, timedelta, timezone

import pytest

from prometheus_backend.news_aggregator.models.news_item import NewsItem, NewsItemStatus, SourceType
from prometheus_backend.news_aggregator.storage.news_item_repository import (
    LocalNewsItemRepository,
    NewsItemRepository,
)


def make_item(
    source_ref: str = "https://reuters.com/article/apple-tsmc", **overrides
) -> NewsItem:
    defaults = dict(
        source_ref=source_ref,
        source_type=SourceType.RSS,
        title="Apple secures TSMC capacity",
        source_id="reuters.com",
        status=NewsItemStatus.FETCHED,
        raw_content="Apple has locked in TSMC N2 node capacity through 2026.",
        creation_time=datetime.now(timezone.utc) - timedelta(minutes=5),
    )
    return NewsItem(**{**defaults, **overrides})


@pytest.fixture
def repo(tmp_path) -> LocalNewsItemRepository:
    return LocalNewsItemRepository(tmp_path / "news_items.jsonl")


# --- setup ---


def test_cannot_instantiate_abstract_repository():
    with pytest.raises(TypeError):
        NewsItemRepository()


def test_creates_parent_directory_if_missing(tmp_path):
    LocalNewsItemRepository(tmp_path / "a" / "b" / "news_items.jsonl")
    assert (tmp_path / "a" / "b").exists()


# --- put ---


def test_put_stores_item(repo):
    item = make_item()
    repo.put(item)
    assert repo.get(item.id) == item


def test_put_upserts_existing_item(repo):
    repo.put(make_item(title="Original"))
    repo.put(make_item(title="Updated"))
    items = repo.list()
    assert len(items) == 1
    assert items[0].title == "Updated"


URL_A = "https://reuters.com/article/apple-tsmc"
URL_B = "https://ft.com/article/tsmc-capacity"


def test_put_multiple_items(repo):
    repo.put(make_item(source_ref=URL_A))
    repo.put(make_item(source_ref=URL_B))
    assert len(repo.list()) == 2


# --- get ---


def test_get_returns_correct_item(repo):
    item = make_item(source_ref=URL_A)
    repo.put(item)
    assert repo.get(URL_A) == item


def test_get_returns_none_when_not_found(repo):
    repo.put(make_item(source_ref=URL_A))
    assert repo.get("https://unknown.com/article") is None


def test_get_returns_none_when_file_does_not_exist(repo):
    assert repo.get(URL_A) is None


# --- list ---


def test_list_returns_all_items(repo):
    repo.put(make_item(source_ref=URL_A))
    repo.put(make_item(source_ref=URL_B))
    assert len(repo.list()) == 2


def test_list_returns_empty_when_file_does_not_exist(repo):
    assert repo.list() == []


URL_C = "https://bloomberg.com/article/nvidia"


def test_list_filter_by_status_pending(repo):
    repo.put(make_item(source_ref=URL_A, status=NewsItemStatus.PENDING, raw_content=None))
    repo.put(make_item(source_ref=URL_B, status=NewsItemStatus.FETCHED))
    results = repo.list(status=NewsItemStatus.PENDING)
    assert len(results) == 1
    assert results[0].source_ref == URL_A


def test_list_filter_by_status_fetched(repo):
    repo.put(make_item(source_ref=URL_A, status=NewsItemStatus.PENDING, raw_content=None))
    repo.put(make_item(source_ref=URL_B, status=NewsItemStatus.FETCHED))
    repo.put(make_item(source_ref=URL_C, status=NewsItemStatus.FETCHED))
    results = repo.list(status=NewsItemStatus.FETCHED)
    assert len(results) == 2
    assert {r.source_ref for r in results} == {URL_B, URL_C}


def test_list_filter_returns_empty_when_no_match(repo):
    repo.put(make_item(source_ref=URL_A, status=NewsItemStatus.PENDING, raw_content=None))
    assert repo.list(status=NewsItemStatus.PROCESSED) == []


def test_list_filter_by_source_id(repo):
    repo.put(make_item(source_ref=URL_A, source_id="reuters.com"))
    repo.put(make_item(source_ref=URL_B, source_id="ft.com"))
    results = repo.list(source_id="reuters.com")
    assert len(results) == 1
    assert results[0].source_ref == URL_A


def test_list_no_filter_returns_all(repo):
    repo.put(make_item(source_ref=URL_A, status=NewsItemStatus.PENDING, raw_content=None))
    repo.put(make_item(source_ref=URL_B, status=NewsItemStatus.FETCHED))
    repo.put(
        make_item(
            source_ref=URL_C, status=NewsItemStatus.FAILED, raw_content=None, error="timeout"
        )
    )
    assert len(repo.list()) == 3


# --- delete ---


def test_delete_removes_correct_item(repo):
    repo.put(make_item(source_ref=URL_A))
    repo.put(make_item(source_ref=URL_B))
    repo.delete(URL_A)
    items = repo.list()
    assert len(items) == 1
    assert items[0].source_ref == URL_B


def test_delete_is_noop_when_id_not_found(repo):
    repo.put(make_item(source_ref=URL_A))
    repo.delete("https://unknown.com/article")
    assert len(repo.list()) == 1


def test_delete_is_noop_when_file_does_not_exist(repo):
    repo.delete("a")  # should not raise
