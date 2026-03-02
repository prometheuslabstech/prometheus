"""Tests for create_content_item_handler."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from prometheus_backend.models.content import (
    ContentCredibility,
    ContentLanguage,
    ContentTheme,
    CreateContentItemRequest,
    LLMContentItemOutput,
)
from prometheus_backend.handlers.create_content_item_handler import execute
from prometheus_backend.storage.local_file_system.content_item_store import (
    ContentItemStore,
)

SOURCE_URL = "https://reuters.com/article/apple-earnings"
RAW_CONTENT = "Apple reported record earnings this quarter."
FIXED_ID = "abc123"

MOCK_LLM_OUTPUT = LLMContentItemOutput(
    source_id="reuters.com",
    title="Apple Reports Record Earnings",
    published_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    summary="Apple had a strong quarter.",
    content=RAW_CONTENT,
    themes=[ContentTheme.TECHNOLOGY],
    entities=["Apple"],
    credibility=ContentCredibility.HIGH,
    language=ContentLanguage.ENGLISH,
)


@pytest.fixture
def store(tmp_path):
    return ContentItemStore(file_path=str(tmp_path / "content_items.jsonl"))


@pytest.fixture
def request_():
    return CreateContentItemRequest(source_url=SOURCE_URL)


@pytest.fixture(autouse=True)
def mock_dependencies():
    with (
        patch(
            "prometheus_backend.handlers.create_content_item_handler.UniqueIdGenerator.generate_id",
            return_value=FIXED_ID,
        ),
        patch(
            "prometheus_backend.handlers.create_content_item_handler.tavily_search.extract",
            return_value=RAW_CONTENT,
        ),
        patch(
            "prometheus_backend.handlers.create_content_item_handler.GeminiClient"
        ) as mock_gemini_cls,
    ):
        mock_gemini = mock_gemini_cls.return_value
        mock_gemini.client.models.generate_content.return_value = MagicMock(
            text=MOCK_LLM_OUTPUT.model_dump_json()
        )
        yield


class TestExecute:
    def test_returns_response_with_valid_id(self, request_, store):
        response = execute(request_, store)
        assert response.id == FIXED_ID

    def test_saves_content_item_to_store(self, request_, store):
        execute(request_, store)
        assert store.get(FIXED_ID) is not None

    def test_saved_item_has_correct_url_and_source_id(self, request_, store):
        execute(request_, store)
        item = store.get(FIXED_ID)
        assert item.url == SOURCE_URL
        assert item.source_id == "reuters.com"

    def test_returned_id_matches_saved_item(self, request_, store):
        response = execute(request_, store)
        assert store.get(response.id) is not None

    def test_raises_when_tavily_fails(self, request_, store):
        with patch(
            "prometheus_backend.handlers.create_content_item_handler.tavily_search.extract",
            side_effect=RuntimeError("Tavily error"),
        ):
            with pytest.raises(RuntimeError, match="Tavily error"):
                execute(request_, store)

    def test_raises_when_gemini_fails(self, request_, store):
        with patch(
            "prometheus_backend.handlers.create_content_item_handler.GeminiClient"
        ) as mock_gemini_cls:
            mock_gemini_cls.return_value.client.models.generate_content.side_effect = RuntimeError("Gemini error")
            with pytest.raises(RuntimeError, match="Gemini error"):
                execute(request_, store)
