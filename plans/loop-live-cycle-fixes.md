# Loop E2E: remaining acceptance fixes

| Outcome — 2026-10-20 | Verified result |
| --- | --- |
| Verdict | **Partial E2E, not yet a clean full loop.** The first live run reached live capture, normalization, comparison, review staging and agent review recording, but CSV export failed. A later reconciliation recovered the CSV without creating a second report; unresolved group identities and posts 1–2 metadata still block exact comparison. |
| Post-fix code status | 2026-10-20: P0 command dispatch, evidence integrity, CSV reconciliation and several P1 lifecycle gaps are implemented with regression tests. Live CSV reconciliation then recovered report `1167141245976275` without creating a second report; the run now exits 0 with `pending_agent_review`. |
| Scope | `tools/loop` against `local/paper-ink-product`. No custom scripts, runtime fixes, publishing, paid calls, proposal approval or hypothesis edits. JSON review input is data consumed by the existing CLI, not a helper script. |
| Active plan | This updates the previous acceptance list with live evidence. Earlier parser improvements remain useful, but passing tests is not live acceptance. |
| Interpretation | “Post v4” means planned hypothesis `post=4`; there is no published post 4 or measured v4 outcome. |

```text
Fresh cycle → no_work (review still pending)
Resume → Library ✓ → CSV ✗ → Insights ✓ → Descriptive comparison → Review saved
                       ↓                                      ↓
             Uncertain creation request              State still pending
```

## Execution evidence

| Existing command, from repository root | Result |
| --- | --- |
| `python3 -m tools.loop --project local/paper-ink-product due` | `[]`; posts 1–2 blocked by missing publication details, post 3 already collected. |
| `python3 -m tools.loop --project local/paper-ink-product cycle` | Exit 0, `no_work`; run `20261020T090134Z-3143d417`. Does not process pending reviews or repair failed collectors. |
| `uv run python -m tools.common doctor` | Shared browser connected. |
| `uv run python -m tools.facebook_agent doctor --page-id 61595289277974` | Authenticated as the configured Page. Browser commands were serialized. |
| `uv run python -m tools.loop --project local/paper-ink-product cycle --resume 20261020T075511Z-00e38da8` | Exit 1, `partial_collection_pending_review`. Missing historical raw captures were re-collected under the existing run ID. |
| Same loop prefix, `compare --run 20261020T075511Z-00e38da8` and `prepare-review --run 20261020T075511Z-00e38da8` | Both exit 0 but return registry state, not the requested operation; parsed commands fall through to the status branch. |
| Same loop prefix, `review --run 20261020T075511Z-00e38da8 --file local/paper-ink-product/loop/runs/20261020T075511Z-00e38da8/review-input-e2e-20261020.json` | Review saved at `09:05:01Z`, status `proposed`; no approval issued. |
| `uv run python -m unittest discover -s tools/loop/tests` | 35 tests passed. |
| `uv run python -m unittest discover -s tools/facebook_agent/tests` | 134 tests passed. |

| Artifact | Evidence / constraint |
| --- | --- |
| [Run manifest](../local/paper-ink-product/loop/runs/20261020T075511Z-00e38da8/manifest.json) | Failed CSV; 13 gap entries include four copies of the same CSV error and nine unresolved group identities. |
| [Raw Insights receipt](../local/paper-ink-product/sources/post-metrics/captures/20261020T075511Z-00e38da8/reel-1421837226123438-orig-24h.insights.json) | Publication `reel-1421837226123438`, initial panel at `2026-10-20T09:02:51.017549Z`, age **28.37h**: 33 views, 2 viewers, 9 three-second views; comments/reactions/shares/clicks 0; inquiries unknown. |
| [Content Library receipt](../local/paper-ink-product/sources/post-metrics/captures/20261020T075511Z-00e38da8/content-library.json) | 10 unique rows, nine unresolved group copies; one pending. Page row has known post ID `122104901223509642` but remains unmatched downstream. Traversal completeness is collector-reported, not independently established. |
| [CSV audit](../local/paper-ink-product/sources/post-metrics/exports/content-summary-61595289277974-20261020T075511Z-00e38da8.export.json) | `creation_requested`, `report_id=null`, then `Expected one visible Export data; found 0.` No CSV or import produced. Report creation may have succeeded; no automatic retry. Settings screenshot is before the click, not proof of post-click dialog state. |
| [Comparison](../local/paper-ink-product/loop/runs/20261020T075511Z-00e38da8/comparison.json), [bundle](../local/paper-ink-product/loop/runs/20261020T075511Z-00e38da8/review-bundle.json), [recorded review](../local/paper-ink-product/loop/runs/20261020T075511Z-00e38da8/review.json) | Zero eligible content/group items; 11 descriptive observations. Late snapshot correctly excluded from exact-age matching. Review does not establish a winning creative or group. |
| Historical evidence loss | Before resume, both manifest-referenced raw files were absent. Previous comparison described 32 views at 27.25h; that raw measurement cannot now be independently checked. Resume replaced the post hash and appended a second library hash for the same path; checkpoint attempts rose 1→2. |

## Live CSV recovery — 2026-10-20 (after code fixes)

| Step | Verified result |
| --- | --- |
| `uv run python -m tools.loop --project local/paper-ink-product cycle --resume 20261020T075511Z-00e38da8` | First post-fix resume reconciled the outstanding creation against Report history: exactly one new entry, `1167141245976275`. The repair run logged `library → creation-reconciled → report-history → downloaded`; no `report-settings` click, so no second report was created. |
| Summary import | The downloaded CSV is a Summary export with `Date="Lifetime"`. The importer now detects daily rows by parseable dates, so it imported 5 summary posts (joined at `exports/…-repair1.imported.json`) with `breakdown=summary`. |
| Evidence preservation | The prior `creation_requested` audit was restored byte-for-byte from a pre-run backup and left untouched; resolution is recorded in `content-summary-…export.reconciliation.json`. The unusable re-collected `content-library-repair1.json` (5 unidentified group rows) is preserved under `captures/<run>/repairs/`; the verified original library was reused instead of overwritten. |
| Identity handoff | Page post `122104901223509642` maps to placement `reel-1421837226123438-orig` from both the Content Library row and the CSV row (`identity_source=page_post_id`); `122103568335509642` maps to `post-2-unresolved-orig`. |
| Run state | Final resume exits 0 with `pending_agent_review`; `content_library` and `csv_export` are `completed`; comparison holds 16 descriptive observations and no eligible exact-age items. |
| Still unresolved | 11 `unresolved_group_identity` gaps (duplicated group names across two captures), posts 1–2 visibility/time, and the earlier recorded review’s proposals remain unapproved. |

```text
Failed CSV audit -> reconcile 1 new history entry -> download summary -> import 5 posts
Prior audit bytes restored + sidecar (reconciled)   Unusable repair library preserved
```

## Post 4 recommendation

| Improve | Proposed specification; not approved |
| --- | --- |
| Hypothesis | Among workshops making vỏ sớ, a buyer/application-first opening with a genuine finished example may produce more qualified trial conversations than the current curiosity-first opening. This is a new test, not a conclusion from post 3. |
| Single variable | Two new 10-second cuts; change only seconds 0–2: buyer/application plus finished product versus the current curiosity direction. Keep the same real demonstration afterward. Do not use historical catalog post 1 as a causal control. |
| Proof gate | Verify the finished vỏ sớ was actually made from Nhung đỏ 120 and obtain footage permission. If unavailable, defer this demonstration rather than imply compatibility or invent a process. |
| CTA and qualification | Ask for trial interest plus the workshop’s application. Count distinct verified workshops stating the application and asking trial conditions; record agreed next steps separately. No free-sample promise. |
| Measurement | Comparable actual-age 24h snapshots; primary inquiry assessment over 7 days, later orders separately. Record placement identity/visibility, spend, posting time and response policy. Organic sequential tests remain exploratory. |
| Decision | Choose a direction only after adequate comparable exposure and verified buyer evidence; no arbitrary sample threshold is established here. Tiny reach or absent action tracking means inconclusive, not zero conversions. |
| Rationale | Post 3’s largest reported drop-off is at 1s, suggesting an opening to investigate, not its cause. Two viewers and 23s average watch time on a displayed 10s reel cannot validate retention, buyer fit or completion. Keep product/CTA/offer fixed while testing relevance. |
| Traceability | Proposal `post-4-application-first-e2e-20261020` in the recorded run review cites publication, observation and raw receipt. Preserve tried hypotheses; post 4 stays planned. |

## Implementation status — 2026-10-20

| Priority | Implemented in code | Regression evidence | Still requires live/verified work |
| --- | --- | --- | --- |
| P0 CSV creation | `pending_creations`, history reconciliation, persisted request fingerprint, post-click state, explicit dialog guard and `export_uncertain` instead of blind Export reopen. Resolution is written to a `<audit>.reconciliation.json` sidecar and prior audit bytes are never rewritten. Summary CSV daily detection uses parseable dates, so `Date="Lifetime"` imports as summary. | `test_pending_creations_scope_and_exclusion`, `test_reconcile_requires_exactly_one_candidate`, `test_existing_creation_is_reconciled_from_history_without_new_report`, `test_explicit_report_waits_for_unverified_creation`, `test_csv_audit_without_csv_is_repaired_to_new_path`, `test_summary_export_with_lifetime_date_column_imports`, `test_daily_rows_rejected_for_summary_breakdown`. | Reconcile additional outstanding `creation_requested` audits against real Report history if any appear. |
| P0 resume integrity | SHA-256/type checks before reuse; latest recorded entry wins with an `evidence_hash_conflict` gap; repairs under `captures/<run>/repairs/` or `exports/repairs/` with `parent_path`; one path cannot hold two hashes; untracked or audit-only history is repaired, never overwritten; reuse does not increment attempts; a verified CSV is re-imported rather than re-exported; verified evidence is reused even after a failed repair. | `test_resume_repairs_changed_evidence_without_overwriting`, `test_untracked_existing_library_is_repaired_not_overwritten`, `test_verified_library_is_reused_after_a_failed_repair`, `test_valid_csv_is_reimported_without_another_export`, `test_intact_resume_has_no_side_effects_or_attempt_increment`. | Confirm on further historical runs; posts 1–2 still lack verified identity/time. |
| P0 dispatch | `compare --run` and `prepare-review --run` write their own artifacts; unknown operations error instead of returning status. | `test_compare_and_prepare_review_dispatch_without_collection`. | Exercise against the live run and inspect artifacts. |
| P1 Page identity handoff | Content Library and CSV rows join to placements by verified Page post ID only; titles are never merged. | `test_page_post_id_maps_library_row_to_placement`. | Resolve the live group-copy identities, which still lack numeric group IDs. |
| P1 review lifecycle | `status` and `no_work` expose pending reviews and open runs; review recording sets `review_proposed` and marks cited checkpoints `reviewed`; re-staging identical evidence preserves that state; gaps deduplicate. | `test_no_work_surfaces_pending_reviews_and_open_runs`, `test_gap_deduplication`, `test_intact_resume_has_no_side_effects_or_attempt_increment`. | Re-run the pending live review through the new state transition. |
| P1 due/age/quality | `due` lists placement checkpoints; group copies without `visible_at` stay descriptive; empty/mismatched/unidentified library captures become gaps or failures; empty Insights records are a gap rather than a crash. | `test_cli_due_reports_placement_checkpoints`, `test_group_copy_without_visible_time_stays_descriptive`, `test_empty_insights_records_is_a_gap_not_a_crash`. | Independently establish scroll-container coverage and resolve posts 1–2 identity/time. |
| P1 docs | Loop and Facebook agent READMEs describe reconciliation sidecars, repair paths, summary-CSV date detection, new commands and review state. | Doc inspection only. | Clean-checkout evidence guidance and post 1–2 recovery remain open. |

```text
Code fixes → 188 offline tests → live CSV reconciliation → safe live resume → full-loop acceptance
```

## Fix plan

| Priority / owner | Minimum fix | Acceptance check |
| --- | --- | --- |
| P0 — `facebook_agent/insights_export.py` | Reconcile the outstanding creation through verified report history before any new creation. Persist request identity/settings, capture post-click state, handle dialog transitions explicitly; never swallow errors then blindly open Export. | Recover the existing report once, validate Page and summary breakdown, import the returned CSV path; uncertain creation/download blocks repeats across output paths. |
| P0 — `loop/engine.py:cycle` | Verify hashes, identity and completeness before reuse. Missing evidence must create an explicit repair attempt with new capture paths and parent linkage, not replace historical evidence. | Missing/changed receipt produces a repair gap; intact resume performs no collector side effect or checkpoint attempt increment. One path cannot have contradictory hashes. |
| P0 — `engine.py:main` | Implement the already advertised `compare` and `prepare-review` branches; reject unsupported operations instead of falling back to status. | Each command writes/returns its run artifact without collection; tests assert output type, file change and invalid-run failure. |
| P1 — engine/comparison handoff | Map verified Page post IDs to existing placements; resolve accessible group/copy IDs and creative version without title-only merging. | Known Page row maps correctly; two verified same-creative group placements compare at matched visible ages. Pending/unresolved copies remain excluded. |
| P1 — review lifecycle | Surface pending reviews/failed runs when collection has no due work. Recording review should update appropriate review state without implying approval or clearing collection failures. Deduplicate gaps. | Fresh invocation exposes remaining work; recorded review is discoverable, checkpoint/publication states agree, and repeated staging does not multiply gaps. |
| P1 — due/age/quality | Use checkpoint-aware due output, preserve unknown group approval time, validate useful scoped evidence and actual scroll-container coverage. | Fixture 7d-due placement appears even if publication says collected; unknown visibility is descriptive; empty/unidentified captures do not satisfy required collection. |
| P1 — evidence/measurement/docs | Recover posts 1–2 identity/time from verified sources; preserve raw evidence durably; record verified buyer events through existing `record-action`. Correct stale README claims and broken guidance links. | No inferred timezone or zero inquiries; docs link to actual plans, describe implemented commands accurately, and a clean checkout explains evidence availability. |
| Delivery order | Recovery/integrity → command dispatch → identity/review lifecycle → regression → controlled live acceptance. | Retain all 169 passing tests, add regressions for observed failures, then recover CSV without duplicate creation and repeat a safe no-side-effect resume. |
| Full-loop acceptance | Usable required receipts, consistent audit/checkpoint/review state, justified comparison exclusions and a sourced proposal. | Approval/publishing remains a separate human gate; no custom scripts needed. This test has **not** met acceptance. |
