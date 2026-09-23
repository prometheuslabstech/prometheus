import json
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from prometheus_backend.content_processing.jobs.content_processing_job import ContentProcessingJob
from prometheus_backend.content_processing.models import AlertCategory, ImpactPotential
from prometheus_backend.models.content import ContentItem, LLMContentItemOutput
from prometheus_backend.news_aggregator.models.news_item import NewsItem, NewsItemStatus, SourceType


LLM_OUTPUT = {
    "title": "Apple secures TSMC capacity for AI chips",
    "published_at": "2026-03-15T14:00:00Z",
    "summary": "Apple locked in TSMC N2 capacity through 2026.",
    "themes": ["technology"],
    "entities": ["AAPL", "TSM"],
    "credibility": "high",
    "language": "en",
    "alert_category": "technology_inflection",
    "impact_potential": "high",
    "narrative_shift": True,
    "reasoning": "Locking N2 capacity structurally limits AI chip supply for competitors.",
}


def make_item(source_ref: str = "https://example.com/article") -> NewsItem:
    return NewsItem(
        source_ref=source_ref,
        source_type=SourceType.RSS,
        title="Test Title",
        source_id="example.com",
        status=NewsItemStatus.DEDUPLICATED,
        raw_content="Full article text.",
        creation_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


def make_gemini(response_text: str) -> MagicMock:
    gemini = MagicMock()
    gemini.model_id = "test-model"
    gemini.client.models.generate_content.return_value = MagicMock(text=response_text)
    return gemini


def make_news_repo(items: list[NewsItem]) -> MagicMock:
    repo = MagicMock()
    repo.list.return_value = items
    return repo


def run_job(items: list[NewsItem], response_text: str):
    news_repo = make_news_repo(items)
    content_store = MagicMock()
    gemini = make_gemini(response_text)
    ContentProcessingJob(news_repo=news_repo, content_store=content_store, gemini=gemini).run()
    return news_repo, content_store, gemini


# --- schema ---


@pytest.mark.parametrize("field", ["impact_potential", "narrative_shift", "reasoning"])
def test_rubric_fields_are_required_in_llm_schema(field):
    assert field in LLMContentItemOutput.model_json_schema()["required"]


def test_requests_llm_output_schema_from_gemini():
    _, _, gemini = run_job([make_item()], json.dumps(LLM_OUTPUT))
    config = gemini.client.models.generate_content.call_args.kwargs["config"]
    assert config["response_schema"] is LLMContentItemOutput


# --- success ---


def test_only_processes_deduplicated_items():
    news_repo, _, _ = run_job([], json.dumps(LLM_OUTPUT))
    news_repo.list.assert_called_once_with(status=NewsItemStatus.DEDUPLICATED)


def test_persists_content_item_with_rubric_fields():
    _, content_store, _ = run_job([make_item()], json.dumps(LLM_OUTPUT))
    stored: ContentItem = content_store.put.call_args.args[0]
    assert stored.alert_category == AlertCategory.TECHNOLOGY_INFLECTION
    assert stored.impact_potential == ImpactPotential.HIGH
    assert stored.narrative_shift is True
    assert stored.reasoning == LLM_OUTPUT["reasoning"]


def test_populates_meta_fields_from_news_item():
    item = make_item()
    _, content_store, _ = run_job([item], json.dumps(LLM_OUTPUT))
    stored: ContentItem = content_store.put.call_args.args[0]
    assert stored.url == item.source_ref
    assert stored.source_id == item.source_id
    assert stored.content == item.raw_content
    assert stored.id


def test_marks_news_item_processed():
    news_repo, _, _ = run_job([make_item()], json.dumps(LLM_OUTPUT))
    updated: NewsItem = news_repo.put.call_args.args[0]
    assert updated.status == NewsItemStatus.PROCESSED


# --- failure ---


def test_marks_failed_when_rubric_field_missing():
    incomplete = {k: v for k, v in LLM_OUTPUT.items() if k != "impact_potential"}
    news_repo, content_store, _ = run_job([make_item()], json.dumps(incomplete))
    content_store.put.assert_not_called()
    updated: NewsItem = news_repo.put.call_args.args[0]
    assert updated.status == NewsItemStatus.FAILED
    assert "impact_potential" in updated.error


def test_marks_failed_on_invalid_impact_value():
    bad = {**LLM_OUTPUT, "impact_potential": "extreme"}
    news_repo, content_store, _ = run_job([make_item()], json.dumps(bad))
    content_store.put.assert_not_called()
    assert news_repo.put.call_args.args[0].status == NewsItemStatus.FAILED


def test_failure_does_not_block_remaining_items():
    items = [make_item("https://example.com/a"), make_item("https://example.com/b")]
    news_repo = make_news_repo(items)
    content_store = MagicMock()
    gemini = make_gemini("")
    gemini.client.models.generate_content.side_effect = [
        MagicMock(text="not json"),
        MagicMock(text=json.dumps(LLM_OUTPUT)),
    ]
    ContentProcessingJob(news_repo=news_repo, content_store=content_store, gemini=gemini).run()

    statuses = [call.args[0].status for call in news_repo.put.call_args_list]
    assert statuses == [NewsItemStatus.FAILED, NewsItemStatus.PROCESSED]
    assert content_store.put.call_count == 1
