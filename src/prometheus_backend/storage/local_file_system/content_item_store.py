from pathlib import Path

from prometheus_backend.models.content import ContentItem


class ContentItemStore:
    def __init__(self, base_dir: str):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, id: str) -> Path:
        return self.base_dir / f"{id}.json"

    def save(self, item: ContentItem) -> None:
        self._path(item.id).write_text(item.model_dump_json())

    def get(self, id: str) -> ContentItem | None:
        path = self._path(id)
        if not path.exists():
            return None
        return ContentItem.model_validate_json(path.read_text())

    def list(self) -> list[ContentItem]:
        return [
            ContentItem.model_validate_json(p.read_text())
            for p in self.base_dir.glob("*.json")
        ]

    def delete(self, id: str) -> None:
        self._path(id).unlink(missing_ok=True)

    def exists(self, id: str) -> bool:
        return self._path(id).exists()
