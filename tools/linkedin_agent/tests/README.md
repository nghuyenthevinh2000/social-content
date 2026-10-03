---
name: tests
summary: Offline LinkedIn tests cover legacy and native-dialog flows, hydration, personal picker evidence, emitted file choosers, decoded ordered media, trusted-click guards, and uncertainty.
tags: [linkedin, tests, validation, browser]
submodules:
  test_models.py: Text limits, signatures, bounded reads, image order, and immutable snapshots.
  test_cli.py: Module help and JSON errors, pre-browser validation, ordered dispatch, exit mapping, and preserve-before-disconnect uncertainty.
  test_browser.py: Mocked CDP lifecycle, secret-safe diagnostics, synthetic for-you feed controls with container identity and click assertions, legacy/mixed ambiguity, blocks, and launcher help.
  test_dom.py: Chromium fixtures for empty-media baselines, delayed uploads, payload hashes/order, overlay mutation cancellation, toast freshness, and listener cleanup.
  test_modern_dom.py: Native-dialog fixtures with selected personal rows, body-level emitted choosers, immutable FileList checks, ordered thumbnail/attachment counts, hydration, and dispatch identity mutations.
---

# LinkedIn agent tests

Modern fixtures model the observed native dialog and chooser contract without
live account identifiers. They exclude duplicated large previews from ordered
thumbnail counts, keep member avatars out of attachment counts, verify selected
radio personal identity against own-feed profile/name/image, and reject old
text/media/files/progress. Visible challenges stop; hidden integration frames
alone do not. Pointerdown identity/marker changes cancel final dispatch. The
hydration fixture requires one Start click, without retrying before handlers load.

Run from the project root:

```bash
uv run python -m unittest discover -s tools/linkedin_agent/tests -v
```

Lifecycle tests patch `playwright.sync_api.sync_playwright`; they never connect
to a CDP endpoint. DOM tests launch separate local headless Chromium instances.
Readiness fixtures use `set_content()`. Composer fixtures fulfill the production
feed URL entirely from inline synthetic HTML and block every other network
request; no request reaches LinkedIn. They model English accessible controls,
LinkedIn composer/media classes and toast markup, with real PNG/JPEG file
payloads and browser-decoded blob previews. JavaScript counters distinguish
media advancement from the final Post invocation.

These fixtures require Playwright Chromium installed
(`uv run playwright install chromium`) and never use account data or make live
posts. Launcher tests run only `--help`. To run just the composer coverage:

```bash
uv run python -m unittest discover -s tools/linkedin_agent/tests -p test_dom.py -v
```

CLI tests run real Python subprocesses for module/command help and invalid
arguments or inputs, all rejected before browser connection. Dispatch tests
patch `Browser` and `publish_post` so no CDP connection or live post occurs.
They verify exact text and ordered byte snapshots, unreadable-file validation,
sanitized JSON failures and exit codes, and preservation of an uncertain posting
tab before context cleanup/disconnection, with one publish invocation and no retry.
Run these tests without an installed Chromium test browser:

```bash
uv run python -m unittest discover -s tools/linkedin_agent/tests -p test_cli.py -v
```

Cases cover identity and draft ambiguity, exact spaces/blank lines and line
endings, ordered snapshot bytes, inline uploads, Next/Done transitions,
missing/duplicate controls, disabled submission, incomplete/broken previews,
upload errors/progress, late draft changes, stale versus fresh success toasts,
confirmation-only URL extraction, missing confirmation, and exceptions before
and after final-click dispatch. Preparation failures assert zero final clicks;
successful and uncertain submissions assert one final invocation with no retry.

Dispatch regressions create success toasts before the real click event, both
from pointerdown and while an overlay blocks Playwright's auto-waiting click.
Neither confirms a post when the final handler emits no success. A fresh
post-dispatch toast still confirms. Listener cleanup is checked on success and
exceptions before/after dispatch. Media fixtures retain a hidden composer input
while a separate dialog is visible or delayed; uploads must use the media input,
while genuinely duplicate active media dialogs still fail before submission.

Final-fix regressions mutate text, author, preview source, preview order/node,
upload progress, and the Post button while an overlay forces the real final Locator.click to
auto-wait. They assert one click invocation, zero application submissions,
specific pre-submit errors, and listener cleanup. Pointerdown mutation is also
blocked before a pre-existing application document capture handler. Losing the
click acknowledgement or cleanup acknowledgement after cancellation remains
uncertain, without retry.

Prepopulated composer/media previews with delayed supplied uploads are rejected
before upload and with zero Post submissions. Hidden previews, old selected
files, and old text fail closed. Reversed files and same-metadata/same-size
changed bytes fail payload verification; a delayed new upload succeeds only
after fresh decoded previews. Secret-bearing endpoint tests verify unchanged
connection arguments and endpoint-free doctor data and CLI failure output.

Semantic readiness regressions model the `/feed/foryou/` layout without account
data: a current Home navigation button with a notification-bearing accessible
label and a focusable Start a post div containing its accessible-label child.
They verify the matched element is the actionable container before separately
checking its click handler, reject unscoped/incomplete
lookalikes, and reject modern, mixed-layout, and hidden duplicate controls.
