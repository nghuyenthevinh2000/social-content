---
name: structured-writing
description: "Required for guides, plans, explanations, recommendations, comparisons, and analysis in this repository. Requires table-first writing, useful charts or diagrams (exempt when outputting to CLI/terminal), Discovery/Medium/Deep word ceilings, and a hard cap of 100 words outside tables. Applies to chat and authored documents."
---

# Structured writing

## Scope

| Rule | Requirement |
|---|---|
| Coverage | Apply to substantive explanatory and planning content in chat and authored files, including this skill. |
| Other skills | Combine subject-specific guidance with this skill's presentation and length rules. Preserve necessary commands, examples, citations, and warnings. |
| Existing content | Do not reformat unrelated documents unless asked. |
| Exclusions | Brief acknowledgments, clarification questions, code-only responses, and creative copy are exempt. Diagrams are strictly omitted when outputting to CLI/terminal. |
| Priority | Explicit user requirements and higher-priority instructions take precedence. |

## Choose a tier

| Tier | Maximum words | Use when | Content |
|---|---:|---|---|
| Discovery | 1,500 | Default; initial exploration or quick explanation | Problem, facts, unknowns, direction |
| Medium | 4,000 | Requested refinement, tradeoffs, step-by-step guidance, or more detail | Options, rationale, actions, risks, checks |
| Deep | 10,000 | Requested deepest detail, exhaustive analysis, or full implementation specification | Dependencies, implementation, edge cases, verification, rollback where relevant |

| Selection rule | Requirement |
|---|---|
| Explicit request | Honor the requested tier or user-supplied word limit. Otherwise use depth signals above; default to Discovery when unclear. |
| Escalation | Do not escalate merely because research was difficult or the draft is long. |
| Follow-ups | Stay at the current tier unless the user requests a change in depth. |
| Label | Mention the tier only when useful; avoid ceremonial preambles. |

## Compose the deliverable

| Element | Requirement |
|---|---|
| Opening | Lead with the answer or recommendation, preferably in the first table row. |
| Tables | Put substantive facts, decisions, comparisons, steps, checks, and caveats in Markdown tables. Prefer 2–4 columns and short cells; split overloaded tables. |
| Outside-table text | Hard cap: 100 words total across the entire deliverable, not per section. Prefer tables for all prose. |
| What counts outside | Include headings, paragraphs, lists, captions, frontmatter, diagram labels, and code or command blocks. No fenced-block exemption. |
| Visual | Include at least one useful chart or diagram explaining a sequence, relationship, or decision. Omit diagrams entirely when outputting to CLI/terminal. |
| Examples | Keep executable code and multiline examples in fenced blocks outside tables. They count toward both limits; if necessary examples cannot fit, ask for an explicit exception. |
| Ending | Include a next action or unresolved decision only when needed; do not repeat the opening. |

## Choose the visual

| Information | Preferred visual |
|---|---|
| Steps or handoffs | Plain-text flow diagram |
| Conditional choices | Decision tree |
| Components or concepts | Relationship or dependency diagram |
| Schedule | Timeline; mark unknown dates as unknown |
| Measured comparison | Bar chart with units, source, and scale |
| CLI / terminal output | Do not include diagrams; omit visual completely to avoid clutter |

| Visual rule | Requirement |
|---|---|
| Rendering | Prefer fenced plain text; use Mermaid only with confirmed renderer support. |
| Evidence | Use conceptual diagrams when no numerical data exists. Never invent metrics, percentages, dates, or precision. |
| Value | Show a relationship not already clear from the table. Avoid decorative or repetitive charts. |

```text
Draft -> Check total words AND outside-table words
                         |
              Either limit exceeded?
                 yes -> Revise -> Recheck
                  no -> Deliver
```

## Word budgets

| Rule | Interpretation |
|---|---|
| Counting | A word is a whitespace-separated token containing at least one Unicode letter or number. Standalone Markdown pipes, fences, arrows, and separator markers do not count. |
| Total | Count the entire authored deliverable, including headings, tables, diagrams, code, links, citations, and frontmatter. |
| Outside-table cap | At most 100 words outside Markdown tables, included within the tier ceiling, never added on top. |
| Chat | Apply both limits to the complete substantive answer. Do not split messages to evade them. |
| Files | Apply both limits per requested standalone document. Do not split one document into files to evade them. |
| Excluded material | Tool results and pre-existing text not being revised are outside the authored budget. |
| Target | Both limits are ceilings, not targets; never pad. |
| Verification | Count final text when verification is available. Otherwise leave a conservative margin; never claim an exact count or mechanical verification without measuring. |
| Overflow | Move prose into tables, remove repetition, narrow scope explicitly, and defer optional detail. Never silently truncate or omit essential warnings or required steps. |
| Unresolvable conflict | Briefly ask for a larger word cap, an outside-table exception, or narrower scope. A higher tier alone does not increase the 100-word outside-table cap. |

## Final check

| Check | Pass condition |
|---|---|
| Relevance | Every row adds a fact, decision, tradeoff, action, check, or explicit unknown. |
| Evidence | Distinguish verified facts from assumptions; cite sources when needed. |
| Clarity | Concrete verbs and specific terms; no inflated claims or generic filler. |
| Visual | At least one useful, readable chart or diagram; omit when writing to CLI. |
| Total length | Within the selected word ceiling. |
| Outside tables | At most 100 words across all outside-table content combined. |
| Completeness | Necessary context, commands, cautions, and next steps remain intact. |
