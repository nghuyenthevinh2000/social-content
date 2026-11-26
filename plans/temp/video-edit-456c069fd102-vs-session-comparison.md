# Comparison & Optimization Plan: `456c069fd102` vs Session Runs

| Metric / Stage | `456c069fd102` (`edit.py` + ACP) | This Session (Jobs 2 & 3) | Gap / Root Cause |
|---|---:|---:|---|
| **Total Delivery** | `8m 31s` (`511s`) | `~1m 59s` – `~2m 25s` | `456c069fd102` is **~6m slower** due to `rea-video`, ACP startup, and a 2-pass visual revision loop |
| **Pre-Decompose (`rea-video`)** | `1m 13s` (`73s`) | `0s` (`ffprobe` + 2–5 frames in `2–4s`) | `rea-video decompose` runs full shot/OCR/packaging pipeline on a `15s` source clip |
| **Startup & Audio Prep** | `0m 47s` (`47s`) | `0s` (cached `target_transcript.json`) | `ACPClient` cold start + reading `VIDEO.md`/`breakdown.json` + WAV extraction |
| **Pass 1 Edit + Render + Verify** | `4m 01s` (`241s`) | `~1m 55s` – `~2m 20s` | ACP runs `faster_whisper` + reads `effects/*.py` + authors 27 subtitles / 5 cards / 6 SFX |
| **Visual Review + Pass 2 + Upload** | `2m 30s` (`150s`: `61s` + `24s` + `65s`) | `0s` (1-pass clean layout) | Pass 1 layout needed revision, triggering full Pass 2 re-render + 6-frame re-inspection |

```text
456c069fd102 (8m 31s)  -> [Pre-Decompose 73s] [ACP Init 47s] [Pass 1 241s] [Revise+Pass2+Upload 150s]
Target (<5m: ~4m 30s)  -> [Fast Probe+ASR 12s] [ACP Init 25s] [Pass 1 180s] [1-Pass Check+Upload 50s]
```

## Optimization Plan to Hit ~5 Minutes

| Priority | Optimization | Current Cost | Target Cost | Est. Savings | Implementation |
|---|---|---:|---:|---:|---|
| **1** | **Replace `rea-video decompose` with fast pre-prep** | `1m 13s` | `~10–15s` | **~60s** | Run `ffprobe` + `faster_whisper` + 3–4 keyframes in `edit.py` before ACP starts; skip `rea-video` on short talking-head clips unless multi-shot cuts exist. |
| **2** | **Pre-compute `transcript.json` + safe-zone bounds** | `~40s` inside Pass 1 | `0s` in ACP | **~40s** | Pass `transcript.json` and `ffprobe` dimensions directly in the ACP prompt so the agent skips WAV extraction and Whisper inside Pass 1. |
| **3** | **Eliminate Pass 2 via deterministic safe-zone defaults** | `1m 25s` (`61s` + `24s`) | `0s` (most runs) | **~85s** | Enforce safe-zone presets (`y=110..1080`, `max_width=600`, `MarginV=192..210`) and `effect_editor.py --check` before Pass 1 render so Pass 1 passes inspection. |
| **4** | **Slim ACP context & reduce verify frames** | `47s` + `65s` | `~25s` + `~45s` | **~42s** | Inline `EFFECT_REGISTRY` schema summary in the prompt (skip reading `effects/*.py` and `VIDEO.md`), and extract 3–4 representative frames instead of 7 + 6. |

## Projected ~5-Minute Budget

| Stage | Optimized Actions | Target Window |
|---|---|---:|
| **1. Claim & Fast Pre-Prep** | Download source, `ffprobe`, `faster_whisper` (`transcript.json`), 3 keyframes (cached `ref-cache` hit). | `0m 15s` |
| **2. ACP Single-Pass Author & Render** | Read pre-computed `transcript.json` + compact schema, author `edit_config.json`, run `effect_editor.py` (`~4s` FFmpeg). | `3m 00s` |
| **3. Inspect & Upload** | Inspect 3–4 extracted frames + `ffprobe`, upload `output.mp4` to RustFS, mark `video_jobs` `completed`. | `0m 50s` |
| **Total Projected Delivery** | End-to-end single-pass pipeline (with ~55s buffer under `5m 00s`). | **`~4m 05s`** |
