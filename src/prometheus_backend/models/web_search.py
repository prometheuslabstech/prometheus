"""Response model for web_search."""

from pydantic import BaseModel, Field


class WebSearchResult(BaseModel):
    title: str = Field(description="Title of the search result")
    url: str = Field(description="URL of the search result")
    content: str = Field(description="Content snippet from the search result")


class WebSearchResponse(BaseModel):
    query: str = Field(description="The search query executed")
    results: list[WebSearchResult] = Field(
        default_factory=list, description="Search results returned"
    )
