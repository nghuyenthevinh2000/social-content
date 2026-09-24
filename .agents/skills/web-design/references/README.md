---
name: references
summary: Design-first prompting guidance and a JSON-driven browser preview for comparing hero directions with complete design specifications.
tags:
- web-design
- references
- ui-design
- design-systems
submodules:
  design-first-ui-prompting.md: Design-first UI prompting playbook and mindset by Meng To governing how UI layouts are architected, specified, and refined.
  design_hero_preview.html: Browser comparison tool that fetches the neighboring JSON and displays each hero with its complete design-first specification.
  design_hero_preview.json: Agent-editable design directions with hero choices and GOAL through NEGATIVE PROMPT specifications.
---

# Web Design References

Design guidance and an editable hero preview for choosing a visual direction before building a full page.

## Compare hero directions

1. Have the agent edit [`design_hero_preview.json`](./design_hero_preview.json): set `project` and add one or more entries to `directions`. Each entry contains `id`, `name`, `notes`, `design`, `hero`, `visual`, and `spec`. The three examples show distinct visual directions.
2. From the repository root, run:

   ```bash
   python3 -m http.server 8000 -d .agents/skills/web-design/references
   ```

3. Open `http://localhost:8000/design_hero_preview.html`. Select a direction card or use Previous/Next to compare heroes, palettes, and full specs. Reload after editing the JSON. A local HTTP server is required because browsers usually block `fetch` from `file://` pages.

Each `spec` follows all eight sections in the [design-first prompt skeleton](./design-first-ui-prompting.md#2-master-spec-driven-prompt-skeleton): `goal` (what, audience, successCriteria), `format` (canvas, safeMargins), `layout` (grid, placement, hierarchy), `typeSystem` (display, metadata, contrast), `colorMaterial` (foundation, surfaces, borders, signal), `copy` (headline, subtitle, actions), `constraints` (font, accent, container), and `negativePrompt` (list of guardrails). The hero renders its headline, subtitle, and up to two linked actions directly from `spec.copy`, so the preview and spec stay in sync. Keep the design tokens and written spec aligned when changing a direction.

For each entry, use `design.layout` = `split`, `centered`, or `editorial`; `design.visual` = `interface`, `abstract`, or `image`; and `design.font` = `editorial`, `modern`, or `classic`. For `image`, set `visual.imageUrl` to an HTTP URL or a path relative to this folder (for example, `./assets/hero.jpg`) and provide `visual.imageAlt`. The `interface` mode uses `visual.interface`. Colors, container width, corner radius, navigation, and labels live in `design` and `hero`. Action links support local `#anchor` targets within the preview.
