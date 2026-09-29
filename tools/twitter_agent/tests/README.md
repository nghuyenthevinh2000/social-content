---
name: tests
summary: Unit, DOM fixture, supervisor review, and subprocess CLI tests for the supervised X agent.
tags: [tests, unittest, sqlite, playwright, dom, cli]
submodules:
  test_models.py: URL validation, Unicode approval binding, and limit validation.
  test_store.py: Real SQLite queue, control, quota, recovery, permission, and process-lock tests.
  test_dom.py: Local Playwright DOM fixtures for extraction, block detection, and reply interactions.
  test_supervisor.py: Human decision binding, approval checks, and submission failure boundary tests.
  test_cli.py: Subprocess interface, JSON stdout/stderr, interactive supervisor guard, and queue imports.
---

# Test suite for supervised X CLI

Run from the social-content root:

```bash
uv run python -m unittest discover -s tools/twitter_agent/tests -v
```

Tests use standard-library `unittest`, isolated Playwright Chromium fixtures,
temporary state directories, and child processes. They require POSIX `flock`
(supported on macOS) and perform no live network operations against X.
