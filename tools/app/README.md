# AIBrand — Excel → viral research → 3 topics per sheet

| Question | Answer |
|---|---|
| What it does | Reads every sheet of an Excel spy file, runs the 48h viral pipeline for that sheet's Facebook channels, then asks an ACP agent harness for exactly 3 viral topics. |
| App | Tauri v2 desktop window (React frontend + Rust shell). |
| Backend | Python API server bundled as a Tauri sidecar with PyInstaller; no Python install needed. |
| Runs on | macOS (Apple Silicon) and Windows 10/11, local only (`127.0.0.1`). No cloud upload. |
| Output | Per-sheet topic cards in the window, plus platform-specific `AIBrand/runs/<job>/sheets/<sheet>/result.json`. |

```text
Excel sheets ──> parse Facebook links ──> pipeline.py per sheet
                                              │
                    ┌─────────────────────────┼─────────────────────────┐
                    ▼                         ▼                         ▼
              Glasser 48h reels       5 traffic pools          video + transcript
                    └─────────────────────────┼─────────────────────────┘
                                              ▼
                                   ACP agent harness
                          (agy / OpenCode / Claude / Codex)
                                              ▼
                                    3 viral topics / sheet
```

## Run

| Step | Command |
|---|---|
| **Build the app** | `cd tools/app && npm run tauri build` |
| **Open the app (macOS)** | Double-click `tools/app/AIBrand.app` (symlink to the Tauri bundle). |
| Build output (macOS) | `tools/app/src-tauri/target/release/bundle/macos/AIBrand.app` |
| DMG | `tools/app/src-tauri/target/release/bundle/dmg/AIBrand_0.1.0_aarch64.dmg` |
| Dev with hot reload | `cd tools/app && npm run tauri dev` |
| Rebuild sidecar only | `cd tools/app && npm run build:sidecar` |
| Backend tests | `python3 -m unittest tools.app.test_backend -v` |
| App log (macOS) | `~/Library/Logs/AIBrand.log` |

## Windows build

| Step | Command / requirement |
|---|---|
| Prerequisites | Node 20+, Rust stable MSVC, `uv`, WebView2 (built into Windows 10/11), Visual Studio Build Tools. |
| Install | `cd tools/app && npm ci` |
| Build | `npm run tauri build` |
| Sidecar | `build_sidecar.mjs` creates `src-tauri\binaries\viral-server-x86_64-pc-windows-msvc.exe`. |
| Installers | `src-tauri\target\release\bundle\msi\*.msi` and `...\nsis\*-setup.exe`. |
| Log | `%LOCALAPPDATA%\AIBrand\logs\aibrand.log` |
| Data | `%LOCALAPPDATA%\AIBrand\runs` |
| CI | `.github/workflows/release-app.yml` builds macOS (DMG, ZIP) + Windows (MSI, NSIS) and creates GitHub releases on the `releases` branch. |

| Packaging detail | Behaviour |
|---|---|
| Sidecar | `src-tauri/binaries/viral-server-<target-triple>[.exe]` is built by `build_sidecar.mjs`; Tauri starts it on a free local port. |
| Rust bridge | `api_base` command gives the WebView the sidecar URL; all API calls use that base. |
| Lifecycle | Closing the window or quitting kills the sidecar; the sidecar also exits if the Tauri process disappears. |
| Frontend | Loaded from `frontendDist`; no browser window and no separate web server for the UI. |
| Data (macOS) | `~/Library/Application Support/AIBrand/runs`; dev server mode keeps `local/app-runs/`. |
| PATH | The sidecar augments PATH with Homebrew / Windows npm / `~/.local/bin` / `~/.opencode/bin` / Cargo / Volta / Bun / nvm locations before detecting harnesses. |
| Gatekeeper | Built locally, so it opens normally. A distributed copy needs signing/notarisation. |

## Options

| UI option | Default | Effect |
|---|---:|---|
| Harness ACP | `VIRAL_APP_AGENT` env (`agy`, `opencode`, `claude`, `codex`); unset = first installed | Backend-only config for the agent that writes the 3 topics. If it is not logged in, the app falls back to data-driven suggestions. |
| Video tối đa / sheet | `5` | Caps downloads per sheet. `0` means no cap. |
| Tải video + transcribe | on | Runs download + speech-to-text. If ASR is not installed, the pipeline continues without transcripts. |

## ACP harnesses

| Harness | Command | Login check |
|---|---|---|
| Antigravity | `agy acp` | `agy` |
| OpenCode | `opencode acp` | `opencode auth login` |
| Claude Code | `npx -y @zed-industries/claude-code-acp` | `claude` |
| Codex | `npx -y @zed-industries/codex-acp` | `codex login` |

| ACP detail | Behaviour |
|---|---|
| Transport | JSON-RPC 2.0 over stdio, newline-delimited. |
| Flow | `initialize` → `session/new` → `session/prompt`. |
| Permissions | Client auto-approves `allow_once`; agents should only need to read the prompt. |
| Failure mode | ACP failure is logged, the sheet still gets 3 fallback topics, and the job continues. |

## Costs and limits

| Limit | Note |
|---|---|
| Glasser calls | One paid profile-reels call per unique channel per job; duplicate channels reuse the job cache. |
| Time | An 18-sheet file with 5 videos/sheet can take tens of minutes. Polling UI stays live. |
| Storage | Videos, JSON and databases live under the platform data directory and are not committed. |
| Transcription (macOS) | Qwen3-ASR 0.6B via `mlx-qwen3-asr`; first run downloads the model from HuggingFace. |
| Transcription (Windows) | Qwen3-ASR 0.6B via `transformers` + PyTorch CPU/CUDA; first run downloads the model. CPU is slower but works offline afterwards. |
| FFmpeg | Uses system `ffmpeg` when present, otherwise the bundled `imageio-ffmpeg` binary. |

## Files

| Path | Purpose |
|---|---|
| `tools/app/server.py` | Python API server, bundled as the Tauri sidecar. |
| `tools/app/backend/research.py` | Excel parsing, per-sheet jobs, topic prompt/parse/fallback. |
| `tools/app/backend/acp.py` | Minimal ACP stdio client. |
| `tools/app/src/api.ts` | Resolves the sidecar URL inside Tauri; relative `/api` in browser dev. |
| `tools/app/src/App.tsx` | Upload, harness picker, progress, topic cards. |
| `tools/app/src-tauri/src/lib.rs` | Starts/kills the sidecar and exposes `api_base`. |
| `tools/app/src-tauri/tauri.conf.json` | Tauri window, bundle and `externalBin` config. |
| `tools/app/build_sidecar.sh` | Builds `src-tauri/binaries/viral-server-<triple>`. |
| `tools/loop/viral_analyzer/pipeline.py` | Reused pipeline; accepts `cache_dir`, `media`, `progress_cb`. |
