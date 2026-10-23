# Test suite for terminal-operated X CLI

Run from the social-content root:

```bash
uv run python -m unittest discover -s tools/twitter_agent/tests -v
```

Tests use standard-library `unittest`, isolated Playwright Chromium fixtures,
temporary state directories, and child processes. They require POSIX `flock`
(supported on macOS) and perform no live network operations against X.
