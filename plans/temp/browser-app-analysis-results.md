# Browser-app analysis results plan

Scope: `tools/app/browser-app/src` results UI, plus the small backend contract change in `tools/app/backend` and `tools/loop/viral_analyzer`.

## Decisions (locked)

| Decision | Value |
|---|---|
| Endpoint | Keep `POST /api/jobs`; no new route |
| Job type | New job-level field `job_kind: 'profile' \| 'reel'`; one job is one kind, never mixed |
| How it is sent | Query param `?job_kind=reel`, like the existing `max_videos` / `model` options (the JSON body is converted to xlsx by `resolve_xlsx_bytes`, so extra body keys are lost) |
| Default | Missing `job_kind` means `profile` (CLI, curl, old stored jobs) |
| Rename | `media` becomes `transcribe` (query, server option, pipeline kwarg); frontend constant `isTranscribe` |
| Rendering | Frontend picks a renderer by `job.job_kind`; no URL sniffing in the UI |

## Problems this fixes

| Problem | Evidence |
|---|---|
| Results UI is inline in a 1,717-line page | `src/pages/Home.tsx:1226-1604` |
| `Sheet` and the card UI assume profile research | pools, source breakdown, "kênh", 48h warning (`Home.tsx:1384-1420`) |
| Backend guesses the job type from URLs | `research_engine/research.py:279` `is_reel_batch` |
| Reel fields are dropped | `visual` returned (`reel_research.py:765`) but missing from `Topic` (`Home.tsx:15`) |
| Profile sort applies to reels | top 10 by views (`Home.tsx:1424`) |
| `media` name hides what it does | it only enables transcription (`pipeline.py:205`) and is always `false` in the app (`Home.tsx:289`) |

## Contract

```text
Library "Chạy"        → POST /api/jobs?job_kind=profile
Saved reel "Phân tích"→ POST /api/jobs?job_kind=reel
                           ↓
create_job stores job["job_kind"] → run_job → _process_sheet branches on job_kind
                           ↓
GET /api/jobs/{id} returns job_kind → RENDERERS[job_kind]
```

| Field | Location | Values |
|---|---|---|
| `job_kind` (request) | query string of `POST /api/jobs` | `profile`, `reel`; anything else returns 400 |
| `job_kind` (response) | top level of the job JSON and `/api/jobs` summaries | same |
| `transcribe` (request) | query string, optional | `1` / `0`, default `0` |

## Backend changes

| File | Change |
|---|---|
| `tools/app/backend/server.py:796` | Replace `"media"` with `"transcribe"`; drop the deprecation comment. Add `"job_kind"` parsed from the query and validated against `{"profile", "reel"}` |
| `research_engine/research.py` `create_job` | Store `job_kind` on the job dict; include it in history summaries |
| `research_engine/research.py:279` | Replace `is_reel_batch = any(is_reel_url(...))` with `job["job_kind"] == "reel"` (pass `job_kind` into `_process_sheet`) |
| `research_engine/profile_research.py:95` | `transcribe=bool(options.get("transcribe"))` |
| `tools/loop/viral_analyzer/pipeline.py:72, 205` | Rename kwarg `media` to `transcribe` |
| `tools/app/backend/tests/test_backend.py:209, 316, 532` | Update `media=False` / `"media": False` to `transcribe` |
| Tests | Add: reel job routes to `research_single_reel`; invalid `job_kind` returns 400; missing defaults to `profile` |

## Frontend structure

```text
Home.tsx (analyzer tab) → <JobResult job onCopy />
  JobResult      header · progress · export · logs        (shared)
   └ SheetSection summary · status · error/notice          (shared)
      └ RENDERERS[job.job_kind]
         ├ profile → ProfileMeta (pools, sources, 48h hint) + TopicCard[] (top 10 by views)
         └ reel    → ReelMeta + TopicCard[] (visual, transcript; no sort)
                       └ ReelPlayer · AnalysisSections · CopyButton (shared)
```

| File | Contents |
|---|---|
| `src/analysis/types.ts` | `JobKind`, `Job` (with `job_kind?`), `Sheet`, `Topic` (with `visual?`), `JobSummary` |
| `src/analysis/format.ts` | `formatCompact`, `formatNumber`, `reelLink`, `getTopicReelUrl`, `formatTopicForAI`, `copyToClipboard`, `formatTime`, `cleanTopicTitle` moved from `Home.tsx` |
| `src/analysis/JobResult.tsx` | Results header, progress bar, sheets loop, logs; `SheetSection` in the same file |
| `src/analysis/TopicCard.tsx` | Player with video/iframe fallback, badges, foot, copy button; renders a `sections: {label, body}[]` list |
| `src/analysis/renderers.tsx` | `RENDERERS: Record<JobKind, {Meta, runningText, emptyText, sections(topic), order(topics)}>` |
| `src/analysis/analysis.css` | Results CSS moved from `Home.css` |
| `src/pages/Home.tsx` | `run(selected, filename, kind)`; library runs pass `profile`, saved-reel runs pass `reel`; `isTranscribe` constant replaces the `media` state |

Adding a future analysis type = one backend `job_kind` value, one branch in `_process_sheet`, one `RENDERERS` entry.

## Phases

| Phase | Work | Behavior change | Check |
|---|---|---|---|
| 0. Lock behavior | Vitest render tests with a profile job fixture and a saved-reel job fixture against the current `Home` | None | Tests pass before refactor |
| 1. Extract | Move types, helpers, results JSX and CSS into `src/analysis/`; rename `media` to `isTranscribe` in the frontend (query `transcribe=1` only when true) | None | Phase 0 tests, `e2e/visual.spec.ts`, stylelint pass |
| 2. Contract | Backend `job_kind` + `transcribe` rename (table above); frontend sends `?job_kind=` | Backend stops URL-sniffing | Backend tests pass, including new ones |
| 3. Renderers | Split profile and reel renderers; show `visual` for reels; profile-only text only on profile jobs | Reel results lose profile hints, gain visual section | One render test per kind; e2e `sources.spec.ts` still passes |
| 4. Cleanup | Remove now-unused code from `Home.tsx` / `Home.css` | Smaller files | `npm run lint`, `npm test`, backend tests |

## Risks

| Risk | Mitigation |
|---|---|
| Old stored saved-reel jobs have no `job_kind` and render with the profile layout | Acceptable for history; they still show topics, only the meta strip differs |
| External callers send `?media=1` | No known callers outside tests; `transcribe` replaces it with no alias |
| Profile job given a reel URL (or the reverse) | Reel path already skips non-reel URLs; the profile scraper reports an empty result as a notice |
| Visual regression during extraction | Phase 1 changes no markup or class names |

## Skipped

| Skipped | Add when |
|---|---|
| Plugin system, dynamic imports, schema-driven UI | More than about 4 job kinds |
| Server-driven `sections[]` payload | Frontend churn per new kind outweighs backend churn |
| State library | Results state is needed outside the analyzer tab |
| Transcription toggle in the UI | Product wants transcripts on profile runs (then pass `transcriber_engine="glasser"` in `profile_research.py`) |
