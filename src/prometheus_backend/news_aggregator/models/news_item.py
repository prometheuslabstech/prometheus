from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from urllib.parse import urlparse

from pydantic import BaseModel, field_validator, model_validator


class NewsItemStatus(str, Enum):
    """Lifecycle status of a NewsItem as it moves through the aggregation pipeline."""

    PENDING = "pending"  # Discovered (e.g. from RSS); full content not yet fetched
    FETCHED = (
        "fetched"  # Full raw_content retrieved; ready for dedup + content processing
    )
    PROCESSED = "processed"  # Successfully passed through dedup and ContentProcessor
    FAILED = "failed"  # Fetch or processing failed; eligible for retry


class NewsItem(BaseModel):
    url: str
    title: str
    source_id: str
    status: NewsItemStatus
    creation_time: datetime
    raw_content: Optional[str] = None  # None until fetched
    error: Optional[str] = None  # populated on FAILED

    @property
    def id(self) -> str:
        return self.url

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        parsed = urlparse(v)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError(f"Invalid URL: {v!r}")
        return v

    @field_validator("title", "source_id")
    @classmethod
    def validate_not_blank(cls, v: str, info) -> str:
        if not v.strip():
            raise ValueError(f"{info.field_name} must not be empty")
        return v

    @model_validator(mode="after")
    def validate_model(self) -> "NewsItem":
        if self.raw_content is not None and not self.raw_content.strip():
            raise ValueError("raw_content must not be empty")
        if self.status == NewsItemStatus.FETCHED and not self.raw_content:
            raise ValueError("raw_content must not be empty when status is FETCHED")
        if self.creation_time > datetime.now(timezone.utc):
            raise ValueError("creation_time must not be in the future")
        return self
