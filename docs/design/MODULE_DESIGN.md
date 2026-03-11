# Module Design — Prometheus Alert Agent Pipeline

> **Reference**: All implementation work on the alert agent pipeline must refer to this document first.
> This design is grounded in [PRD.md](../PRD.md). When in doubt, defer to the PRD.

---

## Overview

The alert agent pipeline ingests news from configurable sources, deduplicates by content hash, processes unique items through an LLM to produce structured content feeds, evaluates each feed item for notification worthiness per user, delivers alerts via configurable channels, and collects feedback that directly tunes future evaluations.

### Design Principles

- **Local-first, DB-ready**: All storage uses a `Repository[T]` abstract interface. Local JSONL implementations ship first; swapping to a database requires only a new concrete implementation — no business logic changes.
- **Scalable evaluator**: The `FeedEvaluator` is abstract. Start with LLM-based evaluation; rule-based or fine-tuned variants can be added without touching the pipeline.
- **Abstract news sources**: `NewsSource` is an interface. Tavily and RSS ship first; paid API sources (Bloomberg, Reuters) plug in without pipeline changes.
- **Feedback closes the loop**: P0 feedback from users directly adjusts per-user `UserEvaluatorConfig`, which the evaluator reads on every run.
- **Precision over recall in alerting**: Per PRD — we would rather miss a borderline event than train users to ignore notifications.

---

## Full Pipeline

```
[PipelineScheduler] triggers ingestion cycle
         |
[NewsSource(s)] ──> RawNewsItem
         |
[Deduplicator]  ──> SHA-256 hash check ──> skip if already seen
         |
[ContentProcessor] ──> ContentItem (LLM structured output) ──> ContentItemRepository
         |
[FeedEvaluator] <── UserProfile + UserEvaluatorConfig
         |
   ┌─────┴──────┐
 PUSH         DIGEST       DISCARD
   |             |
[NotificationService] ──> EmailChannel / SMSChannel
         |
[FeedbackCollector] ──> FeedbackRecord saved to FeedbackRepository
         |
[FeedbackSignalMapper] ──> updates UserEvaluatorConfig ──> saved to UserProfileRepository
         ^______________ closes the loop _______________^
```

Weekly digest cycle is triggered separately by `PipelineScheduler` on a per-user configurable schedule.

---

## Module Specifications

### 1. `news_ingestion`

**Purpose**: Fetch raw news items from one or more sources. Abstracts over source type so paid API sources can be added without touching downstream modules.

**Location**: `src/prometheus_backend/news_ingestion/`

#### Models

```python
@dataclass
class RawNewsItem:
    url: str
    source_id: str          # identifies which NewsSource produced this
    raw_content: str        # full text content
    fetched_at: datetime
```

#### Interfaces and Implementations

```
NewsSource (abstract)
  ├── fetch() -> List[RawNewsItem]
  |
  ├── TavilyNewsSource      # uses existing tavily_search.search() + extract()
  ├── RSSNewsSource         # parses RSS/Atom feeds
  └── APINewsSource         # future: Bloomberg, Reuters, etc. (API key + client)
```

**Notes**:
- Each source is independently configurable (search terms, feed URLs, API credentials).
- Sources are instantiated and injected into the scheduler — the pipeline does not care which sources are active.
- Legal constraint: do not scrape paywalled content. API sources require valid client credentials and must comply with provider terms.

---

### 2. `deduplication`

**Purpose**: Prevent duplicate news items from being processed and surfaced to users, even when the same story appears across different URLs or outlets.

**Location**: `src/prometheus_backend/deduplication/`

**Strategy**: SHA-256 content hash.
- Input: `normalize(title + raw_content)` — lowercased, whitespace-normalized.
- Hash is checked before LLM processing. If seen, item is discarded immediately.
- Hash is stored after a new item is confirmed unique and processed.

#### Interface

```python
class ContentHashRepository(ABC):
    def contains(self, hash: str) -> bool: ...
    def add(self, hash: str) -> None: ...

class LocalContentHashRepository(ContentHashRepository):
    # Backed by a local flat file (one hash per line)
    ...

class Deduplicator:
    def __init__(self, repo: ContentHashRepository): ...
    def is_duplicate(self, item: RawNewsItem) -> bool: ...
    def mark_seen(self, item: RawNewsItem) -> None: ...
```

**Notes**:
- Hash window is unbounded by default (all-time dedup). If storage grows too large, a TTL-based eviction policy can be added later.
- `mark_seen` is called only after successful `ContentProcessor` output — not at ingestion time — to avoid marking items that failed processing as seen.

---

### 3. `content_processing`

**Purpose**: Transform a `RawNewsItem` into a structured `ContentItem` using LLM analysis. Persists the result to storage.

**Location**: `src/prometheus_backend/content_processing/`

**This module wraps the existing `create_content_item_handler`.** The handler already implements:
- Tavily content extraction from URL
- Gemini structured output → `ContentItem` (title, summary, themes, entities, credibility, language)
- Persistence via `ContentItemStore`

The processor adapts the handler to accept `RawNewsItem` as input (instead of URL-on-demand) to fit the pipeline.

#### Interface

```python
class ContentProcessor:
    def process(self, item: RawNewsItem) -> Optional[ContentItem]: ...
```

**Notes**:
- Returns `None` if LLM processing fails — the pipeline skips and logs the failure without blocking.
- `ContentItem` model is defined in `models/content.py` and is the canonical output of this stage.
- After successful processing, the caller (`PipelineScheduler`) invokes `Deduplicator.mark_seen()`.

---

### 4. `feed_evaluation`

**Purpose**: Decide whether a `ContentItem` warrants a push notification, should be held for the weekly digest, or discarded — evaluated per user against their profile and tuned config.

**Location**: `src/prometheus_backend/feed_evaluation/`

#### Evaluation Criteria (from PRD)

All four criteria must be met to route to PUSH. Partial matches route to DIGEST. No match routes to DISCARD.

| Criterion | Description |
|---|---|
| High Relevance | Directly related to a stock or theme in the user's profile |
| High Impact Potential | Meaningful change in fundamentals, industry structure, regulation, technology, or macro |
| Narrative Shift / Early Signal | Structural narrative change or early emerging trend signal |
| Sufficient Confidence | Source credibility is Medium-High or High; cross-source corroboration where available |

#### Alert Categories (from PRD)

- Company Narrative Shift
- Industry Structure Change
- Regulation / Policy Impact
- Technology / Product Inflection
- Macro Impact on User Interests
- Emerging Signal in Focus Areas

#### Models

```python
class AlertRouting(Enum):
    PUSH = "push"
    DIGEST = "digest"
    DISCARD = "discard"

class AlertCategory(Enum):
    COMPANY_NARRATIVE_SHIFT = "company_narrative_shift"
    INDUSTRY_STRUCTURE_CHANGE = "industry_structure_change"
    REGULATION_POLICY = "regulation_policy"
    TECHNOLOGY_INFLECTION = "technology_inflection"
    MACRO_IMPACT = "macro_impact"
    EMERGING_SIGNAL = "emerging_signal"

class ConfidenceLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

@dataclass
class EvaluationResult:
    content_item_id: str
    user_id: str
    routing: AlertRouting
    category: AlertCategory
    confidence: ConfidenceLevel
    reasoning: str              # surfaced to user in the alert ("Why it matters")
    relevance_explanation: str  # surfaced to user ("Why this is relevant to you")

@dataclass
class UserEvaluatorConfig:
    push_threshold: float                          # default: 0.75
    category_weights: Dict[AlertCategory, float]   # default: 1.0 for all
    source_trust: Dict[str, float]                 # keyed by source_id, default: 1.0
    suppression_window_days: int                   # default: 7
```

#### Interfaces

```python
class FeedEvaluator(ABC):
    def evaluate(
        self,
        item: ContentItem,
        user_profile: UserProfile,
    ) -> EvaluationResult: ...

class LLMFeedEvaluator(FeedEvaluator):
    # Uses Gemini or Bedrock
    # Reads user_profile.evaluator_config to calibrate:
    #   - push routing threshold
    #   - category sensitivity weights
    #   - source trust scores
    #   - suppression window (avoids re-alerting on known stories)
    ...
```

**Notes**:
- The evaluator prompt must not produce buy/sell signals, price targets, or investment advice. Per PRD non-goals.
- Push notifications are disabled by default per user config. Even if routing is PUSH, delivery respects `user_profile.notification_prefs.push_enabled`.

---

### 5. `user_profile`

**Purpose**: Store and retrieve structured user context used for relevance evaluation, notification delivery, and feedback-driven config tuning.

**Location**: `src/prometheus_backend/user_profile/`

#### Models

```python
class Channel(Enum):
    EMAIL = "email"
    SMS = "sms"

@dataclass
class NotificationPreferences:
    push_enabled: bool               # False by default (per PRD)
    channels: List[Channel]          # EMAIL, SMS
    digest_schedule: str             # e.g. "Monday 09:00"

@dataclass
class UserProfile:
    user_id: str
    followed_stocks: List[str]       # ticker symbols
    followed_themes: List[ContentTheme]
    interest_reasons: Dict[str, str] # stock/theme -> why user follows it
    notification_prefs: NotificationPreferences
    evaluator_config: UserEvaluatorConfig
```

#### Storage

```python
class UserProfileRepository(ABC):
    def save(self, profile: UserProfile) -> None: ...
    def get(self, user_id: str) -> Optional[UserProfile]: ...
    def list(self) -> List[UserProfile]: ...

class LocalUserProfileRepository(UserProfileRepository):
    # Backed by JSONL file, same pattern as ContentItemStore
    ...
```

---

### 6. `notification`

**Purpose**: Deliver alerts and weekly digests to users via configured channels. Frequency and channel are per-user configurable.

**Location**: `src/prometheus_backend/notification/`

#### Delivery Modes (from PRD)

| Mode | Default | Trigger | Expected frequency |
|---|---|---|---|
| Push notification | Disabled | PUSH-routed item + push_enabled=True | 0–2 per week max |
| Weekly digest | Enabled | Scheduled, per user digest_schedule | Once per week |

#### Interfaces and Implementations

```python
@dataclass
class Notification:
    user_id: str
    alert_category: AlertCategory
    summary: str                # "What happened"
    reasoning: str              # "Why it matters"
    relevance: str              # "Why relevant to you"
    confidence: ConfidenceLevel
    source_url: str
    created_at: datetime

class NotificationChannel(ABC):
    def send(self, notification: Notification, user: UserProfile) -> bool: ...

class EmailChannel(NotificationChannel): ...
class SMSChannel(NotificationChannel): ...

class NotificationFormatter:
    def format_push(self, notification: Notification, channel: Channel) -> str: ...
    def format_digest(self, notifications: List[Notification], channel: Channel) -> str: ...

class DigestScheduler:
    # Checks each user's digest_schedule and triggers digest delivery
    def run(self, user_profiles: List[UserProfile]) -> None: ...

class NotificationService:
    def send_push(self, result: EvaluationResult, user: UserProfile) -> None: ...
    def send_digest(self, results: List[EvaluationResult], user: UserProfile) -> None: ...
```

**Notes**:
- `NotificationService.send_push` is a no-op if `user.notification_prefs.push_enabled` is False — item is held for next digest instead.
- Digest content: top 3–5 attention alerts, notable narrative shifts, 1–2 emerging signals (per PRD).
- Each notification is tagged with its `AlertCategory` so users immediately understand why they are being interrupted.

---

### 7. `feedback`

**Purpose**: Collect user feedback on notifications and apply it to `UserEvaluatorConfig` to directly tune future evaluation behavior.

**Location**: `src/prometheus_backend/feedback/`

#### Models

```python
class InterruptionValue(Enum):
    WORTH_IT = "worth_it"
    COULD_WAIT = "could_wait"
    NOT_USEFUL = "not_useful"

class FailureReason(Enum):
    BAD_REASONING = "bad_reasoning"
    IRRELEVANT = "irrelevant"
    UNRELIABLE = "unreliable"
    REPETITIVE = "repetitive"

@dataclass
class FeedbackRecord:
    feedback_id: str
    alert_id: str
    user_id: str
    timestamp: datetime
    interruption_value: InterruptionValue
    failure_reason: Optional[FailureReason]    # required if NOT_USEFUL
    free_text: Optional[str]                   # P1: stored but not acted on in V1
```

#### Feedback → Evaluator Config Mapping (P0)

| Feedback | Config adjustment |
|---|---|
| WORTH_IT | Decrease `push_threshold` slightly (more willing to push) |
| COULD_WAIT | Increase `push_threshold` slightly |
| NOT_USEFUL (no reason) | Increase `push_threshold` moderately |
| NOT_USEFUL + BAD_REASONING | No threshold change; flagged for prompt review |
| NOT_USEFUL + IRRELEVANT | Decrease `category_weights[alert.category]` |
| NOT_USEFUL + UNRELIABLE | Decrease `source_trust[alert.source_id]` |
| NOT_USEFUL + REPETITIVE | Increase `suppression_window_days` |

#### Interfaces

```python
class FeedbackRepository(ABC):
    def save(self, record: FeedbackRecord) -> None: ...
    def list_by_user(self, user_id: str) -> List[FeedbackRecord]: ...

class LocalFeedbackRepository(FeedbackRepository):
    # Backed by JSONL file
    ...

class FeedbackCollector:
    def __init__(self, repo: FeedbackRepository, signal_mapper: FeedbackSignalMapper): ...
    def collect(self, record: FeedbackRecord, user_profile: UserProfile) -> UserProfile:
        # Saves record, applies signal mapping, returns updated profile
        ...

class FeedbackSignalMapper:
    def apply(
        self,
        record: FeedbackRecord,
        config: UserEvaluatorConfig,
        alert_category: AlertCategory,
        source_id: str,
    ) -> UserEvaluatorConfig:
        # Returns updated config — does not persist, caller is responsible
        ...
```

---

### 8. `scheduler`

**Purpose**: Orchestrate the full pipeline on a schedule. Runs as a standalone process separate from the MCP servers.

**Location**: `src/prometheus_backend/scheduler/`

**Entry point**: `prometheus scheduler` (added to `setup.py` console scripts alongside existing `prometheus analysis` / `prometheus research`)

#### Responsibilities

```python
class PipelineScheduler:
    def run_ingestion_cycle(self) -> None:
        """
        1. Fetch RawNewsItems from all configured NewsSource(s)
        2. For each item:
           a. Check Deduplicator — skip if duplicate
           b. Run ContentProcessor → ContentItem
           c. Mark item as seen in Deduplicator
           d. For each user profile:
              - Run FeedEvaluator → EvaluationResult
              - If PUSH and push_enabled: NotificationService.send_push()
              - If PUSH and push_disabled, or DIGEST: hold for digest
        """
        ...

    def run_digest_cycle(self) -> None:
        """
        1. For each user whose digest_schedule matches now:
           a. Collect all pending DIGEST-routed items for that user
           b. NotificationService.send_digest()
        """
        ...
```

**Notes**:
- `run_ingestion_cycle` is triggered on a fixed interval (configurable, e.g. every 30 minutes).
- `run_digest_cycle` is triggered every hour and checks each user's `digest_schedule` to determine if it's their delivery time.
- Both cycles are independent and can run concurrently.

---

## Directory Structure

```
src/prometheus_backend/
  ├── news_ingestion/
  │   ├── __init__.py
  │   ├── models.py                  # RawNewsItem
  │   └── sources/
  │       ├── __init__.py
  │       ├── base.py                # NewsSource (abstract)
  │       ├── tavily_source.py
  │       └── rss_source.py
  ├── deduplication/
  │   ├── __init__.py
  │   ├── deduplicator.py            # Deduplicator
  │   └── hash_repository.py        # ContentHashRepository + LocalContentHashRepository
  ├── content_processing/
  │   ├── __init__.py
  │   └── processor.py              # ContentProcessor (wraps existing handler)
  ├── feed_evaluation/
  │   ├── __init__.py
  │   ├── models.py                  # EvaluationResult, UserEvaluatorConfig, AlertCategory, etc.
  │   ├── evaluator.py               # FeedEvaluator (abstract) + LLMFeedEvaluator
  │   └── prompts/
  │       └── llm_evaluator_prompt.py
  ├── user_profile/
  │   ├── __init__.py
  │   ├── models.py                  # UserProfile, NotificationPreferences
  │   └── repository.py             # UserProfileRepository + LocalUserProfileRepository
  ├── notification/
  │   ├── __init__.py
  │   ├── models.py                  # Notification
  │   ├── service.py                 # NotificationService
  │   ├── formatter.py               # NotificationFormatter
  │   ├── scheduler.py               # DigestScheduler
  │   └── channels/
  │       ├── __init__.py
  │       ├── base.py                # NotificationChannel (abstract)
  │       ├── email_channel.py
  │       └── sms_channel.py
  ├── feedback/
  │   ├── __init__.py
  │   ├── models.py                  # FeedbackRecord, InterruptionValue, FailureReason
  │   ├── collector.py               # FeedbackCollector
  │   ├── signal_mapper.py           # FeedbackSignalMapper
  │   └── repository.py             # FeedbackRepository + LocalFeedbackRepository
  ├── storage/
  │   ├── __init__.py
  │   ├── base.py                    # Repository[T] (abstract)
  │   └── local_file_system/
  │       ├── __init__.py
  │       └── content_item_store.py  # existing (conforms to Repository[T])
  └── scheduler/
      ├── __init__.py
      └── pipeline_scheduler.py     # PipelineScheduler entry point
```

---

## Storage Files (Local)

All local storage lives under `src/prometheus_backend/data/`:

```
data/
  ├── content_items.jsonl       # existing
  ├── content_hashes.txt        # one SHA-256 hash per line
  ├── user_profiles.jsonl       # one UserProfile JSON per line
  └── feedback.jsonl            # one FeedbackRecord JSON per line
```

---

## Inter-Module Dependencies

```
scheduler ──> news_ingestion
           ──> deduplication
           ──> content_processing ──> (existing) handlers, services, storage
           ──> feed_evaluation    ──> user_profile
           ──> notification       ──> user_profile
           ──> feedback           ──> user_profile, feed_evaluation.models

feed_evaluation ──> user_profile.models (UserProfile, UserEvaluatorConfig)
feedback        ──> feed_evaluation.models (AlertCategory)
                ──> user_profile (read + write UserEvaluatorConfig)
```

No circular dependencies. `user_profile` and `feed_evaluation.models` are the shared foundation.

---

## Implementation Order (Suggested)

1. `storage/base.py` — `Repository[T]` abstract (foundation for all stores)
2. `deduplication` — simplest new module, no external dependencies
3. `news_ingestion` — sources abstraction + Tavily source
4. `content_processing` — wire existing handler into pipeline interface
5. `user_profile` — needed before evaluation can run
6. `feed_evaluation` — core differentiator, depends on user_profile
7. `scheduler` — wires 1–6 together into a runnable cycle
8. `notification` — Email + SMS delivery
9. `feedback` — closes the loop with evaluator config tuning
