# ADR-0004: Client-Side Video Edit Rendering Architecture

```text
Browser / Mobile Web
  ├─ WebCodecs unsupported ─► POST /api/videos/edit (server FFmpeg fallback, max 2)
  └─ WebCodecs supported   ─► videoDecompose (VAD + cuts + 16kHz WAV + 3 JPGs)
                                  └─► POST /api/videos/edit-plan (plan pool, max 8)
                                         └─► Local ASR (Qwen3-ASR) + speech-segment alignment
                                                └─► GET /api/videos/<id>/plan
                                                       └─► WebCodecs + Canvas2D + SFX mix (mediabunny)
                                                              └─► POST /api/videos/<id>/file -> RustFS/S3
```

| Field | Decision |
|---|---|
| Status | Accepted (2026-11-27) |
| Core Principle | Split AI edit planning + local ASR (server, I/O & lightweight inference) from video decoding, effect compositing, SFX mixing, and H.264 encoding (client browser via WebCodecs + Canvas2D + `mediabunny`). |
| Scope | `tools/app/backend/` (`video_engine/edit.py`, `video_engine/jobs.py`, `server.py`, `telemetry/bench_video_edit.py`) and `tools/app/browser-app/src/` (`analysis/videoDecompose.ts`, `videoClientRender.ts`, `videoEditDraft.ts`, `components/VideoTab.tsx`). |

## 1. Context & Benchmark Evidence

| Metric / Observation | Measured Value (Intel i3-10110U, 2C/4T, 31 GiB RAM, No GPU) | Implication |
|---|---|---|
| `effect_editor.py` (`N=1` → `N=2`) | `16.38s` (`3.66 vid/min`) → `29.56s` (`4.06 vid/min`) | CPU saturates at **2** concurrent renders. |
| `effect_editor.py` (`N=4` → `N=8`) | `58.80s` (`4.08 vid/min`, load `16.3`) → `119.18s` (`4.03 vid/min`, load `45.9`) | Flat throughput; linear latency degradation. |
| Full `edit_video()` E2E (`N=1` → `N=2`) | `93.41s` (`0.64 vid/min`) → `107.58s` (`1.12 vid/min`) | Server-side rendering caps at `DEFAULT_MAX_GLOBAL_JOBS = 2`. |
| Memory usage (`N=8` renders) | `+5,361 MiB` RAM delta | RAM is ample; 2C/4T CPU is the sole bottleneck. |

## 2. Decision & Architecture

| Layer | Component | Responsibility |
|---|---|---|
| Capability gate | `canRenderVideoOnClient()` | Checks `VideoDecoder` + `VideoEncoder.isConfigSupported()` (`avc1.42001f`). Unsupported WebViews fall back to `POST /api/videos/edit`. |
| Client decompose & pre-prep | `videoDecompose.ts` + `probeAndExtractKeyframes()` | Extracts `{width, height, duration, fps}`, 3 JPEG frames, 16 kHz mono PCM WAV (`audio_b64`), adaptive RMS VAD `speech_segments`, and visual `cuts` locally; eliminates raw MP4 upload. |
| Server ASR & planner | `plan_edit_video()`, `_transcribe_client_audio()`, `POST /api/videos/edit-plan` | Runs local ASR (`UnifiedTranscriber` / `Qwen/Qwen3-ASR-0.6B-hf`, swappable via `VIDEO_ASR_ENGINE`), aligns text to `speech_segments`, and runs ACP planner in a separate `edit_plan` pool (`DEFAULT_MAX_PLAN_JOBS = 8`, `VIDEO_MAX_PLAN_JOBS`) with zero DB schema changes. |
| Client renderer & store | `renderVideoEditPlan()` (`mediabunny`) | Fetches `GET /api/videos/<id>/plan`, composites `effects[]` (`color_grade`, `punch_zoom`, `transition`, `text_box` incl. `table`/`info.tag`/`highlight_lines`, `subtitles`) on Canvas2D, mixes synthesized `sfx` (`pop`/`ding`/`whoosh`), HW-encodes MP4, and uploads final MP4 via `POST /api/videos/<id>/file` to RustFS/S3 (IndexedDB fallback on upload error). |

## 3. Alternatives, Verification & Rollback

| Aspect | Detail |
|---|---|
| Alternatives rejected | `ffmpeg.wasm` (30–90s+ CPU encode, COOP/COEP header requirement, iOS Safari OOM risk); client-side `Qwen3-ASR-0.6B-hf` (~400 MB+ download & ~0.6–1.2 GB RAM causes mobile tab OOM); native Capacitor plugin deferred until PWA WebCodecs gaps require it. |
| Verification | `.venv/bin/pytest tools/app/backend/tests/test_video_edit_engine.py tools/app/backend/tests/test_video_jobs.py tools/app/backend/tests/test_server_video_routes.py -v` (18 passed) and `npm --prefix tools/app/browser-app run test:unit && npm --prefix tools/app/browser-app run build` (8 test files passed). |
| Rollback | Route all requests to `POST /api/videos/edit` on the frontend or set `VIDEO_MAX_PLAN_JOBS=0`; server-side `edit_video()` remains intact. |
