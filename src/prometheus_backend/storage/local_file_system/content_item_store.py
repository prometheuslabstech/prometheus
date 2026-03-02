from pathlib import Path

from prometheus_backend.models.content import ContentItem


class ContentItemStore:
    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

    def save(self, item: ContentItem) -> None:
        if not self.file_path.exists():
            self.file_path.write_text(item.model_dump_json() + "\n")
            return
        lines = self.file_path.read_text().splitlines()
        updated = False
        for i, line in enumerate(lines):
            if ContentItem.model_validate_json(line).id == item.id:
                lines[i] = item.model_dump_json()
                updated = True
                break
        if not updated:
            lines.append(item.model_dump_json())
        self.file_path.write_text("\n".join(lines) + "\n")

    def get(self, id: str) -> ContentItem | None:
        if not self.file_path.exists():
            return None
        for line in self.file_path.read_text().splitlines():
            item = ContentItem.model_validate_json(line)
            if item.id == id:
                return item
        return None

    def list(self) -> list[ContentItem]:
        if not self.file_path.exists():
            return []
        return [
            ContentItem.model_validate_json(line)
            for line in self.file_path.read_text().splitlines()
        ]

    def delete(self, id: str) -> None:
        if not self.file_path.exists():
            return
        lines = [
            line for line in self.file_path.read_text().splitlines()
            if ContentItem.model_validate_json(line).id != id
        ]
        self.file_path.write_text("\n".join(lines) + "\n" if lines else "")
