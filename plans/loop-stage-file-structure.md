# Loop: stage-based file structure

| Decision | Specification |
| --- | --- |
| Goal | Make each stage of the publication-to-learning flow visible as a named Python file. Replace the responsibilities currently concentrated in `tools/loop/engine.py` and `tools/loop/comparison.py`. |
| Status | Implemented 2026-10-20. Stages split into named modules, `engine.py`/`comparison.py` retired, `status.json` projection written by `workflow.py`. 89 loop tests pass. |
| Acceptance retest | [Status reporting test](loop-status-test-20261020.md): 229 combined tests pass; review reconciliation, stage history, comparison outcome and failure-stage fixes verified. |
| Scope | Refactor existing responsibilities first. Missing metric coverage, reliable group views ranking and other acceptance fixes remain separate behavioral work. |

```text
tools/loop/
├── __main__.py
├── cli.py
├── workflow.py
├── register.py          # 1. Remember published posts
├── checkpoints.py       # 2. Find due measurements
├── collect.py           # 3. Capture evidence
├── normalize.py         # 4. Standardize metrics
├── eligibility.py       # 5. Check comparability
├── compare_posts.py     # 6a. Compare content
├── compare_groups.py    # 6b. Compare distribution
├── review.py            # 7. Prepare/record learning
├── approval.py          # 8. Record human decisions
├── storage.py
├── project_init.py
├── __init__.py
├── README.md
└── tests/
```

## Stage ownership

| File | Responsibility | Output |
| --- | --- | --- |
| `register.py` | Record confirmed canonical publication URL, hypothesis reference and verified publication time. Preserve unknown metadata explicitly; never publish. | Project publications and placements. |
| `checkpoints.py` | Determine due 24h/7d measurements from verified visibility/publication times. Surface pending measurements without treating planned posts as published. | Due measurement worklist. |
| `collect.py` | Invoke existing Facebook collectors sequentially for Content Library, CSV export/import and post Insights. Verify evidence reuse and handle repair attempts without replacing history. Keep browser implementation in `tools/facebook_agent/`. | Raw receipts and collection-stage results. |
| `normalize.py` | Convert dashboard, CSV and group rows to consistent metric observations. Preserve source timestamps, scope, identity references and null values. Keep processing time separate from observation time. | Normalized observations and normalization gaps. |
| `eligibility.py` | Check placement identity, creative/version, visibility, checkpoint, age and reporting scope. Keep descriptive observations rather than silently dropping ineligible evidence. | Comparable observations and exclusions with reasons. |
| `compare_posts.py` | Compare different posts' distribution, attention and verified buyer outcomes. Retain uncertainty; do not infer creative causation from unmatched distribution. | Content comparison. |
| `compare_groups.py` | Compare the same creative across verified group copies at matched visible ages. Separate descending views ranking from buyer-outcome ranking; preserve ties. Show group names/links, views, viewers, actual ages, evidence and excluded placements. | Group leaderboard and exclusions. |
| `review.py` | Assemble metrics, comparisons, hypotheses and gaps for an agent. Record the agent's observation, limitation and next-test proposals; synchronize review state for the evidence reviewed. Do not claim autonomous reasoning. | Review bundle and recorded proposal. |
| `approval.py` | Record explicit human approval of selected proposals. Approval does not publish, leave groups, delete posts or execute allocation changes. | Approved proposal IDs and approval audit. |

## Supporting files

| File | Boundary |
| --- | --- |
| `__main__.py` | Minimal entry point invoking `cli.main()`. |
| `cli.py` | Parse arguments and dispatch commands; no collection, normalization or ranking logic. Preserve existing command names. |
| `workflow.py` | Call stages in order and manage frozen runs, resume, completion and pending-work reporting. Own run-level status and publish `<project>/loop/status.json` at every stage transition; obtain stage results rather than duplicating stage logic. |
| `storage.py` | Shared project-relative paths, configuration loading, atomic JSON writes, locks, timestamps and evidence-hash primitives. No ranking or workflow decisions; avoid becoming a miscellaneous business-logic module. |
| `project_init.py` | One-time project scaffolding and schema migration; not a recurring cycle stage. |
| `README.md` | Show stage order, entry commands, input/output artifacts and implemented versus missing behavior. |
| `tests/` | Mirror stage filenames and retain an end-to-end workflow test, project-isolation checks and resume/CLI regressions. |
| `__init__.py` | Package marker; no initialization side effects. |

## Current-stage reporting

| Contract | Requirement |
| --- | --- |
| Location | `<project>/loop/status.json`, never under shared `tools/loop/`. One project-level view identifies the active run and its current stage. |
| Owner | Only the workflow status writer updates this view. CLI commands, including standalone collection, comparison, review and approval, report transitions through that writer. |
| Source of truth | Existing per-run manifest and project registry remain authoritative. `status.json` is their current-stage projection, not an independent scheduling database. |
| Write timing | Under the existing project lock, write atomically before starting a stage and after success, skip, block, failure or transition to human waiting. If the pre-stage status write fails, do not start the stage. |
| Stage names | `register`, `checkpoints`, `collect`, `normalize`, `eligibility`, `compare_posts`, `compare_groups`, `review`, `approval`. Report collection substeps separately, such as `content_library`, `csv_export`, `csv_import` and `post_insights`. |
| Human handoff | After preparing a review bundle, report stage `review`, state `waiting`, and the required agent action. After recording a proposal, report stage `approval`, state `waiting`. Do not imply an agent or human is actively running. |
| Empty worklist | Report `idle` only if no collection or review/approval work remains. A no-due invocation must retain outstanding work references rather than overwrite an unfinished run with a misleading completed state. With several waiting runs, expose the selected run plus all pending run IDs. |
| Partial results | Preserve each stage's outcome. A partial collection can expose a review bundle while still identifying the failed collector and remaining repair action; do not label the whole loop complete. |
| Recovery | Persist transitions to the run manifest first, then refresh the status projection before the next stage. Rebuild a missing/stale projection from saved state. On the next locked invocation, a saved `running` state left by an exited invocation becomes `interrupted`; never infer completion or retry an uncertain external action. |
| Completion boundary | `completed` means the run reached its defined endpoint and required stages succeeded or were explicitly skipped. Waiting for approval, unresolved required comparisons and collector failures must stay visible. Publishing remains outside this workflow. |

| Field | Meaning |
| --- | --- |
| `schema_version`, `run_id`, `updated_at` | Format version, selected run identity and timezone-aware status-update time; `run_id` may be null before a run exists. |
| `current_stage`, `current_step`, `state` | Exact stage/substep and overall state: `idle`, `running`, `waiting`, `blocked`, `failed`, `interrupted` or `completed`. Null stage/step is allowed when idle. |
| `stages` | Stage-keyed outcomes: `pending`, `running`, `completed`, `waiting`, `blocked`, `failed` or `skipped`, with start/end times and a reason where applicable. |
| `reason`, `error` | Plain-language explanation and structured failure details, including the affected publication/placement when known; null when absent. |
| `next_action` | Specific command or human action needed to continue; null only when no action remains. Do not recommend blind retries of uncertain requests. |
| `artifacts` | Project-relative links to the run manifest, raw evidence, comparison, review bundle and recorded review as available. |
| `pending_run_ids` | Other runs requiring collection repair, agent review or human decision; an empty list is distinct from unknown work. |

| Acceptance scenario | Expected status |
| --- | --- |
| CSV collection fails | `current_stage=collect`, `current_step=csv_export`, `state=failed`; preserve prior completed stages, evidence references and recovery instruction. |
| Review bundle prepared | `current_stage=review`, `state=waiting`; link the bundle and request agent review. |
| Proposal recorded | `current_stage=approval`, `state=waiting`; link the proposal and request an explicit human decision. |
| Intact resume | Correct stage resumes without duplicate collection; projection, manifest and checkpoint review states agree. |
| Crash or multiple waiting runs | Next invocation reports interruption safely; no-due checks preserve waiting work and list other pending runs. |

## Migration

| Order | Action | Acceptance |
| --- | --- | --- |
| 1 | Inventory callers and existing monkeypatch/test seams before extraction. Establish the current test baseline. | Existing commands and tests are mapped to their owning stages. |
| 2 | Extract storage primitives and pure normalization, eligibility and comparison functions. | Preserve current behavior and artifact shapes; imports remain acyclic. |
| 3 | Extract registration, checkpoints, collection, review and approval. Move setup/migration under project initialization. | Each stage owns its responsibility; platform collectors stay outside `tools/loop/`. |
| 4 | Reduce orchestration to `workflow.py`; move argument handling to `cli.py`. Route collection-only commands through the same collection implementation where applicable. Add the shared status writer and stage-transition reporting. | Main cycle and standalone commands do not maintain duplicate stage implementations; `status.json` pinpoints current stage, failures and human handoffs without contradicting saved run state. |
| 5 | Update tests/callers and retire `engine.py` and `comparison.py`. Use temporary compatibility exports only for verified remaining callers. | No competing old/new implementation or permanent wrapper-only stage files. |
| 6 | Update README and run offline regression plus safe project recovery/reuse acceptance. | Existing CLI and project artifact paths remain compatible; evidence and checkpoint history remain intact. No unapproved publishing or paid collection. |

## Behavioral work remains explicit

| Requirement | Refactor boundary / verification |
| --- | --- |
| Group views leaderboard | A named file is not completion. Verify two resolved same-creative group copies reach matched-age comparison; a higher-view/lower-viewer copy wins the views ranking; pending or unknown-age copies cannot rank. Compare repeated common rounds before recommending allocation. |
| Metric coverage | Define required fields through capture, import, normalization, comparison and review. Preserve available values and explain unavailable metrics rather than silently omitting them. |
| Timestamp stability | Re-normalizing unchanged evidence must not assign a new observation time. |
| Review consistency | Bundle, manifest and checkpoint states must agree after recording review and intact resume; new evidence must trigger a new review. Approval stays separate. |
| Existing acceptance findings | Use [the E2E retest](loop-e2e-retest-20261020.md) and [live-cycle fix history](loop-live-cycle-fixes.md) for evidence and unresolved work. Do not claim those gaps are fixed by moving functions. |
