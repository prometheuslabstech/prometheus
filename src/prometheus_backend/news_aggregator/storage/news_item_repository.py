from pathlib import Path

from prometheus_backend.news_aggregator.models.news_item import NewsItem
from prometheus_backend.storage.repository_base import LocalJsonlRepository, Repository


class NewsItemRepository(Repository[NewsItem]):
    pass


class LocalNewsItemRepository(LocalJsonlRepository[NewsItem], NewsItemRepository):
    def __init__(self, file_path: Path) -> None:
        super().__init__(NewsItem, file_path)
