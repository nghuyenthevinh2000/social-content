# Viral Analyzer Consolidation & High-Throughput Plan

```text
Shared Core: platforms | normalize | runtime | glasser | cache
                              ↓
<domain>_research/ = __init__ + __main__ + config + collect + pipeline (+ optional submodule)
  ├── profile_research/  (config.sample.json)
  ├── video_research/    (transcriber/)
  ├── keyword_research/  (campaign/)
  └── <future>_research/ (plug-in engine)
                              ↓
       backend/research_engine/ (research.py + 3 pipeline shims)
```

## 1. Duplication & Bottleneck Audit

| # | Current Defect / Duplication | Exact Locations | Unified Root Fix |
|---|---|---|---|
| 1 | Social URL, platform, handle & video ID parsing duplicated 4×; fallback URL builder duplicated 5× | `tools/facebook_agent/dm_crawl/crawler.py`, `tools/app/backend/profiles.py`, `tools/app/backend/research_engine/reel_research.py`, `tools/loop/viral_analyzer/{pipeline,cache,viral_scrape,transcriber/glasser}.py` | Single pure-stdlib `tools/loop/viral_analyzer/platforms.py` (`PlatformSpec` registry + URL/handle/fallback helpers); delete local copies from `profiles.py` and `crawler.py` |
| 2 | Platform item normalizers & metric parsers duplicated 4×; hardcoded `if platform == ...` switches across 6+ files | `glasser.py` (`_normalize_profile_reels`), `keyword_search.py` (`_normalize_*`), `hashtag_verify.py` (`extract_media`), `viral_scrape.py` (`raw_items`/`_candidate`), `transcriber/glasser.py` | Single pure-stdlib `tools/loop/viral_analyzer/normalize.py` bound into `PlatformSpec`; preserves `None` metrics for `scrape.py` and `0`-default ints for `search.py`/`profile_research` |
| 3 | Glasser CLI execution & failure classification duplicated 3×; upward coupling into `tools.app.backend` | `glasser.py`, `keyword_search.py`, `hashtag_verify.py` | Single failure classifier & runner (`execute_glasser_query`, `run_glasser_json`) in `glasser.py` using `runtime.py` semaphore, atomic I/O, and lazy cost hook; `verify.py` keeps stdlib `run_provider` |
| 4 | `profile_cache` SQL duplicated 3×; `3N` per-reel SQL loop in `persist_to_database`; `DB_POOL_MAX=2` vs 5 threads | `cache.py`, `keyword_search.py`, `tools/app/backend/handler.py` | Batch `executemany` + single `SELECT DISTINCT ON` in `cache.py`; add `read_cached_followers`/`write_cached_followers`; lazy DB imports (no `psycopg` crash on system `python3`); default worker `DB_POOL_MAX=5` |
| 5 | Temp/cache file collisions & unlocked `retention_manifest.json` under parallel workers | `glasser.py:569`, `transcriber/glasser.py:131`, `reel_research.py:681`, `keyword_search.py:299`, `retention.py:52-62` | Unique PID/TID/UUID temp files + atomic `os.replace` cache writes in `runtime.py`; `fcntl.flock` around `retention_manifest.json` in `video_research/collect.py`; isolated per-call video temp paths |
| 6 | Asymmetric module layouts across engines, serial hot loops, cache stampedes, global `_harness_lock` coupling | `pipeline.py:212`, `research.py:175,429`, 14 flat files in `viral_analyzer/` + 4 engine files in `research_engine/` | Identical 5-file contract in every `<domain>_research/` package; bounded `ThreadPoolExecutor` + `SingleFlight` + pluggable `EngineContext`; `backend/research_engine/` keeps only `research.py` + 3 three-line `pipeline` aliases |

## 2. Standardized Engine Contract

| Standard File | Universal Role (Every `<domain>_research/` Package) | `profile_research/` | `video_research/` | `keyword_research/` |
|---|---|---|---|---|
| `__init__.py` | Public API facade exporting domain entrypoints & types | `run_profile_research`, `run_analyzer_pipeline`, `fetch_target_reels`, `classify_pool`, `load_config`, `ViralAnalyzerConfig` | `research_single_reel`, `research_reels`, `suggest_topics`, `heuristic_topics`, `download_video_stream`, retention & transcriber APIs | `run_viral_video_search`, `expand_keyword`, `search_platform`, campaign `build_prompt`..`scrape` & history helpers |
| `__main__.py` | Standardized CLI (`python3 -m tools.loop.viral_analyzer.<domain>_research`) | `--config`, `--dry-run`, `--limit-targets`, `--max-videos`, `--transcriber` | `--url`, `--sheet-name`, `--agent`, `--model`, `--timeout` | Unified 10-command CLI (`search`, `build-prompt`, `import-response`, `plan`, `collect`, `report`, `build-review-prompt`, `record-review`, `history`, `scrape`) |
| `config.py` | Pure-stdlib domain config, constants, schemas, prompt templates | `PoolDefinition`, `DEFAULT_POOLS`, `StorageConfig`, `TranscriptionConfig`, `ViralAnalyzerConfig`, `load_config` (+ `config.sample.json`) | `TEMP_DIR`, `VISUAL_PROMPT`, `build_topic_prompt`, `format_director_prompt` | `PLATFORMS`, `_FALLBACK_EXPANSIONS`, `Problems`, `HistoryConflict`, campaign context/history/redaction/report primitives (`hashtag_common.py`) |
| `collect.py` | External acquisition & caching (Glasser/HTTP/media/download + `SingleFlight`) | `_resolve_profile_query`, `fetch_target_reels` (via `platforms.py`, `normalize.py`, `SingleFlight`) | `download_video_stream`, `_download_reel_video`, `_extract_video_frames`, `fcntl.flock` 7-day retention manifest (`load_manifest`, `register_video`, `purge_expired_videos`) | `expand_keyword`, `_glasser_run_json`, `search_platform`, `_fetch_public_followers`, `_enrich_creator_followers` (via `platforms.py`, `normalize.py`, `cache.py`, `SingleFlight`) |
| `pipeline.py` | Core orchestration, parallel fan-out, analysis, persistence & `run_*` entrypoints (canonical target of backend shims) | `classify_pool`, parallel 48h `run_analyzer_pipeline`, `run_profile_research`, CLI `main` | `analyze_video_visuals`, `suggest_topics`, `heuristic_topics`, `parse_topics`, `normalize_topics`, `_transcribe_local_fallback`, `research_single_reel`, `research_reels` | Parallel 5-platform `run_viral_video_search`, creator aggregation, search CLI runner, re-exports `_glasser_run_json` & campaign pipeline entrypoints |
| Optional submodule | Multi-backend or multi-stage internals only when needed (no empty stubs) | *(none — `config.sample.json` only)* | `transcriber/` (`__init__.py`, `glasser.py`, `local.py`, `download_models.py`) | `campaign/` (`__init__.py`, `generate.py`, `verify.py`, `scrape.py`) |

## 3. Target Package Layout

| Module / Package | Ownership | Extension Point / Replaced Files |
|---|---|---|
| `tools/loop/viral_analyzer/__init__.py`, `__main__.py` | PEP 562 lazy exports (zero eager `psycopg` import); default CLI routes to `profile_research.pipeline:main` | Register future `<x>_research` packages without startup cost |
| `tools/loop/viral_analyzer/platforms.py` | Pure-stdlib `PlatformSpec` dataclass + `PLATFORMS_REGISTRY` (`facebook`, `youtube`, `tiktok`, `instagram`, `google`) + `register_platform()` + URL/handle/video-ID/fallback/transcript routing | Adding a new platform (Threads, X, Douyin) = 1 `register_platform(PlatformSpec(...))` call; deletes duplicate URL/handle code from `profiles.py` & `dm_crawl/crawler.py` |
| `tools/loop/viral_analyzer/normalize.py` | Pure-stdlib `parse_int`, `first_int`, `parse_compact_count`, `extract_metric` (`None`-preserving), `dig`, `unwrap_item`, `raw_media_items`, per-platform profile & search normalizers | Plugged into `PlatformSpec`; deletes duplicated normalizers from `glasser.py`, `keyword_search.py`, `viral_scrape.py` |
| `tools/loop/viral_analyzer/runtime.py` | Pure-stdlib `EngineContext`, `unique_temp_path`, `atomic_write_json`, `SingleFlight`, shared `BoundedSemaphore` (`VIRAL_GLASSER_MAX_CONCURRENCY=8`), context-propagating `submit_fn`, pluggable `agent_runner` | Swap ACP CLI (`_harness_lock`) for parallel API LLM callers or tune concurrency via env/context |
| `tools/loop/viral_analyzer/glasser.py` | Glasser errors, env/key/status checks, single `_classify_glasser_failure()`, `execute_glasser_query()`, `run_glasser_json()` with semaphore + atomic I/O | Profile scraping moved to `profile_research/collect.py`; `_glasser_run_json` body deleted from `keyword_search.py` |
| `tools/loop/viral_analyzer/cache.py` | Lazy-DB PostgreSQL cache: profile reels, batch follower counts, transcripts, batched `persist_to_database()` | Centralizes all SQL; deletes follower SQL from `keyword_search.py` |
| `tools/app/backend/research_engine/` | `research.py` (app job runner, parallel multi-reel dispatch, ACP lock, blobs, `STORE`) + `__init__.py` + 3 symmetric three-line `sys.modules[__name__] = _impl` aliases (`profile_research` → `profile_research.pipeline`, `reel_research` → `video_research.pipeline`, `keyword_search` → `keyword_research.pipeline`) | 0 duplicated engine lines in backend; preserves all existing imports, `mock.patch` targets, and `profiling.py` hooks |

## 4. Parallel Execution & Concurrency Design

| Mechanism | Concrete Implementation | Known Ceiling & Upgrade Path (`ponytail:`) |
|---|---|---|
| Atomic temp & cache files | `unique_temp_path(prefix, suffix)` (`pid_tid_uuid8`) for every Glasser/transcript/video download; `atomic_write_json` via sibling temp + `os.replace` | Safe across threads & processes on local POSIX FS; move cache to Redis/Postgres if multi-node workers share disk |
| Retention manifest lock | `fcntl.flock(LOCK_EX)` on `retention_manifest.lock` around `register_video` and `purge_expired_videos` in `video_research/collect.py` | Local-host multi-process safe; switch to DB-tracked media leases if shared object store replaces local disk |
| In-process `SingleFlight` | Per-key `threading.Lock` in `runtime.py` wrapping cache-miss Glasser fetches in `profile_research/collect.py`, `keyword_research/collect.py`, and `video_research/transcriber/glasser.py` | Prevents duplicate billing within one worker process; upgrade to `pg_advisory_xact_lock(hashtext(key))` if cross-worker stampedes become measurable |
| Bounded Glasser fan-out | Process-wide `BoundedSemaphore(VIRAL_GLASSER_MAX_CONCURRENCY=8)` inside `glasser.py` + `video_research/transcriber/glasser.py` | Caps concurrent Node CLI spawns per worker; add token-bucket rate limiter if upstream 429s appear |
| Parallel target & reel workers | `ThreadPoolExecutor(max_workers=ctx.max_workers)` with `ctx.submit_fn` (`cost_control.submit_with_context`) in `profile_research/pipeline.py` (channels) and `research.py` (`job_kind=="reel"` when >1 target) | Preserves deterministic output ordering and per-job cost/budget scopes |
| Batched DB writes & pool sizing | 3 batched SQL calls per run in `cache.persist_to_database()`; `os.environ.setdefault("DB_POOL_MAX", "5")` in `handler.py` | Eliminates `3N` round-trips and 5-thread / 2-connection pool contention |
| Pluggable `agent_runner` | `EngineContext.agent_runner` defaults to backend ACP + `_harness_lock` when omitted, decoupling core engines from the single global Postgres advisory lock | Drop-in parallel direct-API LLM runner later without modifying `video_research` or `keyword_research` |

## 5. Execution Steps

| Step | Files Touched | Exact Changes |
|---|---|---|
| 1. Shared core & callers | `tools/loop/viral_analyzer/{platforms,normalize,runtime,glasser,cache}.py`; `tools/app/backend/{profiles.py,handler.py,docker-compose.yml}`; `tools/facebook_agent/dm_crawl/crawler.py` | Build `platforms.py`, `normalize.py`, `runtime.py`; unify Glasser runner/classifier with atomic I/O + semaphore in `glasser.py`; batch SQL + follower cache + lazy DB in `cache.py`; deduplicate `profiles.py` & `crawler.py` via `platforms.py`; set worker `DB_POOL_MAX` default to `5` in `handler.py`; mount `../../loop:/app/tools/loop` in `dm-service` |
| 2. `profile_research/` | `tools/loop/viral_analyzer/profile_research/{__init__,__main__,config,collect,pipeline}.py`, `config.sample.json` | Implement standard 5 files: `config.py` (config dataclasses + sample), `collect.py` (profile scraping via `platforms.py` + `normalize.py` + `SingleFlight`), `pipeline.py` (parallel 5-pool pipeline + `run_profile_research` + CLI; fix `parents[3]` path) |
| 3. `video_research/` | `tools/loop/viral_analyzer/video_research/{__init__,__main__,config,collect,pipeline}.py`, `transcriber/` | Implement standard 5 files + `transcriber/`: `config.py` (prompts & `TEMP_DIR`), `collect.py` (stream download, isolated temp path, frame extract, `fcntl.flock` 7d retention), `pipeline.py` (reel analysis, visuals, topics, exposing `_download_reel_video`/`fetch_reel_transcript`/`ACPClient` for shims), `transcriber/` (lazy `cost_control`, `platforms.py`, unique temp files, semaphore + `SingleFlight`) |
| 4. `keyword_research/` | `tools/loop/viral_analyzer/keyword_research/{__init__,__main__,config,collect,pipeline}.py`, `campaign/{__init__,generate,verify,scrape}.py` | Implement standard 5 files + `campaign/`: `config.py` (`hashtag_common.py` + `PLATFORMS` + `dedup_queries`), `collect.py` (keyword expansion, `_glasser_run_json`, `search_platform`, follower enrichment via shared core), `pipeline.py` (parallel `run_viral_video_search` forwarding `_glasser_run_json` + campaign entrypoints), `campaign/` (`generate`, `verify`, `scrape`), unified 10-command `__main__.py` |
| 5. Root cleanup & backend shims | `tools/loop/viral_analyzer/{__init__,__main__}.py`; delete 10 legacy root files/dir; `tools/app/backend/research_engine/{profile_research,reel_research,keyword_search,research,__init__}.py`; `tools/app/backend/server.py` | Add PEP 562 lazy `__getattr__` in `viral_analyzer/__init__.py`; delete old flat files & `transcriber/`; replace backend engine files with 3 symmetric `sys.modules` aliases to `*.pipeline`; parallelize multi-reel loop in `research.py`; update `server.py` transcriber import |
| 6. Migrate tests, skills & docs | `tools/loop/tests/test_{viral_pipeline,hashtag_generate,hashtag_verify,viral_scrape}.py`; `tools/app/backend/tests/test_{backend,cost_control}.py`; `.agents/skills/social-campaign/{SKILL.md,references/hashtag-validation.md,references/viral-analyzer.md}`; `tools/{README.md,loop/README.md,loop/viral_analyzer/README.md,app/README.md,app/desktop-app/README.md}` | Migrate direct imports/patches & CLI docs; document standardized 5-file blueprint in `viral_analyzer/README.md`; keep `research_engine` test mocks untouched to verify shims; add concurrency, `register_platform`, unified CLI, standardized-layout & shim-identity tests in `test_viral_pipeline.py` |

## 6. Risks & Verification

| Check / Risk | Command or Verification | Pass Condition |
|---|---|---|
| Stdlib isolation (no `psycopg`) | `python3 -m unittest discover -s tools/loop/tests -p 'test_hashtag_*.py'` and `-p 'test_viral_*.py'` | All 40 hashtag tests + viral/concurrency/extensibility tests pass on both system `python3` and `.venv/bin/python` |
| Standardized structure contract | Assert all 3 engines contain `{__init__,__main__,config,collect,pipeline}.py` and export public entrypoints | Verified programmatically in `test_viral_pipeline.py` |
| Parallel safety & single-flight | Concurrency tests in `test_viral_pipeline.py` (parallel `register_video` + `SingleFlight` dedup + duplicate-target pipeline crawl) | Zero manifest loss, single upstream call on concurrent identical keys, deterministic output order |
| Unified CLI smoke check | `python3 -m tools.loop.viral_analyzer{,.profile_research,.video_research,.keyword_research} --help` | All exit 0; `keyword_research --help` exposes all 10 subcommands |
| Backend, cost-control & DM regression | `.venv/bin/python -m pytest tools/app/backend/tests/test_cost_control.py tools/app/backend/tests/test_dm_service.py -q` and `test_backend.py -k "not resolve_xlsx_bytes" -q` | 0 regressions (3 `resolve_xlsx_bytes` tests are pre-existing failures on `HEAD`) |
| `mock.patch` & `profiling.py` compatibility | All 3 shims alias `<domain>_research.pipeline`; `keyword_search._glasser_run_json` and `reel_research.*` patches forward cleanly | All existing `mock.patch("tools.app.backend.research_engine...")` and `profiling.py` hooks pass unchanged |
| Dangling refs & net deletion | `git grep -n "viral_analyzer\.\(hashtag_\|viral_scrape\|pipeline\|config\|retention\|video_download\|transcriber\)" -- tools/ .agents/` + `git diff --stat` | 0 hits outside historical `tools/app/adr/`; net line reduction across `tools/` |
