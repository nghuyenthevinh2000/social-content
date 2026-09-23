# Agent Guidelines & Repository Operating System

## 1. Documentation & Frontmatter Integrity Rule

Every directory in this project must maintain standardized YAML frontmatter. This frontmatter forms the hierarchical semantic routing tree used by TypeSafe Jev to navigate the repository without reading around the bush.

- **Repository Root:** The master root of the tree is maintained in [`FRONTMATTER.md`](./FRONTMATTER.md).
- **Subdirectories:** Each folder maintains its frontmatter at the top of its `README.md`.

### Frontmatter Schema

```yaml
---
name: <folder-name>
summary: <1-2 sentences clearly describing this folder's purpose and contents>
tags: [<tag1>, <tag2>, ...]
submodules:
  <child-folder-or-file>: <brief one-line description>
---
```

### Mandatory End-of-Turn Workflow

Whenever you create or modify files in any project folder:

1. You MUST update that folder's `README.md` frontmatter so `summary` and `submodules` accurately reflect the changes.
2. You can automatically sync or refresh the frontmatter by running:

   ```bash
   uv run --project . scripts/sync_readme_tree.py <path/to/folder>
   ```

3. Verify compliance before completing your turn:

   ```bash
   uv run --project . scripts/lint_readme_tree.py --changed-only
   ```

> [!IMPORTANT]
> The repository enforces this via an automated **Antigravity `Stop` Lifecycle Hook** (`scripts/frontmatter_guard_hook.py`). If you attempt to conclude your turn while leaving a modified directory with missing or invalid frontmatter, the execution loop will automatically block your completion and force you to continue until the frontmatter is updated.
