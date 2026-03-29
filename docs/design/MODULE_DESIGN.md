# Module Design — Prometheus Alert Agent Pipeline

> **Reference**: All implementation work on the alert agent pipeline must refer to this document first.
> This design is grounded in [PRD.md](../PRD.md). When in doubt, defer to the PRD.

---

## Overview

The alert agent pipeline discovers and fetches news via a jobs layer, deduplicates by content hash, processes unique items through an LLM to produce structured content feeds (including rubric assessment), evaluates each feed item for notification worthiness per user via rule-based relevance matching, delivers alerts via configurable channels, and collects feedback that directly tunes future evaluations.

### Design Principles

- **Local-first, DB-ready**: All storage uses a `Repository[T]` abstract interface with `list(**filters)` for field-level filtering. Local JSONL implementations ship first; swapping to a database requires only a new concrete implementation — no business logic changes.
- **Two-phase ingestion**: Discovery and fetching are decoupled jobs. `DiscoveryJob` finds URLs and stores `PENDING` items. `PageFetchJob` fetches full content and updates to `FETCHED`. Failures are retryable.
- **Single LLM call per article**: Rubric assessment (impact potential, narrative shift, confidence, category, reasoning) is baked into `ContentProcessor`. `FeedEvaluator` is rule-based — relevance matching only. Cost scales with articles, not users.
- **Scalable evaluator**: `FeedEvaluator` is abstract. Start with rule-based; LLM-assisted variants can be added without touching the pipeline.
- **Abstract discovery sources**: `DiscoverySource` is an interface. `RSSDiscoverySource` ships first; other sources plug in without pipeline changes. Sources are categorized into three types: RSS/XML Pollers (open sources), Webhook/Enterprise API receivers (closed financial ecosystems), and Dynamic Crawlers (JS-heavy walled gardens). A `DiscoverySourceFactory` instantiates the correct type per feed config.
- **Watermark-based crawl tracking**: Each `DiscoverySource` tracks a `last_crawl_timestamp` per feed. On each cycle, only items with `publication_time > last_crawl_timestamp` are returned as new. This is more efficient and semantically correct than URL-only dedup, which cannot distinguish "already seen" from "not yet published." Watermarks are persisted so restarts do not re-discover old content.
- **Edge normalization**: All `DiscoverySource` implementations normalize their native format (XML, JSON, raw HTML) into a standard `DiscoveredItem` before returning. Downstream pipeline stages are insulated from source-specific schema changes.
- **Queue-ready ingestion**: `NewsItemRepository` (PENDING status) acts as a logical work queue between Discovery and Fetch. Local JSONL ships first. The queue boundary can be swapped for a high-throughput broker (Kafka, RabbitMQ) without changing `DiscoveryJob` or `PageFetchJob` — only the repository implementation changes.
- **Feedback closes the loop**: Feedback from users directly adjusts per-user `UserEvaluatorConfig`, which the evaluator reads on every run.
- **Precision over recall in alerting**: Per PRD — we would rather miss a borderline event than train users to ignore notifications.

---

## Pipeline

```
[PipelineScheduler] triggers jobs cycle
         |
[DiscoveryJob] ──> NewsItem(PENDING) ──> NewsItemRepository
         |
[PageFetchJob] ──> NewsItem(FETCHED) ──> NewsItemRepository
         |
[Deduplicator]  ──> SHA-256 hash check ──> skip if already seen
         |
[ContentProcessor] ──> LLM (extraction + rubric) ──> ContentItem ──> ContentItemRepository
  NewsItem updated → PROCESSED
         |
[FeedEvaluator] <── UserProfile + UserEvaluatorConfig
  rule-based relevance check only (no LLM)
         |
   ┌─────┴──────┐
 PUSH         DIGEST       DISCARD
   |             |
[NotificationService] ──> EmailChannel / SMSChannel
         |
[FeedbackCollector] ──> FeedbackRecord ──> FeedbackRepository
         |
[FeedbackSignalMapper] ──> updates UserEvaluatorConfig ──> UserProfileRepository
         ^______________ closes the loop _______________^
```

---

## End-to-End Data Flow

```
═══════════════════════════════════════════════════════════════════════════════
 DISCOVERY  — DiscoveryJob
═══════════════════════════════════════════════════════════════════════════════

 RSSDiscoverySource.discover()
 feed: "https://feeds.reuters.com/reuters/businessNews"

 For each feed entry not already in NewsItemRepository:

     NewsItem written to news_items.jsonl
     ┌────────────────────────────────────────────────────────┐
     │ url:           "https://reuters.com/tech/apple-tsmc-..." │
     │ title:         "Apple secures TSMC capacity for AI chips"│
     │ source_id:     "reuters.com"                            │
     │ status:        PENDING                                  │
     │ raw_content:   None                                     │
     │ creation_time: 2026-03-15T14:00:00Z                     │
     └────────────────────────────────────────────────────────┘

═══════════════════════════════════════════════════════════════════════════════
 PAGE FETCH  — PageFetchJob
═══════════════════════════════════════════════════════════════════════════════

 Loads all PENDING items from NewsItemRepository.
 For each, calls tavily_search.extract(url):

   Success →  NewsItem updated:
     ┌────────────────────────────────────────────────────────┐
     │ status:      FETCHED                                    │
     │ raw_content: "[3,000 words of full article text]"       │
     │ error:       None                                       │
     └────────────────────────────────────────────────────────┘

   Failure →  NewsItem updated:
     ┌──────────────────────────────────┐
     │ status: FAILED                   │
     │ error:  "Tavily timeout"         │
     └──────────────────────────────────┘
     (eligible for retry on next cycle)

═══════════════════════════════════════════════════════════════════════════════
 DEDUPLICATION
═══════════════════════════════════════════════════════════════════════════════

 Deduplicator.is_duplicate(item)
   SHA-256(normalize(title + raw_content)) → "a3f9c2..."

   content_hashes.txt contains "a3f9c2..."?
   ┌─── YES ──→ DISCARD
   └─── NO  ──→ continue

═══════════════════════════════════════════════════════════════════════════════
 CONTENT PROCESSING  (single LLM call — extraction + rubric)
═══════════════════════════════════════════════════════════════════════════════

 ContentProcessor.process(item)  →  Gemini structured output

     ContentItem                         (saved to content_items.jsonl)
     ┌────────────────────────────────────────────────────────────────┐
     │ id:               "cnt_01j..."                                  │
     │ url:              "https://reuters.com/tech/apple-tsmc-..."     │
     │ source_id:        "reuters.com"                                 │
     │ title:            "Apple secures TSMC capacity for AI chips"    │
     │                                                                 │
     │ ── extraction ─────────────────────────────────────────────── │
     │ summary:          "Apple locked in TSMC N2 capacity through     │
     │                    2026, limiting competitor access."           │
     │ themes:           [SEMICONDUCTOR_SUPPLY, AI_INFRASTRUCTURE]     │
     │ entities:         ["AAPL", "TSM", "NVDA"]                       │
     │ credibility:      HIGH                                          │
     │                                                                 │
     │ ── rubric assessment ──────────────────────────────────────── │
     │ alert_category:   TECHNOLOGY_INFLECTION                         │
     │ impact_potential: HIGH                                          │
     │ narrative_shift:  True                                          │
     │ reasoning:        "Apple locking TSMC N2 capacity structurally  │
     │                    limits AI chip supply for competitors."      │
     │                                                                 │
     │ created_at:       2026-03-15T14:01:00Z                          │
     └────────────────────────────────────────────────────────────────┘

 Deduplicator.mark_seen(item)  →  "a3f9c2..." appended to content_hashes.txt
 NewsItem updated → PROCESSED

═══════════════════════════════════════════════════════════════════════════════
 FEED EVALUATION  — rule-based, no LLM  (runs once per user)
═══════════════════════════════════════════════════════════════════════════════

 FeedEvaluator.evaluate(content_item, user_profile)
   Criteria 2 (impact), 3 (narrative shift), 4 (confidence) → from ContentItem.
   Criterion 1 (relevance) → set intersection against UserProfile.

 ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─

 User A  [follows: AAPL, MSFT | themes: AI_INFRASTRUCTURE]
   push_threshold: 0.75 | push_enabled: True

   entities ∩ followed_stocks  → {"AAPL"}  ✓
   themes   ∩ followed_themes  → {AI_INFRASTRUCTURE}  ✓
   impact_potential = HIGH     ✓
   narrative_shift  = True     ✓
   credibility      = HIGH     ✓

   All criteria met → score > 0.75 → PUSH

     EvaluationResult
     ┌────────────────────────────────────────────────────────────────┐
     │ routing:               PUSH                                    │
     │ relevance_explanation: "Matches your AAPL position and         │
     │                         AI Infrastructure theme."              │
     └────────────────────────────────────────────────────────────────┘

 ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─

 User B  [follows: NVDA, AMD | push_threshold: 0.80 | push_enabled: False]

   entities ∩ followed_stocks  → {"NVDA"}  ~ (indirect mention)
   themes   ∩ followed_themes  → {}  ✗

   Weak relevance → score < 0.80 → DIGEST

═══════════════════════════════════════════════════════════════════════════════
 NOTIFICATION
═══════════════════════════════════════════════════════════════════════════════

 User A → PUSH + push_enabled=True  →  EmailChannel delivers:

   ┌────────────────────────────────────────────────────────────────┐
   │ [TECHNOLOGY INFLECTION] Apple secures TSMC capacity            │
   │                                                                 │
   │ What happened:  Apple locked in TSMC N2 capacity through 2026. │
   │ Why it matters: Structurally limits AI chip supply for NVDA.   │
   │ Why relevant:   Matches your AAPL position and AI Infra theme. │
   │ Confidence: HIGH  |  Source: Reuters                            │
   │                                                                 │
   │ [Worth it]  [Could wait]  [Not useful ▾]                        │
   └────────────────────────────────────────────────────────────────┘

 User B → DIGEST, held until Monday 09:00

═══════════════════════════════════════════════════════════════════════════════
 FEEDBACK  (User A taps "Not useful" → "Irrelevant")
═══════════════════════════════════════════════════════════════════════════════

 FeedbackSignalMapper.apply(...)
   NOT_USEFUL + IRRELEVANT → category_weights[TECHNOLOGY_INFLECTION]: 1.2 → 1.0

   Updated UserEvaluatorConfig saved to user_profiles.jsonl.
   Next cycle: TECHNOLOGY_INFLECTION weighted lower for User A.

═══════════════════════════════════════════════════════════════════════════════
 LLM COST
═══════════════════════════════════════════════════════════════════════════════

 1 LLM call per article (ContentProcessor) regardless of user count.
 FeedEvaluator: rule-based set intersection — no LLM.
```

---

## Module Specifications

### 1. `jobs`

**Location**: `src/prometheus_backend/jobs/`

Abstract base for all pipeline jobs.

```python
class Job(ABC):
    def run(self) -> None: ...
```

---

### 2. `news_aggregator`

**Location**: `src/prometheus_backend/news_aggregator/`

#### Models

```python
class NewsItemStatus(str, Enum):
    PENDING   = "pending"    # Discovered; full content not yet fetched
    FETCHED   = "fetched"    # Full raw_content retrieved; ready for pipeline
    PROCESSED = "processed"  # Passed through dedup and ContentProcessor
    FAILED    = "failed"     # Fetch or processing failed; eligible for retry

class NewsItem(BaseModel):
    url:           str              # also serves as id
    title:         str
    source_id:     str              # publisher domain, e.g. "reuters.com"
    status:        NewsItemStatus
    creation_time: datetime
    raw_content:   Optional[str]    # None until fetched
    error:         Optional[str]    # populated on FAILED

    @property
    def id(self) -> str: return self.url
```

Validation: URL must be valid, title/source_id non-blank, raw_content non-blank if provided, FETCHED requires raw_content, creation_time not in future.

#### Storage

```python
class NewsItemRepository(Repository[NewsItem]): ...
class LocalNewsItemRepository(LocalJsonlRepository[NewsItem]): ...
# Backed by data/news_items.jsonl
# Supports: repo.list(status=NewsItemStatus.PENDING)
```

#### Jobs

```python
@dataclass
class DiscoveredItem:
    url: str
    title: str
    source_id: str
    creation_time: datetime

class DiscoverySource(ABC):
    def discover(self) -> list[DiscoveredItem]: ...
    # Implementations must:
    #   1. Filter to items with publication_time > last_crawl_timestamp (watermark check)
    #   2. Normalize native format (XML/JSON/HTML) into DiscoveredItem (edge normalization)
    #   3. Update last_crawl_timestamp after successful discover()

# ── Source Types ────────────────────────────────────────────────────────────
#
# Type 1 — RSS/XML Poller
#   For: open publishers (Reuters, FT, SEC EDGAR, Reddit)
#   Method: feedparser over RSS/Atom feeds; low-bandwidth, stable
#
# Type 2 — Webhook / Enterprise API receiver
#   For: closed financial ecosystems (Bloomberg, Refinitiv/LSEG, Dow Jones)
#   Method: receive pushed data via registered webhook endpoint or pull
#           via authenticated REST/WebSocket API with cursor-based pagination
#
# Type 3 — Dynamic Crawler
#   For: JS-heavy walled gardens (Instagram, Facebook, paywalled sites)
#   Method: headless browser (Playwright) renders the page before extraction;
#           higher cost and maintenance burden — use only when no API exists
#
# DiscoverySourceFactory selects the correct type based on feed config.
# ────────────────────────────────────────────────────────────────────────────

@dataclass
class RSSFeedConfig:
    source_id:           str       # e.g. "reuters.com"
    feed_url:            str       # e.g. "https://feeds.reuters.com/reuters/businessNews"

class RSSDiscoverySource(DiscoverySource):
    # Parses RSS/Atom feed via feedparser
    # Skips entries missing url or title
    # Returns only entries where published_parsed > last_crawl_timestamp
    # Uses published_parsed for creation_time; falls back to now() on first run
    # Updates last_crawl_timestamp after each successful discover()

class DiscoverySourceFactory:
    # Inspects feed config and returns the appropriate DiscoverySource subclass.
    # Config fields (e.g. source_type: "rss" | "webhook" | "crawler") determine selection.
    @staticmethod
    def create(config: FeedConfig) -> DiscoverySource: ...

class DiscoveryJob(Job):
    # Runs all DiscoverySource(s) via DiscoverySourceFactory
    # Skips URLs already in NewsItemRepository (repo.get(url)) as secondary dedup guard
    # Stores new items as NewsItem(status=PENDING) → logical work queue for PageFetchJob

class PageFetchJob(Job):
    # Loads all PENDING items from NewsItemRepository
    # Calls tavily_search.extract(url) per item
    # Success → status=FETCHED, raw_content=content, error=None
    # Failure → status=FAILED, error=str(exception)
```

---

### 3. `deduplication`

**Location**: `src/prometheus_backend/deduplication/`

SHA-256 hash of `normalize(title + raw_content)` (lowercased, whitespace-normalized). Checked before LLM processing. `mark_seen` called only after successful `ContentProcessor` output.

```python
class HashRepository(ABC):
    def contains(self, hash: str) -> bool: ...
    def add(self, hash: str) -> None: ...

class LocalHashRepository(HashRepository): ...  # one hash per line flat file

class Deduplicator:
    def __init__(self, repo: HashRepository): ...
    def is_duplicate(self, item: NewsItem) -> bool: ...
    def mark_seen(self, item: NewsItem) -> None: ...
```

---

### 4. `content_processing`

**Location**: `src/prometheus_backend/content_processing/`

Wraps the existing `create_content_item_handler`. The LLM prompt covers both extraction and rubric assessment in a single Gemini call. `ContentItem` includes four rubric fields populated by the LLM:

| Field | Type | Description |
|---|---|---|
| `alert_category` | `AlertCategory` | Which alert category this falls under |
| `impact_potential` | `ImpactPotential` | HIGH / MEDIUM / LOW |
| `narrative_shift` | `bool` | True if this represents a structural narrative change |
| `reasoning` | `str` | "Why it matters" — surfaced in the notification |

```python
class ContentProcessor:
    def process(self, item: NewsItem) -> Optional[ContentItem]: ...
```

Returns `None` on LLM failure — pipeline skips and logs without blocking. Scheduler calls `Deduplicator.mark_seen()` and updates `NewsItem → PROCESSED` after successful output.

---

### 5. `feed_evaluation`

**Location**: `src/prometheus_backend/feed_evaluation/`

Rule-based. No LLM call. Criterion 1 (relevance) via set intersection; criteria 2–4 read from `ContentItem`.

#### Routing Logic

All four criteria must be met to route to PUSH. Partial match → DIGEST. No match → DISCARD.

| Criterion | Source |
|---|---|
| High Relevance | `ContentItem.entities ∩ UserProfile.followed_stocks` or `ContentItem.themes ∩ UserProfile.followed_themes` |
| High Impact Potential | `ContentItem.impact_potential == HIGH` |
| Narrative Shift | `ContentItem.narrative_shift == True` |
| Sufficient Confidence | `ContentItem.credibility in {MEDIUM, HIGH}` |

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

class ImpactPotential(Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

@dataclass
class EvaluationResult:
    content_item_id: str
    user_id: str
    routing: AlertRouting
    relevance_explanation: str

@dataclass
class UserEvaluatorConfig:
    push_threshold: float                          # default: 0.75
    category_weights: Dict[AlertCategory, float]   # default: 1.0 for all
    source_trust: Dict[str, float]                 # keyed by source_id, default: 1.0
    suppression_window_days: int                   # default: 7
```

#### Interface

```python
class FeedEvaluator(ABC):
    def evaluate(self, item: ContentItem, user_profile: UserProfile) -> EvaluationResult: ...

class RuleBasedFeedEvaluator(FeedEvaluator): ...
```

**Note**: The evaluator must not produce buy/sell signals, price targets, or investment advice.

---

### 6. `user_profile`

**Location**: `src/prometheus_backend/user_profile/`

```python
class Channel(Enum):
    EMAIL = "email"
    SMS = "sms"

@dataclass
class NotificationPreferences:
    push_enabled: bool
    channels: List[Channel]
    digest_schedule: str        # e.g. "Monday 09:00"

@dataclass
class UserProfile:
    user_id: str
    followed_stocks: List[str]
    followed_themes: List[ContentTheme]
    interest_reasons: Dict[str, str]
    notification_prefs: NotificationPreferences
    evaluator_config: UserEvaluatorConfig

class LocalUserProfileRepository(LocalJsonlRepository[UserProfile]): ...
```

---

### 7. `notification`

**Location**: `src/prometheus_backend/notification/`

| Mode | Default | Trigger | Frequency |
|---|---|---|---|
| Push | Disabled | PUSH-routed + push_enabled=True | 0–2/week max |
| Digest | Enabled | Per user digest_schedule | Once/week |

```python
class NotificationChannel(ABC):
    def send(self, notification: Notification, user: UserProfile) -> bool: ...

class EmailChannel(NotificationChannel): ...
class SMSChannel(NotificationChannel): ...

class NotificationService:
    def send_push(self, result: EvaluationResult, item: ContentItem, user: UserProfile) -> None: ...
    def send_digest(self, results: List[EvaluationResult], items: List[ContentItem], user: UserProfile) -> None: ...
```

`send_push` is a no-op if `push_enabled=False` — item held for next digest.

---

### 8. `feedback`

**Location**: `src/prometheus_backend/feedback/`

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
    failure_reason: Optional[FailureReason]
    free_text: Optional[str]                  # stored but not acted on in V1
```

#### Feedback → Config Mapping

| Feedback | Adjustment |
|---|---|
| WORTH_IT | Decrease `push_threshold` slightly |
| COULD_WAIT | Increase `push_threshold` slightly |
| NOT_USEFUL | Increase `push_threshold` moderately |
| NOT_USEFUL + BAD_REASONING | No threshold change; flagged for prompt review |
| NOT_USEFUL + IRRELEVANT | Decrease `category_weights[alert.category]` |
| NOT_USEFUL + UNRELIABLE | Decrease `source_trust[alert.source_id]` |
| NOT_USEFUL + REPETITIVE | Increase `suppression_window_days` |

```python
class LocalFeedbackRepository(LocalJsonlRepository[FeedbackRecord]): ...

class FeedbackCollector:
    def collect(self, record: FeedbackRecord, user_profile: UserProfile) -> UserProfile: ...

class FeedbackSignalMapper:
    def apply(self, record: FeedbackRecord, config: UserEvaluatorConfig,
              alert_category: AlertCategory, source_id: str) -> UserEvaluatorConfig: ...
```

---

### 9. `scheduler`

**Location**: `src/prometheus_backend/scheduler/`

**Entry point**: `prometheus scheduler`

```python
class PipelineScheduler:
    def run_jobs_cycle(self) -> None:
        """
        1. DiscoveryJob.run()     — find new URLs, store as PENDING
        2. PageFetchJob.run()     — fetch content for PENDING items
        3. For each FETCHED item:
           a. Deduplicator check — skip if duplicate
           b. ContentProcessor → ContentItem
           c. Deduplicator.mark_seen(); NewsItem → PROCESSED
           d. For each user profile:
              - FeedEvaluator → EvaluationResult
              - If PUSH and push_enabled: NotificationService.send_push()
              - If PUSH and push_disabled, or DIGEST: hold for digest
        """

    def run_digest_cycle(self) -> None:
        """
        1. For each user whose digest_schedule matches now:
           a. Collect pending DIGEST-routed items
           b. NotificationService.send_digest()
        """
```

`run_jobs_cycle` runs on a fixed interval (default: every 30 minutes). `run_digest_cycle` runs hourly.

---

## Directory Structure

```
src/prometheus_backend/
  ├── jobs/
  │   └── base.py                        # Job (abstract)
  ├── news_aggregator/
  │   ├── jobs/
  │   │   ├── discovery_job.py           # DiscoveryJob, DiscoverySource, DiscoveredItem,
  │   │   │                              # RSSDiscoverySource, RSSFeedConfig
  │   │   └── page_fetch_job.py          # PageFetchJob
  │   ├── models/
  │   │   └── news_item.py               # NewsItem, NewsItemStatus
  │   └── storage/
  │       └── news_item_repository.py    # NewsItemRepository, LocalNewsItemRepository
  ├── deduplication/
  │   └── deduplicator.py                # Deduplicator, compute_hash
  ├── content_processing/
  │   └── processor.py                   # ContentProcessor
  ├── feed_evaluation/
  │   ├── models.py                      # EvaluationResult, UserEvaluatorConfig,
  │   │                                  # AlertCategory, ImpactPotential
  │   └── evaluator.py                   # FeedEvaluator (abstract), RuleBasedFeedEvaluator
  ├── user_profile/
  │   ├── models.py                      # UserProfile, NotificationPreferences
  │   └── repository.py
  ├── notification/
  │   ├── models.py                      # Notification
  │   ├── service.py                     # NotificationService
  │   ├── formatter.py                   # NotificationFormatter
  │   ├── scheduler.py                   # DigestScheduler
  │   └── channels/
  │       ├── base.py                    # NotificationChannel (abstract)
  │       ├── email_channel.py
  │       └── sms_channel.py
  ├── feedback/
  │   ├── models.py                      # FeedbackRecord, InterruptionValue, FailureReason
  │   ├── collector.py                   # FeedbackCollector
  │   ├── signal_mapper.py               # FeedbackSignalMapper
  │   └── repository.py
  ├── storage/
  │   ├── repository_base.py             # Repository[T] + LocalJsonlRepository[M]
  │   │                                  # list(**filters) for field-level filtering
  │   ├── hash_repository_base.py        # HashRepository + LocalHashRepository
  │   └── local_file_system/
  │       └── content_item_store.py      # ContentItemStore
  └── scheduler/
      └── pipeline_scheduler.py
```

---

## Storage Files (Local)

```
src/prometheus_backend/data/
  ├── news_items.jsonl          # NewsItem records (PENDING → FETCHED → PROCESSED)
  ├── content_items.jsonl       # ContentItem records (LLM output)
  ├── content_hashes.txt        # one SHA-256 hash per line
  ├── user_profiles.jsonl
  └── feedback.jsonl
```

---

## Inter-Module Dependencies

```
scheduler ──> news_aggregator (jobs, models, storage)
           ──> deduplication
           ──> content_processing ──> (existing) handlers, services, storage
           ──> feed_evaluation    ──> user_profile
           ──> notification       ──> user_profile
           ──> feedback           ──> user_profile, feed_evaluation.models

news_aggregator.jobs ──> jobs.base
                     ──> news_aggregator.models
                     ──> news_aggregator.storage
feed_evaluation      ──> user_profile.models
feedback             ──> feed_evaluation.models, user_profile
```

No circular dependencies.

---

## Implementation Order

1. ~~`storage/repository_base.py`~~ **done**
2. ~~`deduplication`~~ **done**
3. ~~`news_aggregator/models/news_item.py`~~ **done**
4. ~~`news_aggregator/storage/news_item_repository.py`~~ **done**
5. ~~`jobs/base.py`~~ **done**
6. ~~`news_aggregator/jobs/discovery_job.py`~~ **done**
7. ~~`news_aggregator/jobs/page_fetch_job.py`~~ **done**
8. `content_processing` — extend LLM prompt with rubric fields; update `ContentItem` model
9. `user_profile`
10. `feed_evaluation` — rule-based `RuleBasedFeedEvaluator`
11. `scheduler` — wires everything into a runnable cycle
12. `notification` — Email + SMS delivery
13. `feedback` — closes the loop
