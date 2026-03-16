from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from prometheus_backend.news_aggregator.jobs.page_fetch_job import PageFetchJob
from prometheus_backend.news_aggregator.models.news_item import NewsItem, NewsItemStatus

# ── helpers ───────────────────────────────────────────────────────────────────


def make_pending_item(url: str = "https://reuters.com/article/1") -> NewsItem:
    return NewsItem(
        url=url,
        title="Test Title",
        source_id="reuters.com",
        status=NewsItemStatus.PENDING,
        creation_time=datetime(2026, 3, 15, 10, 0, 0, tzinfo=timezone.utc),
    )


def make_mock_repo(pending: list[NewsItem] | None = None):
    repo = MagicMock()
    repo.list.return_value = pending or []
    return repo


# ── tests ─────────────────────────────────────────────────────────────────────


@patch("prometheus_backend.news_aggregator.jobs.page_fetch_job.tavily_search.extract")
def test_no_pending_items_does_nothing(mock_extract):
    repo = make_mock_repo(pending=[])
    PageFetchJob(repo).run()
    mock_extract.assert_not_called()
    repo.put.assert_not_called()


@patch("prometheus_backend.news_aggregator.jobs.page_fetch_job.tavily_search.extract")
def test_successful_fetch_updates_status_to_fetched(mock_extract):
    mock_extract.return_value = "Full article content."
    repo = make_mock_repo(pending=[make_pending_item()])
    PageFetchJob(repo).run()
    stored = repo.put.call_args[0][0]
    assert stored.status == NewsItemStatus.FETCHED


@patch("prometheus_backend.news_aggregator.jobs.page_fetch_job.tavily_search.extract")
def test_successful_fetch_stores_raw_content(mock_extract):
    mock_extract.return_value = "Full article content."
    repo = make_mock_repo(pending=[make_pending_item()])
    PageFetchJob(repo).run()
    stored = repo.put.call_args[0][0]
    assert stored.raw_content == "Full article content."


@patch("prometheus_backend.news_aggregator.jobs.page_fetch_job.tavily_search.extract")
def test_successful_fetch_clears_error(mock_extract):
    mock_extract.return_value = "Full article content."
    repo = make_mock_repo(pending=[make_pending_item()])
    PageFetchJob(repo).run()
    stored = repo.put.call_args[0][0]
    assert stored.error is None


@patch("prometheus_backend.news_aggregator.jobs.page_fetch_job.tavily_search.extract")
def test_failed_fetch_updates_status_to_failed(mock_extract):
    mock_extract.side_effect = RuntimeError("Tavily timeout")
    repo = make_mock_repo(pending=[make_pending_item()])
    PageFetchJob(repo).run()
    stored = repo.put.call_args[0][0]
    assert stored.status == NewsItemStatus.FAILED


@patch("prometheus_backend.news_aggregator.jobs.page_fetch_job.tavily_search.extract")
def test_failed_fetch_preserves_error_message(mock_extract):
    mock_extract.side_effect = RuntimeError("Tavily timeout")
    repo = make_mock_repo(pending=[make_pending_item()])
    PageFetchJob(repo).run()
    stored = repo.put.call_args[0][0]
    assert stored.error == "Tavily timeout"


@patch("prometheus_backend.news_aggregator.jobs.page_fetch_job.tavily_search.extract")
def test_multiple_pending_items_all_processed(mock_extract):
    mock_extract.return_value = "Content."
    items = [
        make_pending_item(url="https://reuters.com/1"),
        make_pending_item(url="https://reuters.com/2"),
        make_pending_item(url="https://reuters.com/3"),
    ]
    repo = make_mock_repo(pending=items)
    PageFetchJob(repo).run()
    assert repo.put.call_count == 3


@patch("prometheus_backend.news_aggregator.jobs.page_fetch_job.tavily_search.extract")
def test_one_succeeds_one_fails_both_stored(mock_extract):
    mock_extract.side_effect = ["Content.", RuntimeError("timeout")]
    items = [
        make_pending_item(url="https://reuters.com/1"),
        make_pending_item(url="https://reuters.com/2"),
    ]
    repo = make_mock_repo(pending=items)
    PageFetchJob(repo).run()

    stored = [call[0][0] for call in repo.put.call_args_list]
    assert stored[0].status == NewsItemStatus.FETCHED
    assert stored[1].status == NewsItemStatus.FAILED


@patch("prometheus_backend.news_aggregator.jobs.page_fetch_job.tavily_search.extract")
def test_queries_repo_for_pending_items(mock_extract):
    repo = make_mock_repo(pending=[])
    PageFetchJob(repo).run()
    repo.list.assert_called_once_with(status=NewsItemStatus.PENDING)
