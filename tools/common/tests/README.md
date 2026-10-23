# tools.common tests

From `projects/social-content`, run:

```bash
uv run python -m unittest discover -s tools/common/tests -v
```

These tests never publish or connect to a live account. `test_post.py` validates
the unified post format and its adapters without touching the filesystem beyond
temporary files, and never imports Playwright.
