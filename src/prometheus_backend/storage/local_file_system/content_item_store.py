from pathlib import Path

from prometheus_backend.models.content import ContentItem
from prometheus_backend.storage.repository_base import LocalJsonlRepository

DEFAULT_FILE_PATH = (
    Path(__file__).parent.parent.parent.parent / "data" / "content_items.jsonl"
)


class ContentItemStore(LocalJsonlRepository[ContentItem]):
    def __init__(self, file_path: str | Path = DEFAULT_FILE_PATH) -> None:
        super().__init__(ContentItem, Path(file_path))
