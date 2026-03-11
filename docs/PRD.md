📌 Product Aim
One-liner (for pitch / landing page):
Build an AI-powered investment awareness companion that helps users structure their investment context, stay on top of relevant industry and company developments, and surface high-signal changes — without providing investment advice or recommendations.
Product Vision (PRD version):
The product aims to help busy, non-expert investors build a structured understanding of the stocks and industries they care about, continuously track relevant developments, and stay aware of meaningful narrative shifts and emerging signals. By reducing information overload and providing clear, contextualized “attention alerts,” the product empowers users to make better-informed decisions independently, while avoiding any form of financial advice or trade recommendations.

🎯 Core User Problems
Users invest in domains they don’t fully understand yet
 Users explore new industries and companies without a clear mental model of key drivers and risks.


Users don’t have time to track all relevant news
 Important developments are scattered across earnings, regulation, industry reports, and media coverage.


Users forget why they bought certain stocks
 Over time, original assumptions fade, weakening the ability to contextualize new information.


Users miss important changes in industry or company narratives
 Structural shifts happen gradually and are easy to overlook without continuous monitoring.


Users get overwhelmed by noise and headlines
 The volume of financial news makes it difficult to identify what is truly material.


Users fail to identify emerging, fast-growing industries or companies at an early stage
 Early signals of new growth narratives are often missed until they become mainstream.


Users lose trust in alerts and notifications because most alerts are low-value
 Frequent, low-signal notifications lead to alert fatigue. Users mute notifications and miss truly important developments because they no longer trust that interruptions are worth their attention.

🚫 Non-Goals (Explicit Scope Boundaries)
To avoid legal, regulatory, and user trust risks, the product explicitly does not aim to:
Provide any form of investment advice, recommendations, or trade signals
Suggest buying, selling, holding, or timing of specific stocks or assets
Predict stock prices, returns, or market performance
Optimize or manage user portfolios or asset allocations
Execute trades or connect to brokerage accounts
Claim or imply the ability to generate alpha or outperform the market
Positioning Principle:
The product focuses on awareness, context, and signal surfacing, not on decision-making or execution. All investment decisions remain entirely with the user.


Notification Policy (PRD Section)
🎯 Design Principle
Notifications are a scarce and high-cost interruption.
 The product should only notify users when there is a high-confidence, high-impact development that is genuinely worth their attention.
The goal is to maximize trust per notification, not total notification volume.

✅ When We Send Notifications (V1 Policy)
Notifications are sent only when all of the following are true:
High Relevance
 The event is directly related to:


A stock in the user’s portfolio, or


An industry/theme the user explicitly follows.


High Impact Potential
 The event represents a meaningful change in:


Company fundamentals


Industry structure


Regulation / policy environment


Technology trajectory


Macro conditions that disproportionately affect the user’s interests


Narrative Shift or Early Signal
 The event indicates:


A structural narrative change (e.g., strategic pivot, regulatory inflection), or


An early signal of an emerging trend within the user’s interest areas.


Sufficient Confidence
 The system’s confidence level is Medium–High or High, based on:


Source credibility


Cross-source corroboration


Consistency with recent developments


If any of the above criteria are not met, the content is included in the weekly digest instead of triggering a push notification.

🚫 When We Do NOT Send Notifications
We explicitly do not send notifications for:
Routine earnings releases without narrative change


Minor price movements or short-term volatility


General market news not specifically tied to the user’s interests


Low-confidence or speculative headlines


Incremental updates that do not materially change the underlying story


This protects users from alert fatigue and preserves the perceived value of interruptions.

🗂 Notification Categories (User-Facing Framing)
Each notification is tagged with a clear category so users immediately understand why they’re being interrupted:
🏢 Company Narrative Shift


🏭 Industry Structure Change


🧑‍⚖️ Regulation / Policy Impact


🧪 Technology / Product Inflection


🌍 Macro Impact on Your Interests


🌱 Emerging Signal in Your Focus Areas



📅 Default Delivery Strategy (V1)
Push Notifications:


Disabled by default


“Critical only”


Expected frequency: rare (e.g., 0–2 per week at most)


Weekly Digest:


Default primary channel


Summarizes:


Top attention alerts


Narrative shifts


Emerging signals within user interests


This ensures:
Users feel informed without being interrupted unless it truly matters.

📏 Notification Quality Metrics (Internal)
To guard against notification spam, track:
Notification Open Rate


Post-notification engagement (did user read full context?)


Notification Mute Rate


“Was this worth interrupting you?” feedback


Avg. notifications per user per week (should remain low)


A rising mute rate or falling open rate is treated as a product regression.

🧠 Product Philosophy (Optional, for internal alignment)
We would rather miss a borderline-important event
 than train users to ignore all notifications.
This enforces a culture of precision over recall in alerting.


========================================================================
MVP Objective
Deliver a lightweight AI-powered investment awareness tool that helps users:
Build a structured understanding of the stocks, industries, and themes they care about


Discover and track relevant developments over time


Receive high-signal “attention alerts” with clear reasoning


Avoid missing important narrative shifts and early signals


Stay informed without being overwhelmed or spammed


The MVP explicitly does not provide any investment advice or recommendations. All decisions remain with the user.
Target User (V1)
Busy professionals


Curious, non-expert investors


Users exploring new industries or technologies


People who want to stay informed without constantly checking financial news


Not targeting:
Day traders


Professional investors


Users seeking buy/sell signals
In-Scope Features (What V1 Includes)
1️⃣ Guided Onboarding & Personal Profile Builder (P1)
Goal: Create a lightweight, structured user profile to personalize relevance.
User can:
Add stocks they follow (or hold, optional phrasing)


Select industries/themes they are curious about


Choose Discovery Mode if they have no clear interests


AI-guided questions capture:
Why the user is interested in each stock/theme


What kind of stories they care about (technology, growth, regulation, etc.)


Risk & time horizon preferences (lightweight, inferred)


Output:
A structured personal investment context profile used only for relevance ranking and explanation.



2️⃣ Personalized News Tracking & Filtering
Goal: Reduce noise and surface what matters to the user.
System behavior:
Ingest curated company, industry, and macro news


Rank and filter based on:


User’s followed stocks


User’s followed industries/themes


Inferred interests from interactions


User sees:
A personalized feed of relevant developments


Clear explanation: “Why this is relevant to you”



3️⃣ High-Signal Attention Alerts (Core Differentiator)
Goal: Surface only meaningful developments worth the user’s attention.
Each Attention Alert includes:
What happened (concise summary)


Why it matters (AI reasoning)


Which of the user’s stocks or interests it relates to


Category:


Company narrative shift


Industry structure change


Regulation / policy


Technology / product inflection


Macro impact on user interests


Emerging signal


Confidence level (Low / Medium / High)


No:
Buy/sell suggestions


Performance claims


Price targets



4️⃣ Weekly Digest (Primary Delivery Mechanism)
Goal: Keep users informed without overwhelming them.
Default cadence: weekly


Includes:


Top 3–5 attention alerts


Any notable narrative shifts in followed areas


One or two emerging signals related to user interests


Push notifications reserved only for rare, high-confidence, high-impact events (optional, off by default)
4️⃣ Multiple-Choice Feedback Options (P0)
Users can provide quick feedback on the reasoning quality and interruption value, such as:
A. Was this worth interrupting you?
✅ Yes, this was worth a push notification


⚖️ Useful, but this could have waited for the weekly digest


❌ Not useful / not relevant to me


B. What was wrong (optional follow-up)
🧠 The reasoning didn’t make sense


📌 This isn’t relevant to my interests anymore


📰 This seems unreliable or misleading


🔁 This felt repetitive / already known


These options map internally to:
Alert threshold tuning


Category sensitivity


Source trust weighting


Repetition suppression


…but none of that internal logic is shown to the user.

P1 (Post-MVP): Free-Text Feedback for Reasoning Improvement
Goal:
 Allow users to critique the agent’s reasoning in natural language to improve future explanation quality.
1️⃣ Text-Based Feedback (Optional)
Users can provide short comments, e.g.:
“This feels speculative.”


“I care more about regulatory changes than product updates.”


“This isn’t aligned with why I follow this industry.”



2️⃣ How P1 Feedback Is Used
Text feedback is used to:
Improve reasoning phrasing and clarity (prompt engineering)


Refine relevance framing


Improve category tagging and explanation templates


Inform future iterations of reasoning quality models


This feedback loop improves explanations and alert quality, not trading logic.

