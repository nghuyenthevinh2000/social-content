---
name: tests
summary: Offline tests for direct Facebook publishing and messaging, exact content
  and attachment checks, plan validation, pacing, Playwright compatibility, CLI errors,
  and browser lifecycle.
tags:
- facebook
- tests
- playwright
- unittest
submodules:
  test_browser.py: Lifecycle tests with an external CDP boundary double.
  test_dom.py: Real Playwright tests against intercepted local HTML, never Facebook.
  test_groups.py: Offline tests for composer multi-group sharing, against intercepted
    HTML.
  test_messaging.py: Real Playwright tests for direct messaging against intercepted
    local HTML.
  test_models_cli.py: Validation and CLI contracts; no live browser or Facebook calls.
  test_pacing.py: Deterministic tests for the messaging pacer; no real sleeping.
---

# Facebook agent tests

From `projects/social-content`, run:

```bash
uv run python -m unittest discover -s tools/facebook_agent/tests -v
```

These tests never publish or send to a live account. DOM fixtures use an offline
browser context and local route fulfillment, covering both posting and direct
messaging. Plan validation and CLI contract tests run without a browser, and the
pacer is tested with an injected sleep. Browser lifecycle tests replace only the
external CDP connection boundary.
