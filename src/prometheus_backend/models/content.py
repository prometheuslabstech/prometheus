from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class ContentTheme(str, Enum):
    TECHNOLOGY = "technology"
    HEALTHCARE = "healthcare"
    FINANCIALS = "financials"
    ENERGY = "energy"
    CONSUMER_DISCRETIONARY = "consumer_discretionary"
    CONSUMER_STAPLES = "consumer_staples"
    INDUSTRIALS = "industrials"
    MATERIALS = "materials"
    REAL_ESTATE = "real_estate"
    UTILITIES = "utilities"
    COMMUNICATION_SERVICES = "communication_services"
    CRYPTO = "crypto"


class ContentCredibility(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ContentLanguage(str, Enum):
    ENGLISH = "en"
    SPANISH = "es"
    FRENCH = "fr"
    GERMAN = "de"
    CHINESE_SIMPLIFIED = "zh-hans"
    CHINESE_TRADITIONAL = "zh-hant"
    JAPANESE = "ja"
    KOREAN = "ko"
    PORTUGUESE = "pt"
    ARABIC = "ar"


class ContentItemMeta(BaseModel):
    id: str
    url: str = Field(description="Direct URL to the original content.")
    created_at: datetime = Field(description="Timestamp when this item was initialized by the system.")
    content: str = Field(description="Full body text of the content item.")
    source_id: str = Field(description="Identifier of the source that published this content (e.g. Reuters, Bloomberg).")


class LLMContentItemOutput(BaseModel):
    title: str = Field(description="Headline or title of the content.")
    published_at: datetime = Field(description="Timestamp when the content was originally published by the source.")
    summary: str = Field(description="Short, neutral summary of the content suitable for quick scanning.")
    themes: list[ContentTheme] = Field(description="List of industry sectors this content is relevant to.")
    entities: list[str] = Field(description="Named entities mentioned in the content, such as company names, tickers, or people.")
    credibility: ContentCredibility = Field(description="Assessed credibility of the source: high, medium, or low.")
    language: ContentLanguage = Field(description="Language the content is written in, as an ISO 639-1 code.")


class ContentItem(ContentItemMeta, LLMContentItemOutput):
    pass


class CreateContentItemRequest(BaseModel):
    source_url: str


class CreateContentItemResponse(BaseModel):
    id: str
