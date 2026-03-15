from abc import ABC, abstractmethod
from pathlib import Path


class HashRepository(ABC):
    """Abstract repository for storing and querying seen content hashes."""

    @abstractmethod
    def contains(self, hash: str) -> bool:
        """Return True if the hash has been seen before."""
        ...

    @abstractmethod
    def add(self, hash: str) -> None:
        """Record a hash as seen. Idempotent."""
        ...


class LocalHashRepository(HashRepository):
    """Flat-file implementation of HashRepository.

    Stores one SHA-256 hash per line in a local text file.
    Loads all hashes into memory on init for fast lookup.
    """

    def __init__(self, file_path: str) -> None:
        self._path = Path(file_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._hashes: set[str] = self._load()

    def _load(self) -> set[str]:
        if not self._path.exists():
            return set()
        return {line for line in self._path.read_text().splitlines() if line}

    def contains(self, hash: str) -> bool:
        """Return True if the hash has been seen before."""
        return hash in self._hashes

    def add(self, hash: str) -> None:
        """Record a hash as seen. Idempotent — no duplicate lines written."""
        if hash in self._hashes:
            return
        self._hashes.add(hash)
        with self._path.open("a") as f:
            f.write(hash + "\n")
