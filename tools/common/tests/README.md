---
name: tests
summary: Offline unit tests for the shared browser foundation and the unified post format.
tags:
- tests
- common
- browser
- posting
submodules:
  __init__.py: Marks the tests as a package for tools.common.
  test_browser.py: Lifecycle tests for the invisible stealth browser and CDP connection.
  test_cli.py: CLI contract tests for doctor, start-browser, and post commands.
  test_config.py: Configuration and browser-binary discovery tests.
  test_doctor.py: Browser diagnostics tests without platform navigation.
  test_launcher.py: Browser process detection, startup, and readiness tests.
  test_post.py: Unified post validation, inheritance, overrides, and per-platform adapters.
---

# tools.common tests

From `projects/social-content`, run:

```bash
uv run python -m unittest discover -s tools/common/tests -v
```

These tests never publish or connect to a live account. `test_post.py` validates
the unified post format and its adapters without touching the filesystem beyond
temporary files, and never imports Playwright.
