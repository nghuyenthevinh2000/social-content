# Social Content & Skills Overview

This repository contains specialized agent skills, topic research, draft posts, visual assets, and style analyses used for end-to-end content creation, storytelling, and publishing.

## Available Skills

| Name | Description |
| --- | --- |
| [`beautiful-html-templates`](./.agents/skills/beautiful-html-templates/SKILL.md) | A library of 34+ reusable, production-ready HTML slide deck templates and styling systems across diverse aesthetics (editorial, brutalist, minimal, playful, retro, technical, bold). Use when building, designing, generating, or adapting interactive HTML slide presentations, keynotes, or pitch decks with tone-first template matching, live previews, and design-system adaptations. |
| [`documentation`](./.agents/skills/documentation/SKILL.md) | Creates, structures, and reviews technical documentation following the Diátaxis framework (tutorials, how-to guides, reference, and explanation pages). Use when a user needs to write or reorganize docs, structure a tutorial vs. a how-to guide, build reference docs or API documentation, create explanation pages, choose between Diátaxis documentation types, or improve existing documentation structure. |
| [`humanizer`](./.agents/skills/humanizer/SKILL.md) | Rewrite AI-sounding text so it reads naturally without changing what it says. Use when editing or reviewing prose for inflated claims, sales language, vague sources, repetitive structure, stock AI words, passive voice, filler, or chatbot artifacts. Based on Wikipedia's "Signs of AI writing." |
| [`infographic`](./.agents/skills/infographic/SKILL.md) | Author high-impact visual infographics and executive one-pagers as self-contained HTML files with embedded chart logic and Playwright 2x Retina screenshots. Combines 5 structural infographic templates (business plans, executive summaries, enterprise architecture stacks, financial reports, social media dashboards) with 34 curated design styles. Use when the user asks to create an infographic, one-pager, visual chart, executive briefing visual, or architecture stack. |
| [`story-engine`](./.agents/skills/story-engine/SKILL.md) | Unified storytelling skill. Run before writing any story, post, caption, or narrative. Covers two sequential phases: (1) Story Integrity — interrogates whether the story earns the right to be told; (2) Story Craft — shapes and writes the story using a platform-specific format file from story-formats/. LinkedIn formats include Jescil-Richard and Jasmin Alić frameworks. |
| [`writing-style-analyzer`](./.agents/skills/writing-style-analyzer/SKILL.md) | Analyze the writing style of any content creator by name. The agent runs web searches to gather real writing samples, then synthesizes a structured "Style DNA" report covering voice, tone, sentence rhythm, hook patterns, vocabulary, structural conventions, and platform-specific habits. Reports are saved to `reflections/<creator-slug>.md`. Use when you want to study, emulate, or contrast a creator's style. |

## Repository Structure & Directories

| Directory | Purpose / Contents |
| --- | --- |
| [`topics/`](./topics/) | Unified thematic content directories containing written posts, article series, deep-dive research, presentations, and visual assets organized by topic slug for smooth narrative continuation. |
| [`reflections/`](./reflections/) | Style DNA reports, creator style analyses, and retrospective reviews (e.g., produced by `writing-style-analyzer`). |
| [`projects/`](./projects/) | Dedicated sub-projects and external repositories managed as submodules (e.g., [`projects/innovation-research`](./projects/innovation-research/)). |
| [`.agents/skills/`](./.agents/skills/) | Custom agent skills and workflows powering the content generation, analysis, humanization, presentation design, and refinement pipeline. |

## Skill-Selection Router (Jev Hook)

A [TypeSafe](https://typesafe.ai)-backed PreInvocation hook picks the right
skill *and* the right resource inside it (template/reference) for every
request, before the agent reasons on its own.

Quick install into another workspace:

```bash
./scripts/install-skill-hook.sh /path/to/other/workspace
```

This vendors `scripts/skill_selector.py` + `scripts/skill_injector_hook.py`,
fetches `python-dotenv` / `pyyaml` / `typesafe-sdk` via `uv`, and registers
the hook in `.agents/hooks.json`. Requires `uv` and a `TYPESAFE_API_KEY`.

See **[reflections/skill-selection-router-hook-guide.md](./reflections/skill-selection-router-hook-guide.md)**
for the full guide: how it works, all relevant files, install steps for
this repo vs. other workspaces, testing, and the optional visual demo.
