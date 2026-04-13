# Module Design — Prometheus Alert Agent Pipeline

> **Reference**: All implementation work on the alert agent pipeline must refer to this document first.
> This design is grounded in [PRD.md](../PRD.md). When in doubt, defer to the PRD.

---

## Overview

The alert agent pipeline discovers and fetches news via a jobs layer, deduplicates by content hash, processes unique items through an LLM to produce structured content feeds (including rubric assessment), clusters processed content items by entity, theme, and date, then evaluates each cluster against matched user profiles via a batch LLM call, delivers alerts via configurable channels, and collects feedback that directly tunes future evaluations.

### Design Principles

- **Local-first, DB-ready**: All storage uses a `Repository[T]` abstract interface with `list(**filters)` for field-level filtering. Local JSONL implementations ship first; swapping to a database requires only a new concrete implementation — no business logic changes.
- **Two-phase ingestion**: Discovery and fetching are decoupled jobs. `DiscoveryJob` finds URLs and stores `PENDING` items. `PageFetchJob` fetches full content and updates to `FETCHED`. Failures are retryable.
- **Single LLM call per article**: Rubric assessment (impact potential, narrative shift, confidence, category, reasoning) is baked into `ContentProcessor`. Cost scales with articles ingested.
- **Clustering before evaluation**: `ContentItem`s are grouped into `ContentCluster`s by entity, theme, and date window before evaluation. The cluster is the unit of evaluation — not individual items.
- **Batch LLM evaluation**: One Gemini call receives a `ContentCluster` + matched `UserProfile`s and returns a list of `EvaluationResult`s. Cost scales with clusters, not users × items.
- **Routing lives on `EvaluationResult`, not `ContentItem`**: The same item can be PUSH for one user, DIGEST for another, and DISCARD for a third.
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
[ContentProcessingJob] ──> LLM (extraction + rubric) ──> ContentItem ──> ContentItemStore
  NewsItem updated → PROCESSED
         |
[ClusteringJob]
  groups ContentItems by entity / theme / date window
  ──> ContentCluster ──> ContentClusterStore
         |
[FeedEvaluationJob]
  step 1: filter UserProfiles by entity/theme overlap with cluster
  step 2: batch LLM call (cluster summaries + matched user profiles + push history per user)
  step 3: persist EvaluationResult(cluster_id, user_id, routing, synthesis) per user
         |
   ┌─────┴──────┬───────────┐
 PUSH        DIGEST      DISCARD
   |             |
   ▼        (held in EvaluationResultStore for digest scheduler — future work)
[NotificationService] ──> EmailChannel / SMSChannel
  ──> PushHistoryStore
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
 CLUSTERING  — ClusteringJob
═══════════════════════════════════════════════════════════════════════════════

 ClusteringJob groups today's ContentItems by overlapping entities and themes.

 Example: three tech articles published 2026-04-12 share entities [TSM, NVDA, AAPL]

     ContentCluster written to content_clusters.jsonl
     ┌────────────────────────────────────────────────────────────────┐
     │ id:               "clu_01j..."                                  │
     │ content_item_ids: ["cnt_01j...", "cnt_02j...", "cnt_03j..."]    │
     │ summaries:        ["Apple locked in TSMC N2 capacity...",       │
     │                    "TSMC warns of equipment delivery delays...", │
     │                    "NVDA orders shift to alternate suppliers..."]│
     │ entities:         ["AAPL", "TSM", "NVDA"]                       │
     │ themes:           [TECHNOLOGY]                                   │
     │ date_window:      2026-04-12                                     │
     └────────────────────────────────────────────────────────────────┘

═══════════════════════════════════════════════════════════════════════════════
 FEED EVALUATION  — FeedEvaluationJob  (batch LLM call per cluster)
═══════════════════════════════════════════════════════════════════════════════

 Step 1 — filter UserProfiles by entity/theme overlap with cluster
   User A  [follows: AAPL, MSFT | themes: TECHNOLOGY]  → entities ∩ {"AAPL"} ✓  matched
   User B  [follows: NVDA, AMD  | themes: TECHNOLOGY]  → entities ∩ {"NVDA"} ✓  matched
   User C  [follows: JPM        | themes: FINANCIALS]  → no overlap             skipped

 Step 2 — single batch LLM call
   Input:
     cluster summaries   → ["Apple locked in TSMC N2...", "TSMC warns of delays...", ...]
     User A profile      → follows AAPL, MSFT; interest: "AI infrastructure exposure"
     User A push history → ["Nvidia earnings beat — 2026-04-10"]
     User B profile      → follows NVDA, AMD; interest: "semiconductor supply chain"
     User B push history → []

 Step 3 — LLM returns list of EvaluationResults, persisted to evaluation_results.jsonl

     User A → EvaluationResult
     ┌────────────────────────────────────────────────────────────────┐
     │ id:         "evr_01j..."                                        │
     │ cluster_id: "clu_01j..."                                        │
     │ user_id:    "usr_A"                                             │
     │ routing:    PUSH                                                 │
     │ synthesis:  "Apple locking TSMC N2 capacity structurally limits │
     │              AI chip supply — directly affects your AAPL thesis."│
     └────────────────────────────────────────────────────────────────┘

     User B → EvaluationResult
     ┌────────────────────────────────────────────────────────────────┐
     │ id:         "evr_02j..."                                        │
     │ cluster_id: "clu_01j..."                                        │
     │ user_id:    "usr_B"                                             │
     │ routing:    DIGEST                                               │
     │ synthesis:  "TSMC capacity constraints may affect NVDA supply   │
     │              chain — worth watching but no immediate action."   │
     └────────────────────────────────────────────────────────────────┘

═══════════════════════════════════════════════════════════════════════════════
 NOTIFICATION
═══════════════════════════════════════════════════════════════════════════════

 User A → PUSH + push_enabled=True  →  EmailChannel delivers:

   ┌────────────────────────────────────────────────────────────────┐
   │ [TECHNOLOGY INFLECTION] TSMC capacity cluster — 3 developments │
   │                                                                 │
   │ What's happening: Apple locked in TSMC N2 capacity through     │
   │   2026, TSMC warns of equipment delays, NVDA shifts orders.    │
   │ Why it matters:   Structurally limits AI chip supply.          │
   │ Why relevant:     Matches your AAPL position.                  │
   │                                                                 │
   │ [Worth it]  [Could wait]  [Not useful ▾]                        │
   └────────────────────────────────────────────────────────────────┘
   PushHistory record written to push_history.jsonl.

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

 1 LLM call per article (ContentProcessingJob) regardless of user count.
 1 LLM call per ContentCluster (FeedEvaluationJob) regardless of matched user count.
 Cost scales with clusters × days, not users × articles.
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

### 5. `clustering`

**Location**: `src/prometheus_backend/clustering/`

Groups `ContentItem`s into `ContentCluster`s by overlapping entities, themes, and date window.
The cluster is the unit of evaluation downstream — not individual items.

```python
class ContentCluster(BaseModel):
    id: str
    content_item_ids: list[str]
    summaries: list[str]          # ContentItem.summary per item — passed to LLM as context
    entities: list[str]           # union of entities across all items in cluster
    themes: list[ContentTheme]    # union of themes across all items in cluster
    date_window: date             # e.g. 2026-04-12

class ContentClusterStore(LocalJsonlRepository[ContentCluster]): ...
# Backed by data/content_clusters.jsonl

class ClusteringJob(Job):
    # Loads ContentItems for the target date_window from ContentItemStore
    # Groups by overlapping entities and themes into ContentClusters
    # Persists each cluster to ContentClusterStore
```

---

### 6. `feed_evaluation`

**Location**: `src/prometheus_backend/feed_evaluation/`

LLM-assisted. One batch Gemini call per `ContentCluster` covers all matched users.
Routing (PUSH / DIGEST / DISCARD) is a property of `EvaluationResult` — not of `ContentItem` or
`ContentCluster`. The same cluster can produce different routings for different users.

**Note**: The evaluator must not produce buy/sell signals, price targets, or investment advice.

#### Risk: context window size
User filtering in step 1 is load-bearing. If the entity/theme overlap filter is too loose,
the batch LLM prompt grows large on busy news days. Future mitigation: tighter sector-level
pre-filtering or splitting large clusters.

#### Models

```python
class AlertRouting(str, Enum):
    PUSH = "push"
    DIGEST = "digest"      # relevant but not urgent — held for weekly digest
    DISCARD = "discard"

class EvaluationResult(BaseModel):
    id: str
    cluster_id: str
    user_id: str
    routing: AlertRouting
    synthesis: str         # LLM-generated summary, user-facing on PUSH and DIGEST

class PushHistory(BaseModel):
    id: str
    user_id: str
    cluster_id: str
    pushed_at: datetime
```

#### Storage

```python
class EvaluationResultStore(LocalJsonlRepository[EvaluationResult]): ...
# Backed by data/evaluation_results.jsonl
# All routings persisted. Digest scheduler queries routing=DIGEST per user (future work).

class PushHistoryStore(LocalJsonlRepository[PushHistory]): ...
# Backed by data/push_history.jsonl
# Source of truth for "past alerts sent" — passed as user context in batch LLM prompt.
```

#### Job

```python
class FeedEvaluationJob(Job):
    def __init__(
        self,
        cluster_store: ContentClusterStore,
        user_profile_repository: LocalUserProfileRepository,
        evaluation_result_store: EvaluationResultStore,
        push_history_store: PushHistoryStore,
        gemini: GeminiClient,
    ) -> None: ...

    def run(self) -> None:
        # For each ContentCluster not yet evaluated:
        #   step 1: filter UserProfiles by entity/theme overlap with cluster
        #   step 2: batch LLM call with cluster summaries + matched profiles
        #           + recent PushHistory per user (dedup context)
        #   step 3: persist EvaluationResult per user
        #           write PushHistory for PUSH-routed results
```

---

### 7. `user_profile`

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

### 8. `notification`

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
    def send_push(self, result: EvaluationResult, user: UserProfile) -> None: ...
    # result.synthesis is the notification body
    # writes PushHistory on successful delivery
    def send_digest(self, results: list[EvaluationResult], user: UserProfile) -> None: ...
    # collects routing=DIGEST results for user; future work
```

`send_push` is a no-op if `push_enabled=False` — result held for next digest.

---

### 9. `feedback`

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

### 10. `scheduler`

**Location**: `src/prometheus_backend/scheduler/`

**Entry point**: `prometheus scheduler`

```python
class PipelineScheduler:
    def run_jobs_cycle(self) -> None:
        """
        1. DiscoveryJob.run()          — find new URLs, store as PENDING
        2. PageFetchJob.run()          — fetch content for PENDING items
        3. DeduplicationJob.run()      — hash-check FETCHED items, mark DEDUPLICATED
        4. ContentProcessingJob.run()  — LLM extraction + rubric → ContentItem, mark PROCESSED
        5. ClusteringJob.run()         — group today's ContentItems into ContentClusters
        6. FeedEvaluationJob.run()     — batch LLM evaluation per cluster → EvaluationResults
                                         NotificationService.send_push() for PUSH-routed results
        """

    def run_digest_cycle(self) -> None:
        """
        1. For each user whose digest_schedule matches now:
           a. Collect EvaluationResults with routing=DIGEST for that user
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
  ├── clustering/
  │   ├── jobs/
  │   │   └── clustering_job.py          # ClusteringJob
  │   ├── models.py                      # ContentCluster
  │   └── storage.py                     # ContentClusterStore
  ├── feed_evaluation/
  │   ├── jobs/
  │   │   └── feed_evaluation_job.py     # FeedEvaluationJob
  │   ├── models.py                      # EvaluationResult, AlertRouting,
  │   │                                  # PushHistory
  │   └── storage.py                     # EvaluationResultStore, PushHistoryStore
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
  ├── content_clusters.jsonl    # ContentCluster records (ClusteringJob output)
  ├── evaluation_results.jsonl  # EvaluationResult records (all routings)
  ├── push_history.jsonl        # PushHistory records (delivered pushes per user)
  ├── user_profiles.jsonl
  └── feedback.jsonl
```

---

## Inter-Module Dependencies

```
scheduler ──> news_aggregator (jobs, models, storage)
           ──> deduplication
           ──> content_processing ──> (existing) handlers, services, storage
           ──> clustering          ──> content_processing.storage
           ──> feed_evaluation     ──> clustering.models, clustering.storage
                                   ──> user_profile
           ──> notification        ──> user_profile, feed_evaluation.models
           ──> feedback            ──> user_profile, feed_evaluation.models

news_aggregator.jobs ──> jobs.base
                     ──> news_aggregator.models
                     ──> news_aggregator.storage
clustering           ──> content_processing.storage
feed_evaluation      ──> clustering.models, user_profile.models
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
10. `clustering` — `ClusteringJob`, `ContentCluster`, `ContentClusterStore`
11. `feed_evaluation` — `FeedEvaluationJob`, `EvaluationResult`, `PushHistory`, stores
12. `scheduler` — wires all jobs into a runnable cycle
13. `notification` — Email + SMS delivery
14. `feedback` — closes the loop

---

## Future Work

| # | Item | Why deferred |
|---|---|---|
| 1 | Entity dependency graph DB | LLM infers cross-entity dependencies via cluster context for now |
| 2 | Narrative shift DB | LLM detects shifts by comparing summaries in cluster context for now |
| 3 | Agentic evaluator (dynamic web search) | Static cluster batch is sufficient for V1 |
| 4 | Semantic dedup in `ContentProcessingJob` | SHA-256 hash dedup is good enough for V1 |
| 5 | `ContentItem` indexing by theme, entity, date | Python-level filtering acceptable at current scale |
| 6 | `UserProfile` DB + indexing by entity/theme | Small user base for now |
| 7 | Push rate cap enforcement (0–2/week max) | `PushHistoryStore` provides the data; enforcement logic deferred |
| 8 | Digest aggregation + scheduling | `EvaluationResult(routing=DIGEST)` items are persisted; scheduler is future work |
| 9 | Feedback loop wired into evaluator | `UserEvaluatorConfig` fields defined; not yet passed into LLM prompt |
