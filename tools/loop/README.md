# Project-scoped metrics loop

| Responsibility | Location |
| --- | --- |
| Reusable engine, tests and guidance | `tools/loop/` |
| Page identity and optional hypothesis mapping | `<project>/loop/config.json` |
| Publications, pending reviews and lock | `<project>/loop/publications.json`, `<project>/loop/.engine.lock` |
| Metrics and audit evidence | `<project>/sources/post-metrics/` |
| Worked comparisons and historical reports | `<project>/loop/`; not bundled into the shared engine |

```text
tools.loop --project PATH → Project config/state → Collector → Evidence → Agent review
```

| Command, from repository root | Purpose |
| --- | --- |
| `python -m tools.loop.project_init --project PATH --page-id PAGE_ID [--dry-run]` | Standalone full project bootstrapper. Scaffolds `loop/`, `product-marketing.json`, `posts/hypothesis.json`, `posts/1/`, `brand-assets/`, and `customer/`. |
| `python -m tools.loop --project PATH init --page-id PAGE_ID [--dry-run]` | Initialize project configuration, product marketing, initial post, directory layout, and empty registry (Schema v2). Refuses conflicting configuration and preserves existing state. |
| `python -m tools.loop --project PATH init --page-id PAGE_ID --hypotheses-file posts/hypothesis.json` | Optional hypothesis-number validation. Path must stay inside the project; no product-specific schema is required when omitted. |
| `python -m tools.loop --project PATH migrate [--dry-run]` | Migrate project state to Schema v2 with atomic byte backup (`publications.json.v1.bak`) and placement checkpoints. |
| `python -m tools.loop --project PATH status` | Inspect this project's memory. |
| `python -m tools.loop --project PATH due` | List publications and placement checkpoints that still need collection. No browser or paid calls. |
| `python -m tools.loop --project PATH register --post 1 --url https://www.facebook.com/reel/POST_ID [--published-at TIMESTAMP]` | Register a confirmed canonical URL. Accepts omitted publish time without crashing. |
| `python -m tools.loop --project PATH cycle [--dry-run] [--resume RUN_ID]` | Run frozen end-to-end collection, normalization, deterministic comparison, and review bundle staging. |
| `python -m tools.loop --project PATH record-action --file EVENT.json` | Append a verified buyer action or qualified inquiry event to `loop/actions.jsonl`. |
| `python -m tools.loop --project PATH review --run RUN_ID --file REVIEW.json` | Record an agent review with observation, limitation, and test suggestions for a run. |
| `python -m tools.loop --project PATH approve-review --run RUN_ID [--proposals ID1,ID2]` | Record explicit human approval for selected proposals before any actions are executed. |
| `uv run python -m tools.loop --project PATH collect-insights` | Collect due post dashboards through the existing Facebook CLI and authenticated browser. Page identity comes from project config. |
| `python -m tools.loop --project PATH collect --max-cost-usd AMOUNT` | Optional Glasser public-metrics fallback; explicit spend ceiling per invocation. |
| `python -m tools.loop --project PATH review --id PUBLICATION_ID --file REVIEW.json` | Legacy review command on a single publication. |
| `python -m unittest discover -s tools/loop/tests` | Offline tests, including isolation between unrelated projects. |

| Current behavior / limits | Rule |
| --- | --- |
| Project-agnostic, Facebook collector | No fixed product directory, Page ID, audience or product rules. Platform-specific capture remains in `tools/facebook_agent/`. Other platforms are not implemented. |
| Explicit scope | `--project` is required, even for status. Relative project roots resolve from the caller; evidence paths stay project-relative. Browser subprocesses run from the repository root. |
| State ownership | No project records or metrics are stored under `tools/loop`. Existing project state and evidence remain where they were. |
| Checkpoint | Current engine supports one first-invocation-after-24h checkpoint. Actual age is retained; late snapshots cannot reconstruct exact first-day totals. |
| Capture | Authenticated Page required. Retention/age values remain dashboard-reported; unavailable values are null. Collector does not autonomously invoke an agent. |
| Safety | Per-project lock, atomic state writes, paid-run idempotency keys and reused receipts. Browser operations across different projects/platforms must still be serialized; a global browser lock is not implemented here. |
| Activation | No scheduler, publishing, messaging, automatic pruning or new end-to-end cycle is enabled by this move. |

| Guidance | Contents |
| --- | --- |
| [Implementation specification](metrics-learning-plan.md) | Proposed multi-checkpoint collection, run artifacts, comparison and review wiring; separates current behavior from future work. |
| [Content comparison](content-comparison.md) | Reusable evidence and creative-comparison rules. |
| [Group comparison](group-comparison.md) | Reusable same-content placement-ranking and allocation rules. |
