---
name: twitter-reply-strategy
description: Use when discovering, evaluating, or drafting Twitter/X replies. Provides tactical guidance on target selection, reply angles, and deboost avoidance.
---

# Twitter Reply Guy Strategy (2026 Playbook)

This skill guides the agent in discovering high-signal tweets on X, selecting the optimal reply angle, and drafting substantive replies that drive organic profile visits and follower growth.

---

## 0. Pre-Flight Confirmation (REQUIRED)

Before running any discovery, **always confirm these parameters with the user**. Do not proceed until the user explicitly provides or approves each one:

| Parameter | Default | Ask |
| :--- | :--- | :--- |
| **Topics** | `AI, LLM, blockchain, founder` | "What topics should I search? (e.g. AI, blockchain, founder, engineering)" |
| **Window** | `60 minutes` | "How far back should I look? (e.g. last 30 min, 1 hour, 2 hours)" |
| **Min Score** | `80` | "Minimum opportunity score to surface? (0–100, recommend 80+)" |
| **Limit** | `10` | "How many candidates do you want?" |
| **Draft replies?** | `Ask after results` | "Should I auto-draft replies for top candidates, or just surface the list?" |

Only after the user confirms these values, proceed to discovery.

---

## 1. Core Principles

- **The 70/30 Rule**: Spend 70% of X efforts replying to established audiences and 30% publishing original tweets. Replies borrow distribution immediately; original posts only reach your existing followers.
- **Volume Target**: 15–20 high-quality replies per day. Hard ceiling at 50/day.
- **Terminal Review**: Enqueue replies as drafts and let the user review the AI's work in their existing terminal. Submit a selected draft only when the user requests publishing; no separate supervisor terminal is required.

---

## 2. Target Account & Tweet Selection

### The Sweet Spot
When evaluating opportunities:
1. **Account Size**: Aim for accounts with **5–20x your follower count**.
   - Too small (< 1x): Audience too limited to drive traffic.
   - Mega-accounts (> 100x): Reply is quickly buried in hundreds of comments.
2. **Speed is King (< 5 minutes)**:
   - Replying within 5 minutes yields **4.2x more profile visits** than replying after 30 minutes.
   - The first 3–5 replies capture top thread positioning.
3. **Low Competition (< 20 replies)**: Target posts before reply saturation occurs.
4. **Substantive Topics**: Reply to posts sharing data, technical problems, or strong opinions. Skip low-effort memes, generic engagement bait, and platitudes.

### Opportunity Score (0–100)

The tool scores each post automatically. Scores above 80 are reliable targets:

```
score = (age_factor × 40) + (competition_factor × 30) + (velocity_factor × 30)
```

| Age        | Factor | | Replies   | Factor |
|------------|--------|-|-----------|--------|
| < 5 min    | 1.0    | | < 10      | 1.0    |
| 5–15 min   | 0.7    | | 10–20     | 0.7    |
| 15–30 min  | 0.4    | | 21–50     | 0.3    |
| > 30 min   | 0.1    | | > 50      | 0.05   |

> **Important**: Without a confirmed timestamp the age factor caps at 0.5, making 80.0 the hard ceiling for timeline scans. To reliably find posts above 80, always use advanced topic search with a time window (see Section 5).

---

## 3. The 7 Reply Archetypes

Never write generic agreement (`"Great post!"`, `"Totally agree!"`, `"This!"`). Always choose one specific angle:

| Archetype | Engagement Lift | How to Craft |
| :--- | :--- | :--- |
| **Contrarian** | **4.5x** | Respectful disagreement backed by a specific reason, edge case, or counter-data. Never be hostile; challenge the premise thoughtfully. |
| **Data & Metrics** | **3.2x** | Add concrete benchmark numbers, statistics, or metrics that validate or expand the author's point. |
| **Experience** | **2.8x** | Share a brief, real-world case study or personal engineering story: *"We saw this exact behavior when scaling X from 10k to 100k requests..."* |
| **Question** | **2.1x** | Ask a first-principles question that advances the conversation and invites the author to elaborate. |
| **Insight** | High | Provide a non-obvious angle or second-order consequence that the original tweet missed. |
| **Amplification** | High | Extend the author's thesis into a concrete application or adjacent domain. |
| **Analogy** | High | Translate an abstract concept into a vivid, relatable mental model. |

---

## 4. Strict Anti-Patterns & Deboost Avoidance

X algorithms penalize robotic or spam-like behavior:
- ❌ **No external links in replies**: Drastically deprioritized by the ranking algorithm.
- ❌ **No mechanical templates**: Never reuse repetitive opening hooks (`"Here's why this matters:"`).
- ❌ **No account stalking**: Do not reply to the same account multiple times in an hour.
- ❌ **No burst spamming**: Maintain at least 120 seconds between posts; never exceed 3 replies in 30 minutes.
- ❌ **No noise posts**: Skip memes, pop-culture reactions, crypto pumps, non-English posts, and engagement bait even if they score above 80 due to freshness. Always read the post text before drafting.

---

## 5. Agent Operational Workflow

### Step 1 — Confirm parameters (Section 0)

Do not skip this. Collect topics, window, min-score, and limit from the user.

### Step 2 — Run Advanced Discovery

Use `watch --topics` with the confirmed parameters. This is the **primary discovery path** — it uses X advanced search operators with a time window, which is the only reliable way to surface posts scoring above 80.

```bash
uv run python -m tools.twitter_agent watch \
  --topics "<topic1>,<topic2>,<topic3>" \
  --window-minutes <window> \
  --min-score <min_score> \
  --limit <limit>
```

**Example with confirmed defaults:**
```bash
uv run python -m tools.twitter_agent watch \
  --topics "AI,blockchain,founder" \
  --window-minutes 60 \
  --min-score 80 \
  --limit 10
```

Each topic is searched independently with `min_faves:5 lang:en -filter:links` automatically appended. Results are merged, deduplicated, and sorted by score.

### Step 3 — Filter Results

After receiving the JSON output, discard results that:
- Are noise (memes, pop-culture, crypto pumps, non-English)
- Contain no arguable premise or technical substance
- Are from accounts outside the 5–20× follower sweet spot

Present the filtered shortlist to the user with a recommended reply archetype for each.

### Step 4 — Confirm & Draft

For each approved candidate, draft a 1–3 sentence reply using the chosen archetype. Value must come first — no preamble, no throat-clearing.

### Step 5 — Enqueue for Human Review

```bash
uv run python -m tools.twitter_agent reply prepare <target_id> --text "<reply_text>"
```

### Step 6 — Submit When Requested

Inform the operator that drafts are staged for review in the existing terminal.
When the operator requests publishing, submit the selected ID returned by `prepare`:
```bash
uv run python -m tools.twitter_agent reply submit <draft_id>
```

This publishes immediately. Do not automatically retry an `uncertain` attempt;
inspect X manually instead. Queue import alone never authorizes publishing.

---

## 6. X Advanced Search Operators (Reference)

The `search` and `watch --topics` commands pass queries directly to `x.com/search?q=...&f=live`. These operators control result quality and must be used to keep scores above 80. The `--window-minutes` flag computes `since_time` automatically.

| Operator | Effect | Example |
| :--- | :--- | :--- |
| `since_time:<unix>` | Posts after this Unix timestamp (second-level precision) | `since_time:1790692388` |
| `since:YYYY-MM-DD` | Posts on or after this date (day boundary only) | `since:2026-09-29` |
| `min_faves:N` | Minimum like count | `min_faves:50` |
| `min_replies:N` | Minimum reply count | `min_replies:5` |
| `lang:en` | English posts only | `AI lang:en` |
| `-filter:links` | Exclude posts with external URLs | `AI -filter:links` |
| `-filter:replies` | Top-level posts only (no reply threads) | `claude -filter:replies` |
| `from:HANDLE` | Posts from a specific account | `from:swyx` |
| `OR` | Match either term | `claude OR openai` |
| `"exact phrase"` | Exact phrase match | `"context window"` |
| `-term` | Exclude term | `AI -crypto` |

> **Why `since_time` beats `since:`**: `since:YYYY-MM-DD` is day-level only. `since_time:<unix>` is second-level and is the only way to reliably target posts younger than 15 minutes, which is required for `age_factor ≥ 0.7` and scores above 80.

---

## 7. Fallback: Timeline Scan

If `watch --topics` returns insufficient results (e.g. niche topics with low activity), fall back to the home timeline. Note that timeline scores are capped at 80 due to timestamp limitations.

```bash
uv run python -m tools.twitter_agent timeline --limit 30
```

Sort and filter the output manually for posts with the highest scores and substantive content.
