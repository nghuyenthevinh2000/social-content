---
name: social_agent
summary: Shared platform-independent browser CDP diagnostics and browser startup foundation for social content publishing tools.
tags: [tools, automation, social-content, cdp, browser]
submodules:
  __init__.py: Social agent shared package.
  __main__.py: Module CLI entry point.
  cli.py: Shared CLI exposing doctor and start-browser commands.
  config.py: Shared endpoint, timeout, browser binary, port, and profile configuration.
  browser.py: Platform-independent CDP connection and safe disconnection.
  doctor.py: Browser and CDP diagnostics without platform navigation.
  launcher.py: Browser process detection, startup, and readiness check.
  tests/: Unit tests for browser lifecycle, diagnostics, startup, and CLI.
---

# Shared Social Agent Foundation

`tools/social_agent` provides a platform-independent foundation for browser automation tools in this repository. It owns browser DevTools Protocol (CDP) diagnostics and browser startup.

Platform-specific publishing, DOM selectors, authentication, and pacing are intentionally kept out of this package and remain in their respective platform tools.

## CLI Commands

### 1. Browser Diagnostics (`doctor`)

Check CDP connectivity and verify that Chrome has an active browser context without navigating to any social website or altering open tabs:

```bash
uv run python -m tools.social_agent doctor
```

Options:
- `--cdp`, `--endpoint`: Existing Chrome CDP endpoint (default: `http://127.0.0.1:9222` or env `CDP_ENDPOINT`)
- `--timeout-ms`: Connection timeout in milliseconds (default: `30000` or env `DEFAULT_DOCTOR_TIMEOUT_MS`)

Output:
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

Detect an existing responsive CDP browser or start one with the configured profile and remote debugging port:

```bash
uv run python -m tools.social_agent start-browser
```

Options:
- `-p`, `--port PORT`: CDP remote debugging port (default: `9222`)
- `-d`, `--data-dir DIR`: Chrome user data directory (default: `$HOME/chrome-twitter-profile`)
- `--timeout SECONDS`: Readiness timeout in seconds (default: `15.0`)
- `--chrome-bin PATH`: Path to Chromium/Chrome executable (default: auto-detected or env `CHROME_BIN`)

Output:
```json
{
  "ok": true,
  "data": {
    "action": "reused",
    "endpoint": "http://127.0.0.1:9222",
    "port": 9222,
    "user_data_dir": "/Users/user/chrome-twitter-profile"
  }
}
```

## Guarantees

- **User tab preservation**: Diagnostic and launcher operations never close user tabs, browser contexts, or running browser processes.
- **Safe client disconnection**: Detaching Playwright stops the client connection without sending `browser.close()` to the user's browser.
- **Loopback binding**: Chrome debugging is explicitly bound to loopback (`127.0.0.1`).
- **Profile stability**: Preserves `$HOME/chrome-twitter-profile` by default to retain existing login sessions across platforms.
