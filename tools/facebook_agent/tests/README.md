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
