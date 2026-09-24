---
name: infographic
description: "Use when: the user asks to create an infographic, one-pager, visual chart, render data as an HTML chart, produce a screenshot of a visual, or save chart output. This skill authors a self-contained HTML infographic in a standard 16:9 landscape or 9:16 portrait canvas that fits within one browser screen without scrolling, then captures a viewport screenshot with Playwright. Save output in a directory appropriate to the user's request or project context. The agent must ALWAYS confirm first with the user: (1) infographic layout template, (2) design style, (3) rationale for both, (4) content outline, and (5) a dimensioned ASCII layout-content wireframe. ONLY proceed after explicit user approval."
---

# infographic: Author HTML infographics, one-pagers, and charts

## What this skill does

You produce a **self-contained, single-file HTML visual** (charts, infographics, data stories) — no build step, no external bundler. The entire visual must fit within one browser viewport without horizontal or vertical scrolling. After writing the file, capture a **viewport screenshot** with Playwright and save it alongside the HTML in the output folder.

Every one-pager is composed of two coordinated choices:
1. **Infographic Template (Layout & Structure)** from `layout/`: Defines the layout geometry, structural hierarchy, data containers, tables, and chart visualization types.
2. **Design Style (Aesthetic & Skin)** from `design/`: Defines the visual personality, color palette tokens, typography pairing (Google Fonts), borders, corner radii, shadow treatments, and emotional tone.

> [!IMPORTANT]
> **MANDATORY CONFIRMATION GATE**: You must **ALWAYS** confirm with the user first before creating files or taking screenshots:
> 1. **Which Infographic Template** to use (from `layout/` or custom layout).
> 2. **Which Design Style** to apply (from `design/` — 34 production-ready styles).
> 3. **Why** you recommend this combination (rationale for layout structure + aesthetic match).
> 4. **The planned content & data outline** to be included on the 1-pager.
> 5. **The orientation** (16:9 landscape or 9:16 portrait) and how the proposed content fits on one screen.
> 6. **A dimensioned layout-content wireframe** showing real section titles, data, and pixel-height bands across the full canvas, following the example below.
> **DO NOT** write code, create directories, or execute screenshots until the user has explicitly approved.

The workflow is:

1. **Plan & Confirm (MANDATORY GATE)** — Select layout, style, and orientation; draft a dimensioned layout-content wireframe with the actual content; ask the user for approval. Stop calling tools and wait for confirmation.
2. **Author** — Once approved, choose an output directory based on the user's requested location or project conventions, save the approved plan as `<output-dir>/layout_content.md`, then author `<output-dir>/index.html` from that plan with the chosen template and style.
3. **Screenshot** — Run Playwright Retina capture utility (`scripts/screenshot-retina.js`) to capture `<output-dir>/output.png`.
4. **Verify** — Confirm the PNG exists and embed it in your reply.

---

## Skill asset resolution

This skill is repo-local. Resolve the **git repo root** that contains this skill file to locate its templates, design styles, and screenshot utility.

Resolve the repo root at runtime before running any command:

```bash
REPO_ROOT=$(git rev-parse --show-toplevel)
```

Output may live anywhere the user requests. Do not use `$REPO_ROOT` as the output base unless the chosen directory is inside this repository.

---

## Output directory

Use the directory specified by the user. If no location is specified, choose a suitable directory using the current project or working-directory conventions. Keep the HTML and screenshot together:

```
<output-dir>/
├── layout_content.md  approved, dimensioned content wireframe
├── index.html         chart (self-contained)
└── output.png         single-viewport screenshot
```

If creating a new directory for the visual, give it a subject-based name unless the user or project already provides a naming convention. Resolve the chosen directory to an absolute path for capture commands.

Create the folder before writing files:

```bash
OUTPUT_DIR="/absolute/path/to/chosen/output-directory"
mkdir -p "$OUTPUT_DIR"
```

---

## Step 1 — Plan & Confirm with User (MANDATORY GATE)

Before writing any files, creating directories, or running commands, you **MUST STOP AND ASK FOR USER APPROVAL** with the following elements:

1. **Infographic Template (Structure & Layout)**:
   - Choose a template from the [layout index](layout/README.md), or explain if a custom layout is needed.
   - Check the template's `design.md` for specific content slots and layout rules.
2. **Design Style (Aesthetic & Skin)**:
   - Choose a style from the [design index](design/README.md).
   - Specify the target color mood and typography pairing (Google Fonts).
3. **Rationale for Both**:
   - Explain why this **layout** fits the data format (KPI grids, comparison tables, multi-tier architecture, line charts, etc.).
   - Explain why this **aesthetic style** matches the intended tone, brand voice, and audience.
4. **Planned Content Outline**:
   - Headline and branding
   - Key metrics / KPI cards
   - Core sections and tables/lists
   - Chart visualization type and data points
   - Takeaways or quote
   - Choose 16:9 landscape or 9:16 portrait; trim or reorganize the outline if it would require scrolling.
5. **Layout-Content Wireframe (REQUIRED)**:
   - Show the actual headline, sections, labels, metrics, chart data, and footer in a text-box/ASCII layout, not just generic placeholders.
   - Provide a second, vertically annotated view like the example below: each major band has a pixel height and start/end Y coordinate. Heights must sum to **720 px landscape** or **1280 px portrait**, with no gaps, overlaps, or overflow. Split panels must show their content and fit within their shared band.
   - State the chosen width and height, the content hierarchy, and what will be shortened or omitted to keep the text and charts readable on one screen. Adapt the example's measurements to the actual content and canvas.

Example of the annotated view (landscape; replace all content and heights to match the proposal):

```text
1280 × 720 (16:9)
+--------------------------------------------------------+ [Y: 0]
| HEADER: Actual headline and context              100px |
+--------------------------------------------------------+ [Y: 100]
| INSIGHT: Key metric and supporting explanation   180px |
+--------------------------------------------------------+ [Y: 280]
| EVIDENCE: Chart / comparison with data labels     300px |
+--------------------------------------------------------+ [Y: 580]
| TAKEAWAY: Source, conclusion, footer              140px |
+--------------------------------------------------------+ [Y: 720]
Total: 100 + 180 + 300 + 140 = 720px
```

The [wireframe preview reference](references/README.md) contains JSON-driven landscape and portrait examples. You can inspect these examples while planning, but do not edit files or run the preview before the user approves the proposed content and wireframe.

> [!CAUTION]
> **DO NOT PROCEED TO STEP 2 UNTIL THE USER EXPLICITLY APPROVES.** Stop tool execution and wait for user feedback or approval.

---

## Template and style indexes

- [Layout templates](layout/README.md): Browse source structures, previews, and content slots. Reflow source dimensions to the one-screen canvas specified below.
- [Design styles](design/README.md): Browse palettes, typography pairings, and component treatments.

---

## Step 2 — Author index.html (Synthesizing Structure + Design Style)

> **Prerequisite**: Only proceed with this step after the user has explicitly approved the proposed infographic template, design style, rationale, and content outline from Step 1.

First save the approved wireframe as `<output-dir>/layout_content.md`. Keep its section order, exact content, pixel-height allocations, and canvas dimensions aligned with the HTML. If the content or section allocations must materially change, show the revised wireframe to the user and get approval before continuing.

For a visual check, optionally follow the [wireframe preview instructions](references/README.md): copy the launcher, HTML, and JSON into the chosen output directory, fill in the approved content, and run `node preview.js` to load `wireframe_preview.json` automatically. Compare design styles independently of the content layout, then validate all band heights and cell widths. The preview helps refine the plan; the approved `layout_content.md` remains the source of truth for the final infographic.

### How to Combine Layout Structure and Design Style

When creating the 1-pager in `<output-dir>/index.html`:

1. **Start with the Infographic Template Structure**:
   Copy the chosen template from `layout/<template>/` or use its DOM hierarchy (header, cards, KPI grids, tables, charts), then adapt it to the approved `layout_content.md` rather than forcing the content into the source template's sections. Some template `design.md` examples use a fixed output path; use `$OUTPUT_DIR` instead when following their copy or screenshot commands.
2. **Apply the Chosen Design Style**:
   Open `design/<style>/design.md` and `design/<style>/template.json` to extract:
   - **Google Fonts**: Add the `<link>` for the style's `display` and `body` fonts into `<head>`.
   - **CSS Variables**: Replace `:root` colors with the design style's palette:
     ```css
     :root {
       --bg: <design.colors.bg>;
       --primary: <design.colors.primary>;
       --card-bg: <design.colors.card-bg>;
       --text: <design.colors.text>;
       --text-muted: <design.colors.text-muted>;
       --border: <design.colors.border>;
       /* Font Families */
       --font-display: '<DisplayFont>', sans-serif;
       --font-body: '<BodyFont>', sans-serif;
     }
     ```
   - **Typography Rules**: Set headings (`h1`, `h2`, `h3`, metric numbers) to `var(--font-display)` with the style's specified weights and letter-spacing. Set paragraph body, tables, and labels to `var(--font-body)`.
   - **Corner Radii & Shadows**: Apply the style's border-radius rules (`radii.card-lg`, `radii.pill`, etc.) and shadow elevation language (e.g. flat borders for `neo-grid-bold`, soft tinted borders for `blue-professional`).
3. **Populate Approved Content**:
   Fill in the approved wireframe's specific titles, metrics, tables, chart bars/lines, and takeaway copy. Match the planned section order and Y bands.
4. **Self-Contained File**:
   Ensure all CSS is inline in `<style>` and CDN scripts (if Chart.js/D3 are needed) are loaded directly. No external local file dependencies.

### One-screen canvas contract (mandatory)

- Use **1280 × 720 CSS px (16:9)** for landscape or **720 × 1280 CSS px (9:16)** for portrait. The rendered canvas must retain that aspect ratio. These are design and capture dimensions, not a demand for a browser window of that size.
- Fit the entire canvas inside the *available browser viewport* by uniform scaling with `min(viewportWidth / canvasWidth, viewportHeight / canvasHeight, 1)` and center it. Scale down only; never let the page scroll. On narrow or short windows, letterboxing is acceptable. Set `html, body` to the viewport size with no margins, and position the canvas in a viewport-sized centering wrapper. Keep all content inside the canvas at the design dimensions before scaling. Do not rely on `overflow: hidden` to conceal excess content.
- Use this pattern (substitute the chosen width and height); it centers the fixed-size canvas and scales it to fit the viewport:

  ```html
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    html, body { width: 100%; height: 100%; margin: 0; overflow: hidden; }
    #canvas { position: absolute; left: 50%; top: 50%; width: 1280px; height: 720px;
      transform-origin: center center; }
  </style>
  <script>
    const canvas = document.getElementById('canvas');
    function fitCanvas() {
      const scale = Math.min(innerWidth / 1280, innerHeight / 720, 1);
      canvas.style.transform = `translate(-50%, -50%) scale(${scale})`;
    }
    addEventListener('resize', fitCanvas);
    fitCanvas();
  </script>
  ```

  For portrait, substitute `720` for width and `1280` for height everywhere in the example.
- Adapt the template's fixed pixel coordinates, type sizes, chart labels, and padding to the chosen canvas. If the content cannot remain readable at the expected viewing size, reduce the content or choose a less dense layout rather than allowing scroll or clipping.

---

## Step 3 — Capture the Screenshot (High-DPI 2x Retina Standard)

Always use the bundled Retina capture utility (`scripts/screenshot-retina.js`) to capture crisp, high-density visuals.

```bash
REPO_ROOT=$(git rev-parse --show-toplevel)
OUTPUT_DIR="/absolute/path/to/chosen/output-directory"

# For 9:16 portrait (adapt portrait templates to 720 × 1280):
node "$REPO_ROOT/.agents/skills/infographic/scripts/screenshot-retina.js" \
  "$OUTPUT_DIR/index.html" \
  "$OUTPUT_DIR/output.png" \
  --scale 2 --width 720 --height 1280 --timeout 2000

# For 16:9 landscape (adapt landscape templates to 1280 × 720):
node "$REPO_ROOT/.agents/skills/infographic/scripts/screenshot-retina.js" \
  "$OUTPUT_DIR/index.html" \
  "$OUTPUT_DIR/output.png" \
  --scale 2 --width 1280 --height 720 --timeout 2000
```

Do not use `--full-page`. The resulting image must be exactly 1440 × 2560 px (portrait) or 2560 × 1440 px (landscape) at 2x scale.

---

## Step 4 — Verify and Report

1. Confirm output file exists:
   ```bash
   ls -lh "$OUTPUT_DIR/output.png"
   ```
   Open the HTML at the design viewport and at a smaller browser viewport. Check `document.documentElement.scrollWidth <= innerWidth` and `document.documentElement.scrollHeight <= innerHeight` (and the same for `body`); inspect the rendered canvas for clipped text, charts, or labels. Compare the section boundaries and content against `layout_content.md`: all planned bands must fit within the canvas, appear in order, and end exactly at the canvas height. Correct overflow or reduce content before delivery; seek approval for material revisions. Verify the PNG dimensions match the selected orientation.
2. Embed the rendered screenshot in your response using a markdown file link:
   `![Visual](file:///absolute/resolved/path/output.png)`
3. Briefly summarize the template structure used, the design style applied, and the key highlights.

---

## Pre-Capture Checklist

- [ ] User explicitly approved the **Infographic Template** AND **Design Style** selection in Step 1.
- [ ] User approved the dimensioned layout-content wireframe and it is saved as `$OUTPUT_DIR/layout_content.md`.
- [ ] HTML and screenshot match the wireframe's content, section order, and Y bands without clipping.
- [ ] `index.html` is completely self-contained (Google Fonts / CDNs only, no relative local imports).
- [ ] Design style palette (`--bg`, `--primary`, `--text`, `--border`) is cleanly applied.
- [ ] Font pairings match the chosen design style (display + body).
- [ ] Canvas and capture viewport are `720×1280` (9:16 portrait) or `1280×720` (16:9 landscape).
- [ ] The full infographic is legible and fits in both the design viewport and a smaller browser viewport without scrolling or clipped content.
- [ ] All animations trigger on `DOMContentLoaded` (no scroll-triggered logic).
- [ ] Output screenshot verified at 2x Retina resolution with non-zero file size.

---

## Quick Reference

| Task | Command / Action |
|---|---|
| Resolve repo root | `REPO_ROOT=$(git rev-parse --show-toplevel)` |
| Inspect Layout Specs | View `$REPO_ROOT/.agents/skills/infographic/layout/<template>/design.md` |
| Inspect Style Specs | View `$REPO_ROOT/.agents/skills/infographic/design/<style>/design.md` |
| Choose output directory | Follow the user's requested location or project conventions; set `OUTPUT_DIR` to its absolute path |
| Create output directory | `mkdir -p "$OUTPUT_DIR"` |
| Save approved layout plan | Write `$OUTPUT_DIR/layout_content.md` with the ASCII wireframe and pixel-height bands |
| Author visual | Write `$OUTPUT_DIR/index.html` combining layout + style |
| Capture 9:16 portrait Retina (2x) | `node "$REPO_ROOT/.agents/skills/infographic/scripts/screenshot-retina.js" "$OUTPUT_DIR/index.html" "$OUTPUT_DIR/output.png" --scale 2 --width 720 --height 1280` |
| Capture 16:9 landscape Retina (2x)| `node "$REPO_ROOT/.agents/skills/infographic/scripts/screenshot-retina.js" "$OUTPUT_DIR/index.html" "$OUTPUT_DIR/output.png" --scale 2 --width 1280 --height 720` |
| Embed visual | `![Preview](file:///absolute/path/to/chosen/output-directory/output.png)` |
