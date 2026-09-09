# Social Content & Skills Overview

This repository contains specialized agent skills, topic research, draft posts, visual assets, and style analyses used for end-to-end content creation, storytelling, and publishing.

## Available Skills

| Name | Description |
| --- | --- |
| [`beautiful-html-templates`](./.agents/skills/beautiful-html-templates/SKILL.md) | A library of 34+ reusable, production-ready HTML slide deck templates and styling systems across diverse aesthetics (editorial, brutalist, minimal, playful, retro, technical, bold). Use when building, designing, generating, or adapting interactive HTML slide presentations, keynotes, or pitch decks with tone-first template matching, live previews, and design-system adaptations. |
| [`documentation`](./.agents/skills/documentation/SKILL.md) | Creates, structures, and reviews technical documentation following the Diátaxis framework (tutorials, how-to guides, reference, and explanation pages). Use when a user needs to write or reorganize docs, structure a tutorial vs. a how-to guide, build reference docs or API documentation, create explanation pages, choose between Diátaxis documentation types, or improve existing documentation structure. |
| [`humanizer`](./.agents/skills/humanizer/SKILL.md) | Rewrite AI-sounding text so it reads naturally without changing what it says. Use when editing or reviewing prose for inflated claims, sales language, vague sources, repetitive structure, stock AI words, passive voice, filler, or chatbot artifacts. Based on Wikipedia's "Signs of AI writing." |
| [`one-pager-html`](./.agents/skills/one-pager-html/SKILL.md) | Use when: the user asks to create a visual chart or infographic, render data as a stunning HTML chart, produce a screenshot of a visual, or save chart output. This skill authors a self-contained HTML file with embedded chart logic, then captures a full-page screenshot using Playwright. All output goes to a dedicated folder under `topics/<topic-slug>/`. |
| [`story-engine`](./.agents/skills/story-engine/SKILL.md) | Unified storytelling skill. Run before writing any story, post, caption, or narrative. Covers two sequential phases: (1) Story Integrity — interrogates whether the story earns the right to be told; (2) Story Craft — shapes and writes the story using a platform-specific format file from story-formats/. LinkedIn formats include Jescil-Richard and Jasmin Alić frameworks. |
| [`writing-style-analyzer`](./.agents/skills/writing-style-analyzer/SKILL.md) | Analyze the writing style of any content creator by name. The agent runs web searches to gather real writing samples, then synthesizes a structured "Style DNA" report covering voice, tone, sentence rhythm, hook patterns, vocabulary, structural conventions, and platform-specific habits. Reports are saved to `reflections/<creator-slug>.md`. Use when you want to study, emulate, or contrast a creator's style. |

## Repository Structure & Directories

| Directory | Purpose / Contents |
| --- | --- |
| [`posts/`](./posts/) | Written social media posts, article series, narrative drafts, and shortened content iterations organized by topic or series slug. |
| [`topics/`](./topics/) | Deep-dive topic research, background context, project specifications, proposals, source documents, presentation decks, and assets for specific themes or RFPs. |
| [`reflections/`](./reflections/) | Style DNA reports, creator style analyses, and retrospective reviews (e.g., produced by `writing-style-analyzer`). |
| [`.agents/skills/`](./.agents/skills/) | Custom agent skills and workflows powering the content generation, analysis, humanization, presentation design, and refinement pipeline. |
