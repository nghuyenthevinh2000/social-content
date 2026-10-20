# Metrics → comparison → improvement plan

| Recommendation | Scope |
| --- | --- |
| Build one evidence-backed review cycle | Shared implementation in `tools/loop`; every invocation requires `--project PATH`. Reuse project-owned state, the Insights crawler, CSV importer and comparison guides. Keep collection deterministic; agents interpret evidence and propose changes. |
| Business objective | Each project defines its qualified inquiries, partnerships and downstream outcomes—not merely views. Do not bake one product's audience, offers or Page ID into shared code. |
| Status | **Implementation specification, not implemented wiring.** Existing commands cover parts of collection and review storage. Sections 7–12 decide the code changes, contracts, storage and rollout; all new commands below are proposed until their acceptance tests pass. |

```text
Init → Register → Gather → Validate → Compare → Suggest → Approve → Test
                       ↓                               ↑
                  Resolve gaps ────────────────────────┘
```

## 1. Flow and handoffs

| Stage | Input and work | Output / exit condition |
| --- | --- | --- |
| Register | After confirmed publication, record original Post ID, hypothesis, actual creative/version, permalink, timezone and publish time. For every group copy, record its own identity and moderation state. | Publication/placement memory exists. Registration failure never triggers automatic reposting. |
| Gather | Read post Insights for attention, demographics and both discovery tabs. Read Content Library group rows. Import supplied CSVs for daily metrics. Record qualified inquiries through authorized manual entry or integration. | Timestamped raw evidence and snapshots with source, placement, window and capture status. |
| Validate | Check Page/Post IDs, copy identity, publication/approval time, duplicates, missing fields and capture completeness. Keep original posts separate from group copies. | Eligible evidence advances; missing identity/time or pending approval creates a gap-resolution task. |
| Compare | Apply [content-comparison.md](content-comparison.md) across creative versions; apply [group-comparison.md](group-comparison.md) across placements of the **same creative**. | Observations, constraints, provisional ranks and missing outcome data—not an unsupported overall winner. |
| Suggest | Identify the weakest supported step: distribution, opening attention, product relevance, CTA or follow-up. Generate one-variable creative tests and separate allocation recommendations. | Each suggestion cites evidence, expected outcome, controls, measurement window and confidence. |
| Review and learn | Human approves, revises or defers recommendations. Append review history and new hypotheses; register only when a new test is actually published. | Traceable decision linking evidence → suggestion → approved test → later outcome. |

## 2. Collection schedule

| Trigger | Required collection | Guardrail |
| --- | --- | --- |
| Publication / group approval | Identity, actual creative, visible status and timestamps | Group performance age begins at confirmed visibility, not submission. Track moderation delay separately. |
| First invocation after 24h | Post/group snapshot and early comparison | Store actual age. A late capture is not an exact first-day total; never reconstruct it from cumulative totals. |
| First invocation after 7d | Comparable snapshot, qualified inquiries, next steps and allocation review | Requires an additional checkpoint; current engine only completes one 24h checkpoint. |
| New CSV supplied | Validate headers, import daily rows, join by Post ID | CSV lacks group identities, age/gender and discovery categories. Preserve unspecified timezone; do not overwrite due times. |
| Later attributed outcome | Append inquiry/order evidence and revise decision if warranted | Keep previous review intact; uncertain attribution remains uncertain. |
| Scheduled invocation | Start with periodic collection checks after explicit activation | Requires an awake/networked machine and authenticated browser. Scheduling collection does not invoke the reasoning agent. |

## 3. Minimum shared records

| Record | Required fields |
| --- | --- |
| Content | Hypothesis ID, original Post ID, product/application, intended buyer, actual hook/media version, duration and CTA. Separate intended plan from inspected creative. |
| Placement | Content/version link, Page or group ID, copy permalink, submitted/approved/visible timestamps, timezone and status. Group names alone are not stable identifiers. |
| Snapshot | Placement ID, checkpoint, observed-at, actual age, source evidence paths, cumulative/daily scope, values, nulls and warnings. Preserve checkpoint history instead of replacing the latest value. |
| Buyer action | Inquiry date, placement attribution if known, project-defined intent, qualified status, agreed next step and order outcome. Deduplicate people without exposing unnecessary personal information in reports. |
| Review | Content/placement IDs, evidence snapshots, observation, limitation, explanation hypothesis, proposed change, controls, success criteria, decision status and approval state. |

## 4. Comparison and suggestion rules

| Observed pattern | Agent should suggest | Must not conclude |
| --- | --- | --- |
| Early drop-off, with adequate comparable exposure | Test a buyer/application-first opening; keep product, body, CTA, duration and distribution constant | The existing opening caused low sales. |
| Strong attention but unknown buyer actions | Improve inquiry attribution first; consider a clearer application-specific trial CTA as a separate test | High retention means the offer converts. |
| Low reported viewers or dominant Page/Other traffic | Verify visibility and placements; test distribution separately from creative | The creative failed or Other means group traffic. |
| One group repeatedly leads on eligible same-content rounds | Prioritize its next approved placement; retain comparison groups | Every future creative will win there. |
| Repeated weak group outcomes | Verify approval/visibility and buyer data; propose reduce/pause under the group policy | A pending post or a single zero-view row justifies pruning. |
| Tiny or concentrated age/gender sample | Preserve descriptive evidence and seek broader buyer-role observations | Demographics establish purchasing intent or justify excluding other audiences. |

| Evidence discipline | Rule |
| --- | --- |
| Priority | Qualified inquiries/next steps first; attention and exposure support diagnosis. Unknown conversion data prevents a sales ranking. |
| Fairness | Match content, visible age, duration, spend and placement conditions where possible; label mismatches. No pooled unique reach across groups. |
| Definitions | Keep Traffic/Source and daily/cumulative metrics separate. Do not sum daily averages or equate average percentage watched with completion. |
| Decision labels | Observed positive, gap, hypothesis, inconclusive, repeat, revise or proposed allocation change. No opaque score or invented statistical certainty. |

## 5. Implementation sequence

| Phase | Reuse / smallest required change | Acceptance check |
| --- | --- | --- |
| 1. Complete memory | Extend each project's `loop/publications.json` with placement identities, visibility states and checkpoint histories. Resolve missing timestamps without guessing CSV timezone. | One content can have multiple distinct placements; pending is never ranked as failed. |
| 2. Complete collection | Extend `engine.py` beyond one checkpoint; retain both Traffic and Source captures. Add structured group-row ingestion using the existing Facebook CLI. | Repeated runs do not duplicate checkpoints; failed/partial captures stay reviewable; all values retain provenance. |
| 3. Produce comparisons | Generate a dated round report from eligible snapshots using both comparison guides. Keep current worked examples as historical baselines. | Same-content group matrix and creative comparison state their windows, exclusions and unknown outcomes. |
| 4. Produce suggestions | Agent writes a structured review plus a short ranked suggestion table; reuse current observation/limitation/next-test fields and add evidence/approval references as needed. | Every recommendation has a source, a specific change and controls; insufficient evidence produces a collection task instead. |
| 5. Activate operations | After approval, configure collection scheduling and define who invokes the agent review. Keep publishing and group pruning approval-gated. | Demonstrate one full collection → comparison → suggestion → approved-test cycle before claiming autonomous operation. |

## 6. First review backlog

| Priority | Action based on current findings |
| --- | --- |
| 1 | Capture due checkpoints before comparing early observations with older publication totals. |
| 2 | Resolve group IDs/copy permalinks, visible timestamps and Pending outcomes; the supplied CSV cannot fill these fields. |
| 3 | Add qualified-inquiry/next-step records; current public engagement does not answer the primary business question. |
| 4 | Retest promising placements and investigate weak exposure using the project's own group comparison; do not declare a conversion winner prematurely. |
| 5 | Select one project-specific creative contrast with matched durations, body and CTA. Keep creative and group-allocation experiments separate. |

| Planned review artifact | Location / contents |
| --- | --- |
| Raw metrics and exports | `<project>/sources/post-metrics/`; immutable evidence and imported series. |
| Publication/placement state | `<project>/loop/publications.json`; extend rather than introduce a separate database now. |
| Dated round review | Proposed `round-N-review.md`: evidence windows, content matrix, group matrix, gaps and ranked suggestions. Not created by this plan. |
| Decision history | Project registry reviews plus its configured hypotheses file after approval; preserve tried posts and prior measurements. A hypotheses file is optional. |

## 7. Code ownership

| File | Concrete change |
| --- | --- |
| `tools/loop/engine.py` | Shared orchestrator with explicit project root and configured Page ID. Add schema migration, placement/checkpoint state, run manifests and proposed `cycle`, `compare`, `prepare-review`, `record-action`, `approve-review` commands. Preserve current register/due/collection interfaces. No browser selectors or LLM client here. |
| `tools/facebook_agent/cli.py` | Add `content-library` for structured placement discovery. Extend `insights-import` with explicit Summary/Daily detection and `insights-export` with settings selection. Keep authenticated browsing behind this CLI. |
| `tools/facebook_agent/insights.py` | Reuse post capture; give each required panel/tab its own observed-at/status. Ensure a collection includes default Traffic, age/gender, and explicitly opened Source. Missing tabs make the capture partial, not zero. |
| **New:** `tools/facebook_agent/content_library.py` | Extract rows with their rendered column headers, row identity/status, group labels/URLs, copy links and raw row evidence. Scroll the table's actual container, deduplicate stable IDs and report whether traversal reached its end. Never fabricate group IDs from names. |
| `tools/facebook_agent/insights_export.py` | Keep download/reconciliation and import logic. Separate Summary snapshots from Daily series; preserve supplied dates and unspecified timezone. Add explicit `--breakdown summary|daily` and date-range verification; fail on an unsupported UI instead of silently exporting defaults. |
| **New:** `tools/loop/comparison.py` | Pure functions: normalize evidence, select eligible snapshots, build content/group matrices, attach exclusions and emit diagnostic flags. No browser, file mutation, network calls or automatic business decisions. |
| `tools/loop/tests/test_engine.py` and **new** `tools/loop/tests/test_comparison.py` | Test project isolation, migration, independent 24h/7d checkpoints, restart/recovery, evidence selection, ranking and review validation offline. |
| Existing Facebook tests and **new** `tools/facebook_agent/tests/test_content_library.py` | Extend parser/download tests; test virtualized tables, duplicate names, missing IDs, pending rows, tab failures, Summary/Daily imports and export reconciliation. |
| `tools/loop/README.md`, project `AGENTS.md`, comparison guides | Document stable commands and review handoff. Shared guides hold reusable policy; project `loop/` holds worked comparisons. Python must not scrape Markdown to discover rules. No posting/messaging code changes in v1. |

| Architecture decision | Rationale |
| --- | --- |
| Python stdlib + existing Playwright | No new database, queue, framework, Jev, agent SDK or background LLM service. One local coordinator and one pure comparison module are enough. |
| Per-placement checkpoints | The same creative can have one original and several group copies with different approval times. A content-level collected flag cannot represent them accurately. |
| Agent runs in the existing harness | Scripts prepare a bounded evidence bundle; the current agent reads it and writes proposals. V1 does not pretend a scheduled Python command performs reasoning. |
| Policy location | Define `DEFAULT_POLICY` in `tools/loop/comparison.py` for checkpoint tolerances and the proposed three-round group review minimum. Pass it explicitly to functions; no configuration framework. |

## 8. Storage contracts

| Path, relative to `--project PATH` | Ownership / contents |
| --- | --- |
| `loop/config.json` | Existing project-owned configuration: required `page_id`, optional project-relative `hypotheses_file`. No built-in project default; initial supported collector is Facebook, not a universal platform adapter. |
| `loop/publications.json` | Schema v2; mutable index containing existing `publications`, a new root `placements` list, checkpoint references and review references. Atomic replace under the existing lock. |
| `loop/actions.jsonl` | Append-only manual buyer-action events: pseudonymous contact key, intent, event time, qualification/next step/order state, attribution certainty and optional placement ID. No message bodies or phone numbers required. |
| `loop/runs/<UTC-run-id>/manifest.json` | Run phase/status, frozen input IDs, requested checkpoints, attempt IDs, collector results, evidence paths/hashes, warnings and pending review state. Save after every stage. |
| Run/path conventions | Run ID: UTC timestamp plus short UUID. Resolve data from explicit `--project`, never the shared script directory; store project-relative references. Use attempt-specific names and atomic JSON writes. |
| `loop/runs/<UTC-run-id>/comparison.json` | Deterministic matrices, included snapshot IDs, exclusions/reasons, descriptive ranks and diagnostic flags. |
| `loop/runs/<UTC-run-id>/review-bundle.json` | Compact selected metrics, hypothesis excerpts, policy references and evidence paths for the agent. Raw captures remain separate; never truncate evidence silently. |
| `loop/runs/<UTC-run-id>/review.json` and `review.md` | Validated structured review and readable tables; proposals and approval status, not executed changes. Dated runs supersede neither older runs nor original evidence. |
| `sources/post-metrics/exports/` | Flat archive of CSVs and sibling export audits/screenshots. Keep all report audits together so current duplicate-report reconciliation works across runs. Manifests reference the returned actual path, including `status=reused`. |
| `sources/post-metrics/captures/<UTC-run-id>/` | Library and per-placement/tab JSON/screenshots; include placement/checkpoint/attempt IDs in names. Never overwrite partial captures to retry. |
| `sources/post-metrics/normalized/<UTC-run-id>.json` | Normalized observations with explicit metric scope, source type, reporting interval, actual age and raw evidence references. Derived and reproducible, not a second source of truth. |
| `loop/schedule/com.social-content.metrics.<project-key>.plist` | Proposed launchd definition with project-unique label, absolute executable paths, explicit `--project`, authenticated CLI PATH and local logs. Installed only after approval. |
| Existing flat files and `round-1.json` | Leave in place. Import/link historical observations; do not rename or erase them as part of migration. Existing in-file references must keep working. |

| Record | Fields and invariants |
| --- | --- |
| Publication | Preserve existing `id`; add `creative_version`, actual media/caption hashes and optional verified Post ID. Existing hypothesis number remains a reference, not proof a planned test was published. |
| Placement | `id`, `publication_id`, `kind`, `page_id`, `group_id`, `copy_post_id`, `permalink`, `insights_url`, visibility state, submitted/visible/first-seen timestamps and timestamp confidence. IDs use verified platform identifiers; unidentified rows remain unresolved observations. |
| Checkpoints | Each placement has `24h` and `7d` entries with due-at, status, attempts, selected observation reference and review state. Known visibility anchors due times; unknown approval time blocks matched-age eligibility. First-seen is not silently relabeled as approval time. |
| Observation | Immutable ID, placement ID, checkpoint intent, actual observed-at/age, interval/timezone, `daily|cumulative|period_summary` scope, metric values, panel statuses and evidence/hash. Page-level audience data must never be attached as a post demographic. |
| Revisions | Same post/day from a later export is a new source revision, not another amount to sum. Select a revision explicitly and retain earlier evidence. Conflicting rows inside one export still fail validation. |
| Inquiry coverage | Unknown inquiry counts remain null. Add explicit reviewed-zero coverage for a placement/window before counting zero; do not infer absence from an empty actions file. |

## 9. Execution wiring

| Project bootstrap | Decision |
| --- | --- |
| Command, already available | `python -m tools.loop --project local/NEW_PROJECT init --page-id PAGE_ID`. Use the existing `init` command, not another bootstrap script or project-specific copy of the engine. |
| Current behavior | Creates the project directory, `loop/config.json`, an empty schema-v1 `loop/publications.json` and the local lock. Repeating identical initialization preserves state; conflicting configuration fails. No browser connection, download, paid API call or scheduler activation. |
| Planned extension | Extend `initialize()` in `tools/loop/engine.py` to bootstrap the complete local layout below. New projects use the current supported registry schema; initialize v2 only when its implementation lands. Existing registries require explicit migration, never an implicit reset. |
| Directories | Create missing `loop/runs/`, `sources/post-metrics/exports/`, `captures/` and `normalized/`. The last two are also under `sources/post-metrics/`. Do not populate them with fake metrics or empty run reports. |
| Project guide | Create a missing `loop/README.md` with the project-scoped commands, shared-guide links and clearly unfilled goal/audience/qualified-action definitions. Create a missing `loop/AGENTS.md` with collection/review safeguards. Never replace or silently append to existing project instructions; print an integration snippet for the owner instead. |
| Optional hypotheses | Existing `--hypotheses-file RELATIVE_PATH` links an existing JSON file; it does not currently create one. Keep this contract. A new project can omit it and register numeric content references without a product-specific hypothesis schema. |
| Proposed preview | Add `init --dry-run` to validate inputs and list would-create paths without creating even a directory or lock. Resolve all paths from `--project`; refuse escaping paths and invalid Page IDs. |
| Safe rerun | Preflight all known conflicts before writes. Create only missing scaffold files; never overwrite publications, reviews, CSVs or instructions. Report created/reused/conflicting paths and schema version. A partial filesystem failure can be retried without losing previously created data. |
| First-use handoff | Output next commands: `status`, then `register` after a real publication, then `due`. List unresolved business definitions as setup tasks; do not fabricate products, customers, publishing times or posts. |
| Acceptance tests | Fresh directory initializes offline; identical rerun leaves file bytes unchanged; conflicting config fails; existing instructions/data survive; dry-run writes nothing; two project roots remain isolated. Extend `tools/loop/tests/test_engine.py`. |

| Bootstrap sequence | Next step |
| --- | --- |
| Initialize → fill project definitions | Confirm Page identity and business outcome definitions before assessing conversion performance. |
| Register → collect due checkpoints | Registration is proof of a confirmed publication, not permission to publish or start recurring jobs. |

| Proposed interface | Exact responsibility |
| --- | --- |
| Invocation prefix | All engine interfaces below run as `python -m tools.loop --project PATH COMMAND`. Current `init --page-id ID`, `status`, `due`, `register`, `collect`, `collect-insights`, and legacy `review --id` work; new run-oriented commands remain proposed. |
| `engine.py migrate --dry-run` / `migrate` | Preview then create a byte-preserving v1 backup and write v2. Preserve IDs/reviews/early observations. Map valid legacy collection evidence to its actual checkpoint; never complete 7d from an arbitrary late legacy snapshot. |
| `engine.py cycle --dry-run` | List due placements/checkpoints, planned collectors, blocked records and export reuse candidates. No browser actions or report creation. |
| `engine.py cycle` | Freeze the due worklist, create a run manifest, invoke existing Facebook CLI commands sequentially, normalize captures, compare and prepare the review bundle. Stop at `pending_agent_review`; never publish. |
| `engine.py cycle --resume RUN_ID` | Recover only that manifest's unfinished work. Reuse verified evidence and completed exports; unresolved download outcomes block rather than trigger another report request. |
| `engine.py compare --run RUN_ID` | Recompute deterministic comparison artifacts from the run's frozen evidence selection, without crawling or changing publication history. |
| `engine.py prepare-review --run RUN_ID` | Produce the evidence bundle and flag `pending_agent_review`. An agent session discovers this state via `status` and project instructions. |
| `engine.py review --run RUN_ID --file REVIEW.json` | Extend the current review command while keeping legacy `--id` compatibility. Validate referenced evidence and record a proposed review; this is not approval. |
| `engine.py approve-review --run RUN_ID` | Explicit human approval record for selected proposal IDs. V1 leaves applying approved content/distribution changes to a separate agent task; it does not auto-edit hypotheses or leave groups. |
| `engine.py record-action --file EVENT.json` | Validate and append an action event with a unique event ID; corrections append a superseding event. No automated Inbox access in v1. |

| Cycle order | Calls and data handoff |
| --- | --- |
| 1. Discover | Call proposed `facebook_agent content-library` once; save raw rows and visibility/identity gaps. Discovery may run with no due checkpoint to resolve Pending placements, but must not generate exports needlessly. |
| 2. Export | When original Page checkpoints are due, request one Content/Summary export for the explicitly verified current 28-day range, then import its returned path. No due original means no scheduled export. Daily is an explicit optional trend input. Neither replaces group rows or demographics. |
| 3. Capture | For due placements with supported Insights URLs, call `insights --open Source`; initial Traffic/age data and Source are separate observations in the same capture. No per-post CSV download loop. |
| 4. Normalize | Join verified IDs; collect gaps for unverified copy identity. Group rows may support exposure metrics but not age/retention that the row does not expose. Unsupported group Insights stay unavailable. |
| 5. Commit | Validate each checkpoint independently, write immutable normalized evidence, update references atomically, then produce comparison and review artifacts. Partial failure in one placement does not erase valid captures from others. |

| Operational safeguard | Implementation decision |
| --- | --- |
| Concurrency | Hold the existing loop lock for a cycle; acquire one shared advisory browser lock for live CLI work. Put lock acquisition in `tools/common/browser.py`'s CDP connection lifecycle and cover other repository CDP callers before claiming cross-platform exclusion. Release on every exception; avoid nested subprocess deadlocks by not acquiring that browser lock in the parent engine. |
| Timeout after clicking Download | Store report ID and click state before the action. Reconcile sibling audits/hash-verified CSVs first. An unobserved event is uncertain, not confirmed failure. Do not scan unrelated personal directories or retry with a new filename to bypass the guard. |
| Freshness | Resume reuses the same requested report ID only after checking Page, hash, range, breakdown and generation time. An old report is historical evidence, not a fresh checkpoint. Never use demographic or source percentages from one observation time to silently update a newer snapshot. |
| Collection failure | Auth challenges require human action; unsupported DOM/date settings produce explicit gaps. Do not classify these as poor content performance. Glasser fallback stays opt-in with its explicit spend ceiling. |
| Missed checkpoints | Record a late snapshot's actual age. If both 24h and 7d are overdue, one late capture cannot count as two distinct measurements or reconstruct first-day performance. Mark missing historical windows and retain the usable late observation. |
| Scheduling | Initially run `cycle` manually. Later install launchd at a proposed 15-minute interval after approval. It checks/collects only; agent invocation remains a separate, visible handoff. |

## 10. Comparison and review APIs

| Function in new `tools/loop/comparison.py` | Contract |
| --- | --- |
| `normalize_observations(manifest, raw_inputs)` | Return scoped observations and validation gaps. Preserve source revisions and panel timestamps; no mutation or inference of missing values. |
| `select_comparable(observations, placements, policy)` | Partition eligible and descriptive-only records with reasons. V1 matched-age tolerance: observed age within +2h of the requested checkpoint and at most 2h difference between compared placements; configurable operational policy, not statistical proof. Outside that band remains descriptive. |
| `compare_content(selected, hypotheses, actions)` | Compare original Page placements separately from group copies; label duration/product/channel mismatches. Return evidence-backed contrasts, not a causal verdict. |
| `compare_groups(selected, actions)` | Rank visible copies of identical creative within common eligible rounds. Use verified qualified-inquiry counts where coverage is comparable; otherwise label distribution-only ranks. Retain ties and exclusions. Never pool group viewers as unique reach. |
| `build_review_bundle(comparison, hypotheses, policies)` | Return selected evidence, gap tasks and policy context. Prioritize measurement gaps when primary outcomes are unknown. |

| Agent review field | Validation / behavior |
| --- | --- |
| `evidence_refs`, `observation`, `limitation` | All references resolve within the frozen run; distinguish reported metrics from interpretations and partial panels. |
| `suggestions[]` | Each has ID, creative/placement target, explanation hypothesis, one proposed change, expected primary outcome, controls, checkpoints, qualitative confidence and a reason. Allocation and creative experiments remain separate proposals. |
| `decision` | Repeat, revise, inconclusive or proposed focus/retest/reduce/pause. Pause proposals must satisfy the group guide's evidence conditions; no unsupported sales winner. |
| Approval | Machine validation checks structure/references, not truth. Human review is still required. Save accepted/rejected/deferred proposal IDs with timestamp; later outcomes reference the approved proposal. |

## 11. Migration and tests

| Order | Implementation / required proof |
| --- | --- |
| 1. State | Add v2 migration and checkpoint tests first. Re-running migration is a no-op; byte backup and old IDs/paths remain intact. Fix current `register` calling `timestamp(None)` when a known permalink lacks publish time. |
| 2. Evidence | Implement Summary/Daily imports and structured group rows. Fixtures cover column reordering, virtualized duplicates, missing IDs, renamed groups, Pending and unknown timestamps. Same title alone never merges placements. |
| 3. Cycle | Wire existing collectors into restartable runs; use fixture browsers/mocked subprocesses. Assert exactly one report creation/download click and one normalized checkpoint commit across retries. |
| 4. Decisions | Synthetic comparisons prove pending groups are excluded, unknown inquiries remain null, mismatched ages stay descriptive, missing groups are not zeros and average watch percentage is not completion. |
| 5. Agent handoff | Fixture review with invented evidence IDs fails validation. An incomplete capture creates a gap task; a valid review remains proposed until approval. No publishing/messaging/following command is reachable from `cycle`. |
| 6. Pilot | Run a dry-run, then one explicitly approved live collection; inspect CSV reconciliation, capture paths and resulting matrices. Ask the agent for a sourced review. Schedule only after this full handoff works. |

## 12. Delivery boundary

| V1 includes | Deferred |
| --- | --- |
| Stable records, 24h/7d history, current CSV export/import, structured library rows, scoped comparison artifacts, agent review queue and explicit approval history | Automatic publishing, leaving/pruning groups, Inbox crawling, autonomous LLM execution, dashboard redesign, database and multi-host workers |
| Preserve existing evidence and tested collector interfaces | No bulk move of historical files, no regeneration of all reports, no hidden recurring paid calls |
| Ready-to-code exit | Implement in section 11 order; each phase must pass its offline checks before adding live automation. This document itself changes no runtime behavior. |
