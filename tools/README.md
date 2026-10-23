# Tools

| Tool | Purpose |
| --- | --- |
| [`loop/`](./loop/) | Project-agnostic metrics/review engine. Run `python -m tools.loop --project PATH --help`; each project owns its config, publications, evidence and worked comparisons. |

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
