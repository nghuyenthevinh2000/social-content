---
name: tools
summary: Local automation tools for terminal-operated X workflows and direct approved-input Facebook and LinkedIn personal publishing.
tags: [tools, automation, social-content]
submodules:
  facebook_agent/: Direct Facebook text and image publishing using the shared Chrome profile.
  twitter_agent/: Terminal-operated X DOM CLI with direct reply submission and approved image posting.
  linkedin_agent/: Direct approved-input doctor/post CLI with JSON exits, local image validation, and uncertainty-safe personal posting.
---

# Tools

- [`facebook_agent/`](./facebook_agent/): Direct personal-profile publishing of
  approved text and images, using the existing `chrome-twitter-profile`.
- [`twitter_agent/`](./twitter_agent/): Terminal-operated X DOM CLI with visible
  browser operations, draft persistence, direct submission, attempt quotas, and
  approved image posting.
- [`linkedin_agent/`](./linkedin_agent/): Direct `doctor` and `post` CLI for
  already-approved personal LinkedIn text and repeatable ordered images using
  the shared Chrome profile. Local validation precedes browser connection;
  JSON exits distinguish invalid input, preparation failure, and uncertain
  submission, which preserves the tool tab for manual inspection. No supervisor
  or automatic retry. A single-image post was verified on the live modern layout.
