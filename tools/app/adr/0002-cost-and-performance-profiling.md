# ADR-0002: Cost Control and Performance Profiling Architecture

```text
Request -> cost_control.cost_scope (always on, PostgreSQL cost_events)
              |-> check_call_allowed (allowlist + FB URL guard + ACTION_BUDGETS)
              |-> run_glasser_tracked / record_cost_event -> /api/costs/summary & CLI
        -> profiling.span / _ProfiledConn (opt-in via PROFILE_BACKEND=1)
              |-> --context {db,http,supervisor,worker,video,all} -> MetricsCollector
```

| Field | Decision |
|---|---|
| Status | Accepted (2026-11-16) |
| Sources | [backend-profiling-plan.md](file:///Users/thevinhnguyen/Documents/computer-science/projects/social-content/plans/temp/backend-profiling-plan.md), [cost-profiling-plan.md](file:///Users/thevinhnguyen/Documents/computer-science/projects/social-content/plans/temp/cost-profiling-plan.md) |
| Core Principle | Separate always-on financial enforcement (`cost_control.py`) from opt-in stdlib latency/SQL/RSS benchmarking (`profiling.py`). |

## 1. Context & Diagnosed Gaps

| Domain | Root Cause | Impact |
|---|---|---|
| Keyword transcript leak | `_process_sheet()` mapped 50–150 search videos into `sheet["topics"]` without `transcript`; enrichment hooks treated them as missing. | Burst `/v1/facebook/post/transcript` calls after keyword search (`RENDERERS.keyword` never uses transcripts). |
| Unguarded & uncached 400/404s | `fetch_reel_transcript()` sent YouTube/TikTok/IG URLs to `/v1/facebook/post/transcript` (`HTTP 404` = `$0.00188/call`) and fell back to `time.time()` idempotency keys. | Repeated billing on un-transcribable or non-Facebook URLs. |
| Pre-ACP transcript fan-out | `suggest_topics()` called `heuristic_topics()` before ACP, fetching up to 10–13 transcripts before final selection. | Up to 13 transcript calls when at most 3 final topics need transcripts. |
| Scattered Glasser wrappers | `video_search.py`, `viral_analyzer/glasser.py`, and `transcriber/glasser.py` discarded `proc.stdout` (`Run ID`, `Run URL`, `Charge:`). | Zero per-user or per-action Glasser spend visibility. |
| Backend bottlenecks | Synchronous enrichment in `JobStore.snapshot()`, per-request `claim_email_credits()` locks in `_user_id()`, `1+N` queries in `list_topics()`, sequential 15-call keyword search, uncached `_load_env()`/`UnifiedTranscriber`, full-RAM media reads. | High SQL/lock contention, slow worker fan-out, and RSS spikes. |

## 2. Cost Control Architecture (`tools/app/backend/cost_control.py`)

| Component | Specification | Purpose |
|---|---|---|
| Thread-safe `cost_scope` | `ContextVar` scope (`user_id`, `action`, `job_id`, `sheet_slug`) + `submit_with_context()` for `ThreadPoolExecutor`. | Attributes every worker/thread API call and cache hit to the active user and action. |
| Policy & URL guards | `check_call_allowed()`: `keyword_search` allowlist (`/v1/youtube/search`, `/videos`, `/v1/facebook/adLibrary/search/ads`, `/v1/tiktok/search/keyword`, `/v2/instagram/reels/search`); FB-only URL regex on `/v1/facebook/post/transcript`. | Hard-blocks invalid endpoints/URLs before subprocess execution (`CostPolicyError`, HTTP `403` audit row). |
| Budget circuit breakers | `ACTION_BUDGETS`: `keyword_search` (18 calls, `$0.035`), `profile_research` (3 transcripts, `$0.10`), `reel_research` (1 transcript, `$0.01`), `video_generation` (2 Omni calls). | Halts runaway loops before billing. |
| Unified runner & parser | `run_glasser_tracked()` + `parse_glasser_stdout()` (`Decimal` $\rightarrow$ `cost_micro`; flags `http_status >= 400` or `NO_RESULT` with `cost_micro > 0` as `wasted`). | Captures 100% of Glasser charges, `Run URL`s, `google_genai` video costs, and `acp` durations. |
| Leak remediation | Negative sentinel `__NO_TRANSCRIPT__` in `videos` on HTTP 400/404; deterministic `sha256` idempotency keys; `suggest_topics()` fetches once on `topics[:3]`; `research_single_reel()` guards `platform == "facebook"`. | Eliminates non-FB and repeat 400/404 charges; cuts profile/reel transcript calls 70–90%. |
| Ledger, API & CLI | PostgreSQL `cost_events` (`schema.sql`), `sheet["cost_summary"]`, `GET /api/costs/summary?days=30`, and `python3 tools/app/backend/cost_control.py --days 7`. | Queryable per-user profile, per-action, endpoint cache efficiency, and wasted-call audit tables. |

## 3. Performance Profiling Architecture (`tools/app/backend/profiling.py`)

| Component | Specification | Purpose |
|---|---|---|
| Stdlib-only profiler | Uses `time.perf_counter`, `contextvars`, `resource`, `tracemalloc`, `cProfile`, `pstats`; gated by `PROFILE_BACKEND=1` and `PROFILE_CONTEXTS`. | Zero overhead when disabled (`if not ENABLED: yield; return`); no external dependencies. |
| Isolated context modes | CLI `--context {db,http,supervisor,worker,video,all}`, `--iterations`, `--cprofile`, `--live`. | Sub-second (`<1.5s` mock) isolated subsystem benchmarks without starting full stack. |
| Hooked layers | `db.py` (`_ProfiledConn` SQL timing + `EXPLAIN`), `blobs.py` (bytes + throughput), `server.py` (`request_scope`), `handler.py` (`supervisor_tick`), `video_jobs.py`, `research_engine/`. | Outputs p50/p95/max ms, SQL count/lock wait, blob bytes, and RSS delta Markdown tables. |

## 4. Consequences & Verification

| Aspect | Detail |
|---|---|
| Tradeoffs | `cost_events` adds one `INSERT` per API/cache event (failures logged, non-fatal); `profiling.py` adds `_ProfiledConn` proxy only when `PROFILE_BACKEND=1`. |
| Verification | `./.venv/bin/pytest tools/app/backend/tests/test_cost_control.py tools/app/backend/tests/test_profiling.py` and `python3 tools/app/backend/cost_control.py --days 7`. |
| Rollback | Remove `cost_scope` / `run_glasser_tracked` wrappers; unset `PROFILE_BACKEND` to disable performance profiling immediately. |
