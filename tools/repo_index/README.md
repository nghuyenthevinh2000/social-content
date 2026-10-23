# Repository index

The canonical index is `local/index.json`. `local/` is gitignored, so the index can
mention machine-local paths without publishing them. A public build excludes
`local/` entirely.

```bash
uv run python -m tools.repo_index build
uv run python -m tools.repo_index query "where do facebook posts get published?" --mode edit --explain
uv run python -m tools.repo_index check --deep
uv run python -m tools.repo_index ensure
```

## What is indexed

| Field | Purpose |
|---|---|
| `symbols` | Functions, classes, methods, headings, config keys with line numbers. |
| `imports`, `dependencies`, `dependents` | Call and import graph for change-impact checks. |
| `tests`, `tests_for` | Conventional and import-based test mapping. |
| `entrypoint` | CLI, script, `__main__`, shebang, and package `bin` targets. |
| `change_when` | Curated edit guidance from frontmatter or local overrides. |
| `summary`, `tags` | Short routing text derived from frontmatter, docstrings, headings. |

## Curated overrides

Put private guidance in `local/index.overrides.json`:

```json
{
  "files": {
    "tools/loop/metrics.py": {
      "summary": "Collects publication metrics.",
      "change_when": "Change when a platform metric or checkpoint rule changes.",
      "entrypoint": false,
      "tags": ["metrics", "loop"]
    }
  },
  "directories": {
    "tools/loop": {"summary": "Publication metrics loop."}
  }
}
```

Frontmatter fields on tracked files (`summary`, `tags`, `change_when`, `owner`)
are also read, so shared guidance belongs there.
