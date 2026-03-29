# Backlogs

## Ingestion Pipeline

### Filter paywalled syndication sources at discovery
Some RSS feeds (e.g. Yahoo Finance) syndicate articles that link to paywalled third-party sites (Barron's, WSJ). These always fail at fetch time. A domain blocklist should be applied in `RSSDiscoverySource` to skip these URLs before they are stored as `PENDING` items.

### Enforce minimum content length after fetch
Some fetched articles have unusually short `raw_content` (~8K chars vs. a typical 36K–73K range), indicating a soft paywall returning a teaser instead of the full article. `PageFetchJob` should reject content below a minimum length threshold and mark the item `FAILED` with a descriptive error rather than treating it as a successful fetch.

### Add retry logic for FAILED items
Items that fail fetch land permanently in `status=failed` and are never retried. A retry mechanism is needed — either a dedicated retry job that resets eligible `FAILED` items back to `PENDING` after a cooldown, or a max-attempt counter to avoid retrying indefinitely.

### Add more RSS sources
The pipeline is currently wired to Yahoo Finance only. Additional sources should be added to `RSS_FEEDS` in `scripts/run_news_aggregator.py` to improve content diversity and reduce single-source concentration risk.
