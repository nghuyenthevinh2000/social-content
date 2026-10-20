# Loop status reporting: acceptance test

| Verdict | Result |
| --- | --- |
| Current-stage reporting | **Core fixes verified; one schema consistency issue remains.** The real project retains `approval / waiting`, review completes correctly and no-due checks preserve timestamps. Standalone preparation still replaces detailed comparison status with a string. |
| Current file | [local/paper-ink-product/loop/status.json](../local/paper-ink-product/loop/status.json), selected run `20261020T075511Z-00e38da8`; older run `20261020T072158Z-645dd4e7` remains in `pending_run_ids`. |
| Scope | Existing CLI and tests only. No helper scripts, runtime/test edits, approval, publishing or paid calls. Failure/crash scenarios used existing offline fixtures, not destructive real-project experiments. |

```text
Existing proposal → prepare-review → approval/waiting ✓
                         ↓ resume
                 approval/waiting ✓
                 review stage completed ✓
                         ↓ no-due cycle
                 approval retained ✓
                 recorded stage timings preserved ✓
```

## Independent new-fixes retest

| Check — 2026-10-20, 11:41 UTC | Result |
| --- | --- |
| Existing suites | Re-ran both: 89 loop tests and 140 Facebook tests passed, **229 total**. Changed-evidence invalidation and failure-stage attribution were exercised by existing offline tests, not by modifying real evidence. |
| Real `prepare-review --run 20261020T075511Z-00e38da8` | Exit 0 at `11:41:07Z`; `pending_agent_review=false`, proposal retained, no invalidation. Projection remains `approval / waiting`; review stage is completed. |
| Real intact resume | Exit 0 at `11:41:22Z`, `review_proposed`; review completed, approval waiting with no end time. Bundle says `pending_agent_review=false`, `review_status=proposed`. |
| Evidence safety | Four raw/imported hashes unchanged before/after; checkpoint attempts still 2 and publication/checkpoint review state still reviewed. No new approval, paid calls, runtime edits or custom scripts. |
| Real no-due cycle | Exit 0 at `11:41:43Z`, new run `20261020T114143Z-643c572b`; projection retains the proposal run and the older pending run. Native diff confirms all stage timestamps remain unchanged; only update/explanatory text changes. |
| Comparison honesty | Resume reports `not_comparable`, zero eligible content/group items, 16 descriptive observations and exclusion counts. Group stage remains waiting with an explanation; this is not a valid group leaderboard. |
| Remaining schema bug | Before preparation and after resume, `status.comparison_result` is an object with result, reason, counts and exclusions. Immediately after standalone preparation it is only the string `not_comparable`. `workflow.prepare_review_run` passes the scalar returned by `review.prepare_review` to `StatusWriter.finish`. Keep the object shape across all entry points, using the bundle's `comparison_summary`; add an assertion for type and retained detail in the standalone preparation test. |
| Preserved evidence | [After preparation](../local/paper-ink-product/loop/runs/20261020T075511Z-00e38da8/status-fixes-after-prepare-20261020.json), [resume output](../local/paper-ink-product/loop/runs/20261020T075511Z-00e38da8/status-fixes-resume-result-20261020.json), [before no-work](../local/paper-ink-product/loop/runs/20261020T075511Z-00e38da8/status-fixes-before-no-work-20261020.json). |

## Original verification before fixes

| Command / check | Observed result |
| --- | --- |
| `uv run python -m unittest discover -s tools/loop/tests` | **89 passed**, including review invalidation/retention, stage-history rebuilds, comparison outcome and failure-stage cases. |
| `uv run python -m unittest discover -s tools/facebook_agent/tests` | **140 passed**. Total: **229**. |
| `uv run python -m tools.loop --project local/paper-ink-product status` | Reports projection, registry and pending work; initial stage `approval`, state `waiting`. |
| Same loop prefix, `due` | `[]`; projection retains the waiting run instead of reporting idle. |
| Same loop prefix, `compare --run 20261020T075511Z-00e38da8` | Exit 0; current stage becomes `compare_groups`, waiting for bundle preparation. Zero eligible content/group items, 14 gaps. |
| Same loop prefix, `prepare-review --run 20261020T075511Z-00e38da8` | Exit 0; at `11:22:06Z`, projection says `review / waiting` while manifest remains `review_proposed`, `review_status=proposed`. Existing review was not invalidated against an evidence revision. |
| Same loop prefix, `cycle --resume 20261020T075511Z-00e38da8` | Exit 0, `review_proposed`; at `11:22:19Z`, projection says `approval / waiting`, but `stages.review.state=waiting`. |
| Native `shasum -a 256`, before/after resume | Original library, Insights, repaired CSV and imported JSON hashes unchanged. Checkpoint attempts remain 2, review state remains reviewed. |
| Same loop prefix, `cycle` | Exit 0, `no_work`, run `20261020T112239Z-bb4401af`. Projection stays on the earlier approval-waiting run and lists the other pending run. Prior stage timestamps are rebuilt as `11:22:39Z`, not preserved. |

## Fixes applied

| Priority / location | Failure | Resolution and evidence |
| --- | --- | --- |
| P1 — `workflow.prepare_review_run`, `review.prepare_review` | Bundle rebuilding regressed approval to review without synchronizing manifest, proposal and checkpoint states. Bundle kept `pending_agent_review=true`. | Reviews now store an evidence revision. Unchanged evidence retains `proposed` and keeps the approval handoff; changed evidence writes a `superseded` archive, resets manifest/checkpoint states to pending and rebuilds a pending bundle. Copy-project check: `approval / waiting` retained; legacy artifact reported `not_comparable` with 16 descriptive exclusions. |
| P1 — `workflow.cycle` | Resumed proposal had overall approval-waiting while the review stage remained waiting. | Cycle closes `review` completed when a matching proposal survives unchanged evidence, and the bundle records `pending_agent_review=false`. Intact-resume tests assert stage history and the bundle flag. |
| P1 — `report_no_work`, `_projection_from_manifest` | No-due invocation fabricated stage start/end times from reconstruction time. Waiting approval also received an end time. | Transitions persist in `manifest.stage_history`; rebuilds use those times, leave unknown times null, and keep waiting stages without `ended_at`. Status schema 2 rebuilds stale projections. No-work checks preserve selected-run history. |
| P1 — comparison visibility | Comparison stages said completed despite empty matrices and unresolved identities. | Artifacts and status now include `comparison_summary` with eligible/descriptive counts, exclusion reasons and an explicit `comparable` or `not_comparable` result. Empty comparisons remain descriptively reviewable without implying a leaderboard. |
| Additional inspection — `compare_run` | One exception handler always labeled eligibility, post-comparison or group-comparison errors `compare_groups`. | The active stage is tracked; a fault-injected `compare_posts` failure reports `compare_posts` and leaves `eligibility` completed. |

## Evidence

| Artifact / next step | Reference |
| --- | --- |
| Resume result | [status-retest-resume-20261020.json](../local/paper-ink-product/loop/runs/20261020T075511Z-00e38da8/status-retest-resume-20261020.json) |
| Contradictory stage snapshot | [status-retest-after-resume-20261020.json](../local/paper-ink-product/loop/runs/20261020T075511Z-00e38da8/status-retest-after-resume-20261020.json) |
| Authoritative review state | [manifest.json](../local/paper-ink-product/loop/runs/20261020T075511Z-00e38da8/manifest.json), [review.json](../local/paper-ink-product/loop/runs/20261020T075511Z-00e38da8/review.json) |
| Next acceptance | Fix the comparison-status object/scalar inconsistency, then repeat standalone preparation and intact resume with type/detail assertions. The real-project sequence was exercised in the independent retest above using verified stored evidence; fresh collection and a usable group leaderboard remain outside this status acceptance. Do not approve the actual proposal merely to exercise a test endpoint. |
