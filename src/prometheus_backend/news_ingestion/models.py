from dataclasses import dataclass
from datetime import datetime


@dataclass
class RawNewsItem:
    """Raw news item as fetched from a news source before LLM processing."""

    url: str
    title: str
    source_id: str
    raw_content: str
    fetched_at: datetime
