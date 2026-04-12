# Project Design and Structure

## Overview

Prometheus is a financial news intelligence backend. It ingests articles from RSS and other sources, classifies them into structured content items, evaluates their relevance against investor profiles, and delivers personalized alerts.

## Project Structure

```
prometheus/
├── src/
│   └── prometheus_backend/
│       ├── news_aggregator/        # RSS discovery and full-page fetch pipeline
│       ├── content_processing/     # Classification pipeline (NewsItem → ContentItem)
│       ├── user_profile/           # Investor profile models, builder, repository
│       ├── models/                 # Shared domain models (ContentItem, AlertCategory, etc.)
│       ├── prompts/                # LLM system prompts
│       ├── servers/                # MCP servers (analysis, research, profile)
│       ├── services/               # External clients (Gemini, Bedrock, Tavily)
│       ├── storage/                # Storage abstractions and local file-system impl
│       ├── handlers/               # Notification delivery handlers (not yet built)
│       └── dagger/                 # AWS client initialization
├── scripts/                        # Manual pipeline runners
├── tests/
├── DESIGNS.md
├── BACKLOGS.md
├── IDEAS.md
└── AGENTS.md
```

## Pipeline Architecture

The system is structured as a sequential pipeline with four discrete stages:

```
[1] News Aggregator
    RSS/Twitter discovery + full-page fetch
    Output: NewsItem (raw content, status=FETCHED)
        ↓
[2] Content Processor
    Per-article classification via Gemini
    Output: ContentItem (structured metadata, single-article scope)
        ↓
[3] Feed Evaluator  ← not yet built
    Relevance scoring against UserProfile
    Output: alert decision (yes/no + score)
        ↓
[4] Notification Delivery  ← not yet built
    Email digest, push, SMS per NotificationPreferences
```

### Stage 1 — News Aggregator

Discovers URLs from RSS feeds and fetches their full content. Stores raw articles as `NewsItem` with a status machine (`PENDING → FETCHED → DEDUPLICATED → PROCESSED`). Writes to local JSONL files.

### Stage 2 — Content Processor

Reads `DEDUPLICATED` items and sends each article body to Gemini with a structured extraction prompt. Outputs a `ContentItem` containing: title, summary, themes, entities, credibility, language, and `AlertCategory`.

**Scope: single article, no external context.** The content processor only sees the article itself. It classifies what the article *is* — it does not evaluate whether it matters to any particular user or in the context of other news.

### Stage 3 — Feed Evaluator (not yet built)

Takes a `ContentItem` and a `UserProfile` and decides whether to trigger an alert. The current model applies `category_weights` (framework-specific) and checks overlap with `followed_stocks` / `followed_themes` against `push_threshold`.

### Stage 4 — Notification Delivery (not yet built)

Dispatches alerts via channels specified in `NotificationPreferences` (email, SMS). Digest scheduling is modeled but not wired.

---

## MCP Servers

Three MCP servers expose tools for Claude Code sessions:

| Server | Tools | Purpose |
|---|---|---|
| `prometheus-analysis` | `extract_research_keywords`, `generate_research_plan` | Parse financial text; plan a web research sequence |
| `prometheus-research` | `web_search` | Execute Tavily web searches from a research plan |
| `prometheus-profile` | `list_investment_frameworks`, `generate_profile_interest_reasons`, `save_user_profile`, `get_user_profile` | Build and manage investor profiles interactively |

These servers are separate from the automated pipeline — they are tools for Claude to use in interactive research sessions, not steps in the ingestion flow.

---

## Feed Evaluator — Future Expansion Principles

The current Feed Evaluator design is a **relevance filter**: it scores a single `ContentItem` against a `UserProfile` using static category weights. This is intentionally simple for the initial implementation.

As the system matures, the Feed Evaluator should evolve toward a **contextual intelligence layer** governed by the following principles:

### Principle 1: Content processor output is a signal, not a conclusion

The `ContentItem` produced by the content processor (themes, entities, `AlertCategory`) is structured metadata extracted from a single article in isolation. The Feed Evaluator must treat this as raw signal — not as a final judgment. The evaluator is responsible for drawing conclusions in context.

### Principle 2: Relevance requires cross-content context

A single article rarely tells the full story. The evaluator should compare incoming content against the corpus of recently processed items to detect:
- **Narrative shifts**: Is this contradicting or confirming earlier coverage of the same entity?
- **Signal clustering**: Are multiple independent sources converging on the same theme or entity in a short window?
- **Absence of corroboration**: Is a strong claim being made by a single low-credibility source with no supporting coverage?

Evaluating any one item in isolation risks both false positives (noisy one-off articles) and false negatives (weak signals that only become meaningful in aggregate).

### Principle 3: Internet research closes the context gap

When a `ContentItem` references an entity or event the system has no historical context for, the evaluator should be able to trigger web research (via the `prometheus-research` server's `web_search` tool) to gather corroborating or contradicting evidence before scoring relevance. This grounds the evaluation in real-world context rather than relying solely on the article text.

### Principle 4: Historical holdings context shapes scoring

A user's `interest_reasons` (per-stock/per-theme theses captured during profile building) encode *why* they care about each holding. The evaluator should compare incoming content against these stored reasons to assess fit — not just whether an entity is mentioned, but whether the article speaks to the specific thesis the user is tracking. For example, a user holding NVDA for AI infrastructure reasons should score a data-center supply story higher than an NVDA consumer gaming story, even though both mention the same ticker.

### Principle 5: Framework weights are a starting point, not the full model

The `category_weights` in `framework_defaults.py` capture broad tendencies (e.g. macro investors care less about individual company narrative shifts). As the system accumulates data on which alerts a user acts on or dismisses, these weights should be refined per-user rather than remaining static per-framework.

---

## Configuration

- **Python 3.12+** required
- **Black** — code formatting
- **flake8** — linting
- **mypy** — type checking
- **pytest + pytest-cov** — testing and coverage

