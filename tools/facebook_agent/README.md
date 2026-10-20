---
name: facebook_agent
summary: Direct DOM publishing to a personal Facebook profile or explicitly named
  active Fanpage, with optional multi-group sharing, plus planned direct messaging
  with humanized typing, pacing, and exact content checks.
tags:
- facebook
- playwright
- cdp
- publishing
- messaging
- groups
submodules:
  tests/: Offline tests for direct Facebook publishing and messaging, exact content
    and attachment checks, plan validation, pacing, Playwright compatibility, CLI
    errors, and browser lifecycle.
  __init__.py: Direct DOM publishing of approved content to a Facebook personal profile.
  __main__.py: Entry point for python -m tools.facebook_agent.
  browser.py: Connect to existing Chrome, preserving user tabs and the browser process.
  cli.py: Direct publishing CLI with structured JSON output and stable exit codes.
  dom.py: Facebook DOM identifiers, grouped by feature. Each function returns a locator,
    not a click or a visibility/uniqueness check. Page features take a page
  messaging.py: Direct-message navigation, humanized typing, and one-click sending.
    Adapted from the reference messaging tool's flow (open a profile, open its message
  models.py: Stable errors and validation before any browser interaction.
  pacing.py: Randomized inter-recipient delays and periodic cooldowns for direct messaging.
    Mirrors the reference tool's anti-detection intent (short jittered paus
  posting.py: Profile/Page navigation, composer validation, and one-click publishing.
  selectors.py: Visibility, uniqueness, and account safety checks; identifiers live
    in dom.py.
---

# Facebook profile and Fanpage agent

## Read-only Page Insights

| Action | Command / behavior |
| --- | --- |
| Capture dashboard | `uv run python -m tools.facebook_agent insights --page-id 61595289277974 --output local/paper-ink-product/sources/post-metrics/insights-new.json` |
| Specific section/post | Supply an observed dashboard URL with `--url`; post Insights IDs must belong to the verified Page. |
| Read-only navigation | Optional `--open 'Top countries'` or `--open Source`; only allowlisted navigation labels. No publishing, engagement or settings changes. |
| Evidence | New JSON plus screenshots; `capture_complete` marks success. Rendered text, links and labeled `post_metrics` are retained. Existing JSON paths are refused. |
| Limits | English labels; no hidden API calls or exact chart-point extraction. Suppressed metrics stay null; average percentage watched is not completion rate. Page and post scopes remain separate. |
| Age and gender | Captures rendered `data-metric` gender labels, percentage-width segments and age rows; no guessing gender from colors. `--hover-demographics` also captures any exposed tooltips. |
| Discovery | Captures the active Traffic/Source tab and labeled percentages. Use `--open Source` to retain both initial Traffic and Source snapshots. |
| CSV join | `uv run python -m tools.facebook_agent insights-import --page-id PAGE_ID --csv EXPORT.csv --dashboard CAPTURE.json --output JOINED.json` (`--dashboard` repeatable). Joins by Post ID; preserves daily rows and cumulative snapshots separately. CSV publish timezone stays unknown; daily averages are not summed. |
| CSV download | `uv run python -m tools.facebook_agent insights-export --page-id PAGE_ID --output NEW.csv`. Creates one Content report using the current UI date range/default Summary settings, then downloads the newly generated report from Report history. |
| Existing report | Add `--report-id REPORT_ID` to download a specific completed report without creating another. Supports existing Daily breakdown files as well. On timeout, inspect the saved audit/history before requesting another report. |
| Download safeguards | Verifies active Page and CSV Page IDs, saves settings/screenshots/hash, refuses existing output/audit/staging paths, and handles downloads opening in a popup. Never publishes or deletes content. Summary CSVs differ from daily exports; the existing daily importer must not be used blindly for Summary files. |
| Duplicate prevention | Before downloading a report ID, inspect sibling export audits. A verified file with a matching hash/Page ID is returned as `reused`, without another download. An uncertain prior click blocks retries until reconciled. Checks cover this output directory, not a scan of personal Downloads or other folders. |

```text
Verify active Page → Read dashboard → Save DOM/screenshots → Review labeled metrics
```

Design: [`2026-10-02-facebook-agent-design.md`](../../../../docs/superpowers/specs/2026-10-02-facebook-agent-design.md).
Implementation plan: [`2026-10-02-facebook-agent.md`](../../../../docs/superpowers/plans/2026-10-02-facebook-agent.md).

Publish **already-approved** text and one optional image through a visible
Facebook composer, or send **already-approved** direct messages from a JSON
plan. No supervisor, draft queue, or approval prompt. Invoking `post` or
`message` authorizes immediate sending; do not invoke them to preview content.

## Setup

From `projects/social-content`:

```bash
uv sync
uv run python -m tools.common start-browser
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

# Also share the same post to named groups (repeatable, max 9).
uv run python -m tools.facebook_agent post --text "Approved caption" \
  --group "Austin Small Biz" --group "Local Makers"

# Or read the group names from a JSON file.
uv run python -m tools.facebook_agent post --text "Approved caption" \
  --groups-file /absolute/path/groups.json

# Optional connection and per-stage timeout overrides, before the command.
uv run python -m tools.facebook_agent --cdp http://127.0.0.1:9222 \
  --timeout-ms 20000 doctor
```

Text is passed unchanged; links can appear in the text. For multiline text in
bash/zsh, use `--text $'First line\nSecond line'`. Nonempty text is required;
image-only posts, multiple images, videos, scheduling, and posting *into* a Group
as the top-level destination are not supported. Sharing a profile/Page post to
your groups through the composer is supported — see below. Image validation
checks PNG/JPEG/GIF/WebP file signatures; Facebook still decides whether the
actual file can be uploaded.

### Fanpage publishing (explicit opt-in)

Manually switch into the intended Page in the shared Chrome browser first.
Supply its exact displayed name to both commands:

```bash
uv run python -m tools.facebook_agent doctor --page-name "Your Page Name"
uv run python -m tools.facebook_agent post --page-name "Your Page Name" \
  --text "Approved caption" --image "/absolute/path/photo.png"
```

Alternatively, use `--page-id 123` for a
`profile.php?id=123` Page: the active `/me` URL must contain that exact ID.
A vanity URL redirect is rejected in ID mode; use the verified exact name instead.
Without either Page option, Pages remain rejected. Page-name mode checks editable-owner
and management controls, the exact heading, and the composer author before
posting. It rejects a "Switch into Page" prompt rather than switching accounts.
When both `--page-id` and `--page-name` are supplied, repeated identical Page
headings are accepted only after verifying the active URL's exact Page ID.
Composer identity and all actionable controls still require unique matches.
Audience, exact text, image checks, and single-click/uncertain-result behavior
are unchanged. Missing or ambiguous controls stop publication; this supports
the regular Create post composer, not Meta Business Suite or paid campaigns.
Offline fixtures cover Page mode; live Facebook UI compatibility still needs
a read-only `doctor` check and a user-approved post.

### Sharing to groups (JSON plan or flags)

Modern Facebook moves the composer to a **Post settings** step (via **Next**)
after you write the post. That step carries a **Share to groups** control
("Post in up to 9 groups that you're in."). `post` uses it to also publish the
same post to groups you name, without posting into a Group as a destination.

```bash
# Group names exactly as shown in the picker; repeatable, up to 9.
uv run python -m tools.facebook_agent post --text "Approved caption" \
  --group "Austin Small Biz" --group "Local Makers"

# A JSON array of names, or an object with a "groups" array.
# ["Austin Small Biz", "Local Makers"]   or   {"groups": ["Austin Small Biz"]}
uv run python -m tools.facebook_agent post --text "Approved caption" \
  --groups-file tools/common/samples/groups.json
```

`--group` and `--groups-file` combine (flags first). Names must be unique; a
duplicate, a blank name, or more than 9 names is rejected before the browser
connects. During the run, each name is matched against a group row's exact first
line, so a duplicated display name stops the post rather than guessing, and an
unknown name reports `group_not_found` with nothing submitted. The selected
groups are included in the result as `groups`. Because the picker is part of
Facebook's evolving composer, a live read-only check is worthwhile before the
first real group share.

## Read-only Reels recommendations

| Command | Behavior |
| --- | --- |
| `uv run python -m tools.facebook_agent reels --page-id 61595289277974 --limit 15 --output local/facebook-reels/session.json` | Verifies the already-active Page, opens For You Reels, and captures up to 15 visible observations as JSON. Existing output files are never overwritten. |
| Scope | Captures visible text, links, and labeled controls. Review language, URLs, and engagement labels before reporting. No publication-date filter or nationwide ranking. |
| Side effects | Opens and preserves a tool-owned tab; watches and scrolls only. Viewing can influence recommendations. No likes, follows, comments, or shares. |

```text
Verify Page → Open For You → Capture → Scroll → Save JSON → Review
```

### Product-aware agent review

| Stage | Behavior |
| --- | --- |
| Context | Read the product directory before selecting inspiration. For paper campaigns, start with `local/paper-ink-product/product-marketing.json` and `posts/hypothesis.json`. |
| Selection | Agent reviews raw observations directly; no separate Jev/TypeSafe calls or automatic audience probability threshold. |
| Promotion | Allow by default. Exclude only explicit unrelated product/service promotion with observed evidence. Ordinary dancing, daily life, and education remain eligible. |
| Audience | Use observed Vietnamese captions or actually inspected speech/context; a creator name alone is insufficient. |
| Output | Keep raw observations unchanged; save selections and reasons separately. Historical Jev results remain available, but those commands are removed. |
| Timer | Prefix the `reels` command with `/usr/bin/time -p` to measure collection CLI wall time. Track agent review separately; collection time is not end-to-end discovery time. |

```text
Product context + saved observations → Agent review → Selected Reels + evidence
```

## Explicit creator follows

| Command / constraint | Behavior |
| --- | --- |
| `uv run python -m tools.facebook_agent follow --page-id 61595289277974 --creator "Lão Nông" --reel https://www.facebook.com/reel/3707988839450143 --approved --output local/paper-ink-product/sources/new-follow.json` | Requires explicit approval for one creator, verifies the active Page, resolves the creator profile from the observed Reel, and clicks only its unique Follow button. |
| Confirmation | Records `confirmed` only after the profile shows Following. Existing follows are left unchanged. No likes, comments, shares, or unfollows. |
| Direct profile | Use `--profile-url https://www.facebook.com/nam.anh.marketing.finance` instead of `--reel`. The supplied vanity URL must remain the same identity after navigation; `--creator` is optional and the observed display name is recorded. |
| Safety | Refuses existing audit files; captures before/after evidence. Exit 4 means a click may have happened without confirmation: stop and inspect, never automatically retry. Exit 3 means failure before a confirmed result; inspect `clicked` before any retry. |

```text
Verify active Page → Match Reel creator → Check profile → Follow once → Confirm Following
```

## Publishing behavior

1. Open a new visible tab and navigate through Facebook `/me`.
2. Verify own-profile Edit profile controls and name; reject Page-management UI
   unless `--page-name` explicitly selects the exact active Page.
3. Open Create post, check posting identity and read the existing audience.
   Reject restored attachments rather than merging them with this request.
4. Fill the exact text; attach the optional image and wait for its removal control.
5. Recheck identity, text, audience, and final attachments. If group sharing was
   requested, move to Post settings (Facebook's **Next** step), open **Share to
   groups**, select the named groups by their exact first line, and confirm with
   **Done**.
6. Click Post once; report `confirmed` only if a new sharing confirmation appears
   and the composer closes. Otherwise report `uncertain` without retrying.

**Audience is inherited from Facebook's current composer setting, not changed
by the agent.** Set it manually beforehand if you need Public/Friends/Only me.
The observed audience is included in the result. There are no credentials,
cookie exports, screenshots, or persistent state files created by this tool.

The posting tab stays open, including on preparation errors and uncertain
outcomes. Doctor closes only its own tab. Neither command closes your Chrome,
its context, or existing tabs.

## Direct messaging (JSON plan)

Send one **already-approved** custom message per recipient from a JSON plan.
Each recipient gets its own text; there is no random template rotation.
This command targets personal-profile messaging only and uses the same shared
Chrome profile shown by `doctor`. Every recipient is a live navigation and send,
so review the plan before running it.

```bash
# Send every entry in the plan, pacing between recipients.
uv run python -m tools.facebook_agent message --plan /absolute/path/plan.json

# Cap this run and tune pacing (all optional).
uv run python -m tools.facebook_agent message \
  --plan /absolute/path/plan.json \
  --max-messages 25 \
  --min-delay-ms 3200 --max-delay-ms 4500 \
  --cooldown-every 25 --cooldown-ms 240000
```

### Plan format

A top-level JSON array, or an object with a `recipients` array. Each entry needs
a Facebook profile URL and a message. `recipient`/`text` are accepted aliases for
`url`/`message`; `label` is optional and defaults to the URL for reporting.

```json
[
  { "url": "https://www.facebook.com/first.person", "message": "Hi Sam — ...", "label": "Sam" },
  { "recipient": "https://www.facebook.com/second.person", "text": "Hey Alex — ..." }
]
```

Validation runs before the browser connects: the plan must be valid JSON with at
least one recipient, every URL must be a Facebook profile path (not `/messages`,
`/groups`, `/pages`, etc.), every message must be nonempty text up to 20,000
characters without NUL bytes, and unknown keys are rejected. Plan problems exit
`2` without touching the browser.

### Behavior

1. Read the plan and validate every entry up front.
2. For each recipient: open its profile, reject login/challenge/restricted
   pages, and reject a profile that cannot be messaged.
3. Open the message composer and reject a composer that already contains text.
4. Type the exact message with humanized per-character delays; a newline is typed
   as Shift+Enter so it becomes a line break instead of an early send.
5. Re-check the composer text, then click Send **once**.
6. Report `confirmed` only if a new message bubble appears and the composer
   clears. Otherwise report `uncertain` and keep the tab open — the send is
   never retried.
7. Pause a random delay between recipients and a longer cooldown every
   `--cooldown-every` recipients (`0` disables it).

A login screen, challenge, or account restriction stops the run immediately
(`stopped_reason`). A per-recipient preparation failure is recorded as `failed`
and the run continues. `--max-messages` stops the run once that many recipients
have been attempted. All delays use wall-clock time; keep the run foreground and
do not run it alongside `post` or another write operation on the same profile.

## Results and recovery

Commands emit JSON with `ok` and either `data` or `error`.

| Exit | Meaning |
| --- | --- |
| 0 | Doctor succeeded; a post was shared; or every planned message was confirmed (a `max_messages_reached` stop is not an error). |
| 1 | Unexpected internal error. |
| 2 | Invalid arguments, text, image, message plan, or group names. |
| 3 | Connection, authentication, challenge, or DOM preparation failure; a `post` preparation failure; or a `message` run with a failed recipient or an early safety stop. |
| 4 | A submit click was attempted from `post` or `message`, but the outcome is uncertain. |

On exit 4, **inspect your profile and the open tab before rerunning**. The post
or message may already exist. Repeated CLI invocations are separate requests and
are not deduplicated. Do not put `post` or `message` in a retry loop. Interrupted
processes can also leave an uncertain outcome: inspect manually before trying
again. The `message` result JSON lists `confirmed`, `uncertain`, `failed`,
`attempted`, `stopped_reason`, and a per-recipient `results` array.

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
| Group sharing | `post_settings_dialog`, `share_to_groups_button`, `groups_picker_dialog`, `groups_done_button` |
| Open message composer | `message_button` |
| Message dialog / input | `message_dialog`, `message_textbox` |
| Message send | `send_button` |
| Sent bubble / not deliverable | `sent_bubble`, `cannot_message_notice` |

Profile locators take a page; composer locators take the composer dialog; message
locators take the direct-message dialog. `post_button` accepts either scope for
Facebook's optional Next step. `selectors.py` handles visibility, uniqueness, and
account safety; `posting.py` handles post navigation, validation, and publishing;
`messaging.py` handles direct-message navigation, humanized typing, and sending.

## Tests

```bash
uv run python -m unittest discover -s tools/facebook_agent/tests -v
uv run python -m tools.facebook_agent --help
```

If local Chromium is unavailable, install it with
`uv run playwright install chromium`. DOM fixtures run in an offline browser
context with all pages fulfilled locally.
