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
- `-d`, `--data-dir DIR`: Profile directory to diagnose; uses its recorded CDP port when set
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
- `-p`, `--port PORT`: CDP remote debugging port, or `auto` to assign a free port per profile and remember it (default: `9222`)
- `-d`, `--data-dir DIR`: Browser profile directory, one per logged-in identity (default: `$HOME/chrome-twitter-profile`)
- `--seed SEED`: Deterministic fingerprint seed for invisible browser
- `--binary PATH`: Browser engine executable
- `--headless`: Run browser in headless mode
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

### 3. Multiple browser profiles

One Chrome profile directory (`--user-data-dir`) holds one login session, so one
Facebook Page per profile means one profile directory per Page. Use `--port auto`
so each profile gets its own unused CDP port instead of all profiles contending
for `9222`:

```bash
# Page A: own profile, own port
uv run python -m tools.common start-browser --data-dir ~/chrome-page-a --port auto

# Page B: own profile, own port
uv run python -m tools.common start-browser --data-dir ~/chrome-page-b --port auto
```

| Behavior | Detail |
| --- | --- |
| Port choice | `--port auto` binds an unused loopback port on first run and writes it to `<profile>/.cdp-port`. |
| Port reuse | Later runs read that file, so a profile keeps a stable endpoint; Chrome cannot serve two processes from one profile directory. |
| Already running | If the recorded port is responsive, `start-browser` reports `"action": "reused"` and launches nothing. |
| Initial tab | A fresh profile is launched with `about:blank` so it keeps a browser context; Chrome drops to zero contexts once its first-run tab closes and CDP clients then refuse to attach. |
| Diagnostics | `doctor --data-dir DIR` targets the profile's recorded port. |
| Targeting an agent | Read `data.endpoint` from the output, or use `live_profile_endpoint(data_dir)` from Python, and pass it as the agent's `--cdp`. |
| Recorded list | Every `start-browser` run records the profile, its backend, and its port in `tools/common/local/profiles.json` (gitignored). |

```bash
uv run python -m tools.common start-browser --data-dir ~/chrome-page-a --port auto
# {"ok": true, "data": {"action": "started", "endpoint": "http://127.0.0.1:61316", "port": 61316, ...}}

uv run python -m tools.facebook_agent --cdp http://127.0.0.1:61316 post --page-id 1234567890 --text "..."
```

Agents keep their existing `--cdp` contract, so profiles stay independent and no
profile directory is shared between identities. The `invisible` backend already
isolates profiles through `--data-dir` and ignores `--port`.

### 4. Recorded profiles (`profiles`)

List the profiles this machine has used, with the port and the accounts each one
is logged into:

```bash
uv run python -m tools.common profiles
uv run python -m tools.common profiles --data-dir ~/chrome-page-a --facebook-page-id 61595289277974
```

`start-browser` records every profile it starts or reuses, so the list grows as
identities are added. Entries are keyed by the profile directory name and stored
in `tools/common/local/profiles.json`, which is gitignored because ports and
profile paths are machine-specific:

```json
{
  "profiles": {
    "chrome-twitter-profile": {
      "backend": "cdp",
      "data_dir": "/Users/user/chrome-twitter-profile",
      "identities": {
        "facebook": {"page_id": "61595289277974"},
        "linkedin": {"account": "..."},
        "twitter": {"account": "TheVinhNguyen4"}
      },
      "last_used": "2026-10-20T08:11:50Z",
      "port": 62818
    }
  }
}
```

| Key | Meaning |
| --- | --- |
| `backend`, `data_dir`, `port` | How the profile is launched and which endpoint it holds. |
| `identities.facebook` | `page_id`, ASCII digits from the Page's `profile.php?id=` URL. |
| `identities.linkedin` | `account`: the LinkedIn member or page this profile is logged into. |
| `identities.twitter` | `account`: the X handle this profile is logged into. |
| `last_used` | UTC timestamp of the last record. |

Identity fields mirror the unified post schema, so an entry maps straight onto an
agent's arguments. `identities` is optional per platform and merged field by
field, so adding one platform never clears another, and a later `start-browser`
run that only updates the port leaves the links intact.

| Flag | Effect |
| --- | --- |
| `--data-dir DIR` | Profile to record or update; required by every identity flag. |
| `--backend cdp\|invisible` | How the profile is launched (default: the configured backend). |
| `--facebook-page-id` | Link a Facebook Page by ID. |
| `--linkedin-account`, `--twitter-account` | Link the LinkedIn and X accounts. |
| `--base-dir DIR` | Point the registry elsewhere (tests use temp dirs). |

`load_registry()`, `record_profile()`, `normalize_identity()`, and
`validate_registry()` expose the same operations to Python callers. A registry
with an unknown platform or a malformed `page_id` fails closed with
`invalid_registry` instead of being listed as valid.

### 5. Unified post validation (`post`)

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
- **Profile isolation**: Each profile directory is an independent login session with its own recorded CDP port, so several social identities can run side by side.
