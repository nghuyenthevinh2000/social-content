# Skills Overview

This directory contains specialized agent skills used for content creation, storytelling, documentation, and visual chart rendering.

## Available Skills

| Name | Description |
| --- | --- |
| [`documentation`](./.agents/skills/documentation/SKILL.md) | Creates, structures, and reviews technical documentation following the Diátaxis framework (tutorials, how-to guides, reference, and explanation pages). Use when a user needs to write or reorganize docs, structure a tutorial vs. a how-to guide, build reference docs or API documentation, create explanation pages, choose between Diátaxis documentation types, or improve existing documentation structure. |
| [`html-visual-chart`](./.agents/skills/html-visual-chart/SKILL.md) | Use when: the user asks to create a visual chart or infographic, render data as a stunning HTML chart, produce a screenshot of a visual, or save chart output to a visual folder. This skill authors a self-contained HTML file with embedded chart logic, then captures a full-page screenshot using Playwright. All output goes to a dedicated folder under `visual/<topic-slug>/`. |
| [`story-engine`](./.agents/skills/story-engine/SKILL.md) | Unified storytelling skill. Run before writing any story, post, caption, or narrative. Covers two sequential phases: (1) Story Integrity — interrogates whether the story earns the right to be told; (2) Story Craft — shapes and writes the story using a platform-specific format file from story-formats/. LinkedIn formats include Jescil-Richard and Jasmin Alić frameworks. |
