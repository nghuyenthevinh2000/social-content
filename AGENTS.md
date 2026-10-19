# Repository instructions

## Structured writing

Before drafting or substantially revising guides, plans, explanations, recommendations,
comparisons, or analysis, load the `structured-writing` skill. If the skill tool cannot
load it, read `.agents/skills/structured-writing/SKILL.md` directly and follow it.
Apply this to both chat responses and authored documents in this repository.

| Requirement | Rule |
|---|---|
| Format | Use tables for substantive information and at least one useful chart or diagram per deliverable. Text outside tables has a hard cap of 100 words total. |
| Default tier | Discovery, unless the user requests Medium or Deep, or explicitly requests equivalent detail. |
| Word ceilings | Discovery: 1,500; Medium: 4,000; Deep: 10,000. Count all authored content. The 100-word outside-table cap is included, not additional. |
| Quality | No padding, invented data, redundant charts, or silent truncation. |
| Exclusions | Brief acknowledgments, clarification questions, code-only output, and creative/social copy do not require this format. |

Explicit user requirements and higher-priority instructions take precedence. These
are agent instructions, not a runtime output validator; do not claim mechanical
enforcement or an exact word count without checking it.
