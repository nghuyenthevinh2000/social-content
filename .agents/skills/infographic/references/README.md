---
name: references
summary: JSON-driven browser wireframe preview with a one-command launcher for comparing landscape and portrait content plans across independent design styles.
tags: [infographic, wireframe, preview, planning]
submodules:
  preview.js: Local Node.js launcher that opens the HTML and serves its sibling JSON automatically.
  wireframe_preview.html: Interactive browser preview with independent layout and style choices, scaled canvas, and layout checks.
  wireframe_preview.json: Editable sample content directions and reusable palettes, typography, and design styles.
---

# Infographic wireframe preview

Use this optional planning tool alongside the [infographic skill workflow](../SKILL.md). The example JSON shows two directions on standard **1280 × 720 landscape** and **720 × 1280 portrait** canvases, plus four styles you can apply to either direction. The preview is a content and aesthetic study, not the final infographic.

1. After the skill's confirmation gate, copy `preview.js`, `wireframe_preview.html`, and `wireframe_preview.json` into the chosen output directory. Edit the JSON copy to reflect the **approved** headline, real section copy, metrics, chart labels and values, template, and style. Keep these reusable examples intact. If the proposed plan changes materially, obtain approval again.
2. From the output directory, launch the preview:

   ```bash
   node preview.js
   ```

3. The browser opens automatically and the HTML loads **`wireframe_preview.json`** from the same directory. Select a content direction, then compare design choices independently: Cobalt Grid, Editorial Forest, Neo-Grid Bold, and Monochrome. Changing direction restores that direction's default style. Reload after editing the JSON. Press Ctrl+C to stop the launcher. Browsers block automatic reads of neighboring JSON files from `file://`, so opening the HTML directly cannot auto-load the JSON.
4. Correct all validation errors and visible text overflow. Keep the approved `layout_content.md` alongside `index.html` and `output.png`, and compare the final HTML and screenshot to that plan.

## JSON structure

`project` names the study. `designs` is an array of styles with `id` (matching a design folder), `name`, `note`, `colors` (`paper`, `ink`, `accent`, `line`, `chart`), `displayFont`, and `bodyFont`. `directions` is an array of plans, each with `id`, `name`, `orientation` (`landscape` or `portrait`), `template`, `style` (the default design ID), `rationale`, and ordered `bands`. Each band has `label`, `height` (CSS pixels), and ordered `cells`; each cell has `type` (`text`, `metric`, `chart`, `source`), `width` (CSS pixels), and `text` (final visible content; `\n` creates separate lines). Use actual content rather than placeholder instructions. For production, consult the chosen [style specification](../design/README.md); the preview approximates its visual language.

Band heights must add to **720** or **1280** respectively. Cell widths in **every band** must add to **1280** or **720** respectively. The preview reports invalid totals and overflowing text and scales the entire wireframe without cropping it. The HTML and JSON are a planning aid; the final `index.html` must remain self-contained.
