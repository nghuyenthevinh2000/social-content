---
name: common
summary: Shared platform-independent browser diagnostics, invisible stealth engine, and browser startup foundation for social content publishing tools.
tags: [tools, automation, social-content, cdp, browser, invisible-playwright, stealth]
submodules:
  __init__.py: Social agent shared package.
  __main__.py: Module CLI entry point.
  cli.py: Shared CLI exposing doctor, start-browser, and post (dry-run) commands.
  cli_support.py: Shared JSON output and argument-parser helpers; exit policies remain platform-local.
  errors.py: Canonical structured agent error with compatibility re-exports in platform models.
  groups.py: Canonical sharing-group validation and nine-group limit.
  config.py: Shared endpoint, timeout, browser binary, port, profile, and backend configuration.
  browser.py: Platform-independent invisible stealth browser and CDP connection with safe disconnection.
  doctor.py: Browser and connectivity diagnostics without platform navigation.
  launcher.py: Browser process detection, startup, and readiness check.
  post.py: Unified platform-agnostic post schema, validation, and per-platform argument adapters.
  samples/: Example input files (unified post, group list, and facebook_agent message plan).
  tests/: Unit tests for browser lifecycle, diagnostics, startup, CLI, and the unified post format.
---

# Shared Social Agent Foundation

`tools/common` provides a platform-independent foundation for browser automation tools in this repository. It owns browser diagnostics, browser startup, and stealth automation backed by [`tools/invisible_playwright_mcp`](../invisible_playwright_mcp), plus the shared posting format described below.

Platform-specific publishing, DOM selectors, authentication, and pacing remain in their respective platform tools (`facebook_agent`, `linkedin_agent`, `twitter_agent`).

## Backends

1. **`invisible` (Default)**: Anti-detect stealth browser powered by `invisible-playwright` / `invisible_playwright_mcp`. Eliminates bot detection, captchas, and tracking using humanized cursor movement, typing pauses, and deterministic identity seeds (`--seed`).
2. **`cdp`**: Connects to an existing Chrome/Chromium instance running with `--remote-debugging-port` over Chrome DevTools Protocol.

Switch backends via `--backend invisible|cdp` or environment variable `BROWSER_BACKEND=invisible|cdp`.

## CLI Commands

### 1. Browser Diagnostics (`doctor`)

Check browser availability and context readiness without navigating to any social website or altering open tabs:

```bash
uv run python -m tools.common doctor
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
uv run python -m tools.common start-browser
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

### 3. Unified post validation (`post`)

Validate a single platform-agnostic post document and print the resolved
per-platform plans and equivalent commands. This never connects to a browser or
posts anything:

```bash
uv run python -m tools.common post tools/common/samples/post.json
uv run python -m tools.common post tools/common/samples/post.json --platform twitter
```

## Unified posting format

One JSON document records approved content once and resolves it into each
posting agent's arguments, so a post authored for one platform can be reused on
the others. See [`samples/post.json`](./samples/post.json) for a complete
example and [`post.py`](./post.py) for the schema and validation.

| Field | Meaning |
| --- | --- |
| `id`, `title` | Optional labels for reporting. |
| `content.text` | Required shared caption; every platform inherits it. |
| `content.images` | Shared image paths, resolved relative to the post file. |
| `content.video` | Optional single video path (Facebook only). |
| `posting_groups` | Exact Facebook group names to also share to (max 9). |
| `platforms` | Required map of `facebook`, `linkedin`, and/or `twitter` blocks. |

Each platform block enables that platform (unless `"enabled": false`) and may
override `text`, `images`, or `video`. A present key replaces the shared value:
`"images": []` clears inherited media, and `"video": null` clears an inherited
video. Platform-specific keys:

- **facebook**: `profile` (`personal` or `page`), `page_name`, `page_id`, and a
  `posting_groups` override. At most one image or one video.
- **linkedin**: 1–20 images, no video. Text up to 3,000 characters.
- **twitter**: `account` (required) and `approved` (default `false`). Exactly one
  image, no video. Text up to 280 characters.

Per-platform length and media limits are enforced at load time, so a shared
caption that is too long for X must be shortened in its `platforms.twitter.text`
override. `load_post()` returns a `Post` whose `for_platform(name)` gives
`arguments()` (matching each agent's publish function) and `command()` (the
equivalent `uv run` invocation).

## Guarantees

- **Anti-bot stealth**: Employs `invisible_playwright_mcp` stealth stack against automated detection.
- **User tab preservation**: Diagnostic and launcher operations never close user tabs, browser contexts, or running browser processes.
- **Safe client disconnection**: Detaching Playwright stops the client connection without closing the user's browser.
- **Loopback binding**: Debugging and local endpoints are explicitly bound to loopback (`127.0.0.1`).
- **Profile stability**: Preserves persistent profiles across runs to retain existing login sessions.
