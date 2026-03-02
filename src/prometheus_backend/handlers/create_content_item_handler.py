from datetime import datetime, timezone
from urllib.parse import urlparse

from appdevcommons.unique_id import UniqueIdGenerator

from prometheus_backend.models.content import (
    ContentItem,
    CreateContentItemRequest,
    CreateContentItemResponse,
    LLMContentItemOutput,
)
from prometheus_backend.services.gemini import GeminiClient
from prometheus_backend.services import tavily_search
from prometheus_backend.prompts.create_content_item_handler_prompt import (
    SYSTEM_INSTRUCTION,
    user_message,
)


def execute(request: CreateContentItemRequest) -> CreateContentItemResponse:
    content_item_id = UniqueIdGenerator.generate_id()

    raw_content = tavily_search.extract(request.source_url)

    gemini = GeminiClient()
    response = gemini.client.models.generate_content(
        model=gemini.model_id,
        contents=user_message(raw_content),
        config={
            "system_instruction": SYSTEM_INSTRUCTION,
            "response_mime_type": "application/json",
            "response_schema": LLMContentItemOutput,
        },
    )
    llm_output = LLMContentItemOutput.model_validate_json(response.text)

    source_id = urlparse(request.source_url).netloc

    content_item = ContentItem(
        id=content_item_id,
        source_id=source_id,
        url=request.source_url,
        content=raw_content,
        created_at=datetime.now(timezone.utc),
        **llm_output.model_dump(),
    )

    return CreateContentItemResponse(id=content_item.id)
