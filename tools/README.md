---
name: tools
summary: Local automation tools for supervised X workflows, direct Facebook publishing, and direct approved-input LinkedIn CLI readiness and personal posting.
tags: [tools, automation, social-content]
submodules:
  facebook_agent/: Direct Facebook text and image publishing using the shared Chrome profile.
  twitter_agent/: Supervised X DOM CLI with visible browser review and approval.
  linkedin_agent/: Direct approved-input doctor/post CLI with JSON exits, local image validation, and uncertainty-safe personal posting.
---

# Tools

- [`facebook_agent/`](./facebook_agent/): Direct personal-profile publishing of
  approved text and images, using the existing `chrome-twitter-profile`.
- [`twitter_agent/`](./twitter_agent/): Supervised X DOM CLI with visible browser
  operations, draft persistence, attempt quotas, and mandatory human review.
- [`linkedin_agent/`](./linkedin_agent/): Direct `doctor` and `post` CLI for
  already-approved personal LinkedIn text and repeatable ordered images using
  the shared Chrome profile. Local validation precedes browser connection;
  JSON exits distinguish invalid input, preparation failure, and uncertain
  submission, which preserves the tool tab for manual inspection. No supervisor
  or automatic retry; no live posting verification has been performed.
