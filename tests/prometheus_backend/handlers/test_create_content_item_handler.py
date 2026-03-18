"""Tests for create_content_item_handler."""

from datetime import datetime, timezone
from pathlib import Path
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

INTEGRATION_TEST_URL = "https://en.wikipedia.org/wiki/Nvidia"

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


class TestExecute:
    @pytest.fixture(autouse=True)
    def mock_dependencies(self):
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
                "prometheus_backend.handlers.create_content_item_handler.settings"
            ) as mock_settings,
            patch(
                "prometheus_backend.handlers.create_content_item_handler.GeminiClient"
            ) as mock_gemini_cls,
        ):
            mock_settings.gemini_api_key = "test-key"
            mock_gemini = mock_gemini_cls.return_value
            mock_gemini.client.models.generate_content.return_value = MagicMock(
                text=MOCK_LLM_OUTPUT.model_dump_json()
            )
            yield

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
            mock_gemini_cls.return_value.client.models.generate_content.side_effect = (
                RuntimeError("Gemini error")
            )
            with pytest.raises(RuntimeError, match="Gemini error"):
                execute(request_, store)


@pytest.mark.integration
class TestCreateContentItemHandlerIntegration:
    """Integration tests for create_content_item_handler.

    Run with: pytest --run-integration
    Requires AWS credentials to be configured for KMS decryption.
    """

    @pytest.fixture(autouse=True)
    def aws_setup(self):
        from prometheus_backend.config import settings
        from prometheus_backend.dagger.aws import AWSClients

        aws_clients = AWSClients(region_name=settings.aws_region)
        aws_clients.initialize()
        settings.set_aws_clients(aws_clients)

    @pytest.fixture
    def integration_store(self):
        path = Path(__file__).parent.parent.parent / "data" / "content_items.jsonl"
        return ContentItemStore(file_path=path)

    def test_execute_creates_and_saves_content_item(self, integration_store):
        request = CreateContentItemRequest(source_url=INTEGRATION_TEST_URL)
        response = execute(request, integration_store)

        assert response.id is not None
        assert len(response.id) > 0

        item = integration_store.get(response.id)
        assert item is not None
        assert item.url == INTEGRATION_TEST_URL
        assert item.source_id is not None
        assert item.title != ""
        assert item.summary != ""
        assert item.content != ""
        assert len(item.themes) > 0
        assert len(item.entities) > 0
        assert item.credibility in ContentCredibility
        assert item.language in ContentLanguage
        assert item.published_at is not None
        assert item.created_at is not None
