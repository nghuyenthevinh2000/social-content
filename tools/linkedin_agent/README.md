---
name: linkedin_agent
summary: Direct approved-input LinkedIn CLI supports legacy and native-dialog composers with verified personal author pickers, emitted media choosers, ordered previews, and guarded one-click uncertainty handling.
tags: [linkedin, automation, validation, browser]
submodules:
  __init__.py: Independent LinkedIn package marker.
  __main__.py: Python module entry point for the direct CLI.
  cli.py: Doctor and repeatable-image post commands with pre-browser validation, JSON results, and uncertainty-safe disconnect.
  models.py: Structured errors and immutable validated text and image inputs.
  browser.py: CDP lifecycle and feed doctor with final readiness revalidation and endpoint-free diagnostics.
  dom.py: Feature-grouped legacy and native DOM identifiers for feed, author, composer, media, and confirmation controls.
  selectors.py: Fail-closed readiness, uniqueness, login, and visible challenge checks using dom.py identifiers.
  posts.py: Hydrated empty personal drafts, selected-member evidence, emitted choosers, hashed ordered files, decoded previews, and guarded trusted dispatch.
  tests/: Offline subprocess CLI, mocked dispatch/CDP, local Chromium fixtures, and input validation tests.
---

# LinkedIn agent

This package is independent of the supervised Twitter agent. Input validation
requires nonblank text of at most 3,000 characters and 1–20 PNG/JPEG images,
each at most 10 MiB. Signatures determine MIME types, not file extensions.
Duplicate resolved paths are rejected; immutable byte snapshots preserve the
provided image order and original text, including CRLF line endings.

The CLI has only `doctor` and `post`: **supplied text and images are treated as
already approved**. `post` publishes directly without a review prompt. There is
no `supervise` command, generated content, scheduler, quota system, or automatic
retry. Run commands from the `projects/social-content` project root.

## Setup and shared profile

```bash
uv sync
uv run python -m tools.social_agent start-browser
```

The browser startup reuses `$HOME/chrome-twitter-profile` and local CDP port `9222`;
it is the same dedicated Chrome profile used by the other social tools, not
your ordinary Chrome profile. In that Chrome window, visit LinkedIn, **log in
manually**, complete any checkpoint/2FA yourself, and select English as the
LinkedIn language. The tool does not accept credentials or bypass challenges.
Keep the intended personal account logged in; company-page posting is unsupported.
Do not run concurrent automation against this profile. Keep CDP local and protect
the profile directory: both provide access to logged-in sessions.

```bash
uv run python -m tools.linkedin_agent doctor
uv run python -m tools.linkedin_agent --help
```

For a different port/profile, launch with `--port 9223 --data-dir PATH` and use
`--cdp http://127.0.0.1:9223` in the CLI. Global `--cdp` and `--timeout-ms`
options must come **before** the command. Timeout defaults to 15,000 ms and must
be a positive integer. Playwright is installed by `uv sync`; local DOM tests
also require `uv run playwright install chromium` (posting attaches to Chrome
instead of launching that test browser).

## Direct posting examples

These commands make real posts when used with an authenticated browser. Review
and approve the exact text and image files first; examples are not dry runs.

```bash
uv run python -m tools.linkedin_agent post \
  --text 'Already-approved update.' --image ./assets/approved-cover.png

uv run python -m tools.linkedin_agent --timeout-ms 30000 post \
  --text 'Already-approved multi-image update.' \
  --image ./assets/approved-cover.png --image ./assets/approved-detail.jpg
```

Repeat `--image PATH` for 1–20 distinct readable PNG/JPEG files, in the desired
order. Each file must be at most 10 MiB; GIF, WebP, video, documents and text-only
posts are unsupported. Local validation checks signatures and bounded byte
size, not full image decoding; LinkedIn previews must decode before submission.
Symlinks resolving to the same file count as duplicates. Text must be nonblank
and at most 3,000 Python characters. It is not trimmed or rewritten; browser
draft comparison normalizes line endings only. Text supplied on the command
line may be visible in shell history and process listings.

## JSON results and exit codes

Except ordinary `--help`, stdout contains one JSON result, not a traceback:

```json
{"ok": true, "data": {"status": "posted", "url": null}}
```

```json
{"ok": false, "error": {"code": "submission_uncertain", "message": "Submission may have completed. Inspect LinkedIn manually before retrying.", "human_action_required": true}}
```

`doctor` success data contains only `connected` and `authenticated`. The CDP
endpoint is deliberately omitted from results and connection errors, because
credentials, query strings, and even endpoint paths may contain secrets. The
original configured URL is still used unchanged to connect.
Posting success requires fresh explicit notification evidence; a URL is optional.

| Exit | Meaning |
| --- | --- |
| 0 | Success (or normal help). |
| 1 | Unexpected failure; exception details are deliberately omitted. |
| 2 | Invalid arguments, timeout, text, or images; no browser connection. |
| 3 | Browser, authentication, challenge, or pre-submission preparation failure. |
| 4 | `submission_uncertain`: the final click may have posted. |

On exit 4 the tool leaves its posting tab open **before disconnecting**. Inspect
that tab and your LinkedIn activity manually; do not blindly rerun the command
or let a wrapper retry it, because that could create a duplicate. Normal tool
tabs are closed on exit; existing tabs and user Chrome remain open. Unexpected
exit 1 also requires manual inspection before retrying.

`validate_inputs(text, paths)` returns the original text and a tuple of frozen
`ImageInput(name, mime_type, buffer)` snapshots. Validation raises `AgentError`
with `invalid_text` or `invalid_images`, an actionable message without input
content, and `human_action_required=False`. Composer comparison may normalize
line endings later; validation never rewrites the approved text.

## Browser connection

`Browser(endpoint='http://127.0.0.1:9222', timeout_ms=15000)` is a context
manager. It uses Chrome's existing context, creates its own temporary tabs with
`new_page()`, and closes only those tabs on exit. `preserve_page(page)` leaves a
tool-created tab open for human inspection. Disconnecting stops the Playwright
client without calling `browser.close()` or closing existing user tabs.

`doctor()` loads `https://www.linkedin.com/feed/` and waits for unique, visible
authenticated navigation and Start a post controls, then rechecks both controls'
uniqueness and visibility immediately before success. It returns `connected`,
`authenticated` without opening a composer or echoing the endpoint. Login and
checkpoint detection raises `not_authenticated` or `browser_challenge` with
`human_action_required=True`. Unknown DOM fails with `dom_timeout`; duplicate
controls fail with `ambiguous_selector`. Nonpositive timeouts are rejected.

Readiness supports legacy `#global-nav` feed links and current Home buttons
inside `nav` with Home text and a Home accessible label (including notification
counts). Start a post may be a legacy button or a focusable `div[role="button"]`
containing a `div[aria-label="Start a post"]`. These alternatives share the
same uniqueness checks: mixed layouts and hidden duplicates fail closed. Feed
links outside legacy navigation are not authentication evidence; no dynamic
hashed classes are used.

Browser startup uses `uv run python -m tools.social_agent start-browser`, retaining
`$HOME/chrome-twitter-profile` and CDP port `9222`. The runtime does not import Twitter
models or selectors.

## Scoped personal posting

`publish_post(page, text, images, timeout_ms=15000)` in `posts.py` accepts
validated text and an ordered tuple of `ImageInput` snapshots. It navigates to
the feed with a bounded timeout, opens a unique visible Start a post control,
and requires a unique personal `/in/` author link in legacy composer headers.
Company `/company/`, missing, ambiguous, or changed authors fail closed.

The observed modern native dialog uses the `ShareCompose` screen and
`ShareBox_textEditor` editor. A modern Start a post container is clicked once,
only after `body[data-rehydrated=true]`. Its own-feed profile is pinned from
`#shareboxProfilePictureComponentRef a[href]`; a unique personal figure with
the same profile URL and an accessible member name binds the feed identity.
The author picker is opened without changing its selection. Its single checked
radio and associated label must belong to a personal-icon row whose name and
profile image match the pinned member. It is reopened before final preparation
validation and closed before dispatch. The final capture guard pins control,
feed/profile, member name, selected-row evidence, and personal avatar marker.
Missing or ambiguous evidence fails closed; no hardcoded member name is used.

Modern Media is wrapped in `expect_file_chooser`: the emitted chooser may own a
hidden body-level input, but arbitrary page-wide file inputs are never selected.
`Loading` before file selection is the observed awaiting-file state, not a
reason to retry Media. Only its specific disabled busy drop-zone loader is
allowed in the empty baseline. Chooser FileList names, MIME, sizes, SHA-256
bytes and order are verified before advancing. Media counts use decoded ordered
`img[alt="image 0"]`, etc., excluding the duplicated `Image Preview` display.
Composer counts use image-icon attachment figures, excluding member avatars.

Only the active composer/media dialog is used for editing and uploading. File
payloads contain the snapshot name, MIME type, and bytes in input order; source
paths are never reread. The personal composer must start with empty text and
no pre-existing media. Both composer and media dialog reject old previews
(including hidden ones), selected files, progress, and upload errors before
uploading. The browser's selected file list is compared in order against each
snapshot's name, MIME type, size, and SHA-256 digest. With an empty baseline,
only newly created, decoded previews can satisfy readiness. Inline uploads and
uniquely visible media Next/Done transitions are supported, with at most three distinct transitions and no
repeated click on an unchanged control. Preparation has a shared monotonic
deadline after bounded feed navigation. Previews must match the requested
count, be decoded, and have no visible upload progress or error.

The media selector excludes the underlying composer even if it retains hidden
file inputs. Distinct visible media dialogs take precedence; duplicate active
dialogs are rejected. Inline fallback requires a newly exposed composer input
after Add media, so a persistent chooser cannot bypass a delayed media dialog.

Immediately before submission, the agent rechecks author, exact rendered draft
text (normalizing only CRLF/CR to LF), previews, and a unique visible enabled
Post button. Native browser selection text preserves spaces and blank lines;
the user's prior selection is restored. Preparation errors make no final click.

The final Post button is invoked exactly once, without retry. A synchronous
window capture listener checks the draft again at the actual trusted click,
after Playwright's actionability/overlay waits and pointerdown. It checks the
personal author, exact draft text, unique composer/control, and the validated
ordered preview nodes and sources, decoding, upload progress and errors. A Post
button replaced during the wait is intercepted and rejected too. If
anything changed, it prevents the default action and stops propagation before
document/target application click handlers. An acknowledged cancellation with
successful click completion and listener cleanup returns a pre-submit error
(exit 3), with zero application Post submissions. Every exception beginning with
the click invocation still becomes `AgentError('submission_uncertain', ..., True)`;
this includes lost cancellation acknowledgements or cleanup failures.
inspect LinkedIn manually before any retry. Composer disappearance is not
confirmation. Only fresh visible explicit success notification evidence within
the confirmation timeout returns `{'status': 'posted', 'url': ...}`. Existing
unchanged success toasts and link-only/whitespace-only changes are ignored.
The same capture-phase listener snapshots notification state at the chosen button's
actual allowed trusted click dispatch, before the application's click handler. Toasts
appearing during Playwright actionability waits or pointerdown remain baseline,
not confirmation. Missing dispatch evidence is uncertain. The listener and its
handle are removed in `finally` on success, missing confirmation, and click
exceptions; cleanup failures also remain inside the uncertainty boundary.
A notification may be a new DOM node, become visible, or change its success
message after dispatch. URLs must be
HTTPS LinkedIn `/posts/` or `/feed/update/urn:li:activity:` links attached to
that notification; otherwise success returns `url=None`.

## Limitations and verification

Live diagnostics verified preparation of the explicitly approved draft and
image through native chooser upload, decoded previews, Next, author recheck,
exact text validation, and final guard installation/removal. Diagnostics stopped
before Post and discarded only their own exact draft. **No live posting or
modern success-notification verification has been performed.** Success still
requires fresh explicit supported toast/status/alert evidence; missing or changed
confirmation markup yields submission uncertainty, never a retry.

Selectors use LinkedIn's English accessible controls, native dialog/screen
markers, personal/image icons, and legacy `share-*`,
`image-sharing-preview-*`, and `artdeco-*` markup. Unsupported layout/localization
fails closed. LinkedIn DOM changes, experiments, and account-specific layouts
can break readiness or posting; this is browser automation, not an official API.
Modern identity checks pin the logged-in own-feed personal profile, not an
externally configured expected account; verify the logged-in account yourself.
Hidden challenge integration iframes alone are not proof of a challenge. Visible
challenge frames and checkpoint URLs/forms still stop automation; no bypass is
performed. Tests use local synthetic HTML and real Chromium with all external
requests blocked.
