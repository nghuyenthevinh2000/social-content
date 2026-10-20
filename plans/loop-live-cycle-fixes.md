# Loop: remaining acceptance fixes

| Current baseline | Status |
| --- | --- |
| Latest verification | [Read-only recheck v3](../local/paper-ink-product/sources/post-metrics/captures/recheck-20261020-v3/recheck.md): **169 tests pass; live library names, metrics and placement types now parse correctly.** |
| Resolved items | Collector wiring, duplicate due work, all-null library metrics, wrong group labels, duplicate observation IDs, CSV response-envelope parsing, uninitialized CSV resume path, normalization-gap propagation and descriptive review context are no longer the old unresolved tasks. |
| Acceptance boundary | Dry-run reports `no_work`. No new full cycle or CSV recovery was forced. Passing parser/tests does not establish complete live recovery or verified group ranking. |
| Scope | This is the only active fix list. Preserve historical evidence, project isolation and successful checkpoints; no runtime changes implemented by this document. |

```text
Parsed evidence → Verified identities → Matched comparisons → Safe recovery → Acceptance
```

| Priority / file | Remaining work | Acceptance test |
| --- | --- | --- |
| P0 — `tools/facebook_agent/content_library.py`, `tools/loop/engine.py` | Resolve group/copy identity from verified links where accessible, then map rows to publication/placement records. All nine live group-copy rows currently lack stable group/copy IDs. | A real or fixture copy resolves to the correct existing creative and group placement without title-only merging. Unavailable IDs remain explicit gaps and never authorize pruning. |
| P0 — `tools/loop/comparison.py`, engine handoff | Prove a resolved due group can pass through scoped normalization, checkpoint eligibility and same-content comparison. Current live rows remain descriptive/unmatched. | Two verified placements of the same creative yield a valid group matrix at comparable visible ages; pending, unverified and mismatched rows stay excluded with reasons. |
| P0 — `tools/facebook_agent/insights_export.py` | Reconcile the last outstanding creation request before claiming live export recovery. Dialog waits exist but exceptions are swallowed and the latest recheck did not exercise export. | Locate the previously generated report by verified identity/history, download/reuse it once and import the returned path. No new report/download merely because a prior event was missed. |
| P1 — `engine.py:cycle --resume` | Compare saved evidence hashes against file bytes before reuse; verify Page/content identity, completeness and timestamps. Recomputing and replacing a hash is not verification. | A modified or partial capture creates a repair gap; an intact completed capture is reused without another collector side effect. Preserve frozen run inputs and audit history. |
| P1 — visible-age policy | Confirmed `visible_at` now has priority, but fallbacks can still treat submission, first-seen or Page publication as group approval time. | Unknown group visibility produces descriptive evidence, not an exact checkpoint match. Test differing submission/approval times and 24h/7d recovery. |
| P1 — traversal and collector quality | Validate actual scroll-container coverage and distinguish usable structured results from mere file/row presence. | Fixture virtualized tables and live evidence demonstrate final-row coverage. An all-unidentified/all-null collection cannot be reported as complete required collection. |

| Delivery order | Required result |
| --- | --- |
| 1. Identity and comparison fixtures | Stable IDs, matching creative/version, group-visible age and explicit unknown-identity cases. |
| 2. Recovery fixtures | Real `ok/data` CLI envelopes, returned CSV paths, changed hashes, partial captures, delayed dialogs and interrupted downloads. Keep the already passing reuse tests. |
| 3. Offline regression | Run both `tools/loop/tests` and `tools/facebook_agent/tests`; do not equate passing tests with live completion. |
| 4. Controlled live recovery | Reconcile the existing report first; use a safe resume path or genuine due work. Do not reset the already collected 24h checkpoint. |
| Done | Usable evidence, verified or explicitly unresolved placement identities, correct comparison exclusions, integrity-checked reuse and sourced review output. No invented winner, zero inquiry count or approval time. |
