# Skills Overview

This directory contains specialized agent skills used for content creation, storytelling, documentation, and visual chart rendering.

## Available Skills

| Name | Description |
| --- | --- |
| [`documentation`](./documentation/SKILL.md) | Creates, structures, and reviews technical documentation following the Diátaxis framework (tutorials, how-to guides, reference, and explanation pages). Use when a user needs to write or reorganize docs, structure a tutorial vs. a how-to guide, build reference docs or API documentation, create explanation pages, choose between Diátaxis documentation types, or improve existing documentation structure. |
| [`html-visual-chart`](./html-visual-chart/SKILL.md) | Use when: the user asks to create a visual chart or infographic, render data as a stunning HTML chart, produce a screenshot of a visual, or save chart output to a visual folder. This skill authors a self-contained HTML file with embedded chart logic, then captures a full-page screenshot using Playwright. All output goes to a dedicated folder under `visual/<topic-slug>/`. |
| [`jescil-richard-storytelling`](./jescil-richard-storytelling/SKILL.md) | Use when writing social media posts, captions, LinkedIn content, or any short-form story that needs to hook, connect emotionally, and drive action. Use before drafting any narrative content. |
| [`story-integrity-interrogation`](./story-integrity-interrogation/SKILL.md) | Run before writing any story, post, or narrative. This skill interrogates whether a story deserves to be told, whether the protagonist earns their transformation, and whether the storyteller's intent is honest. Pair with `jescil-richard-storytelling`, which handles craft and execution. |
