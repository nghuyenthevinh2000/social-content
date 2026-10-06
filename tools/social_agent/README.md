---
name: social_agent
summary: Shared platform-independent browser diagnostics, invisible stealth engine, and browser startup foundation for social content publishing tools.
tags: [tools, automation, social-content, cdp, browser, invisible-playwright, stealth]
submodules:
  __init__.py: Social agent shared package.
  __main__.py: Module CLI entry point.
  cli.py: Shared CLI exposing doctor and start-browser commands.
  config.py: Shared endpoint, timeout, browser binary, port, profile, and backend configuration.
  browser.py: Platform-independent invisible stealth browser and CDP connection with safe disconnection.
  doctor.py: Browser and connectivity diagnostics without platform navigation.
  launcher.py: Browser process detection, startup, and readiness check.
  tests/: Unit tests for browser lifecycle, diagnostics, startup, and CLI.
---

# Shared Social Agent Foundation

`tools/social_agent` provides a platform-independent foundation for browser automation tools in this repository. It owns browser diagnostics, browser startup, and stealth automation backed by [`tools/invisible_playwright_mcp`](../invisible_playwright_mcp).

Platform-specific publishing, DOM selectors, authentication, and pacing remain in their respective platform tools (`facebook_agent`, `linkedin_agent`, `twitter_agent`).

## Backends

1. **`invisible` (Default)**: Anti-detect stealth browser powered by `invisible-playwright` / `invisible_playwright_mcp`. Eliminates bot detection, captchas, and tracking using humanized cursor movement, typing pauses, and deterministic identity seeds (`--seed`).
2. **`cdp`**: Connects to an existing Chrome/Chromium instance running with `--remote-debugging-port` over Chrome DevTools Protocol.

Switch backends via `--backend invisible|cdp` or environment variable `BROWSER_BACKEND=invisible|cdp`.

## CLI Commands

### 1. Browser Diagnostics (`doctor`)

Check browser availability and context readiness without navigating to any social website or altering open tabs:

```bash
uv run python -m tools.social_agent doctor
```

Options:
- `-b`, `--backend BACKEND`: Browser backend (`invisible` or `cdp`, default: `invisible` or env `BROWSER_BACKEND`)
- `--seed SEED`: Deterministic fingerprint seed for invisible browser
- `--binary PATH`: Custom browser engine binary
- `--headless`: Run browser in headless mode
- `--cdp`, `--endpoint`: Chrome CDP endpoint (default: `http://127.0.0.1:9222` or env `CDP_ENDPOINT`)
- `--timeout-ms`: Connection timeout in milliseconds (default: `30000` or env `DEFAULT_DOCTOR_TIMEOUT_MS`)

Output (invisible):
```json
{
  "ok": true,
  "data": {
    "connected": true,
    "backend": "invisible",
    "browser_version": "invisible-firefox/0.27.0",
    "user_data_dir": "/Users/user/chrome-twitter-profile",
    "seed": 42,
    "context_count": 1
  }
}
```

Output (cdp):
```json
{
  "ok": true,
  "data": {
    "connected": true,
    "endpoint": "http://127.0.0.1:9222",
    "browser_version": "Chrome/133.0.6943.98",
    "context_count": 1
  }
}
```

### 2. Browser Startup (`start-browser`)

Initialize the invisible stealth browser profile or detect/start a responsive CDP browser:

```bash
uv run python -m tools.social_agent start-browser
```

Options:
- `-b`, `--backend BACKEND`: Browser backend (`invisible` or `cdp`, default: `invisible`)
- `-d`, `--data-dir DIR`: Browser profile directory (default: `$HOME/chrome-twitter-profile`)
- `--seed SEED`: Deterministic fingerprint seed for invisible browser
- `--binary PATH`: Browser engine executable
- `--headless`: Run browser in headless mode
- `-p`, `--port PORT`: CDP remote debugging port (default: `9222`)
- `--timeout SECONDS`: Readiness timeout in seconds (default: `15.0`)
- `--chrome-bin PATH`: Path to Chromium/Chrome executable (default: auto-detected or env `CHROME_BIN`)

Output (invisible):
```json
{
  "ok": true,
  "data": {
    "action": "ready",
    "backend": "invisible",
    "user_data_dir": "/Users/user/chrome-twitter-profile",
    "seed": null,
    "headless": false,
    "binary_path": null,
    "engine_status": "invisible engine ready"
  }
}
```

## Guarantees

- **Anti-bot stealth**: Employs `invisible_playwright_mcp` stealth stack against automated detection.
- **User tab preservation**: Diagnostic and launcher operations never close user tabs, browser contexts, or running browser processes.
- **Safe client disconnection**: Detaching Playwright stops the client connection without closing the user's browser.
- **Loopback binding**: Debugging and local endpoints are explicitly bound to loopback (`127.0.0.1`).
- **Profile stability**: Preserves persistent profiles across runs to retain existing login sessions.
