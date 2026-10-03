# Platform Constraints & CLI Reference Matrix

This reference document outlines the exact technical specifications, input validations, CLI invocations, and error handling for the three social automation tools in `tools/`.

---

## 1. Feature & Constraint Comparison

| Parameter / Constraint | Facebook (`tools/facebook_agent`) | LinkedIn (`tools/linkedin_agent`) | Twitter / X (`tools/twitter_agent`) |
| :--- | :--- | :--- | :--- |
| **Directory** | `tools/facebook_agent/` | `tools/linkedin_agent/` | `tools/twitter_agent/` |
| **Account Type** | Personal Profile only (`/me`) | Personal Profile only | Specific handle (`--account`) |
| **Page / Group Support** | No (rejected by DOM check) | No (Company pages unsupported) | N/A |
| **Text Requirement** | Non-empty text required | Non-blank text required | Non-empty text required |
| **Text Character Limit** | Facebook post limit | Max 3,000 characters | 280 characters (standard) |
| **Multiline Support** | Supported via bash `$'line1\nline2'` | Supported (preserves CRLF/LF) | Supported |
| **Image Requirement** | **Optional**: 0 or 1 image | **Mandatory**: 1 to 20 images | **Mandatory** for `publish.py`: 1 image |
| **Allowed Image Formats** | PNG, JPEG, GIF, WebP | PNG, JPEG only | JPEG, PNG, GIF, WebP (photo upload) |
| **Image Size Limit** | Checked by Facebook upload UI | Max 10 MiB per file | Standard Twitter limits |
| **Text-Only Posts** | **Supported** | **UNSUPPORTED** (Tool errors if no image) | Supported via `reply` (not standalone `publish`) |
| **Multi-Image Posts** | Unsupported (Max 1) | **Supported** (1–20 ordered images) | Unsupported in `publish.py` (Max 1 photo) |
| **Video Support** | Unsupported | Unsupported | Unsupported |
| **Audience Control** | Inherited from Facebook composer | Inherited from LinkedIn composer | Public / Account visibility |
| **Approval Protocol** | Immediate on `post` invocation | Immediate on `post` invocation | Explicit `--approved` flag required |
| **Submission Pacing** | No automated rate limit | No automated rate limit | 6/hr, 20/24hr, 120s interval, 3/30m burst |
| **Exit Code 4 (Uncertain)** | Composer tab kept open | Page preserved in browser context | DB event recorded, lock preserved |

---

## 2. Command Line Invocation Syntax

### Shared Browser Setup
```bash
# Launch Chrome with dedicated social profile and CDP on port 9222
uv run python -m tools.social_agent start-browser
```

### Pre-Flight Doctor Checks
```bash
# Facebook
uv run python -m tools.facebook_agent doctor

# LinkedIn
uv run python -m tools.linkedin_agent doctor

# Twitter / X
uv run python -m tools.twitter_agent doctor
```

### Publishing Commands

#### Facebook (`tools/facebook_agent`)
```bash
# Text-only
uv run python -m tools.facebook_agent post \
  --text "This is the approved Facebook update."

# Text + 1 Image
uv run python -m tools.facebook_agent post \
  --text "This is the approved caption." \
  --image "/absolute/path/to/image.png"

# Custom timeout and CDP endpoint (global flags precede subcommand)
uv run python -m tools.facebook_agent --cdp http://127.0.0.1:9222 --timeout-ms 20000 post \
  --text "Custom endpoint post"
```

#### LinkedIn (`tools/linkedin_agent`)
```bash
# Single image post (image is required!)
uv run python -m tools.linkedin_agent post \
  --text "Already-approved LinkedIn post." \
  --image "/absolute/path/to/slide-1.png"

# Multi-image post (1-20 images, preserves specified order)
uv run python -m tools.linkedin_agent post \
  --text "Already-approved carousel summary." \
  --image "/absolute/path/to/slide-1.png" \
  --image "/absolute/path/to/slide-2.png" \
  --image "/absolute/path/to/slide-3.png"

# Custom timeout (global flags precede subcommand)
uv run python -m tools.linkedin_agent --timeout-ms 30000 post \
  --text "Post with 30s timeout" \
  --image "/absolute/path/to/slide-1.png"
```

#### Twitter / X (`tools/twitter_agent`)
```bash
# Standalone Image Post (requires --approved)
uv run python -m tools.twitter_agent.publish \
  --account TheVinhNguyen4 \
  --text "Punchy tweet text under 280 chars" \
  --image "/absolute/path/to/image.png" \
  --approved

# Engagement / Reply Guy Workflow
uv run python -m tools.twitter_agent search "LLM evaluation" --limit 5 --window-minutes 60
uv run python -m tools.twitter_agent thread 1840000000000000000
uv run python -m tools.twitter_agent reply target 1840000000000000000
uv run python -m tools.twitter_agent reply draft DRAFT_ID --text "Substantive reply"
uv run python -m tools.twitter_agent reply submit DRAFT_ID
```

---

## 3. Exit Codes & JSON Payloads

All three tools produce JSON on stdout:

### Success Payloads (Exit Code 0)
- **Facebook**:
  ```json
  {"ok": true, "data": {"status": "confirmed", "audience": "Public"}}
  ```
- **LinkedIn**:
  ```json
  {"ok": true, "data": {"status": "posted", "url": null}}
  ```
- **Twitter Publish**:
  ```json
  {"ok": true, "data": {"state": "submitted", "url": "https://x.com/i/status/184..."}}
  ```

### Error Payloads (Exit Codes 1, 2, 3, 4)
```json
{
  "ok": false,
  "error": {
    "code": "submission_uncertain",
    "message": "Submission may have completed. Inspect LinkedIn manually before retrying.",
    "human_action_required": true
  }
}
```

### Exit Code Definitions:
- **0**: Success.
- **1**: Unexpected internal error.
- **2**: Invalid input parameters (arguments, character limits, bad image format).
- **3**: Browser connectivity or authentication failure (login required, challenge detected).
- **4**: Uncertain submission — DOM submit clicked, but confirmation was not received within timeout. **DO NOT RETRY AUTOMATICALLY.**
