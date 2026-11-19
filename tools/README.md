# Tools

| Tool | Purpose |
| --- | --- |
| [`app/`](./app/) | Full-stack Viral Reel Analyzer & AI Video Creator ([`app/README.md`](./app/README.md)): Python [`app/backend/`](./app/backend/) (`python3 tools/app/backend/server.py --port 8765`, P1–P5 profile traffic-pool scoring, Glasser/ACP transcript & prompt generation, 15s reference-to-video engine, Meta Graph API Page DM Reel sync, micro-USD cost/credit controls, opt-in profiling) and Ionic React [`app/browser-app/`](./app/browser-app/) (`Library`, `Analyzer`, `Video`, `Profile`). |
| [`common/`](./common/) | Shared platform-independent browser CDP diagnostics, browser startup foundation, and the canonical unified post format ([`common/samples/post.json`](./common/samples/post.json)) resolved across every publishing agent ([`common/README.md`](./common/README.md)). |
| [`facebook_agent/`](./facebook_agent/) | Direct personal-profile and named Fanpage publishing of approved text, images, and Reels, optional sharing to up to 9 named groups through the composer, Content Library/Insights collection, following, and JSON-planned direct messaging/DM crawling with humanized pacing using `chrome-twitter-profile` ([`facebook_agent/README.md`](./facebook_agent/README.md)). |
| [`linkedin_agent/`](./linkedin_agent/) | Direct `doctor` and `post` CLI for already-approved personal LinkedIn text and repeatable ordered images using the shared Chrome profile. Local validation precedes browser connection; JSON exits distinguish invalid input, preparation failure, and uncertain submission, preserving the tool tab for manual inspection with no automatic retry ([`linkedin_agent/README.md`](./linkedin_agent/README.md)). |
| [`loop/`](./loop/) | Project-agnostic metrics, preflight gate, and review engine (`python3 -m tools.loop --project PATH --help`). Each project owns its config, hash-bound approvals, publications, evidence, and worked comparisons ([`loop/README.md`](./loop/README.md)). |
| [`loop/viral_analyzer/`](./loop/viral_analyzer/) | Unified viral analyzer engine (`profile_research`, `video_research`, `keyword_research`) on a shared core (`platforms`, `normalize`, `runtime`, `glasser`, `cache`), plus campaign hashtag validation and gated expansion. Tests live in [`loop/tests/`](./loop/tests/). |
| [`reddit-research-mcp/`](./reddit-research-mcp/) | Dialog FastMCP server for zero-credential semantic search across 20,000+ indexed subreddits, post/comment deep-dives with citations, and persistent research feeds ([`reddit-research-mcp/README.md`](./reddit-research-mcp/README.md)). |
| [`reddit_agent/`](./reddit_agent/) | Lightweight, zero-credential Reddit Atom/RSS scraper ([`reddit_agent/research.py`](./reddit_agent/research.py)) that fetches subreddit posts and nested replies with automatic HTTP 429 rate-limit handling and JSON export. |
| [`taktik-bot/`](./taktik-bot/) | Python, ADB, and `uiautomator2` mobile automation engine for TikTok, Instagram, YouTube, Threads, and Gmail on real Android devices ([`taktik-bot/README.md`](./taktik-bot/README.md)). |
| [`tribeV2_ViralAnalyser/`](./tribeV2_ViralAnalyser/) | Local web app (`python3 tools/tribeV2_ViralAnalyser/app.py`) wrapping Meta TRIBE v2 (`CC BY-NC 4.0`) to review 1–4 short video ad cuts via predicted brain-response curves, 3D heatmaps, Whisper timing hints, landing-page attention maps, and visual-grid salience checks ([`tribeV2_ViralAnalyser/README.md`](./tribeV2_ViralAnalyser/README.md)). |
| [`twitter_agent/`](./twitter_agent/) | Terminal-operated X DOM CLI with visible browser operations, draft persistence, direct reply/post submission, attempt quotas, and approved image posting ([`twitter_agent/README.md`](./twitter_agent/README.md)). |
| [`video_edit/`](./video_edit/) | Texture compositing, corner detection, circular face overlays, and static-video watermark removal (`uv run python -m tools.video_edit --help` from the repository root; [`video_edit/README.md`](./video_edit/README.md)). |

## Hashtag generation and verification

```text
campaign files + hashtag history → build-prompt → agent JSON → import-response
                                                                    ↓
                     plan → collect --execute → build-review-prompt → record-review → history JSON
                                                                                          ↓
                                        promising / limited_expand only → keyword_research scrape → expansion candidates
```

| Interface | Behavior |
|---|---|
| `python3 -m tools.loop.viral_analyzer.keyword_research build-prompt --project local/<slug> --run <id> --platform instagram --market-language vi --application "<need>" --hypothesis <post>` | Writes `sources/viral/<id>/{prompt.md,context.json}` from the scaffold's fixed file keys. Missing or conflicting required context blocks collection; no directory crawling or scaffold sample facts. |
| `python3 -m tools.loop.viral_analyzer.keyword_research import-response --project local/<slug> --run <id> --response <json>` | Preserves the raw response, validates campaign/run/context hash, kinds, duplicates, evidence references and bounds, then writes `candidates.json`. Invalid output exits `2` and stays on disk. |
| `python3 -m tools.loop.viral_analyzer.keyword_research plan --project local/<slug> --run <id> --schema <json> [--web-evidence <json>]` | Builds an exact request plan from a saved `glasser inspect` schema/price file. Hashtags and keywords use separate endpoints/fields; a phrase is never sent to a hashtag endpoint. Saved web snippets stay separate from native calls and cannot authorize expansion. |
| `python3 -m tools.loop.viral_analyzer.keyword_research collect --project local/<slug> --run <id> [--execute --ceiling <usd>]` | Without `--execute` it only previews. With `--execute` it checks price and ceiling, persists an idempotency key before dispatch, and records request, raw response, status, charge and ordered samples. Unconfirmed retries require `--resume` and are capped. |
| `python3 -m tools.loop.viral_analyzer.keyword_research build-review-prompt --project local/<slug> --run <id>` | Writes `review-prompt.md` with intended context, first three unique accessible samples and any transcript/media evidence. |
| `python3 -m tools.loop.viral_analyzer.keyword_research record-review --project local/<slug> --run <id> --review <json>` | Validates labels and evidence, computes counts/decisions and appends to `sources/viral/hashtag-performance.json` under a lock with atomic replace. Identical retries are no-ops; `--correction` appends a superseding evaluation. |
| `python3 -m tools.loop.viral_analyzer.keyword_research history --project local/<slug> [--platform <p>] [--key <term>]` | Read-only summary. String schema `1.0.0` is read explicitly; integer legacy versions fail instead of being coerced. |
| `python3 -m tools.loop.viral_analyzer.keyword_research scrape --project local/<slug> --run <id> --schema <json> [--execute --ceiling <usd>]` | Gate: every target's latest history decision must be `promising` or `limited_expand`. Preview is read-only; `--execute` writes `expansion/calls/*` and `expansion/viral-candidates.json`. No untargeted trending. |

| Rule | Behavior |
|---|---|
| Labels | `direct_application` = hit; `adjacent_process`, `creative_only`, `irrelevant` = miss; `insufficient_evidence` = unknown. Code counts only agent labels. |
| Probe decision | 2–3/3 hits → `promising`; 1/3 → `mixed`; 0/3 assessed misses → `deferred_for_context`; fewer than three reviewed or unknowns with zero hits → `insufficient_evidence`. |
| Confirmation | Six unique videos, at least four hits and three creators → `limited_expand`; otherwise `insufficient_evidence` or `deferred_for_context`. Thresholds are operational, not scientific. |
| Failure | Empty response, 404, auth failure, unsupported endpoint, timeout and provider error are collection outcomes, never semantic misses or zero-valued videos. |
| History identity | Hashtag keys use the normalized tag; keyword keys use `keyword:<normalized text>` so the same words cannot share a judgment. Legacy entries are preserved and their kind is inferred read-only. |
| Resume | The persisted idempotency key is reused and a call stops after two attempts. Ambiguous receipts are inspected manually before `--resume`; there is no automatic receipt reconciliation. |
| Migration | No structural migration is performed. `history` reads string `1.0.0` explicitly; an owner-approved migration must produce a dry-run diff and backup outside these commands. |
| Limits | No network in tests, no fabricated popularity, no platform-wide meaning, no publication approval. A useful hashtag does not qualify every retrieved video. |
