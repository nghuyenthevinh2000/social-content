# Skills Overview

This directory contains specialized agent skills used for content creation, storytelling, documentation, visual chart rendering, and writing style research.

## Available Skills

| Name | Description |
| --- | --- |
| [`documentation`](./.agents/skills/documentation/SKILL.md) | Creates, structures, and reviews technical documentation following the Diátaxis framework (tutorials, how-to guides, reference, and explanation pages). Use when a user needs to write or reorganize docs, structure a tutorial vs. a how-to guide, build reference docs or API documentation, create explanation pages, choose between Diátaxis documentation types, or improve existing documentation structure. |
| [`html-visual-chart`](./.agents/skills/html-visual-chart/SKILL.md) | Use when: the user asks to create a visual chart or infographic, render data as a stunning HTML chart, produce a screenshot of a visual, or save chart output to a visual folder. This skill authors a self-contained HTML file with embedded chart logic, then captures a full-page screenshot using Playwright. All output goes to a dedicated folder under `visual/<topic-slug>/`. |
| [`story-engine`](./.agents/skills/story-engine/SKILL.md) | Unified storytelling skill. Run before writing any story, post, caption, or narrative. Covers two sequential phases: (1) Story Integrity — interrogates whether the story earns the right to be told; (2) Story Craft — shapes and writes the story using a platform-specific format file from story-formats/. LinkedIn formats include Jescil-Richard and Jasmin Alić frameworks. |
| [`writing-style-analyzer`](./.agents/skills/writing-style-analyzer/SKILL.md) | Analyze the writing style of any content creator by name. The agent runs web searches to gather real writing samples, then synthesizes a structured "Style DNA" report covering voice, tone, sentence rhythm, hook patterns, vocabulary, structural conventions, and platform-specific habits. Reports are saved to `reflections/<creator-slug>.md`. Use when you want to study, emulate, or contrast a creator's style. |

## Output Directories

| Directory | Produced by | Contents |
| --- | --- | --- |
| [`visual/`](./visual/) | `html-visual-chart` | Self-contained HTML charts and PNG screenshots, one subfolder per topic |
| [`reflections/`](./reflections/) | `writing-style-analyzer` | Style DNA reports per creator, one markdown file per creator (`<creator-slug>.md`) |
