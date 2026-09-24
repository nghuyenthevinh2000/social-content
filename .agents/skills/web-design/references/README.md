---
name: references
summary: Design-first prompting guidance and a JSON-driven preview for comparing hero directions, production page-content wireframes, and complete specifications.
tags:
- web-design
- references
- ui-design
- design-systems
submodules:
  design-first-ui-prompting.md: Design-first UI prompting playbook and mindset by Meng To governing how UI layouts are architected, specified, and refined.
  preview.js: Local Node preview server that serves the HTML and JSON from this folder or a project directory and opens the browser.
  wireframe_preview.html: Browser comparison tool rendering each hero, adjustable section-by-section production wireframe, and complete design specification.
  wireframe_preview.json: Agent-editable hero directions with exact page copy, ordered sections and cells, and full design specifications.
---

# Web Design References

Design guidance and an editable hero preview for choosing a visual direction before building a full page.

## Compare hero directions

1. Have the agent edit [`wireframe_preview.json`](./wireframe_preview.json): set `project` and add one or more entries to `directions`. Each entry contains `id`, `name`, `notes`, `wireframe`, `design`, `hero`, `visual`, and `spec`. The three examples show distinct visual directions and wireframes.
2. From the repository root, run [`preview.js`](./preview.js) with Node:

   ```bash
   node .agents/skills/web-design/references/preview.js
   ```

3. The script prints a localhost URL and opens the preview in your browser. Select a direction card or use Previous/Next to compare heroes, wireframes, palettes, and full specs. Reload after editing the JSON. A local HTTP server is required because browsers usually block `fetch` from `file://` pages. Press Ctrl+C to stop the server.

To serve a project-specific copy instead, pass the folder containing **both** `wireframe_preview.html` and `wireframe_preview.json`:

```bash
node .agents/skills/web-design/references/preview.js scripts/my-site/static
```

### Plan the actual page content

Inspired by the infographic skill's [Step 1 layout-content wireframe](../../infographic/SKILL.md#step-1--plan--confirm-with-user-mandatory-gate), each direction includes a `wireframe` table that specifies the **actual page to build**, from header through footer. Every row is a page section, and its cells are ordered left to right. Write the final visible copy in `text`, not descriptions such as “add a hero” or “include some metrics.” Add metrics only when verified; use `image` cells with real asset URLs and alt text. Update the hero's `spec.copy` and `hero` fields to match the Hero and Header rows.

`wireframe.title` is the table heading. Add, remove, or reorder `rows`; each row has `label` (such as `Body 01 · Work`) and an ordered `cells` array. Each cell has `type` (`brand`, `text`, `link`, `image`, `visual`, or `space`) and `pixels`, the exact desktop width in CSS pixels (1–1600 for content; 0–1600 for open space). Use `text` for exact visible words, `src` and `alt` for an image, and `href` for a link destination. Newlines in `text` render as separate lines. For example:

```json
{
  "label": "Header",
  "cells": [
    { "type": "brand", "text": "FORMA®", "pixels": 180 },
    { "type": "space", "pixels": 50 },
    { "type": "link", "text": "Work", "href": "#work", "pixels": 90 },
    { "type": "link", "text": "Studio", "href": "#studio", "pixels": 90 },
    { "type": "link", "text": "Contact", "href": "#contact", "pixels": 100 }
  ]
}
```

The browser renders each row as an adjustable side-by-side strip. Rows wider than the viewport can scroll horizontally; on small screens, content cells stack and blank space disappears. Selecting another direction replaces the entire wireframe. The section is omitted when `rows` is empty. Build the final website in this order with this copy, and revise the JSON first if the planned content changes.

Each `spec` follows all eight sections in the [design-first prompt skeleton](./design-first-ui-prompting.md#2-master-spec-driven-prompt-skeleton): `goal` (what, audience, successCriteria), `format` (canvas, safeMargins), `layout` (grid, placement, hierarchy), `typeSystem` (display, metadata, contrast), `colorMaterial` (foundation, surfaces, borders, signal), `copy` (headline, subtitle, actions), `constraints` (font, accent, container), and `negativePrompt` (list of guardrails). The hero renders its headline, subtitle, and up to two linked actions directly from `spec.copy`, so the preview and spec stay in sync. Keep the design tokens and written spec aligned when changing a direction.

For each entry, use `design.layout` = `split`, `centered`, or `editorial`; `design.visual` = `interface`, `abstract`, or `image`; and `design.font` = `editorial`, `modern`, or `classic`. For `image`, set `visual.imageUrl` to an HTTP URL or a path relative to this folder (for example, `./assets/hero.jpg`) and provide `visual.imageAlt`. The `interface` mode uses `visual.interface`. Colors, container width, corner radius, navigation, and labels live in `design` and `hero`. Action links support local `#anchor` targets within the preview.
