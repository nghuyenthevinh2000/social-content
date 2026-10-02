---
name: tests
summary: Offline tests for direct Facebook publishing, exact content and attachment checks, Playwright compatibility, CLI errors, and browser lifecycle.
tags: [facebook, tests, playwright, unittest]
submodules:
  test_models_cli.py: Validation and structured JSON CLI contracts.
  test_dom.py: Offline publishing, restored attachment rejection, identity checks, and visibility compatibility.
  test_browser.py: CDP lifecycle boundary tests preserving user browser tabs.
---

# Facebook agent tests

From `projects/social-content`, run:

```bash
uv run python -m unittest discover -s tools/facebook_agent/tests -v
```

These tests never publish to a live account. DOM fixtures use an offline browser
context and local route fulfillment. Browser lifecycle tests replace only the
external CDP connection boundary.
