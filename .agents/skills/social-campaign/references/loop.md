# Loop Lifecycle Specification and Execution Reference

```text
register → checkpoints (24h/7d due) → collect → normalize → eligibility → compare → review → approval
```

## Stage Architecture

| Stage | Responsible Module | Input Data | Output Artifact / Transition | Invariant |
|---|---|---|---|---|
| 0. Scaffolding | `tools.loop.project_init` | Project path `local/<slug>`, page ID from `profiles.json` | `loop/`, `product-marketing.json`, `posts/hypothesis.json`, `sources/` | One-time non-destructive init; requires explicit user interview before populating. |
| 1. Registration | `tools.loop.register` | Confirmed URL, post number, publish ISO timestamp | Append entry to `loop/publications.json`; arm 24h & 7d placement timers | Never publishes or touches browser; records canonical URL only. |
| 2. Checkpoints | `tools.loop.checkpoints` | Verified publication timestamps and age against system time | Frozen 24h & 7d due measurement worklist | Planned posts never count as published; actual age strictly retained. |
| 3. Collection | `tools.loop.collect` | Frozen due worklist | Raw receipts in `sources/post-metrics/captures/` and `exports/` | Browser Insights collection (zero cost) or authenticated CSV exports. |
| 4. Normalization | `tools.loop.normalize` | Raw evidence receipts | Standardized observation records in `sources/post-metrics/normalized/` | Preserves original timestamps, post identity, and missing/null values without fabrication. |
| 5. Eligibility | `tools.loop.eligibility` | Normalized observations | Eligible observation set plus explicit exclusion reasons | Non-comparable items marked with explicit reasons; never discarded silently. |
| 6a. Post Compare | `tools.loop.compare_posts` | Eligible page observations | Creative matrix, outlier flags, and variance limits | Evaluates hook, format, and angle performance across matched age windows. |
| 6b. Group Compare | `tools.loop.compare_groups` | Eligible group placements | Distribution-only ranking or qualified inquiry ranking | Ranks performance with ties preserved; reach is never pooled across groups. |
| 7. Review | `tools.loop.review` | Comparisons, hypothesis file, and detected gaps | `review-bundle.json`, structured proposals, review log | Packages observations and test suggestions; does not authorize changes. |
| 8. Approval | `tools.loop.approval` | Selected proposal IDs from human reviewer | `approval-audit.json` in run folder; unblocks next post hypothesis | Strict human gate; never publishes or reallocates ad budget automatically. |

## CLI Commands Reference

| Operation | Command Syntax | Required Flags / Args | Purpose & Precondition |
|---|---|---|---|
| Scaffolding Dry-Run | `python -m tools.loop --project local/<SLUG> init --page-id <ID> --dry-run` | `--project`, `--page-id`, `--dry-run` | Previews planned directories and target files without modifying disk. |
| Execute Scaffolding | `python -m tools.loop --project local/<SLUG> init --page-id <ID>` | `--project`, `--page-id` | Bootstraps Schema v2 files; page ID must resolve from `profiles.json`. |
| Status Inspection | `python -m tools.loop --project local/<SLUG> status` | `--project` | Reads authoritative manifest and current `loop/status.json` projection. |
| Due Audit | `python -m tools.loop --project local/<SLUG> due` | `--project` | Lists mature 24h and 7d checkpoints without launching browser. |
| Register Post | `python -m tools.loop --project local/<SLUG> register --post <ID> --url "<URL>" [--published-at "<TS>"]` | `--project`, `--post`, `--url` | Registers confirmed publication URL and freezes checkpoint schedule. |
| Insights Capture | `python -m tools.loop --project local/<SLUG> collect-insights` | `--project` | Navigates authenticated browser to Meta Insights dashboards (zero API cost). |
| Stage Cycle | `python -m tools.loop --project local/<SLUG> cycle [--dry-run] [--resume <RUN_ID>]` | `--project` | Runs frozen stage pipeline from checkpoints through eligibility and review staging. |
| Recompute Compare | `python -m tools.loop --project local/<SLUG> compare --run <RUN_ID>` | `--project`, `--run` | Recomputes comparisons from stored observations without re-collecting. |
| Prepare Review | `python -m tools.loop --project local/<SLUG> prepare-review --run <RUN_ID>` | `--project`, `--run` | Rebuilds `review-bundle.json` matching recorded evidence revisions. |
| Record Review | `python -m tools.loop --project local/<SLUG> review --run <RUN_ID> --file <REVIEW.json>` | `--project`, `--run`, `--file` | Records agent observation, limitation notes, and test suggestions. |
| Human Approval | `python -m tools.loop --project local/<SLUG> approve-review --run <RUN_ID> [--proposals <IDS>]` | `--project`, `--run` | Records explicit human approval; unlocks subsequent post hypothesis drafting. |

## File Storage and Projection Boundaries

| Artifact / Path | Format / Schema | Primary Reader | Authoritative Writer | Content Description |
|---|---|---|---|---|
| `loop/config.json` | JSON Schema v2 | `tools.loop.storage` | `tools.loop.project_init` | Holds page ID, hypothesis file path (`posts/hypothesis.json`), and brand manifest link. |
| `loop/publications.json` | JSON Schema v2 | `tools.loop.workflow` | `tools.loop.register` | Registered canonical publication records, permalinks, timestamps, and placement arrays. |
| `loop/status.json` | JSON Schema v3 | Orchestrator CLI | `tools.loop.workflow` | Non-authoritative runtime projection of active run stage, errors, and next actions. |
| `loop/.engine.lock` | OS File Lock | All loop stages | `tools.loop.storage` | Atomic mutual exclusion lock preventing concurrent stage execution on the same project. |
| `sources/post-metrics/` | Raw JSON / CSV | Normalization stage | Collection stage | Raw exports and DOM captures preserved with original timestamps and hashes. |
| `loop/runs/<run_id>/` | Run Folder | Review and approval | `tools.loop.workflow` | Manifest, observations, comparisons, review bundles, and approval logs. |

## Status Schema Projection Fields

| Field Name | Type / Values | Description |
|---|---|---|
| `schema_version` | Integer (`3`) | Format version for `loop/status.json` projection. |
| `run_id` | String / UUID / null | Selected active or historical execution run identifier. |
| `state` | `idle` \| `running` \| `waiting` \| `blocked` \| `failed` \| `interrupted` \| `completed` | Overall workflow execution state. `idle` indicates no remaining due work. |
| `current_stage` | Stage name / null | Name of the stage currently executing or awaiting handoff. |
| `stages` | Object mapping | Detailed start/end timestamps, completion states, and failure reasons per stage. |
| `comparison_result` | `comparable` \| `not_comparable` \| null | Summarizes observation eligibility, exclusion counts, and plain-language rationale. |
| `pending_run_ids` | Array of strings | Identifiers of other runs requiring repair, agent review, or human decision. |

## Invariants and Safety Protocols

| Safety Protocol | Rule Specification | Rationale & Failure Behavior |
|---|---|---|
| Project Isolation | All project operations must pass `--project local/<slug>`. | Prevents cross-campaign data leakage; paths remain strictly relative to project root. |
| Atomic Persistence | All JSON updates use temporary files (`.tmp`) followed by atomic rename. | Guarantees file integrity in the event of process interruptions or crashes. |
| Evidence Immutability | Evidence reuse requires matching path, SHA-256 fingerprint, and type. | Corrupted or changed evidence routes to repairs; historical receipts are never overwritten. |
| Checkpoint Discipline | Measurements execute strictly at 24h and 7d post-publication windows. | Late snapshots record actual age; missing first-day data is never fabricated. |
| Review Invalidation | Changed evidence revision supersedes existing review and resets state. | Ensures human approval is never given on stale, modified, or out-of-date metrics. |
