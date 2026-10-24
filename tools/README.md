# Tools

| Tool | Purpose |
| --- | --- |
| [`loop/`](./loop/) | Project-agnostic metrics/review engine. Run `python -m tools.loop --project PATH --help`; each project owns its config, publications, evidence and worked comparisons. |
| [`loop/viral_analyzer/`](./loop/viral_analyzer/) | Campaign-scoped hashtag vocabulary tools: prompt/context builder, response importer, bounded platform probes, evidence review, hashtag/keyword history and tested-target viral expansion. Tests live in [`loop/tests/`](./loop/tests/). |

- [`video_edit/`](./video_edit/): Texture compositing and static-video watermark
  removal. Run `uv run python -m tools.video_edit --help` from the repository root.

- [`common/`](./common/): Shared platform-independent browser CDP diagnostics,
  browser startup foundation, and the canonical unified post format
  ([`samples/post.json`](./common/samples/post.json)) one platform-agnostic post
  is resolved from for every publishing agent.
- [`facebook_agent/`](./facebook_agent/): Direct personal-profile publishing of
  approved text and images, optional sharing to up to 9 named groups through the
  composer, and JSON-planned direct messaging with humanized typing and pacing,
  using the existing `chrome-twitter-profile`.
- [`twitter_agent/`](./twitter_agent/): Terminal-operated X DOM CLI with visible
  browser operations, draft persistence, direct submission, attempt quotas, and
  approved image posting.
- [`linkedin_agent/`](./linkedin_agent/): Direct `doctor` and `post` CLI for
  already-approved personal LinkedIn text and repeatable ordered images using
  the shared Chrome profile. Local validation precedes browser connection;
  JSON exits distinguish invalid input, preparation failure, and uncertain
  submission, which preserves the tool tab for manual inspection. No supervisor
  or automatic retry. A single-image post was verified on the live modern layout.

## Hashtag generation and verification

```text
campaign files + hashtag history → build-prompt → agent JSON → import-response
                                                                    ↓
                     plan → collect --execute → build-review-prompt → record-review → history JSON
                                                                                          ↓
                                        promising / limited_expand only → viral_scrape → expansion candidates
```

| Interface | Behavior |
|---|---|
| `python3 -m tools.loop.viral_analyzer.hashtag_generate build-prompt --project local/<slug> --run <id> --platform instagram --market-language vi --application "<need>" --hypothesis <post>` | Writes `sources/viral/<id>/{prompt.md,context.json}` from the scaffold's fixed file keys. Missing or conflicting required context blocks collection; no directory crawling or scaffold sample facts. |
| `python3 -m tools.loop.viral_analyzer.hashtag_generate import-response --project local/<slug> --run <id> --response <json>` | Preserves the raw response, validates campaign/run/context hash, kinds, duplicates, evidence references and bounds, then writes `candidates.json`. Invalid output exits `2` and stays on disk. |
| `python3 -m tools.loop.viral_analyzer.hashtag_verify plan --project local/<slug> --run <id> --schema <json> [--web-evidence <json>]` | Builds an exact request plan from a saved `glasser inspect` schema/price file. Hashtags and keywords use separate endpoints/fields; a phrase is never sent to a hashtag endpoint. Saved web snippets stay separate from native calls and cannot authorize expansion. |
| `python3 -m tools.loop.viral_analyzer.hashtag_verify collect --project local/<slug> --run <id> [--execute --ceiling <usd>]` | Without `--execute` it only previews. With `--execute` it checks price and ceiling, persists an idempotency key before dispatch, and records request, raw response, status, charge and ordered samples. Unconfirmed retries require `--resume` and are capped. |
| `python3 -m tools.loop.viral_analyzer.hashtag_verify build-review-prompt --project local/<slug> --run <id>` | Writes `review-prompt.md` with intended context, first three unique accessible samples and any transcript/media evidence. |
| `python3 -m tools.loop.viral_analyzer.hashtag_verify record-review --project local/<slug> --run <id> --review <json>` | Validates labels and evidence, computes counts/decisions and appends to `sources/viral/hashtag-performance.json` under a lock with atomic replace. Identical retries are no-ops; `--correction` appends a superseding evaluation. |
| `python3 -m tools.loop.viral_analyzer.hashtag_verify history --project local/<slug> [--platform <p>] [--key <term>]` | Read-only summary. String schema `1.0.0` is read explicitly; integer legacy versions fail instead of being coerced. |
| `python3 -m tools.loop.viral_analyzer.viral_scrape --project local/<slug> --run <id> --schema <json> [--execute --ceiling <usd>]` | Gate: every target's latest history decision must be `promising` or `limited_expand`. Preview is read-only; `--execute` writes `expansion/calls/*` and `expansion/viral-candidates.json`. No untargeted trending. |

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
