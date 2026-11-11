# Tools App

Agnostic backend with multi-client applications.

## Directory Structure

| Directory | Purpose | Tech Stack |
|---|---|---|
| [`backend/`](./backend/) | Shared, client-agnostic API server, SQLite job queue, and viral research worker | Python 3.12+, ThreadingHTTPServer, Docker |
| [`desktop-app/`](./desktop-app/) | Native desktop application for macOS and Windows | Tauri v2, React 19, TypeScript, Vite |
| [`browser-app/`](./browser-app/) | Mobile-first browser application with native iOS & Android feel | Ionic Framework 8, React, TypeScript, Vite, Capacitor |
| [`adr/`](./adr/) | Architecture Decision Records for application design choices | Markdown |

## Architecture Decision Records (ADRs)

| ADR | Title | Status |
|---|---|---|
| [`0001`](./adr/0001-use-glasser-api-transcription-over-local-asr.md) | Adopt Glasser.ai API transcription in place of local offline ASR | Accepted |

## Running the Backend

```bash
# Direct Python execution
python3 tools/app/backend/server.py --port 8765

# Or via Docker
docker compose -f tools/app/backend/docker-compose.yml up -d
```

## Running the Frontends

```bash
# Desktop App (Tauri)
cd tools/app/desktop-app && npm run tauri dev

# Browser App (Ionic)
cd tools/app/browser-app && npm run dev
# or: ionic serve
```
