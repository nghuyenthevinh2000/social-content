# Viral Video Search Plan

```text
Keyword ("gyno conditions") -> Expand <=3 terms [orig, abbr, VI] -> Search 5 platforms x 3 terms -> Normalize videos + creators -> UI "+ Thêm Kênh" / "+ Lưu Video"
```

## 1. Architecture & Reuse

| Area | Decision | Reused from repo / `local/social-listening-test` |
|---|---|---|
| Engine module | Add `tools/app/backend/research_engine/video_search.py` and export `run_viral_video_search`, `expand_keyword` in `research_engine/__init__.py`. | Mirrors `profile_research.py` + `reel_research.py` module boundaries. |
| Job contract | Extend `job_kind` to `'profile' \| 'reel' \| 'keyword'` on `POST /api/jobs?job_kind=keyword`. Sheet name = input keyword. | Reuses `STORE`, `create_job`, `run_job`, `_process_sheet`, and `plans/temp/browser-app-analysis-results.md`. |
| Keyword expansion | `expand_keyword(keyword)` returns at most 3 exact queries: `[original, abbreviation, vietnamese_translation]`, deduplicated. Uses ACP agent with deterministic fallback dictionary/heuristics. | Reuses `_harness_lock`, `resolve_agent`, and `ACPClient` in `research_engine/research.py`. |
| Glasser execution | Run `glasser run` per `(platform, query)` with disk cache under `run_dir / "cache"` and `ErrorAggregator` handling. | Reuses `ensure_glasser_env`, `check_glasser_key`, and subprocess/error patterns from `tools/loop/viral_analyzer/glasser.py`. |
| URL & platform detection | Add `detect_platform(url)` and `social_handle(url)` supporting `youtube`, `google`, `facebook`, `tiktok`, `instagram` so non-Facebook creator URLs are not rewritten to `facebook.com`. | Reuses `detect_platform` from `local/social-listening-test/extractor.py` and extends `facebook_handle` in `tools/app/backend/profiles.py`. |
| Save to library | Creators save to `topics`/`profiles` via existing `POST /api/sources/topics`. Videos save to `saved_reels` via new `POST /api/saved-reels` handler. | Reuses `PROFILE_STORE.add_profile` and existing `saved_reels` table in `tools/app/backend/schema.sql`. |

## 2. Keyword Expansion & 5-Platform Search Matrix

| Step / Platform | Provider & Endpoint | Exact Query Input (3 queries max) | Output Normalized Fields | Price / Call |
|---|---|---|---|---|
| 0. Expand keyword | ACP (`agy` / fallback) | Input `"gyno conditions"` $\rightarrow$ `["gyno conditions", "gynecomastia", "nữ hóa tuyến vú"]` (1 original + 1 abbreviation/synonym + 1 Vietnamese translation = max 3). | `queries: [{kind: "original" \| "abbreviation" \| "vi", text: str}]` | $0.00 |
| 1. YouTube | `scrapecreators` `/v1/youtube/search` (v4) | `{"query": f"\"{q}\"", "sortBy": "popular"}` | `video_id`, `title`, `url`, `views`, `author_name`, `author_handle`, `author_url`, `platform="youtube"` | $0.00188 |
| 2. Google Video | `serper` `/videos` (v2) | `{"q": f"\"{q}\"", "gl": "vn", "hl": "vi"}` | `video_id`, `title`, `url`, `duration`, `author_name` (channel/source), `author_url`, `platform="google"` | $0.00100 |
| 3. Facebook | `serper` `/videos` (v2) + `scrapecreators` `/v1/facebook/adLibrary/search/ads` (v4) | Serper `{"q": f"site:facebook.com \"{q}\"", "gl": "vn", "hl": "vi"}` + ScrapeCreators `{"query": q, "media_type": "VIDEO", "search_type": "keyword_exact_phrase"}` | `video_id`, `title`, `url`, `video_url`, `author_name`, `author_url`, `platform="facebook"` | $0.00100–$0.00188 |
| 4. TikTok | `scrapecreators` `/v1/tiktok/search/keyword` (v4) | `{"query": q, "sort_by": "most-liked", "trim": true}` | `video_id`, `title`, `url`, `views`, `likes`, `comments`, `shares`, `author_handle`, `author_url`, `platform="tiktok"` | $0.00188 |
| 5. Instagram | `scrapecreators` `/v2/instagram/reels/search` (v4) | `{"query": q}` | `video_id`, `title`, `url`, `video_url`, `views`, `likes`, `comments`, `author_handle`, `author_url`, `platform="instagram"` | $0.00188 |

## 3. File-by-File Implementation Tasks

| File | Planned Changes |
|---|---|
| `tools/app/backend/research_engine/video_search.py` | Implement `expand_keyword(keyword, agent_id, model, cwd, log)` returning $\le 3$ terms; `search_platform(platform, query, cache_dir, log)`; `run_viral_video_search(keyword, run_dir, options, log, job_id)` returning `{queries, reels, creators, source_breakdown, error, notice, errors}`. |
| `tools/app/backend/research_engine/__init__.py` | Export `expand_keyword` and `run_viral_video_search`. |
| `tools/app/backend/research_engine/research.py` | Allow `job_kind == "keyword"` in `create_job` and `_process_sheet`. Store `queries`, `creators`, `reels`, and map each video into `topics` with `platform`, `matched_query`, `author_name`, `author_handle`, `author_url`, `reel_url`, `views`, `likes`. |
| `tools/app/backend/profiles.py` | Add `detect_platform(url)` and `social_handle(url)` so `SocialProfileStore.add_profile` and `upsert_topic` preserve YouTube, TikTok, Instagram, Google, and Facebook profile URLs instead of forcing `facebook.com`. |
| `tools/app/backend/server.py` | Accept `job_kind="keyword"` in `_create_job`. Add `POST /api/saved-reels` to let users save any discovered video (`reel_url`, `platform`, `title`/`sender_name`) into `saved_reels`. |
| `tools/app/browser-app/src/analysis/types.ts` | Extend `JobKind` with `'keyword'`. Add optional `platform`, `author_url`, `matched_query` on `Topic`, and `queries`, `creators` on `Sheet`. |
| `tools/app/browser-app/src/analysis/renderers.tsx` | Add `RENDERERS.keyword`: render expanded keyword chips (`Original`, `Abbr`, `VI`), platform counts, creator pills with `+ Thêm Kênh`, and video cards sorted by views. |
| `tools/app/browser-app/src/analysis/TopicCard.tsx` | Support non-Facebook external links (`YouTube ↗`, `TikTok ↗`, `Instagram ↗`, `Google ↗`, `Facebook ↗`) and optional action buttons: `+ Thêm Kênh` (saves creator to `topics`) and `+ Lưu Video` (saves video to `saved_reels`). |
| `tools/app/browser-app/src/pages/Home.tsx` | Add keyword search form in `Thư viện` tab (`input` + `Tìm Video Viral` button) calling `run([{name: kw, slug: kw, targets: [{name: kw, url: kw}]}], kw, 'keyword')`; wire `onAddCreator` (`POST /api/sources/topics`) and `onSaveVideo` (`POST /api/saved-reels`). |

## 4. Verification & `"gyno conditions"` Test Plan

| Phase | Test / Command | Pass Condition |
|---|---|---|
| 1. Unit tests (Backend) | `pytest tools/app/backend/tests/test_backend.py -k "keyword or viral_video_search"` | `expand_keyword("gyno conditions")` returns 3 exact strings (`"gyno conditions"`, `"gynecomastia"`, `"nữ hóa tuyến vú"`); `run_viral_video_search` queries at most $3 \times 5$ endpoints, deduplicates URLs, extracts creators; `POST /api/saved-reels` and `POST /api/sources/topics` persist non-FB URLs. |
| 2. Unit tests (Frontend) | `cd tools/app/browser-app && npm test -- AnalysisResults` | `JobResult` with `job_kind: "keyword"` renders the 3 expanded queries, creator list, platform badges, and triggers `/api/sources/topics` and `/api/saved-reels` on click. |
| 3. Live Glasser test (`"gyno conditions"`) | Run `run_viral_video_search("gyno conditions", ...)` with Glasser task `tsk_3f4103850fec7f5c` (max 15 calls $\approx \$0.026$). | Returns real videos & creators across YouTube, Google Video, Facebook, TikTok, and Instagram for `"gyno conditions"`, its abbreviation, and Vietnamese translation; logs charge and Run URLs. |
