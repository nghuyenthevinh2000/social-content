# Viral Analyzer Engine

```text
Shared Core: platforms | normalize | runtime | glasser | cache
                               ↓
<domain>_research/: __init__ + __main__ + config + collect + pipeline
  ├── profile_research/  (48h creator crawls & P1–P5 traffic pools)
  ├── video_research/    (reel visuals, topics, 7d retention, transcriber/)
  └── keyword_research/  (5-platform keyword search & campaign/)
                               ↓
tools/app/backend/research_engine/ (research.py imports canonical pipelines directly)
```

## Standardized Package Layout

| Module / Package | Role | Key Exports & Responsibilities |
|---|---|---|
| `tools/loop/viral_analyzer/__init__.py`, `__main__.py` | Root facade & default CLI | PEP 562 lazy exports (zero eager `psycopg` import); routes default CLI to `profile_research` |
| `platforms.py` | Platform registry core | Pure-stdlib `PlatformSpec`, `PLATFORMS_REGISTRY` (`facebook`, `youtube`, `tiktok`, `instagram`, `google`), `register_platform()`, URL/ID/handle/transcript routing |
| `normalize.py` | Payload normalizers | Pure-stdlib `parse_int`, `first_int`, `parse_compact_count`, `extract_metric` (`None`-preserving), `raw_media_items`, per-platform profile & search normalizers |
| `runtime.py` | High-throughput primitives | `EngineContext` (`max_workers`, `submit_fn`, pluggable `agent_runner`), `SingleFlight`, shared `BoundedSemaphore` (`VIRAL_GLASSER_MAX_CONCURRENCY=8`), `unique_temp_path`, `atomic_write_json` |
| `glasser.py` | Shared Glasser client | Env/key checks, unified failure classifier, `execute_glasser_query()`, `run_glasser_json()` with single-flight + semaphore + atomic cache |
| `cache.py` | Centralized DB cache | Lazy-DB `profile_cache` (reels & batch followers), `videos` transcripts, batched `persist_to_database()` (3 SQL calls/run) |
| `profiling.py` | Opt-in profiler & bench | Stdlib `span()` instrumentation (`PROFILE_VIRAL_ANALYZER=1`), `profile_callable()` (`cProfile` + `tracemalloc`), and 6-context isolated benchmarks (`core`, `profile`, `video`, `keyword`, `concurrency`, `cache`) |
| `profile_research/` | Profile & pool engine | 48h creator scraper, P1–P5 classification (`0..500`, `500..5k`, `5k..50k`, `50k..500k`, `>=500k`), parallel target fan-out (`ViralAnalyzerConfig` defaults) |
| `video_research/` | Video & transcript engine | Single-reel research, frame extraction, topic & director prompts, `fcntl.flock` 7-day retention manifest, `transcriber/` (`glasser`, `local` Qwen3-ASR 0.6B/Whisper) |
| `keyword_research/` | Keyword & hashtag engine | Parallel 5-platform `search`, follower enrichment, and `campaign/` (`generate`, `verify`, `scrape`) gated hashtag workflow |

## Standardized 5-File Engine Contract

| File | Shared Contract Across Every `<domain>_research/` Package |
|---|---|
| `__init__.py` | Public domain facade exporting types and `run_*` entrypoints |
| `__main__.py` | Standalone CLI (`python3 -m tools.loop.viral_analyzer.<domain>_research`) |
| `config.py` | Pure-stdlib domain settings, schemas, prompt templates, constants |
| `collect.py` | External acquisition & caching (Glasser/HTTP/download + `SingleFlight` / `flock`) |
| `pipeline.py` | Parallel orchestration, scoring/analysis, persistence (`sys.modules` backend shim target) |
| Submodule *(optional)* | Present only for multi-stage/backend internals (`video_research/transcriber/`, `keyword_research/campaign/`) |

## CLI Entrypoints & Backend Integration

| Entrypoint | Command | Behavior |
|---|---|---|
| Profile pipeline | `python3 -m tools.loop.viral_analyzer.profile_research [--config <JSON>] [--target <URL>] [--max-videos N] [--dry-run]` | Retention sweep (`>7d`), parallel 48h target crawl, transcription (`local` or `glasser`), batched DB + atomic JSON write |
| Video pipeline | `python3 -m tools.loop.viral_analyzer.video_research --url <URL> [--sheet-name <S>] [--agent <ID>]` | Direct single-reel transcript, visual frame analysis (capped 80 MB stream / 180s audio), and topic generation |
| Keyword search | `python3 -m tools.loop.viral_analyzer.keyword_research search --keyword <KW> [--platforms p1,p2] [--run-dir DIR]` | Keyword expansion (`<=3` queries) + parallel search across registered platforms (`youtube`, `google`, `facebook`, `tiktok`, `instagram`) |
| Hashtag campaign CLI | `python3 -m tools.loop.viral_analyzer.keyword_research <build-prompt\|import-response\|plan\|collect\|report\|build-review-prompt\|record-review\|history\|scrape>` | Offline prompt build/import, preview-first bounded probes, locked `hashtag-performance.json` history, `promising`/`limited_expand`-gated `scrape` |
| Backend integration | `tools/app/backend/research_engine/research.py` | Imports `profile_research`, `video_research`, and `keyword_research` pipelines directly; fans out multi-reel jobs concurrently |
| Engine benchmark CLI | `python3 -m tools.loop.viral_analyzer.profiling --context all --iterations 5 --cprofile` | Benchmarks `core`, `profile`, `video`, `keyword`, `concurrency`, and `_test` DB `cache` operations with p50/p95/max latency and RSS delta |

## Extensibility & Verification

| Task | Procedure | Check Command |
|---|---|---|
| Add a social platform | Call `platforms.register_platform(PlatformSpec(...))` with domains, `reel_patterns`, query specs, and `normalize` helpers | `python3 -m unittest discover -s tools/loop/tests -p 'test_viral_*.py'` |
| Add `<new>_research/` domain | Create the 5 standard files (`__init__`, `__main__`, `config`, `collect`, `pipeline`) reusing `runtime`, `platforms`, `normalize`, `glasser`, `cache`; register lazy export in `__init__.py` | `python3 -m tools.loop.viral_analyzer.<new>_research --help` |
| Swap LLM runner or tune concurrency | Pass `EngineContext(max_workers=..., agent_runner=...)` or set `VIRAL_MAX_WORKERS` / `VIRAL_GLASSER_MAX_CONCURRENCY` | `.venv/bin/python -m pytest tools/app/backend/tests/test_cost_control.py tools/app/backend/tests/test_backend.py` |
| Hashtag regression suite | Offline prompt, collection, review, locking, and expansion gate coverage (no `psycopg` required) | `python3 -m unittest discover -s tools/loop/tests -p 'test_hashtag_*.py'` |
| Opt-in stage spans | Set `PROFILE_VIRAL_ANALYZER=1` and `PROFILE_VIRAL_CONTEXTS=all\|profile,video,keyword,cache` | `python3 -m unittest discover -s tools/loop/tests -p 'test_viral_*.py'` |
