---
name: facebook_agent
summary: Direct DOM publishing of approved text and an optional image to a personal Facebook profile, with exact content checks and restored attachment rejection, using the shared Chrome Twitter profile.
tags: [facebook, playwright, cdp, publishing]
submodules:
  tests/: Offline DOM fixture, validation, CLI, and browser lifecycle tests.
  __init__.py: Facebook agent package.
  __main__.py: Module entry point.
  models.py: Content validation and structured errors.
  dom.py: Feature-by-feature English DOM identifiers and locator functions.
  selectors.py: Visibility, uniqueness, and account challenge checks.
  browser.py: Existing Chrome CDP connection and tab lifecycle.
  posting.py: Personal-profile and attachment checks with single-click DOM publishing.
  cli.py: Doctor and direct post commands with JSON output.
---

# Facebook personal-profile agent

Design: [`2026-10-02-facebook-agent-design.md`](../../../../docs/superpowers/specs/2026-10-02-facebook-agent-design.md).
Implementation plan: [`2026-10-02-facebook-agent.md`](../../../../docs/superpowers/plans/2026-10-02-facebook-agent.md).

Publish **already-approved** text and one optional image through a visible
Facebook composer. No supervisor, draft queue, or approval prompt. Invoking
`post` authorizes immediate publication; do not invoke it to preview content.

## Setup

From `projects/social-content`:

```bash
uv sync
uv run python -m tools.social_agent start-browser
```

The browser startup uses the shared `$HOME/chrome-twitter-profile` and CDP port
`9222`. If that Chrome is already running, it is reused. **Manually log into
Facebook in that same Chrome window.** Your X login is unaffected. Do not launch
two Chrome processes with the same profile or run X and Facebook write operations
concurrently.

Use Facebook's English-language interface for this initial version.

```bash
# Read-only: verifies CDP, login, own-profile controls, and profile identity.
uv run python -m tools.facebook_agent doctor

# Publishes immediately, without prompting.
uv run python -m tools.facebook_agent post --text "Your approved text"

uv run python -m tools.facebook_agent post \
  --text "Your approved caption" \
  --image "/absolute/path/photo.png"

# Optional connection and per-stage timeout overrides, before the command.
uv run python -m tools.facebook_agent --cdp http://127.0.0.1:9222 \
  --timeout-ms 20000 doctor
```

Text is passed unchanged; links can appear in the text. For multiline text in
bash/zsh, use `--text $'First line\nSecond line'`. Nonempty text is required;
image-only posts, multiple images, videos, scheduling, Pages, and Groups are not
supported. Image validation checks PNG/JPEG/GIF/WebP file signatures; Facebook
still decides whether the actual file can be uploaded.

## Publishing behavior

1. Open a new visible tab and navigate through Facebook `/me`.
2. Verify own-profile Edit profile controls and name; reject Page-management UI.
3. Open Create post, check posting identity and read the existing audience.
   Reject restored attachments rather than merging them with this request.
4. Fill the exact text; attach the optional image and wait for its removal control
   and an enabled Post button.
5. Recheck identity, text, audience, and final attachments; click Post once.
6. Report `confirmed` only if a new sharing confirmation appears and the composer
   closes. Otherwise report `uncertain` without retrying.

**Audience is inherited from Facebook's current composer setting, not changed
by the agent.** Set it manually beforehand if you need Public/Friends/Only me.
The observed audience is included in the result. There are no credentials,
cookie exports, screenshots, or persistent state files created by this tool.

The posting tab stays open, including on preparation errors and uncertain
outcomes. Doctor closes only its own tab. Neither command closes your Chrome,
its context, or existing tabs.

## Results and recovery

Commands emit JSON with `ok` and either `data` or `error`.

| Exit | Meaning |
| --- | --- |
| 0 | Doctor succeeded or Facebook displayed sharing confirmation. |
| 1 | Unexpected internal error. |
| 2 | Invalid arguments, text, or image. |
| 3 | Connection, authentication, challenge, or DOM preparation failure. |
| 4 | A submission click was attempted, but publication is uncertain. |

On exit 4, **inspect your profile and the open tab before rerunning**. The post
may already exist. Repeated CLI invocations are separate requests and are not
deduplicated. Do not put `post` in a retry loop. Interrupted processes can also
leave an uncertain outcome: inspect manually before trying again.

Facebook's DOM varies by account, locale, and UI rollout. Unsupported or
ambiguous controls stop the agent rather than guessing. Automated fixtures
validate the flow, not compatibility with every live Facebook account. No live
posts were made during development. Platform restrictions still apply; login
and challenges require manual attention rather than bypassing them.

## DOM identifiers

All Facebook UI identifiers live in [`dom.py`](dom.py), grouped by feature.
Each named function returns a locator; it does not click or choose the first
match. Update the relevant function when Facebook changes that feature.

| Feature | Locator function(s) |
| --- | --- |
| Login / restrictions | `login_password_input`, `account_restriction_dialog` |
| Profile name | `profile_name`, `profile_primary_heading`, `profile_heading` |
| Own-profile / Page controls | `profile_edit_control`, `page_management_control` |
| Open composer | `composer_trigger` |
| Create post dialog | `composer_dialog`, `composer_dialog_with_textbox` |
| Posting author | `posting_identity` |
| Audience | `audience_button` |
| Post text | `post_textbox` |
| Upload | `photo_video_button`, `image_upload_input`, `attachment_inputs` |
| Attachment / image preview | `remove_attachment_button`, `remove_photo_button`, `uploaded_image` |
| Next / Post | `next_button`, `post_button`, `submission_dialog` |
| Sharing confirmation | `post_confirmation` |

Profile locators take a page; composer locators take the composer dialog.
`post_button` accepts either scope for Facebook's optional Next step.
`selectors.py` handles visibility, uniqueness, and account safety;
`posting.py` handles navigation, validation, and publishing.

## Tests

```bash
uv run python -m unittest discover -s tools/facebook_agent/tests -v
uv run python -m tools.facebook_agent --help
```

If local Chromium is unavailable, install it with
`uv run playwright install chromium`. DOM fixtures run in an offline browser
context with all pages fulfilled locally.
