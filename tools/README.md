---
name: tools
summary: Local automation tools for terminal-operated X workflows and direct approved-input
  Facebook and LinkedIn personal publishing, built on a shared unified post format.
tags:
- tools
- automation
- social-content
submodules:
  video_edit/: OpenCV texture compositing and static-video watermark removal.
  facebook_agent/: Direct DOM publishing to a personal Facebook profile or explicitly
    named active Fanpage, with optional multi-group sharing, plus planned direct
    messaging with humanized typing, pacing, and exact content checks.
  linkedin_agent/: Direct approved-input LinkedIn CLI supports legacy and native-dialog
    composers with verified personal author pickers, emitted media choosers, ordered
    previews, and guarded one-click uncertainty handling.
  reddit-research-mcp/: Subdirectory containing reddit-research-mcp modules
  reddit_agent/: Subdirectory containing reddit_agent modules
  common/: Shared platform-independent browser diagnostics, invisible stealth
    engine, and browser startup foundation, plus the unified post format and
    example input files (samples/) for social content publishing tools.
  twitter_agent/: Terminal-operated X DOM CLI with direct reply submission and explicitly
    approved standalone image posting, exact content checks, attempt quotas, randomized
    browsing delays, single-click submissions, and JSON-configured topic reporting
    with an agent workflow.
---

# Tools

- [`video_edit/`](./video_edit/): Texture compositing and static-video watermark
  removal. Run `uv run python -m tools.video_edit --help` from the repository root.

- [`common/`](./common/): Shared platform-independent browser CDP diagnostics,
  browser startup foundation, and the canonical unified post format
  ([`samples/post.json`](./common/samples/post.json)) one platform-agnostic post
  is resolved from for every publishing agent.
- [`facebook_agent/`](./facebook_agent/): Direct personal-profile publishing of
  approved text and images, optional sharing to up to 9 named groups through the
  composer, and JSON-planned direct messaging with humanized typing and pacing,
  using the existing `chrome-twitter-profile`.
- [`twitter_agent/`](./twitter_agent/): Terminal-operated X DOM CLI with visible
  browser operations, draft persistence, direct submission, attempt quotas, and
  approved image posting.
- [`linkedin_agent/`](./linkedin_agent/): Direct `doctor` and `post` CLI for
  already-approved personal LinkedIn text and repeatable ordered images using
  the shared Chrome profile. Local validation precedes browser connection;
  JSON exits distinguish invalid input, preparation failure, and uncertain
  submission, which preserves the tool tab for manual inspection. No supervisor
  or automatic retry. A single-image post was verified on the live modern layout.
