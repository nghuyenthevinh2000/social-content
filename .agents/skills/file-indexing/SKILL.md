---
name: file-indexing
description: "Use for repository file indexing and navigation: build or refresh a lightweight manifest, split a large Repomix pack into domain file lists, and find exact files with a search-first workflow. Use when indexing a repo, locating code, or when a packed codebase is too large to load."
metadata:
  tags: file-indexing, repository-index, repository-search, manifest, repomix, context-budget, token-budget, code-navigation, split-output
---

## Use when

| Signal | Action |
|---|---|
| Need to index or refresh the repository | Run `build_index.py`; use `index.md` as the map |
| One pack exceeds the context budget or is several MB | Build a manifest; never paste the whole pack |
| Need the exact file to edit | `select.py --mode edit`, then search the group pack |
| Need a repo overview | Read `local/repomix/index.md` domains table, then open one domain |
| Repeating navigation across sessions | Regenerate the index after commits or pulls |
| Working with a remote repo | Pack with `--remote`, then run the same index flow |
| Need flag or config details | Read `references/repomix-cli.md` |
| Need a scenario recipe | Read `references/retrieval-recipes.md` |
| Need a starting config | Copy `assets/repomix.config.json` to the repo root |

## Protocol

```text
index.md -> select.py -> group pack -> search_pack -> read slice -> edit
```

| Step | Command | Stop condition |
|---|---|---|
| 1 | `python3 .agents/skills/file-indexing/scripts/select.py "<task>" --mode edit` | Top group fits the budget |
| 2 | `python3 .agents/skills/file-indexing/scripts/search_pack.py <group.pack> "<symbol or phrase>"` | Exact path and line found |
| 3 | `python3 .agents/skills/file-indexing/scripts/slice_pack.py --group <id> --out <file>` | Slice is under budget |
| 4 | Read only the matching `files` entry or slice | Enough context to act |
| 5 | If no hit, rerun with `--mode any` or a parent prefix | One escalation only |

## Build

| Goal | Command |
|---|---|
| Manifest from an existing pack | `python3 .agents/skills/file-indexing/scripts/build_index.py --source local/repomix/repomix-output.json --out local/repomix` |
| Check drift | `python3 .agents/skills/file-indexing/scripts/build_index.py --source local/repomix/repomix-output.json --out local/repomix --check` |
| List groups | `python3 .agents/skills/file-indexing/scripts/select.py "<task>" --manifest local/repomix/index.json` |
| Search a pack | `python3 .agents/skills/file-indexing/scripts/search_pack.py <pack> "<pattern>" --context 2` |
| Fresh compressed pack | `cat local/repomix/filelists/<id>.txt \| npx repomix@latest --stdin --compress --style xml --token-budget 40000 -o local/repomix/packs/<id>.xml` |
| Tree only | `npx repomix@latest --no-files --style json -o local/repomix/tree.json` |
| Domain pack | `npx repomix@latest --include "tools/**" --compress --split-output 2mb --token-budget 60000` |
| Targeted pack | `grep -Rl --exclude-dir=.git --exclude-dir=node_modules "<pattern>" . \| npx repomix@latest --stdin --compress --style xml` |
| Remote reference | `npx repomix@latest --remote owner/repo --compress --style json -o local/repomix/remote.json` |

## Pack recipes

| Need | Flags | Effect |
|---|---|---|
| Repository map | `--no-files --style json` | Structure and metadata only |
| Code overview | `--compress` | Signatures and imports, not bodies |
| Exact files | `--stdin` | Only the paths you selected |
| Large repo | `--split-output 2mb` | Top-level grouping, no file split |
| Per-file detail | `output.patterns` | Full docs, compressed code, structure-only data |
| Change context | `--include-diffs --include-logs --include-logs-count 20` | Recent edits and intent |
| Agent-native search | `--mcp --sandbox` | `grep_repomix_output`, partial `read_repomix_output` |
| Static skill export | `--skill-generate` | Repo reference as a Claude-style skill |

## Guardrails

| Risk | Control |
|---|---|
| 41 MB pack suffocates the model | `index.md` -> `select.py` -> slice; never load `index.json` directly |
| Private `local/` paths leak | Keep every output in `local/repomix/`; `local/` is gitignored |
| Secrets in a pack | Keep Secretlint on; scripts skip `.env` and key material by default; never share slices |
| Stale index | Run `--check` in pre-commit; rebuild after pulls |
| Oversized group | `oversized: true`; slice with `--max-chars` or repack with `--compress` |
| XML broken by code | Add `--parsable-style` |
| Submodule or vendor noise | Default excludes submodules; add `--include-submodules` only on demand |
| Context overspend | Budget 5% map, 25% pack, 70% task |

## Verify

| Check | Command |
|---|---|
| Manifest fresh | `python3 .agents/skills/file-indexing/scripts/build_index.py ... --check` |
| Group under budget | `python3 .agents/skills/file-indexing/scripts/select.py "<task>" --budget 40000` |
| Pack token guard | `npx repomix@latest ... --token-budget 40000` |
| Slice size | `ls -lh local/repomix/packs/` |
| No private paths in a public pack | `grep -R '"local/' local/repomix/packs/` |
