from abc import ABC, abstractmethod
from pathlib import Path
from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")
M = TypeVar("M", bound=BaseModel)


class Repository(ABC, Generic[T]):
    @abstractmethod
    def put(self, item: T) -> None: ...

    @abstractmethod
    def get(self, id: str) -> T | None: ...

    @abstractmethod
    def list(self) -> list[T]: ...

    @abstractmethod
    def delete(self, id: str) -> None: ...


class LocalJsonlRepository(Repository[M], Generic[M]):
    def __init__(self, model_class: type[M], file_path: Path) -> None:
        self._model_class = model_class
        self.file_path = file_path
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

    def put(self, item: M) -> None:
        if not self.file_path.exists():
            self.file_path.write_text(item.model_dump_json() + "\n")
            return
        lines = self.file_path.read_text().splitlines()
        updated = False
        for i, line in enumerate(lines):
            if self._model_class.model_validate_json(line).id == item.id:
                lines[i] = item.model_dump_json()
                updated = True
                break
        if not updated:
            lines.append(item.model_dump_json())
        self.file_path.write_text("\n".join(lines) + "\n")

    def get(self, id: str) -> M | None:
        if not self.file_path.exists():
            return None
        for line in self.file_path.read_text().splitlines():
            item = self._model_class.model_validate_json(line)
            if item.id == id:
                return item
        return None

    def list(self) -> list[M]:
        if not self.file_path.exists():
            return []
        return [
            self._model_class.model_validate_json(line)
            for line in self.file_path.read_text().splitlines()
        ]

    def delete(self, id: str) -> None:
        if not self.file_path.exists():
            return
        lines = [
            line for line in self.file_path.read_text().splitlines()
            if self._model_class.model_validate_json(line).id != id
        ]
        self.file_path.write_text("\n".join(lines) + "\n" if lines else "")
