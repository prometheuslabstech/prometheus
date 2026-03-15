# Module Design — Prometheus Alert Agent Pipeline

> **Reference**: All implementation work on the alert agent pipeline must refer to this document first.
> This design is grounded in [PRD.md](../PRD.md). When in doubt, defer to the PRD.

---

## Overview

The alert agent pipeline ingests news from configurable sources, deduplicates by content hash, processes unique items through an LLM to produce structured content feeds (including rubric assessment), evaluates each feed item for notification worthiness per user via rule-based relevance matching, delivers alerts via configurable channels, and collects feedback that directly tunes future evaluations.

### Design Principles

- **Local-first, DB-ready**: All storage uses a `Repository[T]` abstract interface. Local JSONL implementations ship first; swapping to a database requires only a new concrete implementation — no business logic changes.
- **Single LLM call per article**: Rubric assessment (impact potential, narrative shift, confidence, category, reasoning) is baked into `ContentProcessor`. `FeedEvaluator` is rule-based — relevance matching only. Cost scales with articles, not users.
- **Scalable evaluator**: `FeedEvaluator` is abstract. Start with rule-based; LLM-assisted variants can be added without touching the pipeline.
- **Abstract news sources**: `NewsSource` is an interface. Tavily and RSS ship first; paid API sources plug in without pipeline changes.
- **Feedback closes the loop**: Feedback from users directly adjusts per-user `UserEvaluatorConfig`, which the evaluator reads on every run.
- **Precision over recall in alerting**: Per PRD — we would rather miss a borderline event than train users to ignore notifications.

---

## Pipeline

```
[PipelineScheduler] triggers ingestion cycle
         |
[NewsSource(s)] ──> RawNewsItem
         |
[Deduplicator]  ──> SHA-256 hash check ──> skip if already seen
         |
[ContentProcessor] ──> LLM (extraction + rubric) ──> ContentItem ──> ContentItemRepository
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
 INGESTION
═══════════════════════════════════════════════════════════════════════════════

 TavilyNewsSource.fetch()
 queries: ["Apple AI chip supply chain", "TSMC capacity 2025"]

     RawNewsItem
     ┌────────────────────────────────────────────────────────┐
     │ url:         "https://reuters.com/tech/apple-tsmc-..."  │
     │ title:       "Apple secures TSMC capacity for AI chips" │
     │ source_id:   "tavily"                                   │
     │ raw_content: "[3,000 words of full article text]"       │
     │ fetched_at:  2026-03-15T14:00:00Z                       │
     └────────────────────────────────────────────────────────┘

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
     │ source_id:        "tavily"                                      │
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

### 1. `news_ingestion`

**Location**: `src/prometheus_backend/news_ingestion/`

```python
@dataclass
class RawNewsItem:
    url: str
    title: str
    source_id: str       # identifies which NewsSource produced this
    raw_content: str     # full text content
    fetched_at: datetime
```

```
NewsSource (abstract)
  ├── fetch() -> List[RawNewsItem]
  ├── TavilyNewsSource      # search() + extract() per result
  ├── RSSNewsSource         # feedparser; raw_content = RSS summary
  └── APINewsSource         # future: Bloomberg, Reuters, etc.
```

Each source is independently configurable (search queries, feed URLs, API credentials). Sources are instantiated and injected into the scheduler.

---

### 2. `deduplication`

**Location**: `src/prometheus_backend/deduplication/`

SHA-256 hash of `normalize(title + raw_content)` (lowercased, whitespace-normalized). Hash is checked before LLM processing. `mark_seen` is called only after successful `ContentProcessor` output.

```python
class HashRepository(ABC):
    def contains(self, hash: str) -> bool: ...
    def add(self, hash: str) -> None: ...

class LocalHashRepository(HashRepository): ...  # one hash per line flat file

class Deduplicator:
    def __init__(self, repo: HashRepository): ...
    def is_duplicate(self, item: RawNewsItem) -> bool: ...
    def mark_seen(self, item: RawNewsItem) -> None: ...
```

---

### 3. `content_processing`

**Location**: `src/prometheus_backend/content_processing/`

Wraps the existing `create_content_item_handler`. The LLM prompt is extended to also return rubric assessment fields alongside extraction fields. `ContentItem` gains four new fields populated by the LLM:

| New field | Type | Description |
|---|---|---|
| `alert_category` | `AlertCategory` | Which alert category this falls under |
| `impact_potential` | `ImpactPotential` | HIGH / MEDIUM / LOW |
| `narrative_shift` | `bool` | True if this represents a structural narrative change |
| `reasoning` | `str` | "Why it matters" — surfaced directly in the notification |

```python
class ContentProcessor:
    def process(self, item: RawNewsItem) -> Optional[ContentItem]: ...
```

Returns `None` on LLM failure — pipeline skips and logs without blocking. `Deduplicator.mark_seen()` is called by `PipelineScheduler` after successful processing.

---

### 4. `feed_evaluation`

**Location**: `src/prometheus_backend/feed_evaluation/`

Rule-based. No LLM call. Evaluates criterion 1 (relevance) via set intersection; criteria 2–4 are read directly from `ContentItem`.

#### Routing Logic

All four criteria must be met to route to PUSH. Partial match routes to DIGEST. No match routes to DISCARD.

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
    relevance_explanation: str   # "Matches your AAPL position and AI Infra theme."

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

class RuleBasedFeedEvaluator(FeedEvaluator):
    # Reads rubric fields from ContentItem.
    # Runs relevance check against UserProfile.
    # Applies UserEvaluatorConfig thresholds and weights.
    ...
```

**Note**: The evaluator must not produce buy/sell signals, price targets, or investment advice.

---

### 5. `user_profile`

**Location**: `src/prometheus_backend/user_profile/`

```python
class Channel(Enum):
    EMAIL = "email"
    SMS = "sms"

@dataclass
class NotificationPreferences:
    push_enabled: bool          # False by default
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

class UserProfileRepository(Repository[UserProfile]):
    def put(self, profile: UserProfile) -> None: ...
    def get(self, user_id: str) -> Optional[UserProfile]: ...
    def list(self) -> List[UserProfile]: ...
    def delete(self, user_id: str) -> None: ...

class LocalUserProfileRepository(LocalJsonlRepository[UserProfile]): ...
```

---

### 6. `notification`

**Location**: `src/prometheus_backend/notification/`

| Mode | Default | Trigger | Frequency |
|---|---|---|---|
| Push | Disabled | PUSH-routed + push_enabled=True | 0–2/week max |
| Digest | Enabled | Per user digest_schedule | Once/week |

```python
@dataclass
class Notification:
    user_id: str
    alert_category: AlertCategory
    summary: str          # from ContentItem
    reasoning: str        # from ContentItem
    relevance: str        # from EvaluationResult
    credibility: ContentCredibility
    source_url: str
    created_at: datetime

class NotificationChannel(ABC):
    def send(self, notification: Notification, user: UserProfile) -> bool: ...

class EmailChannel(NotificationChannel): ...
class SMSChannel(NotificationChannel): ...

class NotificationFormatter:
    def format_push(self, notification: Notification, channel: Channel) -> str: ...
    def format_digest(self, notifications: List[Notification], channel: Channel) -> str: ...

class NotificationService:
    def send_push(self, result: EvaluationResult, item: ContentItem, user: UserProfile) -> None: ...
    def send_digest(self, results: List[EvaluationResult], items: List[ContentItem], user: UserProfile) -> None: ...
```

`send_push` is a no-op if `push_enabled=False` — item is held for next digest. Digest content: top 3–5 PUSH-worthy items, notable narrative shifts, 1–2 emerging signals.

---

### 7. `feedback`

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
    failure_reason: Optional[FailureReason]   # required if NOT_USEFUL
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
class FeedbackRepository(Repository[FeedbackRecord]):
    def put(self, record: FeedbackRecord) -> None: ...
    def get(self, id: str) -> Optional[FeedbackRecord]: ...
    def list(self) -> List[FeedbackRecord]: ...
    def list_by_user(self, user_id: str) -> List[FeedbackRecord]: ...
    def delete(self, id: str) -> None: ...

class LocalFeedbackRepository(LocalJsonlRepository[FeedbackRecord]): ...

class FeedbackCollector:
    def __init__(self, repo: FeedbackRepository, signal_mapper: FeedbackSignalMapper): ...
    def collect(self, record: FeedbackRecord, user_profile: UserProfile) -> UserProfile: ...

class FeedbackSignalMapper:
    def apply(
        self,
        record: FeedbackRecord,
        config: UserEvaluatorConfig,
        alert_category: AlertCategory,
        source_id: str,
    ) -> UserEvaluatorConfig: ...
```

---

### 8. `scheduler`

**Location**: `src/prometheus_backend/scheduler/`

**Entry point**: `prometheus scheduler`

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

    def run_digest_cycle(self) -> None:
        """
        1. For each user whose digest_schedule matches now:
           a. Collect pending DIGEST-routed items for that user
           b. NotificationService.send_digest()
        """
```

`run_ingestion_cycle` runs on a fixed interval (default: every 30 minutes). `run_digest_cycle` runs hourly and checks each user's `digest_schedule`. Both cycles are independent.

---

## Directory Structure

```
src/prometheus_backend/
  ├── news_ingestion/
  │   ├── models.py                  # RawNewsItem
  │   └── sources/
  │       ├── base.py                # NewsSource (abstract)
  │       ├── tavily_source.py
  │       └── rss_source.py
  ├── deduplication/
  │   └── deduplicator.py            # Deduplicator, compute_hash
  ├── content_processing/
  │   └── processor.py               # ContentProcessor (wraps existing handler)
  ├── feed_evaluation/
  │   ├── models.py                  # EvaluationResult, UserEvaluatorConfig, AlertCategory, ImpactPotential
  │   └── evaluator.py               # FeedEvaluator (abstract) + RuleBasedFeedEvaluator
  ├── user_profile/
  │   ├── models.py                  # UserProfile, NotificationPreferences
  │   └── repository.py
  ├── notification/
  │   ├── models.py                  # Notification
  │   ├── service.py                 # NotificationService
  │   ├── formatter.py               # NotificationFormatter
  │   ├── scheduler.py               # DigestScheduler
  │   └── channels/
  │       ├── base.py                # NotificationChannel (abstract)
  │       ├── email_channel.py
  │       └── sms_channel.py
  ├── feedback/
  │   ├── models.py                  # FeedbackRecord, InterruptionValue, FailureReason
  │   ├── collector.py               # FeedbackCollector
  │   ├── signal_mapper.py           # FeedbackSignalMapper
  │   └── repository.py
  ├── storage/
  │   ├── repository_base.py         # Repository[T] + LocalJsonlRepository[M]
  │   ├── hash_repository_base.py    # HashRepository + LocalHashRepository
  │   └── local_file_system/
  │       └── content_item_store.py  # ContentItemStore
  └── scheduler/
      └── pipeline_scheduler.py
```

---

## Storage Files (Local)

```
src/prometheus_backend/data/
  ├── content_items.jsonl       # existing
  ├── content_hashes.txt        # one SHA-256 hash per line
  ├── user_profiles.jsonl
  └── feedback.jsonl
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

feed_evaluation ──> user_profile.models
feedback        ──> feed_evaluation.models, user_profile
```

No circular dependencies.

---

## Implementation Order

1. ~~`storage/repository_base.py`~~ **done**
2. ~~`deduplication`~~ **done**
3. ~~`news_ingestion/models.py`~~ **done**
4. `news_ingestion/sources/` — `NewsSource` abstract + `TavilyNewsSource` + `RSSNewsSource`
5. `content_processing` — extend LLM prompt with rubric fields; update `ContentItem` model
6. `user_profile`
7. `feed_evaluation` — rule-based `RuleBasedFeedEvaluator`
8. `scheduler` — wires 1–7 into a runnable cycle
9. `notification` — Email + SMS delivery
10. `feedback` — closes the loop
