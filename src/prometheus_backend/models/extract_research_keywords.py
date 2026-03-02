"""Response model for extract_research_keywords."""

from pydantic import BaseModel, Field


class ResearchKeyword(BaseModel):
    security: str = Field(description="Full company name or security identifier")
    theme: str = Field(description="Industry theme or topic")
    context: str = Field(description="Brief explanation of why this security-theme pair is relevant")


class ExtractResearchKeywordsResponse(BaseModel):
    keywords: list[ResearchKeyword] = Field(default_factory=list)
