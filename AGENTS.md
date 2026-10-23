# Repository instructions

## Routing

| Trigger | Required behavior |
|---|---|
| Social project/brand content, posts, captions, drafting, posting, publishing, campaigns or distribution | Load `social-campaign` before authoring, including single-platform requests. Resolve the existing `local/<slug>/` project; explicitly read its root `AGENTS.md`, `loop/config.json`, loop safeguards, hypothesis and brand references. |
| Channel selection | Use only explicitly configured `allowed_channels`; never default to cross-platform work or copy prior drafts. Ask if project identity or channel policy is ambiguous. |
| Progression and publication | Follow the skill's content gates; do not self-approve. Use project-scoped publishing with current hash-bound approval and exact Page identity. A draft request is not publication approval. |
| Campaign execution | Invoke public repository CLIs directly. Use `post --text-file` for saved copy and public `preflight` for validation. No inline Python/subprocess wrappers, private-helper probes, or raw CDP/Playwright/JS workarounds. Inspect `--help`; missing capabilities require stopping and reporting or an explicitly requested, tested repository-tool change. This restriction governs campaign operations, not repository development/tests. |

```text
Request → social-campaign → policy → approval → publish
```

## Structured writing

Before drafting or substantially revising guides, plans, explanations, recommendations,
comparisons, or analysis, load the `structured-writing` skill. If the skill tool cannot
load it, read `.agents/skills/structured-writing/SKILL.md` directly and follow it.
Apply this to both chat responses and authored documents in this repository.

| Requirement | Rule |
|---|---|
| Format | Use tables for substantive information and at least one useful chart or diagram per deliverable (omit diagram when writing to CLI). Text outside tables has a hard cap of 100 words total. |
| Default tier | Discovery, unless the user requests Medium or Deep, or explicitly requests equivalent detail. |
| Word ceilings | Discovery: 1,500; Medium: 4,000; Deep: 10,000. Count all authored content. The 100-word outside-table cap is included, not additional. |
| Quality | No padding, invented data, redundant charts, or silent truncation. |
| Exclusions | Brief acknowledgments, clarification questions, code-only output, and creative/social copy do not require this format. |

Explicit user requirements and higher-priority instructions take precedence. These
are agent instructions, not a runtime output validator; do not claim mechanical
enforcement or an exact word count without checking it.

## File indexing

Always load `file-indexing` before repo search or edit planning; pair it with `structured-writing` for prose.

| Rule | Action |
|---|---|
| Load first | Read `.agents/skills/file-indexing/SKILL.md` or invoke the `file-indexing` skill before broad `grep`, `find`, `read`, or code search. |
| Index first | Start from `local/repomix/index.md`; run `python3 .agents/skills/file-indexing/scripts/select.py "<task>" --mode edit` to choose one group. |
| Search narrow | Run `python3 .agents/skills/file-indexing/scripts/search_pack.py <pack> "<pattern>"`; read only matching files or a `slice_pack.py` slice. |
| Never bulk-load | Do not paste `local/repomix/repomix-output.json` or the full `local/repomix/index.json` into context. |
| Refresh | Rebuild with `python3 .agents/skills/file-indexing/scripts/build_index.py` after pulls or structural changes; verify with `--check`. |
| Privacy | Keep packs, indexes, slices, and file lists under `local/`; never commit them. |
| Fallback | Widen to a parent or domain pack only when a group misses; use the full pack last. |
