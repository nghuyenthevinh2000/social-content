# Standardized Viral Reels Analyzer Engine (`tools.loop.viral_analyzer`)

Standardized, end-to-end operational engine for 48-hour short-form viral video discovery, traffic pool classification, 7-day video cache retention, and Apple Silicon Metal GPU speech-to-text transcription.

---

## 1. Core Operating Contract

> **Crucial Rule:** The engine alone is the sole execution mechanism. Never write one-off crawler scripts, glue wrappers, or ad-hoc runners in `local/`. Every operation is driven from a single input config JSON file via standard module invocation.

```bash
# Standard end-to-end execution
uv run python -m tools.loop.viral_analyzer --config <path/to/config.json>

# With optional video quota ceiling (e.g., stop once 100 videos are reached)
uv run python -m tools.loop.viral_analyzer --config <path/to/config.json> --max-videos 100

# Dry-run preview without network queries or transcription
uv run python -m tools.loop.viral_analyzer --config <path/to/config.json> --dry-run
```

---

## 2. Architecture & Pipeline Sequence

```text
Config JSON -> Retention Sweep (Purge > 7d) -> Glasser v2 Ingestion (48h Window)
                    │
                    ├── 5-Pool View Classification (P1-P5)
                    ├── Direct CDN / yt-dlp Video Stream Download (< 80MB)
                    ├── 7-Day Video Retention Manifest Registration
                    ├── FFmpeg 16kHz Mono Audio Capping (180s max)
                    ├── Apple Silicon Metal GPU Qwen3-ASR (0.6B) Transcription
                    └── Database Upsert (traffic_pools.db) & Multi-Pool JSON Artifact
```

---

## 3. Configuration Reference (`config.sample.json`)

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `window_hours` | `int` | `48` | Lookback window in hours for video publication timestamps. |
| `retention_days` | `int` | `7` | Cache retention TTL in days. Expired videos are purged automatically. |
| `max_videos` | `int` | `null` | Optional stop quota. Halts additional downloads once target is reached. |
| `pools` | `dict` | Pools 1–5 | View count thresholds defining each traffic pool. |
| `storage.db_path` | `string` | `local/.../traffic_pools.db` | SQLite database destination path. |
| `storage.video_dir` | `string` | `local/.../cache/videos` | Directory for downloaded video MP4 files and manifest. |
| `storage.output_file` | `string` | `local/.../viral_reels_48h.json` | Path to output JSON summary artifact. |
| `transcription.engine` | `string` | `"qwen3"` | STT engine (`"qwen3"` or `"faster-whisper"`). |
| `transcription.model` | `string` | `"Qwen/Qwen3-ASR-0.6B"` | Model HuggingFace identifier. |
| `transcription.language` | `string` | `null` | Speech language (`null` enables native auto-detection). |
| `transcription.max_audio_duration_sec` | `int` | `180` | Maximum audio duration extracted to prevent memory spikes. |
| `glasser_provider` | `string` | `"scrapecreators"` | Glasser provider name. |
| `glasser_endpoint` | `string` | `"/v1/facebook/profile/reels"` | Glasser API endpoint (must start with `/` and use version 2). |
| `glasser_endpoint_version` | `int` | `2` | Glasser endpoint version. |
| `targets` | `list` | `[]` | List of target accounts (`handle`, `url`, `name`, `category`). |
| `creators_file` | `string` | `null` | Path to a `creators.json` file for automated candidate discovery. |

---

## 4. 5 Traffic Pools Classification

| Pool Level | Name | View Range | Typical Characteristics |
| --- | --- | --- | --- |
| **Pool 1** | `sandbox` | 0 – 500 | Newly published reels, initial testing phase. |
| **Pool 2** | `testing` | 500 – 5,000 | Algorithmic exploration, seed engagement. |
| **Pool 3** | `niche` | 5,000 – 50,000 | Community / niche traction, steady velocity. |
| **Pool 4** | `surge` | 50,000 – 500,000 | Broad algorithmic recommendation across multiple audiences. |
| **Pool 5** | `mega_breakout` | ≥ 500,000 | Viral breakout, mass reach, national-level trend. |

---

## 5. Key Operational Findings & Production Nuances

### 5.1 Speech-to-Text: Qwen3-ASR 0.6B vs. Whisper Base

- **Failure Mode:** Whisper Base (74M) severely hallucinates Vietnamese diacritics, slang, and brand terms (e.g. transcribing "đổ xăng tiện cầm" as "đủ răng tiện cơm").
- **Solution:** `Qwen/Qwen3-ASR-0.6B` running natively on Apple Silicon Metal GPU via `mlx-qwen3-asr` delivers ground-truth accuracy in ~1–2 seconds per video.
- **Language Detection:** Always set `language=None` so Qwen3-ASR's native multilingual routing detects Vietnamese without throwing unsupported language alias warnings.

### 5.2 Audio Preprocessing & OOM Prevention

- **Failure Mode:** Decoding full-length live broadcast videos (e.g. 841 MB Gala livestreams) directly in Python/PyAV causes process termination (Exit code 137 / Out of Memory).
- **Solution:** Pre-extract 16kHz mono WAV audio using FFmpeg (`-vn -ar 16000 -ac 1 -t 180`), capped at 180 seconds. Video streaming downloads are capped at 80 MB.

### 5.3 7-Day Video Retention TTL

- **Manifest:** Video files are registered in `cache/videos/retention_manifest.json` with an explicit `expires_at = downloaded_at + 7 days`.
- **Automated Sweep:** [`purge_expired_videos()`](retention.py) runs on every engine launch, removing physical video files exceeding 7 days while keeping transcripts and analytics permanently in SQLite.

### 5.4 Glasser Ingestion & Direct CDN Streaming

- **Endpoint:** Glasser provider `scrapecreators` endpoint `/v1/facebook/profile/reels` with `--endpoint-version 2`.
- **Direct CDN Streaming:** Many Glasser records provide direct Facebook CDN `video_url` (`https://video-*.xx.fbcdn.net/...`). The engine streams directly over HTTP chunking, downloading clips in 1–2 seconds without invoking external CLI subprocesses. `yt-dlp` is used strictly as a fallback.
- **Transcript Cache Reuse:** Before extracting audio, the engine checks `traffic_pools.db` for existing transcripts. If already transcribed, GPU computation is skipped immediately.
