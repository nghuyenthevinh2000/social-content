---
name: tests
summary: Unit, pacing, DOM fixture, supervisor review, topic configuration, and subprocess
  CLI tests for the supervised X agent.
tags:
- tests
- unittest
- sqlite
- playwright
- dom
- cli
submodules:
  test_cli.py: Subprocess interface tests for CLI commands, JSON output, and interactive
    guard.
  test_dom.py: Local fixture browser tests for DOM extraction and browser lifecycle.
  test_models.py: Input and exact-content approval contracts.
  test_pacing.py: Deterministic delay ranges, action-budget breaks, and browser read pacing tests.
  test_report.py: Deterministic selection, bounded collection, and atomic JSON artifact writing tests.
  test_store.py: Real SQLite, injected time, and process-lock regression tests.
  test_supervisor.py: Tests for supervisor review loop, human decisions, and submission
    boundaries.
  test_topic_config.py: Topic validation, query construction, and configuration-driven bundled topic coverage.
---

# Test suite for supervised X CLI

Run from the social-content root:

```bash
uv run python -m unittest discover -s tools/twitter_agent/tests -v
```

Tests use standard-library `unittest`, isolated Playwright Chromium fixtures,
temporary state directories, and child processes. They require POSIX `flock`
(supported on macOS) and perform no live network operations against X.
