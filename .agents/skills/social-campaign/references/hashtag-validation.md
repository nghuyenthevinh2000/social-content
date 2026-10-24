# Hashtag Vocabulary Validation

Treat a hashtag as a hypothesis about platform vocabulary. Verify observed usage before trusting or banning a term.

```text
campaign context + hashtag history → build-prompt → agent JSON → import-response
                                                                       ↓
                     plan → collect preview → collect --execute → build-review-prompt
                                                                       ↓
                                          agent labels → record-review → hashtag-performance.json
                                                                       ↓ promising / limited_expand
                                   viral_scrape preview → --execute → expansion/viral-candidates.json
```

## Campaign binding

| Rule | Requirement |
|---|---|
| Resolve first | Map to the existing `local/<slug>/`; only `product-marketing.json` supplies required campaign facts: `marketing_goal` and `product.catalog`. No brand, customer-profile, hypothesis, loop-config or scaffold requirement. Never initialize or borrow another campaign. |
| Context gate | `build-prompt` sets `collection_blocked` only for missing/invalid product goal/catalog. Repair those inputs and rebuild context/regenerate the response before verification. Do not create brand or safeguard files to enable research. History and supplied seed evidence are optional feedback, not extra factual prerequisites. |
| History source | `local/<slug>/sources/viral/hashtag-performance.json` is campaign-local cross-run history. Prior results are leads, not proof, and never override campaign candidate selection. |
| Past analyses | `build-prompt` also includes optional `context.prior_analysis` from past campaign-local `sources/viral/` reports/analyses/reviews/relevance/evaluations/creator-style files. Up to five newest readable files, at most 20,000 bytes each, with warnings for exclusions/limits. Raw/calls/expansion folders, prompts and this run are excluded. Use findings/limitations to inform proposals, cite included paths, and never treat them as current product truth, observed seeds, fresh verification or validation on another platform. |
| Cold start | Missing history or no matching platform evaluations means generate new `generated_unverified` candidates from campaign applications/processes/buyer roles. History is optional input, not a prerequisite; never replace it with obsolete scraper DB audits, old reports or another campaign's results. |
| Order and scope | Generate → import → verification plan/preview → approved collection → review → expansion. No preliminary web-search loop; optional seed searches must have a finite declared budget. Use only requested research platforms, with separate runs/evidence per platform. |
| Isolation | Candidates, probes, labels and history never cross campaigns or platforms. TikTok usage does not validate Instagram usage. |

## Commands, from repository root

| Layout | Contract |
|---|---|
| New runs | Only `brief.md`, `report.md` and `artifacts/` at the root. All supporting files in the Writes column below are inside `artifacts/`, unless explicitly marked root/campaign history. Save agent responses, provider schemas and web evidence there too. Public CLI output paths are authoritative. |
| Legacy runs | Existing flat context/plan/manifest/call/expansion data resumes in place without moving evidence. Mixed nested and flat artifact layouts are rejected. |
| Closure | Finalize root `report.md` for every platform/outcome, including empty/error responses. Explain the tested route's Vietnam-market yield and campaign recommendation without asserting a platform-wide absence of buyers. |

| Step | Command | Writes |
|---|---|---|
| Prompt | `python3 -m tools.loop.viral_analyzer.hashtag_generate build-prompt --project local/<SLUG> --run <RUN_ID> --platform <P> --market-language <L> --application "<NEED>" [--seed-evidence <JSON>] [--max-candidates <N>]` | `context.json`, `prompt.md`; root `brief.md`/`report.md` starters if not already authored |
| Compatibility | `--hypothesis` / `--new-test` are deprecated optional flags; neither reads a hypothesis file nor changes product-only context. | nothing |
| Import | `python3 -m tools.loop.viral_analyzer.hashtag_generate import-response --project local/<SLUG> --run <RUN_ID> --response <JSON>` | `response.raw.json`, `candidates.json` |
| Plan | `python3 -m tools.loop.viral_analyzer.hashtag_verify plan --project local/<SLUG> --run <RUN_ID> --schema <JSON> [--web-evidence <JSON>] [--ceiling <USD>]` | `plan.json` |
| Collect preview | `python3 -m tools.loop.viral_analyzer.hashtag_verify collect --project local/<SLUG> --run <RUN_ID>` | nothing |
| Collect paid | `python3 -m tools.loop.viral_analyzer.hashtag_verify collect --project local/<SLUG> --run <RUN_ID> --execute --ceiling <USD> [--resume]` | `calls/*.json`, `calls/*.txt`; root automatic `report.md` updated even for empty/errors |
| Report / recover | `python3 -m tools.loop.viral_analyzer.hashtag_verify report --project local/<SLUG> --run <RUN_ID>` | Root `brief.md` if missing and missing/automatic `report.md` from saved receipts; no network or history changes; authored reports preserved |
| Review prompt | `python3 -m tools.loop.viral_analyzer.hashtag_verify build-review-prompt --project local/<SLUG> --run <RUN_ID>` | `review-prompt.md` |
| Record review | `python3 -m tools.loop.viral_analyzer.hashtag_verify record-review --project local/<SLUG> --run <RUN_ID> --review <JSON> [--correction] [--human-corrected]` | `review.json`, `evaluations.json`, campaign history |
| History | `python3 -m tools.loop.viral_analyzer.hashtag_verify history --project local/<SLUG> [--platform <P>] [--key <TERM>]` | nothing |
| Expand | `python3 -m tools.loop.viral_analyzer.viral_scrape --project local/<SLUG> --run <RUN_ID> --schema <JSON> [--platform <P>] [--limit <N>] [--execute --ceiling <USD>] [--resume]` | `expansion/calls/*`, `expansion/viral-candidates.json` |
| Tests | `python3 -m unittest discover -s tools/loop/tests -p 'test_hashtag_*.py'` | nothing |
| Tests (expansion) | `python3 -m unittest discover -s tools/loop/tests -p 'test_viral_scrape.py'` | nothing |

## Provider boundary

| Rule | Requirement |
|---|---|
| Inspect first | The `--schema` file must come from a live `glasser inspect` (provider, endpoint, supported request field, current `price_usd`, result limit). Never invent endpoints, fields or prices. |
| Fixed calls | `collect` runs fixed provider commands/arguments only. It never executes AI-supplied shell commands, URLs or request shapes. |
| Spend | `collect` previews without `--execute`. Spending needs `--execute --ceiling <USD>` and explicit approval; no account balance is assumed. |
| Idempotency | An idempotency key is persisted before dispatch. A confirmed call is a no-op on retry; an unconfirmed call needs `--resume` and stops after two attempts. Inspect ambiguous receipts manually. |
| Tags vs keywords | Instagram/TikTok hashtag calls and TikTok keyword calls use separate endpoints/fields. A phrase is never sent to a hashtag endpoint as an invented compound tag. |

## Evidence and labels

| Item | Rule |
|---|---|
| Sample | Inspect the first three unique accessible videos in returned order. Retain duplicates, inaccessible results and encounter order; never popularity-sort or cherry-pick. |
| Label | `direct_application` = hit; `adjacent_process`, `creative_only`, `irrelevant` = miss; `insufficient_evidence` = unknown. |
| Required detail | Every sample needs a reason, an evidence reference (caption quote or URL), and observed meaning, application, process, role, language and tag presence where available. |
| Origin | `observed` candidates need a supplied seed excerpt containing the exact term; everything else is `generated_unverified`. No invented popularity, existence, sample result or approval. |
| Failure | Empty response, 404, authentication failure, unsupported endpoint, timeout, provider error and inaccessible content are collection outcomes, never semantic misses or zero-valued videos. |

## Decisions

| Observed result | Decision |
|---|---|
| 2–3 direct fits out of 3 | `promising`; confirmation only, not unrestricted collection |
| 1 direct fit out of 3 with no unknowns | `mixed`; narrow or re-probe |
| 0 direct fits, all three assessed | `deferred_for_context`; not a permanent ban |
| Fewer than three reviewed, or no hits with unknowns | `insufficient_evidence` |
| Confirmation: six unique videos, at least four hits and three creators | `limited_expand` |
| Confirmation below those thresholds | `insufficient_evidence` or `deferred_for_context` |

## Expansion gate

| Rule | Requirement |
|---|---|
| Activated only | A target is scraped only when its latest history decision is `promising` or `limited_expand`. `mixed`, `deferred_for_context` and `insufficient_evidence` never activate. |
| Fetch | `viral_scrape` is schema-driven and previews by default. `--execute` needs `--ceiling` and explicit spend approval; it writes request, raw response, status and normalized candidates. |
| No trending | Never substitute untargeted trending or an invented query. Scrape the tested target text on its own platform and query kind. |
| Metrics | Missing views/likes/comments/shares stay null; never coerce them to zero. Candidates feed viral relevance review, not automatic qualification. |

## History contract

| Field | Rule |
|---|---|
| Key | Hashtags use the normalized tag (leading `#` and case removed, diacritics preserved); keywords use `keyword:<normalized text>` so identical words cannot share a judgment. |
| Evaluation | Campaign/run/probe/candidate IDs, platform, query kind and exact text, intended application, market/language, endpoint and ranking context, timestamps, per-video labels/evidence/creator IDs, counts, decision and collection status. |
| Write safety | Validate, lock, read–merge–write and atomically replace. Identical retries are no-ops; `--correction` appends a superseding evaluation; conflicting IDs are reported. Raw evidence is never overwritten. |
| Reading | Schema `1.0.0` is read explicitly; integer legacy versions fail rather than being coerced. Legacy evaluations are preserved and marked inferred/unverified. |
| Meaning | Report usage observed in this sample, not a platform-wide definition. Relevance counts are separate from engagement or viral qualification. A useful tag does not qualify every retrieved video. |

## Limits

| Limit | Reality |
|---|---|
| No approval | A passing review is research evidence, not content approval, channel authorization or publication permission. |
| No semantics proof | Captions and transcripts cannot prove audience composition, machine operation or statistical accuracy. |
| No migration | No structural history migration is performed; an owner-approved migration needs a dry-run diff and backup outside these commands. |

## Templates

| Template | Path |
|---|---|
| AI response envelope | [response](../assets/hashtag-generation/response.json) |
| Evidence review | [review](../assets/hashtag-generation/review.json) |
| Provider schema/price | [provider schema](../assets/hashtag-generation/provider-schema.json) |
