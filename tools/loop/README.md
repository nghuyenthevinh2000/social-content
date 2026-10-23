# Project-scoped metrics loop

| Responsibility | Location |
| --- | --- |
| Reusable stage modules, tests and guidance | `tools/loop/` |
| Page identity and optional hypothesis mapping | `<project>/loop/config.json` |
| Publications, pending reviews, lock and current stage | `<project>/loop/publications.json`, `<project>/loop/.engine.lock`, `<project>/loop/status.json` |
| Metrics and audit evidence | `<project>/sources/post-metrics/` |
| Worked comparisons and historical runs | `<project>/loop/runs/<run_id>/` |

```text
register → checkpoints → collect → normalize → eligibility
        → compare_posts / compare_groups → review → approval
```

## Stage files

| Pre-publication gate | Contract |
|---|---|
| `preflight.py` | Offline project/channel, research, copy, SVG/PNG and hash-bound approval checks. Never publishes. |
| `preflight --post <ID> --stage research\|draft\|visual\|publish` | Read-only JSON report; exit 2 on failure. See [content gates](../../.agents/skills/social-campaign/references/content-gates.md). |
| `review-research --post <ID> --reviewer <HUMAN> --approved` | Record human evidence/applicability approval; required before drafting when research policy is configured. |
| `approve-content --post <ID> --reviewer <HUMAN> --approved --visual-reviewed` | Record final human copy/media/destination approval. Hash changes invalidate decisions; this is not `approve-review`. |
| Facebook enforcement | `facebook_agent post --project <PATH> --post <ID>` invokes the shared guard before browser connection and before submission; exact Page, text, media and group destinations must match. |
| Registration audit | Policy-managed projects attach registration-time preflight outcome to the publication record. Historical facts can still be registered even when current artifacts fail; registration cannot prevent prior publication. |

| Stage | File | Input → output |
| --- | --- | --- |
| 1. Remember published posts | `register.py` | Confirmed URL, hypothesis number, verified publish time → publications and placements. Never publishes. |
| 2. Find due measurements | `checkpoints.py` | Verified visibility/publication times → frozen 24h/7d worklist. Planned posts never count as published. |
| 3. Capture evidence | `collect.py` | Due worklist → Content Library, CSV export/import and Insights receipts. Facebook collectors stay in `tools/facebook_agent/`. |
| 4. Standardize metrics | `normalize.py` | Raw receipts → scoped observations; original timestamps, identity and nulls preserved. |
| 5. Check comparability | `eligibility.py` | Observations → eligible set plus descriptive exclusions with reasons. |
| 6a. Compare content | `compare_posts.py` | Eligible page observations → creative matrix, flags and limits. |
| 6b. Compare groups | `compare_groups.py` | Eligible group copies → distribution or inquiry ranking with ties preserved. |
| 7. Prepare/record learning | `review.py` | Comparison, hypotheses and gaps → review bundle, proposal, review log. |
| 8. Record human decisions | `approval.py` | Selected proposal IDs → approval audit. Does not publish or reallocate. |

| Supporting file | Boundary |
| --- | --- |
| `workflow.py` | Calls stages in order, owns frozen runs/resume/completion/pending work and is the only writer of `status.json`. |
| `cli.py` | Arguments and dispatch only; no collection, normalization or ranking logic. |
| `__main__.py` | Minimal entry point invoking `cli.main()`. |
| `storage.py` | Project paths, config, atomic writes, locks, timestamps and evidence-hash primitives. No ranking or workflow decisions. |
| `project_init.py` | Non-overwriting scaffolding, project-root instructions, explicit Facebook Page content policy/manifest, and Schema v1→v2 migration. |
| `tests/` | Stage-named offline tests plus end-to-end workflow, isolation and resume/CLI regressions. |

## Current-stage reporting

`<project>/loop/status.json` projects the active run's stage. The run manifest and project registry remain authoritative; the projection never schedules work.

| Field | Meaning |
| --- | --- |
| `schema_version`, `run_id`, `updated_at` | Format version, selected run and timezone-aware write time. |
| `current_stage`, `current_step`, `state` | Stage/substep and overall state: `idle`, `running`, `waiting`, `blocked`, `failed`, `interrupted` or `completed`. |
| `stages` | Stage-keyed outcome, start/end time and reason. Waiting and running stages have no end time. |
| `comparison_result` | `comparable` or `not_comparable`, with eligible/descriptive counts, exclusion reasons and a plain-language reason. |
| `reason`, `error`, `next_action` | Plain-language status, structured failure detail and the specific next command. |
| `artifacts` | Project-relative manifest, evidence, comparison, review bundle and review links. |
| `pending_run_ids` | Other runs needing repair, agent review or human decision. |

| Rule | Behavior |
| --- | --- |
| Write timing | Under the project lock, atomically before a stage and after success, skip, block, failure or human handoff. A failed pre-stage write prevents the stage. Transitions are mirrored into `manifest.stage_history`. |
| No due work | `idle` only when nothing remains; otherwise `waiting`, retaining the selected run and all pending run IDs. Existing stage times are not rewritten. |
| Partial collection | The failed collector and remaining repair stay visible while the partial review bundle is linked. |
| Recovery | A `running` state left by an exited invocation becomes `interrupted` on the next locked invocation. Missing or older-schema projections rebuild from saved run state and recorded transitions; unknown times stay null. No blind retry. |
| Review reconciliation | `prepare-review` retains a proposal while its evidence revision matches. Changed evidence supersedes the review and resets manifest/checkpoint states to pending. |

## Commands

| Command, from repository root | Purpose |
| --- | --- |
| `python -m tools.loop --project PATH init --page-id PAGE_ID [--dry-run]` | Initialize project config, directories and empty Schema v2 registry without overwriting existing files. |
| `python -m tools.loop --project PATH migrate [--dry-run]` | Migrate Schema v1 state with byte backup (`publications.json.v1.bak`). |
| `python -m tools.loop --project PATH status` | Project memory, pending work and `status.json`. |
| `python -m tools.loop --project PATH due` | List due placement checkpoints and legacy publications. No browser or paid calls. |
| `python -m tools.loop --project PATH register --post 1 --url https://www.facebook.com/reel/POST_ID [--published-at TIMESTAMP]` | Register a confirmed canonical URL. |
| `python -m tools.loop --project PATH cycle [--dry-run] [--resume RUN_ID]` | Run the stage pipeline, freeze the due worklist and stage the review bundle. |
| `python -m tools.loop --project PATH compare --run RUN_ID` | Recompute comparisons from stored observations without collecting. |
| `python -m tools.loop --project PATH prepare-review --run RUN_ID` | Rebuild `review-bundle.json` without collecting. |
| `python -m tools.loop --project PATH record-action --file EVENT.json` | Append a verified buyer action or qualified inquiry to `loop/actions.jsonl`. |
| `python -m tools.loop --project PATH review --run RUN_ID --file REVIEW.json` | Record observation, limitation and test suggestions; hand off to approval. |
| `python -m tools.loop --project PATH approve-review --run RUN_ID [--proposals ID1,ID2]` | Record explicit human approval; no publishing. |
| `python -m tools.loop --project PATH collect-insights` | Collect due dashboards through the authenticated browser; no Glasser charge. |
| `python -m tools.loop --project PATH collect --max-cost-usd AMOUNT` | Optional paid public-metrics fallback with an explicit per-invocation ceiling. |
| `python -m tools.loop --project PATH review --id PUBLICATION_ID --file REVIEW.json` | Legacy single-publication review. |
| `python -m unittest discover -s tools/loop/tests` | Offline stage, status, workflow, CLI and project-isolation tests. |

| Behavior / limit | Rule |
| --- | --- |
| Project scope | `--project` is required; evidence paths stay project-relative. Browser subprocesses run from the repository root. |
| Evidence integrity | Reuse requires recorded path, matching SHA-256 and matching type. Missing or changed evidence is collected to `repairs/`; history is never overwritten. |
| Checkpoints | 24h and 7d ceremony supported. Actual age is retained; late snapshots cannot reconstruct first-day totals. Reused evidence does not increment `attempts`. |
| Review lifecycle | `no_work` and `status` expose pending reviews and open runs. A recorded review is not approval and does not clear collection failures. |
| Safety | Per-project lock, atomic writes, paid-run idempotency keys and reused receipts. No scheduler, publishing, messaging or automatic pruning. |

## Implemented versus missing behavior

| Area | Implemented | Still missing |
| --- | --- | --- |
| Stage visibility | Named files, frozen runs, resume and `status.json` transitions. | None in the refactor scope. |
| Group views leaderboard | Distribution-only ranking and inquiry ranking stay separate; ties preserved; no reach pooling. | Resolved same-creative group copies at matched ages, a views-first leaderboard, group names/links and evidence in the matrix; repeated common rounds before allocation. |
| Metric coverage | Available metrics carried through capture, import, normalization, comparison and review; unavailable values stay null. | A defined required-field contract across all stages with explicit reasons for each unavailable metric. |
| Timestamp stability | Status transitions persist in the run manifest; rebuilds use recorded times and leave unknown times null. Original capture timestamps are carried where present. | Re-normalizing unchanged evidence must not assign a new observation time; library/CSV fallbacks still use processing time. |
| Comparison visibility | Empty comparisons report `not_comparable` with eligible/descriptive counts and exclusion reasons; descriptive review stays possible. | A ranked leaderboard still requires resolved identities and eligible matched-age observations. |
| Review consistency | Evidence revisions retain an unchanged proposal, supersede a stale one, and keep bundle/manifest/checkpoint states aligned; approval remains separate. | A human decision is still required after any rebuilt review. |
| Existing acceptance findings | Refactor preserves behavior covered by tests. | See [the E2E retest](../../plans/loop-e2e-retest-20261020.md) and [live-cycle fix history](../../plans/loop-live-cycle-fixes.md); moving functions does not close those gaps. |

| Guidance | Contents |
| --- | --- |
| [Implementation specification](../../plans/metrics-learning-plan.md) | Multi-checkpoint collection, run artifacts, comparison and review wiring. |
| [Content comparison](../../plans/content-comparison.md) | Reusable evidence and creative-comparison rules. |
| [Group comparison](../../plans/group-comparison.md) | Same-content placement-ranking and allocation rules. |
