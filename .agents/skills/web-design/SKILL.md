---
name: web-design
description: "Design and build web pages and interfaces using a preview-first workflow. Use for websites, landing pages, dashboards, portfolios, pricing pages, UI redesigns, and layout work. Requires a project-specific browser preview and complete design spec before implementing the full page."
---

# Web Design: Preview First, Then Build

For website and UI design work, **produce a browser-loadable hero preview and obtain the user's explicit approval before building the full interface**. A written design brief, `DESIGN_HERO.md`, layout demo, or finished `index.html` does not replace this deliverable. The preview is a separate artifact the user can open and compare.

## Workflow

### 1. Understand the page

- Read the user's goal, audience, required content, existing app routes/data, and target web-serving directory. Inspect only the relevant files.
- Select a layout archetype from [`layouts/README.md`](layouts/README.md); consult its `SKILL.md` and demo if useful. Use real product content and data rather than placeholder claims.
- Choose a small set of distinct hero directions (or one if the user has locked the direction). Specify layout, typography, one signal color, visual treatment, copy, and constraints. Plan actual page content first: headline/brand, verified metrics if any, sections, visual evidence, and takeaway/actions. Use the eight-part skeleton in [`references/design-first-ui-prompting.md`](references/design-first-ui-prompting.md).

### 2. Create and showcase the project preview — required

Before writing the full page, create **both** `wireframe_preview.html` and `wireframe_preview.json` next to each other in the project's web-serving directory (for example, `scripts/my-site/static/`). Copy [`references/wireframe_preview.html`](references/wireframe_preview.html) as the HTML template and [`references/wireframe_preview.json`](references/wireframe_preview.json) as the JSON starting point; replace sample directions with the actual project's choices. The HTML fetches its sibling JSON by relative URL. Keep the shared reference templates intact.

- Fill each JSON direction's `wireframe.rows` as an **exact page wireframe**, from header through footer. Each row names a section; its ordered `cells` specify the actual visible copy, image asset/alt, link label/destination, or intentional empty space. Add/remove/reorder rows and cells and size every cell with `pixels` (CSS pixels) to match the intended page. Do not substitute abstract content categories or invented metrics. Then fill `design`, `hero`, `visual`, and all eight `spec` sections: GOAL, FORMAT, LAYOUT, TYPE SYSTEM, COLOR + MATERIAL, COPY, CONSTRAINTS, NEGATIVE PROMPT. `spec.copy` drives the hero headline, subtitle, and actions; keep it identical to the matching wireframe cells. See [`references/README.md`](references/README.md) for the schema.
- Serve the **project copy** with `node .agents/skills/web-design/references/preview.js <web-serving-directory>`. The script prints a localhost URL and opens the browser; check that the JSON loads and the direction selector works. See [`references/README.md`](references/README.md) for setup. `file://` will not reliably fetch JSON.
- **Show the user the working preview**: give its project path and reachable URL, or a rendered screenshot when available; explain how to compare both directions and their wireframes. Do this before settling on the final visual direction. A URL for the shared reference template, a spec-only document, or a claim that a preview exists is insufficient.
- **Pause for approval**: ask the user to review the preview and approve a direction (or request changes). End the turn here if approval has not yet arrived. Showing a URL, receiving an unrelated reply, or interpreting silence as consent does not count as approval.

**Approval gate:** Do not create or modify the finished page (`index.html`, application UI, styles, components, routes, etc.) until the project-specific HTML and JSON are present, the preview has been shown, and the user has explicitly approved a direction. Revisions to the preview require showing the revised preview and obtaining approval before implementation. If the user already chose a direction, preview that direction anyway and ask for approval. If no browser is available, verify both files are served and provide the URL and the command to open it; still wait for approval.

### 3. Build from the approved direction

- Build the real page in the `wireframe.rows` order, using their exact text, images, links, and intended cell relationships; carry the preview's tokens and typography through the layout. Implement the user's required interactions and backend contract. If copy or sections need to change, update the wireframe first so it remains the source of truth. The preview is a design checkpoint, not the finished product.
- Build section by section. Use semantic HTML, responsive grid, consistent spacing and border weights, legible contrast, and accessible controls. Prefer deliberate framing and whitespace over unnecessary cards, gradients, and decorative widgets.
- Test the real page at desktop and mobile widths and exercise its actual interactions/API flows. Adjust the preview JSON if the approved direction changes so the showcase stays accurate.

### 4. Verify and hand off

- Verify the preview HTML, JSON fetch, and direction switching; validate the JSON and test the finished app as appropriate.
- Follow repository frontmatter rules for every directory touched. In the final handoff, link or give the exact path/URL to the **project-specific preview** and the finished page, plus the verification performed.

## Reference files

- [`references/README.md`](references/README.md): JSON fields and local preview setup.
- [`layouts/README.md`](layouts/README.md): available layout systems and demos.
- [`references/design-first-ui-prompting.md`](references/design-first-ui-prompting.md): full design-spec skeleton and craft guidance.
