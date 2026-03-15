"""Tests for Repository and LocalJsonlRepository in storage/base.py."""

import pytest
from pydantic import BaseModel

from prometheus_backend.storage.repository_base import LocalJsonlRepository, Repository


class Item(BaseModel):
    id: str
    value: str = "default"


@pytest.fixture
def repo(tmp_path):
    return LocalJsonlRepository(Item, tmp_path / "items.jsonl")


# ---------------------------------------------------------------------------
# Repository ABC
# ---------------------------------------------------------------------------

class TestRepositoryABC:
    def test_cannot_instantiate_without_implementing_abstract_methods(self):
        with pytest.raises(TypeError):
            Repository()


# ---------------------------------------------------------------------------
# LocalJsonlRepository — put
# ---------------------------------------------------------------------------

class TestPut:
    def test_inserts_when_file_does_not_exist(self, repo):
        repo.put(Item(id="a"))
        assert repo.get("a") == Item(id="a")

    def test_inserts_new_item_when_file_has_other_entries(self, repo):
        repo.put(Item(id="a"))
        repo.put(Item(id="b"))
        assert len(repo.list()) == 2

    def test_upserts_existing_item_without_creating_duplicate(self, repo):
        repo.put(Item(id="a", value="original"))
        repo.put(Item(id="a", value="updated"))
        items = repo.list()
        assert len(items) == 1
        assert items[0].value == "updated"


# ---------------------------------------------------------------------------
# LocalJsonlRepository — get
# ---------------------------------------------------------------------------

class TestGet:
    def test_returns_correct_item_by_id(self, repo):
        item = Item(id="a")
        repo.put(item)
        assert repo.get("a") == item

    def test_returns_none_when_id_not_found(self, repo):
        repo.put(Item(id="a"))
        assert repo.get("z") is None

    def test_returns_none_when_file_does_not_exist(self, repo):
        assert repo.get("a") is None


# ---------------------------------------------------------------------------
# LocalJsonlRepository — list
# ---------------------------------------------------------------------------

class TestList:
    def test_returns_all_items(self, repo):
        repo.put(Item(id="a"))
        repo.put(Item(id="b"))
        assert len(repo.list()) == 2

    def test_returns_empty_list_when_file_does_not_exist(self, repo):
        assert repo.list() == []

    def test_returns_empty_list_when_file_is_empty(self, repo):
        repo.file_path.write_text("")
        assert repo.list() == []


# ---------------------------------------------------------------------------
# LocalJsonlRepository — delete
# ---------------------------------------------------------------------------

class TestDelete:
    def test_removes_correct_item_leaving_others_intact(self, repo):
        repo.put(Item(id="a"))
        repo.put(Item(id="b"))
        repo.delete("a")
        items = repo.list()
        assert len(items) == 1
        assert items[0].id == "b"

    def test_is_noop_when_id_not_found(self, repo):
        repo.put(Item(id="a"))
        repo.delete("z")
        assert len(repo.list()) == 1

    def test_is_noop_when_file_does_not_exist(self, repo):
        repo.delete("a")  # should not raise


# ---------------------------------------------------------------------------
# LocalJsonlRepository — __init__
# ---------------------------------------------------------------------------

class TestInit:
    def test_creates_parent_directory_if_missing(self, tmp_path):
        nested = tmp_path / "a" / "b" / "c" / "items.jsonl"
        repo = LocalJsonlRepository(Item, nested)
        assert nested.parent.exists()
