from prometheus_backend.storage.hash_repository_base import (
    HashRepository,
    LocalHashRepository,
)


def test_abstract_interface():
    assert issubclass(LocalHashRepository, HashRepository)


def test_contains_returns_false_for_missing_hash(tmp_path):
    repo = LocalHashRepository(str(tmp_path / "hashes.txt"))
    assert repo.contains("abc123") is False


def test_contains_returns_true_after_add(tmp_path):
    repo = LocalHashRepository(str(tmp_path / "hashes.txt"))
    repo.add("abc123")
    assert repo.contains("abc123") is True


def test_file_created_on_first_add(tmp_path):
    path = tmp_path / "hashes.txt"
    repo = LocalHashRepository(str(path))
    assert not path.exists()
    repo.add("abc123")
    assert path.exists()


def test_file_not_created_without_add(tmp_path):
    path = tmp_path / "hashes.txt"
    LocalHashRepository(str(path))
    assert not path.exists()


def test_load_from_existing_file(tmp_path):
    path = tmp_path / "hashes.txt"
    path.write_text("hash1\nhash2\n")
    repo = LocalHashRepository(str(path))
    assert repo.contains("hash1")
    assert repo.contains("hash2")
    assert not repo.contains("hash3")


def test_add_is_idempotent(tmp_path):
    path = tmp_path / "hashes.txt"
    repo = LocalHashRepository(str(path))
    repo.add("abc123")
    repo.add("abc123")
    lines = [line for line in path.read_text().splitlines() if line]
    assert lines.count("abc123") == 1


def test_multiple_hashes_stored(tmp_path):
    repo = LocalHashRepository(str(tmp_path / "hashes.txt"))
    repo.add("hash1")
    repo.add("hash2")
    repo.add("hash3")
    assert repo.contains("hash1")
    assert repo.contains("hash2")
    assert repo.contains("hash3")
