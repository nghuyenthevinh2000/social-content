# Hook Validation Loop — Product Requirements & Roadmap

> Source: `competitor-research-report.md`. This document turns the research into feature specs and a phased roadmap.

---

## 0. Locked Decisions

| Decision | Choice | Implication |
| :--- | :--- | :--- |
| Target market | **Southeast Asia (SEA)** | Multilingual hooks (incl. code-mixed speech), FB Reels + TikTok heavy, local payments, SEA-adjusted pricing |
| ICP | **All four** (Indie founders, E-com/TikTok Shop sellers, Creators, Growth marketers/agencies) | One shared loop core. Each persona has a **Goal Profile** that changes the winning metric |
| Distribution (MVP) | **Organic first** | Statistical noise is the main product risk, so the experiment design must control it (see §5) |
| Video formats (MVP) | **Text-on-screen + B-roll** and **User's own footage (hook swap)** | Templated rendering (Remotion/Shotstack). No avatars in MVP |
| Autonomy | **Fully autonomous by default** | Guardrails, budgets, and a kill switch are MVP features, not extras (see F9) |

---

## 1. Positioning

**One-liner:** *The autopilot that finds your winning hook. It generates hook variants, posts them, reads the results, and writes the next round without you.*

**Whitespace (from research):**
- Generators (Higgsfield, Arcads, MakeUGC) stop at the `.mp4`.
- Creatify AdMax costs $299/mo, is paid-only, and still needs a human to trigger the next round.
- Analytics tools (Motion, Triple Whale) only diagnose. Schedulers (Buffer, Metricool) only post.
- No one offers an **organic, autonomous, closed loop** at SEA-affordable pricing with **native SEA-language hook intelligence**.

**What we don't compete on:** render quality, avatars, or foundation video models. We are the **orchestration + intelligence layer** and stay model-neutral.

---

## 2. Personas & Goal Profiles

Every Project picks a Goal Profile. It sets the **Primary Metric** the loop optimizes and the guardrails it applies.

| Persona | Typical SEA example | Goal Profile | Primary metric (organic) | Secondary |
| :--- | :--- | :--- | :--- | :--- |
| **Creator** | VN/PH lifestyle creator on TikTok + FB Reels | `GROWTH` | Hook Score (early retention) | Follows per 1k views, shares |
| **E-com / TikTok Shop seller** | ID skincare seller on TikTok Shop / Shopee | `CONVERSION` | Hook Score, then link clicks / product-tag clicks | Comments with purchase intent |
| **Indie founder / SaaS** | SG/MY SaaS founder on YT Shorts + LinkedIn | `AWARENESS → SIGNUP` | Hook Score | UTM click-throughs, signups |
| **Growth marketer / agency** | TH agency managing 10 brands | Any per brand | Per-brand | Cross-brand benchmarks, reporting |

**MVP stance:** All personas share the same loop. MVP optimizes **Hook Score** (universal), and the persona-specific secondary metrics are display-only. Agencies get multi-brand workspaces in V1.

---

## 3. Core Domain Concepts

| Concept | Definition |
| :--- | :--- |
| **Workspace** | Billing entity. One for a solo user, many brands for an agency. |
| **Project / Brand** | A brand or product being tested. Holds Brand Context, connected accounts, Goal Profile, budgets. |
| **Brand Context** | Product, audience, tone, languages, banned claims/words, CTA, visual kit (fonts, colors, logo). |
| **Base Body** | The constant part of a video (B-roll sequence or the user's uploaded footage after the hook window). Holding it constant isolates the hook. |
| **Hook Archetype** | A category of opening (see §4.2). The unit the loop learns over. |
| **Hook Variant** | A concrete hook: on-screen text + optional voiceover line + first-frame choice + archetype tags. |
| **Round** | One experiment: N variants sharing one Base Body, posted under controlled conditions, measured over a fixed window. |
| **Diagnosis** | Statistical ranking + LLM explanation of a Round's outcome. |
| **Playbook** | A per-brand, accumulated model of which archetypes and features win. This is the switching-cost moat. |
| **Winners Library** | Hooks validated across ≥2 rounds. They can be reused, scaled, and (V2) promoted to micro-ads. |

---

## 4. Feature Specifications

Tags: **[MVP]** must ship · **[V1]** next · **[V2]** later

### F1. Onboarding & Brand Context
- **[MVP]** Guided setup: paste a URL (website / TikTok Shop / Shopee listing / social profile). An LLM drafts Brand Context, and the user edits it.
- **[MVP]** Language selection per project, with **code-mix toggle** (e.g. Taglish, Manglish, Vietnamese with English loanwords).
- **[MVP]** Goal Profile picker (§2).
- **[MVP]** Banned claims / compliance list (pre-seeded for regulated categories like health, skincare, finance in each SEA country).
- **[MVP]** Connect accounts via OAuth (see F4).
- **[V1]** Auto-import the last 30–90 days of posts to compute the **account baseline** and seed the Playbook ("cold start from history").

**Acceptance:** A new user reaches a ready-to-run Round 1 from a single URL plus a single connected account.

### F2. Hook Ideation Engine (Archetype Generator)
- **[MVP]** Generate hook variants per archetype from Brand Context + Base Body transcript.
- **[MVP]** Built-in archetype taxonomy (extensible):
  `Curiosity Gap`, `Negative / Warning`, `Contrarian`, `Pain-Point Callout`, `Result-First / Proof`, `Number / Listicle`, `POV / Relatable`, `Direct Question`, `Audience Callout ("If you're a … stop scrolling")`, `Before/After`, `Social Proof`, `Storytime`.
- **[MVP]** Automatic **feature tagging** of each variant: archetype, word count, language/code-mix, has number, has question, 2nd-person address, emotion, urgency, first-frame type. Diagnosis needs these tags.
- **[MVP]** Native generation per language. Prompts are written for each language, not translated from English. Prompts also cover local slang and register (e.g. Vietnamese pronoun choice: *bạn / mình / anh chị*).
- **[MVP]** Pre-flight filters: dedupe near-identical hooks, enforce banned claims, cap length for readability in the first 2 seconds.
- **[V1]** Trend-aware ideation: pull trending sounds, formats, and phrases per SEA country.
- **[V2]** Outcome-trained hook model (fine-tuned/reranked on cross-account results; see Moat #3).

### F3. Video Assembly (Model-Neutral)
- **[MVP] Format A — Text-on-screen + B-roll:** Templated composition (Remotion or Shotstack). Hook text overlay on the first 1–3 s, then the Base Body. B-roll comes from the user's uploads or a stock API (Pexels/Pixabay).
- **[MVP] Format B — Own-footage hook swap:** The user uploads one long video. The system transcribes it, auto-detects the hook window (first ~3 s), and renders N versions that differ **only** in the hook. That can be new overlay text, an alternative opening clip from the same footage, or a re-ordered "cold open" pulled from a later highlight.
- **[MVP]** Vietnamese, Thai, Bahasa, and Tagalog captions and font support (Thai and Vietnamese diacritics must render correctly; this is a known failure point).
- **[MVP]** Brand kit applied to templates.
- **[V1]** AI voiceover per hook line (multi-language TTS), on/off per project.
- **[V1]** Pluggable render-provider interface (route to cheapest/fastest).
- **[V2]** Avatar talking-head plugin (HeyGen/Tavus/Arcads API) as an add-on with credit pass-through.

**Acceptance:** One Base Body + 5 hooks yields 5 renders that are identical after the hook window.

### F4. Distribution (Organic Auto-Post)
- **[MVP]** Platforms (priority for SEA): **TikTok**, **Facebook Reels**, **YouTube Shorts**, **Instagram Reels** (see §7 for API constraints and launch order).
- **[MVP]** Controlled posting scheduler (see §5): staggered slots, same time-of-day bands, caps per account per day.
- **[MVP]** Per-variant caption/hashtag control. Captions stay constant within a Round so they don't confound the hook test.
- **[MVP]** Tracking: every post gets a Variant ID and, if there's a link, UTM params.
- **[V1]** Multi-account distribution (agencies, or creators with several accounts) to cut per-account noise and duplicate-content risk.
- **[V1]** Fallback via Ayrshare-type aggregator if a native API is blocked.
- **[V2] Mode B — Micro-Validation Ads:** Meta/TikTok Ads API at $3–5 per variant for statistically clean hook-rate data in ~24 h.

### F5. Metrics Ingestion
- **[MVP]** Scheduled pulls at T+2h, 6h, 24h, 48h, 72h per post. The Round is scored at a fixed window (default 72 h).
- **[MVP]** Normalized metric set per post: views/plays, avg watch time, watch-time ÷ duration, retention-at-3s (when available), completion rate, likes, comments, shares, saves, follows, link clicks.
- **[MVP]** **Hook Score** (0–100): a composite weighted toward early retention, normalized against the **account baseline** (rolling median of the account's recent posts). This makes small accounts comparable to large ones.
- **[MVP]** Data-quality flags: post suppressed or under review, abnormally low distribution, missing metrics. A flagged variant is excluded rather than counted as a loss.
- **[V1]** Comment mining: LLM classifies comments (purchase intent, confusion, objection) in local languages.
- **[V2]** Commerce attribution: TikTok Shop / Shopee / Lazada affiliate link and order data.

### F6. AI Diagnosis
Two layers. Statistics decide **who won**. The LLM explains **why**, and may only cite evidence that exists in the data.
- **[MVP] Statistical layer:** Bayesian ranking of variants on Hook Score with credible intervals. Each result gets a confidence label: `Clear winner` / `Leaning` / `Inconclusive`.
- **[MVP] Explanation layer:** LLM receives the ranking + feature tags + retention data and outputs:
  - Winner/loser summary in the user's language
  - Feature-level hypotheses ("Hooks with a number + 2nd-person address held 1.8× longer at 3s")
  - What to test next
- **[MVP]** Round Report (in-app + notification digest).
- **[V1]** Cross-round pattern detection. A pattern is upgraded from `hypothesis` to `validated` only after it replicates in ≥2 rounds.
- **[V1]** Retention-curve overlay (where the platform exposes curves, e.g. YouTube).

### F7. Autonomous Loop Controller (Round N+1)
The engine that makes it a loop, not a dashboard.
- **[MVP]** After each Round is scored, the controller automatically:
  1. Updates the Playbook (archetype + feature priors).
  2. Picks the next Round's mix via **explore/exploit** (Thompson sampling over archetypes): ~70% mutations of winners, ~30% new or under-tested archetypes.
  3. Generates hooks (F2), renders (F3), schedules (F4).
- **[MVP]** Round sizing: default 3–5 variants per Round, adjusted to the account's posting capacity.
- **[MVP]** Stop / graduate rules:
  - A hook that wins 2 Rounds → **Winners Library** + notification ("Ready to scale").
  - Inconclusive 2× in a row → controller rotates the Base Body or widens archetype spread.
- **[MVP]** Body rotation: when the user supplies multiple Base Bodies, the loop rotates them so hook learnings generalize beyond one video.
- **[V1]** "Iterate the body" mode: once a hook is validated, start testing the next 3–10 s.
- **[V2]** Auto-promote Winners to Micro-Ad mode within budget.

### F8. Brand Playbook
- **[MVP]** Per-brand view: archetype leaderboard, winning features, losing patterns, best posting bands, sample winning hooks.
- **[MVP]** Playbook feeds F2 prompts directly (closed loop).
- **[V1]** Exportable Playbook (PDF/Notion). This is the deliverable agencies hand to clients.
- **[V2]** Cross-account **SEA Hook Benchmarks** (anonymized, opt-in): "In ID beauty, Before/After hooks beat Curiosity by 22%". This is a data moat and a marketing asset.

### F9. Autopilot Guardrails (required because autonomy is the default)
- **[MVP]** **Kill switch** per project and global. One tap pauses all posting.
- **[MVP]** Content safety gate before every post: banned claims, platform policy classifier, profanity/sensitivity check per language, and country-specific sensitive topics (e.g. monarchy in TH, religion/ethnicity across the region).
- **[MVP]** Posting caps: max posts per account per day (default 2–3) and min spacing, to avoid spam/originality penalties.
- **[MVP]** Spend caps: monthly render-credit and API-cost limits. The loop pauses when a cap is hit.
- **[MVP]** Auto-pause triggers: account warning/strike detected, 3 consecutive suppressed posts, sharp drop vs baseline, negative-sentiment spike in comments.
- **[MVP]** Full audit log: what was generated, posted, deleted, and why.
- **[MVP]** Optional "veto window" (off by default): posts are queued X hours before publishing so the user can review via notification.
- **[V1]** Auto-archive/hide clearly losing variants after the measurement window (user-configurable) to keep the profile grid clean.

### F10. Dashboard, Notifications & Agent Chat
- **[MVP]** Loop overview: current Round, status per stage (Ideate → Render → Post → Measure → Diagnose), next action ETA.
- **[MVP]** Round history + Winners Library.
- **[MVP]** Notifications: Zalo (VN), LINE (TH), WhatsApp/Telegram (ID/MY/PH), plus email. Each sends a digest per Round and an alert per auto-pause.
- **[MVP]** Agent chat (reuses the existing LangGraph chat UI): "Why did round 4 lose?", "Test more Contrarian hooks", "Pause TikTok this week". This is the natural-language control surface over the loop.
- **[V1]** Agency client view (read-only shared report links, white-label).

---

## 5. Organic Experiment Methodology (Core Product Risk)

Organic reach on small accounts is noisy. Without controls, the loop learns garbage. MVP rules:

1. **One variable per Round:** Only the hook changes. Body, caption, hashtags, sound, and duration are held constant.
2. **Time-band control:** Variants post in equivalent time-of-day bands across days, in randomized order.
3. **Baseline normalization:** Scores are relative to the account's rolling baseline, not absolute views.
4. **Fixed measurement window:** All variants are compared at the same post age (default 72 h).
5. **Early-retention focus:** Hook quality is judged mainly on 3s retention / avg watch-time ratio, which is less sensitive to reach luck than raw views.
6. **Replication before belief:** Patterns must replicate across ≥2 Rounds before entering the Playbook as `validated`.
7. **Honest confidence:** The UI always shows the confidence label. An "Inconclusive" result is a valid outcome.
8. **Duplicate-content mitigation:** Platforms may penalize near-identical uploads. Mitigations: minimum spacing, slight non-hook variation (e.g. color grade, crop jitter) that does not affect the test, and multi-account spread (V1). This needs real-world validation in the MVP pilot.

---

## 6. SEA Localization Requirements

| Area | Requirement |
| :--- | :--- |
| Languages | **MVP:** English, Vietnamese, Bahasa Indonesia. **V1:** Thai, Tagalog/Taglish, Malay. Code-mixing is supported. |
| Rendering | Correct diacritics (VI), Thai script line-breaking, font fallback |
| Platforms | TikTok & FB Reels are must-haves across SEA. YT Shorts is strong for SG/MY/PH founders. |
| Commerce | V1/V2: TikTok Shop, Shopee, Lazada link tracking |
| Messaging | Zalo, LINE, WhatsApp, Telegram notifications |
| Payments | Cards + local wallets/QR (MoMo, VNPay, GCash, GoPay, OVO, DANA, PromptPay) via a regional gateway (e.g. Xendit / 2C2P / Stripe where supported) |
| Compliance | Per-country claims rules (health/cosmetic advertising), data-protection laws (VN PDPD, TH PDPA, ID PDP Law, SG/MY PDPA) |
| UI | App UI localized for the same languages as hook generation |

---

## 7. Platform API Constraints (verify before build)

| Platform | Auto-post | Retention-grade metrics | Key constraint / risk |
| :--- | :--- | :--- | :--- |
| **YouTube Shorts** | Data API upload | YouTube Analytics API (avg view duration, `audienceWatchRatio` retention curve) | Upload quota per project is tight by default. Request a quota increase early. |
| **Facebook Reels** | Graph API (Pages) | Reels insights (plays, avg watch time) | Requires Meta App Review. Page-based, not personal profiles. |
| **Instagram Reels** | Graph API (Business/Creator accounts) | Reels insights (plays, avg watch time, saves, shares) | Same Meta App Review. Personal accounts are not supported. |
| **TikTok** | Content Posting API | Basic stats via Display API. Deeper organic metrics via TikTok Business API for business accounts. | **Unaudited apps can only post privately.** An app audit is required for public auto-posting. Until it's approved, the fallback is "send to TikTok inbox as draft", which breaks full autonomy. Start the audit immediately. |

**Launch order recommendation:** Build on **YouTube Shorts + FB/IG Reels** first (one Meta review covers both). Run the TikTok audit in parallel and ship TikTok as soon as it's approved. TikTok is the most important SEA platform, so its audit is the critical path.

---

## 8. Phased Roadmap

### Phase 0 — Foundations
- Persistent storage (the current scaffold has no DB): workspaces, projects, variants, rounds, posts, metrics, playbook.
- Job scheduler/queue for render, post, and metric-pull jobs.
- Object storage for footage and renders.
- Auth + OAuth token vault (encrypted).
- Start Meta App Review, TikTok audit, and YouTube quota requests **now**. These are the long-lead items.

### Phase 1 — MVP: "One closed loop, autonomous, organic"
Goal: prove the loop produces a Hook Score lift vs the account baseline within a few Rounds.
- F1 onboarding (URL → Brand Context), EN/VI/ID
- F2 archetype generator + feature tagging
- F3 Format A (text + B-roll) and Format B (own-footage hook swap)
- F4 posting to YT Shorts + FB/IG Reels (TikTok when audited)
- F5 ingestion + Hook Score + baseline normalization
- F6 statistical ranking + LLM explanation, Round Report
- F7 autonomous controller with explore/exploit + graduate rules
- F8 basic Playbook
- F9 all guardrails (kill switch, safety gate, caps, auto-pause, audit log)
- F10 loop dashboard, agent chat control, Zalo/WhatsApp/email digests
- Closed pilot: ~20–30 SEA accounts mixed across all four personas

### Phase 2 — V1: "Multi-platform, multi-brand, smarter"
- TikTok public auto-post (post-audit) + TikTok Business metrics
- Thai, Tagalog/Taglish, Malay
- History import for cold-start baseline
- Cross-round pattern validation, retention-curve overlays
- Comment mining in local languages
- Agency workspaces, client report links, exportable Playbook
- AI voiceover, pluggable render routing
- Multi-account distribution, auto-archive losers
- Local payment methods, trend-aware ideation
- Body iteration mode

### Phase 3 — V2: "Paid validation + data moat"
- Mode B Micro-Validation Ads (Meta/TikTok Ads API), auto-promote winners
- Avatar plugin (HeyGen/Tavus/Arcads) as an add-on
- Commerce attribution (TikTok Shop / Shopee / Lazada)
- SEA Hook Benchmarks (opt-in cross-account dataset)
- Outcome-trained hook generation model

---

## 9. Pricing & Packaging (SEA-adjusted draft)

The report's $49–99/mo targets Western indies. That is high for VN/ID/PH creators and sellers, so the draft below uses tiered regional pricing. All numbers are hypotheses to validate in the pilot.

| Tier | Draft price (USD-equivalent, local-currency billing) | Includes |
| :--- | :--- | :--- |
| **Starter** | ~$15–19/mo | 1 brand, 1–2 connected accounts, ~8 Rounds/mo, Format A |
| **Pro** | ~$39–49/mo | 3 brands, 6 accounts, Format A + B, full Playbook, voiceover |
| **Agency** | ~$99–149/mo | 10+ brands, client reports, white-label, priority rendering |
| **Add-ons** | Pass-through + margin | Avatar renders, Micro-Ad mode (ad spend billed by the platform) |

Annual discount; free trial = one full Round on the user's own footage, so they get an aha moment before paying.

---

## 10. Success Metrics

| Layer | Metric |
| :--- | :--- |
| **North Star** | % of active projects with ≥1 validated winning hook within 30 days |
| Loop health | Rounds completed autonomously without human intervention; Inconclusive-rate per Round |
| Outcome | Median Hook Score lift (Round 1 vs Round 5) vs account baseline |
| Activation | Time from signup → first Round posted |
| Trust | Kill-switch usage rate, auto-pause rate, safety-gate block rate, account strike incidents (target: ~0) |
| Business | Trial→paid conversion, M1/M3 retention, churn reason ("no lift" vs "price") |

---

## 11. Risks & Mitigations

| Risk | Severity | Mitigation |
| :--- | :--- | :--- |
| TikTok audit delay/rejection blocks autonomy on SEA's #1 platform | High | Start audit in Phase 0; launch on YT + Meta; inbox-draft fallback |
| Organic noise → false "winners" | High | §5 methodology, confidence labels, replication rule |
| Duplicate/unoriginal-content penalties from near-identical hooks | High | Posting caps, spacing, non-hook variation, multi-account spread; validate in pilot |
| Autonomous post causes brand/legal harm (claims, sensitive topics) | High | F9 safety gate, per-country rules, audit log, kill switch |
| Serving all four personas dilutes focus | Medium | Shared core + Goal Profiles; watch pilot data to pick a beachhead for go-to-market |
| Small accounts post too rarely for fast learning | Medium | Smaller Rounds, longer windows, history import, V2 micro-ads |
| Render/LLM costs exceed SEA price points | Medium | Templated renders (cheap), spend caps, model routing |
| Profile grid cluttered by test variants | Low–Med | Auto-archive losers (V1), user-controlled |

---

## 12. Open Questions

1. **Beachhead for go-to-market:** The product serves all personas, but which one gets launch marketing first? (Suggestion: E-com/TikTok Shop sellers in VN/ID, because the money motivation is strongest and TikTok Shop is huge there. That would raise the TikTok audit's priority further.)
2. **MVP languages:** Is EN/VI/ID the right first trio, or does Thai/Tagalog matter more for the pilot?
3. **Loser handling:** Should losing variants stay public, be auto-archived, or be posted from a secondary "test" account?
4. **Stock B-roll licensing:** Is free stock (Pexels/Pixabay) acceptable, or are licensed libraries needed?
5. **Data sharing:** Is opt-in vs opt-out right for the SEA Benchmarks dataset, given regional privacy laws?
6. **Pilot recruitment:** Do you have access to ~20–30 SEA accounts across the four personas?
