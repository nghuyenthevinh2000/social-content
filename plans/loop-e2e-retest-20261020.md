# Loop E2E retest — 2026-10-20

| Verdict | Result |
| --- | --- |
| Recovery pipeline | **Pass through agent proposal:** existing evidence → normalization → comparison → bundle → recorded review → safe resume. |
| Full acceptance | **Not complete.** Observation timestamps change on reuse, bundle review state contradicts manifest/checkpoint state, and verified group comparisons remain unavailable. |
| Boundary | No due checkpoints existed. This tested recovery and reuse of run `20261020T075511Z-00e38da8`, not a new live collection or fresh CSV creation. No custom scripts, runtime edits, paid calls, approval or publishing. |

```text
Verified receipts → compare ✓ → prepare-review ✓ → record review ✓ → resume ✓
                          ↓                               ↓
               No eligible matched items       Bundle still says pending
```

## Checks

| Existing command / check | Observed result |
| --- | --- |
| `uv run python -m unittest discover -s tools/loop/tests` | **48 passed.** |
| `uv run python -m unittest discover -s tools/facebook_agent/tests` | **140 passed.** Total: 188. |
| `python3 -m tools.loop --project local/paper-ink-product due` | `[]`; no forced checkpoint reset. |
| `uv run python -m tools.loop --project local/paper-ink-product cycle` | Initially exposes one pending checkpoint and two open historical runs despite `no_work`. |
| Same loop prefix, `compare --run 20261020T075511Z-00e38da8` | Exit 0, `compared`, correct artifact returned; zero eligible content/group items. Former dispatch failure resolved. |
| Same loop prefix, `prepare-review --run 20261020T075511Z-00e38da8` | Exit 0, `review_prepared`; 16 descriptive observations and 14 gap records. |
| Same loop prefix, `cycle --resume 20261020T075511Z-00e38da8` | Exit 0; collectors both completed, previously recovered summary CSV reused. |
| Same loop prefix, `review --run 20261020T075511Z-00e38da8 --file local/paper-ink-product/loop/runs/20261020T075511Z-00e38da8/review-input-retest-20261020.json` | At `10:58:13Z`, manifest becomes `review_proposed`; publication and collected 24h checkpoint become `reviewed`. Previous review preserved as `review-before-retest-20261020.json`. |
| Repeat resume after review | Exit 0, remains `review_proposed`; checkpoint attempts stay **2**, unchanged from before this retest. Four checked SHA-256 values unchanged: original library, Insights, repaired CSV and imported JSON. |
| Fresh cycle after reviewed resume | At `10:58:26Z`, `pending_review_count=0`; two open runs remain: this proposal awaiting a decision and an older empty-evidence run. No approval inferred. |

## Remaining fixes

| Priority / owner | Verified gap | Fix and acceptance |
| --- | --- | --- |
| P0 — group view comparison | No usable leaderboard answers which group generates the most views for the same creative. Current group ranking prefers inquiries/viewers rather than a separate views objective. Library rows normalize to checkpoint `observation`, which is excluded from matched comparison even if identity is resolved. | Carry verified group/copy IDs, creative version, visibility time, capture time and checkpoint into group observations. Produce a separate descending **views** leaderboard for the same creative at matched 24h/7d visible ages, preserving ties. Include group name/link, views, viewers, actual age, evidence and eligibility reason; show excluded copies separately. Verify two resolved same-creative copies reach the matrix, a higher-view/lower-viewer copy wins the views ranking, and pending/unknown-age copies cannot rank. Compare repeated common creative rounds before recommending allocation; buyer effectiveness stays a separate outcome. |
| P1 — `tools/loop/comparison.py:152,189`; engine handoff | Reused library receipt says `09:02:14.741488Z`, but normalized observations move from `10:57:35Z` to `10:58:17Z` across resumes. CSV observations also use normalization time. | Carry original capture/export observation time through normalization; use null when unknown and a separate processing timestamp. Repeated normalization of identical evidence must retain observation times. |
| P1 — bundle lifecycle | After successful review and second resume, manifest says `review_proposed`, checkpoint says `reviewed`, but `review-bundle.json` still has `pending_agent_review=true`. | Derive bundle state from the review’s evidence revision. Review + prepare-review + intact resume must agree; genuinely new evidence must require a new review. |
| P1 — group identity and metadata | Eleven unresolved-group gap records remain, including historical repair rows. Posts 1–2 still lack verified publication metadata. Matrices remain empty. | Resolve verified group/copy identities, visibility time and creative linkage; recover publication metadata without guessing timezone. Demonstrate same-content matched-age comparison; keep unresolved/pending/late evidence excluded. |
| P2 — historical run/audit clarity | Run `20261020T072158Z-645dd4e7` still requests review despite no evidence files. Successful recovered run retains old failure warnings and historical hash/repair gaps. | Add an explicit audited superseded/resolved workflow; separate current blockers from historical events. Do not delete or silently close old runs. |
| Acceptance boundary | CSV recovery and reuse are now working; cold-start collection, scroll coverage and matched group ranking were not re-exercised here. | After timestamp/lifecycle fixes, rerun regressions and the same reuse sequence, then verify a genuinely due live checkpoint without resetting completed work. |

## Evidence

| Artifact | Location |
| --- | --- |
| Final resume output | [retest-resume-result-20261020.json](../local/paper-ink-product/loop/runs/20261020T075511Z-00e38da8/retest-resume-result-20261020.json) |
| Manifest and review | [manifest.json](../local/paper-ink-product/loop/runs/20261020T075511Z-00e38da8/manifest.json), [review.json](../local/paper-ink-product/loop/runs/20261020T075511Z-00e38da8/review.json) |
| Contradictory bundle flag | [review-bundle.json](../local/paper-ink-product/loop/runs/20261020T075511Z-00e38da8/review-bundle.json), `pending_agent_review` |
| Source observation time | [content-library.json](../local/paper-ink-product/sources/post-metrics/captures/20261020T075511Z-00e38da8/content-library.json), top-level `observed_at` |
| Proposal | Post 4 remains an unapproved application-first opening test using a genuine vỏ sớ example. No new attention metrics were collected; two viewers still cannot validate the hook. |
