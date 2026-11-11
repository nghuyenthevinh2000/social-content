# ADR 0001: Glasser API Transcription over Local ASR

```text
Glasser API -> Metadata + Higher-Quality Transcripts [Active]
Video Download -> Local ASR Qwen3/Whisper [Obsolete]
```

| Field | Value |
|---|---|
| ADR Number | 0001 |
| Title | Adopt Glasser.ai API transcription in place of local offline ASR |
| Status | Accepted |
| Decision Date | 2026-11-11 |
| Scope | `tools/app/backend`, `tools/loop/viral_analyzer`, Docker deployment |

| Context & Driver | Description |
|---|---|
| Transcription Quality | Glasser.ai platform captions yield significantly higher accuracy, punctuation, and Vietnamese nuance fidelity than local 0.6B ASR / Whisper inference. |
| Heavy Dependencies | Local ASR required `torch`, `transformers`, `huggingface_hub`, and `ffmpeg`, inflating image size by >2GB. |
| Operational Friction | Pre-downloading model weights (`download-models` container, HF cache) was slow and fragile in Docker environments. |
| Media Overhead | Local transcription required downloading full MP4 binaries locally, consuming high bandwidth and local disk storage. |
| Direct API Availability | Glasser.ai harvesting returns transcripts and speech text directly within the metadata JSON payload. |

| Aspect | Local Offline ASR (Deprecated) | Glasser.ai API (Adopted) |
|---|---|---|
| Output Quality | Lower accuracy on noisy audio/accents; prone to hallucinations and punctuation errors in compact local models | Superior transcription quality directly extracted from platform-level captions and speech processing |
| Architecture | Video download + local model inference | Direct API fetch with transcript extraction |
| Dependencies | `huggingface_hub`, `transformers`, `ffmpeg`, local cache | Zero local ML dependencies; lightweight REST client |
| Hardware Demands | Heavy CPU/GPU memory footprint (~2GB+ RAM) | Minimal CPU & network I/O only |
| Execution Latency | Tens of seconds per reel (download + transcribing) | Sub-second JSON retrieval per reel |
| Maintenance | Model weight drift, Docker profile maintenance | Centralized credential management (`GLASSER_API_KEY`) |

| Decision Outcome | Detail |
|---|---|
| Primary Strategy | Extract transcripts directly from Glasser.ai API responses during harvesting. |
| Quality Advantage | Leverage cleaner, higher-fidelity transcripts to boost downstream AI director prompts and viral topic extraction. |
| Backward Compatibility | Mark local transcription (`transcription.py`, `pipeline.py`, `download_models.py`) as `@deprecated [OBSOLETE]`. |
| Infrastructure Cleanup | Comment out `download-models` service in `docker-compose.yml`; preserve HF volume for backward compat. |
| Fallback Policy | If transcript is missing from API payload, proceed without transcript rather than initiating local download. |

| Component | Status | Notes |
|---|---|---|
| [`tools/app/backend/download_models.py`](file:///Users/thevinhnguyen/Documents/computer-science/projects/social-content/tools/app/backend/download_models.py#L1-L10) | Obsolete | Marked `@deprecated [OBSOLETE]`; warns on CLI invocation. |
| [`tools/app/backend/docker-compose.yml`](file:///Users/thevinhnguyen/Documents/computer-science/projects/social-content/tools/app/backend/docker-compose.yml#L109-L118) | Inactive | Service `download-models` commented out. |
| [`tools/loop/viral_analyzer/transcription.py`](file:///Users/thevinhnguyen/Documents/computer-science/projects/social-content/tools/loop/viral_analyzer/transcription.py#L3-L5) | Obsolete | Retained only for offline research fallback. |
| [`tools/app/backend/server.py`](file:///Users/thevinhnguyen/Documents/computer-science/projects/social-content/tools/app/backend/server.py) | Active | Consumes harvested transcript data directly. |
