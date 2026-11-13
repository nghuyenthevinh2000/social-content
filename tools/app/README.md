# Tools App

## Architecture

```text
Library (Topics, Imports, DM Reels) -> Analyzer (P1-P5, Transcripts, Prompts) -> Video (Media, Credits, Render)
```

| Layer | Role | Stack |
|---|---|---|
| [`backend/`](./backend/) | API server, job queues, research engine, video generation, DM sync | Python 3.12+, ThreadingHTTPServer, PostgreSQL/SQLite, S3 blobs, Docker |
| [`browser-app/`](./browser-app/) | Mobile-first web and hybrid app (4 tabs: Library, Analyzer, Video, Profile) | Ionic React, TypeScript, Vite, Capacitor, Firebase Auth |
| [`adr/`](./adr/) | Architecture Decision Records | Markdown |

## Features

| Area | Feature | Details |
|---|---|---|
| Library (`Thư viện`) | Topic & channel management | Create/delete topics and add/remove Facebook creator URLs (`/api/sources/topics`, `/api/sources/profiles/delete`). |
| Library (`Thư viện`) | Spreadsheet import | Upload `.xlsx`/`.xlsm`/`.xls` or paste Google Sheets URLs; each sheet becomes a topic (`/api/sources/parse`). |
| Library (`Thư viện`) | Curated creator packs | Built-in preset creator lists (e.g., Top 50 Creators in `creatorPacks.ts`). |
| Library (`Thư viện`) | Saved Reels via DM sync | 24/7 Meta Graph API v27.0 Page DM polling (`dm_service.py`) captures shared Reels into user libraries (`/api/saved-reels`). |
| Analyzer (`Phân tích`) | Batch & single-topic jobs | Run viral research on one or all topics with background polling, cancel, delete, and export (`/api/jobs`). |
| Analyzer (`Phân tích`) | Profile traffic-pool scoring | Crawls competitor channels, tracks views/velocity/engagement, and classifies reels into P1–P5 pools (`profile_research.py`). |
| Analyzer (`Phân tích`) | Reel & transcript analysis | Fetches transcripts (Glasser/ASR), analyzes 9:16 UGC pacing, explains "Why Viral" triggers, and generates Director Prompts via ACP (`reel_research.py`, `acp.py`). |
| Analyzer (`Phân tích`) | Results & AI prompt export | Structured topic cards, job history, and one-click "Copy cho AI" script/prompt export (`JobResult.tsx`). |
| Video (`Tạo Video`) | Reference-to-video generation | Generates short AI videos (default 15s) from a prompt, required profile face image, and optional context images (`video_engine.py`). |
| Video (`Tạo Video`) | Credits & cost estimation | Pre-flight micro-USD cost estimation (`/api/videos/estimate`), balance checks, and credit ledger (`/api/credits`). |
| Video (`Tạo Video`) | Concurrency & recovery | Global and per-user job limits, crash recovery, status polling, cancellation, in-app playback, and download (`/api/videos`). |
| Profile (`Hồ sơ`) | Authentication & linking | Firebase Email/Password and Facebook OAuth (`AuthModal.tsx`), plus Facebook Page DM linking/unlinking (`/api/facebook/*`). |
| Profile (`Hồ sơ`) | Actor & media management | Configure actor gender, age, name, and Vietnamese voice tone (`Bắc`/`Trung`/`Nam`); upload/delete JPEG/PNG/WEBP images up to 10MB (`/api/media`, `/api/user/profile`). |
| Onboarding & Ops | Guided tour & diagnostics | 4-tab interactive tour (`Tour.tsx`), health checks (`/api/health`), server/client logs (`/api/logs`), and graceful shutdown (`/api/shutdown`). |

## Architecture Decision Records

| ADR | Title | Status |
|---|---|---|
| [`0001`](./adr/0001-use-glasser-api-transcription-over-local-asr.md) | Adopt Glasser.ai API transcription in place of local offline ASR | Accepted |

## Running

```bash
python3 tools/app/backend/server.py --port 8765
docker compose -f tools/app/backend/docker-compose.yml up -d
cd tools/app/browser-app && npm run dev
```
