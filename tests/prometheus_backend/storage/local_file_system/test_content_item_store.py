"""Tests for ContentItemStore."""

from datetime import datetime, timezone

import pytest

from prometheus_backend.models.content import (
    ContentCredibility,
    ContentItem,
    ContentLanguage,
    ContentTheme,
)
from prometheus_backend.storage.local_file_system.content_item_store import (
    ContentItemStore,
)


def make_item(id: str, title: str = "Test Article") -> ContentItem:
    return ContentItem(
        id=id,
        url="https://example.com/article",
        source_id="example.com",
        title=title,
        published_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        summary="A test summary.",
        content="Full article content.",
        themes=[ContentTheme.TECHNOLOGY],
        entities=["Apple"],
        credibility=ContentCredibility.HIGH,
        language=ContentLanguage.ENGLISH,
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )


@pytest.fixture
def store(tmp_path):
    return ContentItemStore(file_path=str(tmp_path / "content_items.jsonl"))


class TestPut:
    def test_appends_new_item_when_file_does_not_exist(self, store):
        item = make_item("abc")
        store.put(item)
        assert store.get("abc") == item

    def test_appends_new_item_when_file_has_other_items(self, store):
        store.put(make_item("abc"))
        store.put(make_item("def"))
        assert len(store.list()) == 2

    def test_updates_existing_item_without_creating_duplicate(self, store):
        store.put(make_item("abc", title="Original"))
        store.put(make_item("abc", title="Updated"))
        items = store.list()
        assert len(items) == 1
        assert items[0].title == "Updated"


class TestGet:
    def test_returns_correct_item_by_id(self, store):
        item = make_item("abc")
        store.put(item)
        assert store.get("abc") == item

    def test_returns_none_when_id_does_not_exist(self, store):
        store.put(make_item("abc"))
        assert store.get("xyz") is None

    def test_returns_none_when_file_does_not_exist(self, store):
        assert store.get("abc") is None


class TestList:
    def test_returns_all_items(self, store):
        store.put(make_item("abc"))
        store.put(make_item("def"))
        assert len(store.list()) == 2

    def test_returns_empty_list_when_file_does_not_exist(self, store):
        assert store.list() == []

    def test_returns_empty_list_when_file_is_empty(self, store):
        store.file_path.write_text("")
        assert store.list() == []


class TestDelete:
    def test_removes_correct_item_leaving_others_intact(self, store):
        store.put(make_item("abc"))
        store.put(make_item("def"))
        store.delete("abc")
        items = store.list()
        assert len(items) == 1
        assert items[0].id == "def"

    def test_is_noop_when_id_does_not_exist(self, store):
        store.put(make_item("abc"))
        store.delete("xyz")
        assert len(store.list()) == 1

    def test_is_noop_when_file_does_not_exist(self, store):
        store.delete("abc")  # should not raise
