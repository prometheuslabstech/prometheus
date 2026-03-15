from datetime import datetime, timezone
from urllib.parse import urlparse

from appdevcommons.unique_id import UniqueIdGenerator

from prometheus_backend.models.content import (
    ContentItem,
    CreateContentItemRequest,
    CreateContentItemResponse,
    LLMContentItemOutput,
)
from prometheus_backend.config import settings
from prometheus_backend.services.gemini import GeminiClient
from prometheus_backend.services import tavily_search
from prometheus_backend.prompts.create_content_item_handler_prompt import (
    SYSTEM_INSTRUCTION,
    user_message,
)
from prometheus_backend.storage.local_file_system.content_item_store import (
    ContentItemStore,
)


_MAX_ANALYSIS_CHARS = 20_000


def execute(
    request: CreateContentItemRequest,
    store: ContentItemStore,
) -> CreateContentItemResponse:
    content_item_id = UniqueIdGenerator.generate_id()

    raw_content = tavily_search.extract(request.source_url)

    gemini = GeminiClient(api_key=settings.gemini_api_key)
    response = gemini.client.models.generate_content(
        model=gemini.model_id,
        contents=user_message(raw_content[:_MAX_ANALYSIS_CHARS]),
        config={
            "system_instruction": SYSTEM_INSTRUCTION,
            "response_mime_type": "application/json",
            "response_schema": LLMContentItemOutput,
        },
    )
    llm_output = LLMContentItemOutput.model_validate_json(response.text)

    content_item = ContentItem(
        id=content_item_id,
        source_id=urlparse(request.source_url).netloc,
        url=request.source_url,
        created_at=datetime.now(timezone.utc),
        content=raw_content,
        **llm_output.model_dump(exclude={"source_id"}),
    )

    store.put(content_item)

    return CreateContentItemResponse(id=content_item.id)
