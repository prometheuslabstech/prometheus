# Ideas

## Investor Persona Themes for FeedEvaluator

Users select one or more investor personas when configuring their feed. The `FeedEvaluator` uses the chosen persona(s) to determine whether a processed article is relevant enough to trigger a push notification.

Each persona is built from a deep-dive into the investor's publicly documented principles, mental models, and areas of focus. These characteristics are encoded as evaluation criteria that map onto the structured fields already extracted by `ContentProcessor` (themes, entities, impact potential, narrative shift, credibility).

### Proposed Personas

**Charlie Munger**
Focus: mental models, moat quality, business rationality, avoiding stupidity. Alerts on companies with durable competitive advantages, rational capital allocation, and management integrity. Filters out speculative or momentum-driven noise.

**Warren Buffett**
Focus: intrinsic value, margin of safety, consumer brands, long holding horizon. Alerts on earnings quality, franchise durability, insider buying, and undervaluation signals. Ignores macro and short-term price action.

**Stanley Druckenmiller**
Focus: macro reflexivity, global liquidity, currency flows, asymmetric risk/reward. Alerts on central bank policy shifts, credit market stress, commodity regime changes, and geopolitical inflection points.

### How It Works

1. User sets their persona(s) in `UserEvaluatorConfig`.
2. `FeedEvaluator` loads the persona definition(s) and evaluates the `ContentItem` against their criteria.
3. If the article scores above the relevance threshold for the user's persona, a push notification is dispatched.
4. Multiple personas can be combined — the union of their criteria applies.

### Why This Is Better Than Generic Filtering

Generic keyword filtering produces noisy, low-signal alerts. Persona-based evaluation mirrors how a real investor would read the news — a Druckenmiller follower genuinely does not care about a consumer brand's earnings beat, and a Buffett follower genuinely does not care about Fed dot plots. Encoding this intent at the evaluator level means the user gets alerts that match their actual investment philosophy.
