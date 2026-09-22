---
name: infographic
description: "Use when: the user asks to create an infographic, one-pager, visual chart, render data as a stunning HTML chart, produce a screenshot of a visual, or save chart output. This skill authors a self-contained HTML file with embedded chart logic, then captures a full-page screenshot using Playwright. All output goes to a dedicated folder under topics/<topic-slug>/. The agent must ALWAYS confirm first with the user: (1) which infographic layout template to use, (2) which design style to apply from design/, (3) rationale for both, and (4) planned content outline. ONLY proceed after explicit user approval."
---

# infographic: Author HTML infographics, one-pagers, and charts

## What this skill does

You produce a **self-contained, single-file HTML visual** (charts, infographics, data stories) — no build step, no external bundler. After writing the file, you capture a **full-page screenshot** with Playwright and save it alongside the HTML in the output folder.

Every one-pager is composed of two coordinated choices:
1. **Infographic Template (Layout & Structure)** from `layout/`: Defines the layout geometry, structural hierarchy, data containers, tables, and chart visualization types.
2. **Design Style (Aesthetic & Skin)** from `design/`: Defines the visual personality, color palette tokens, typography pairing (Google Fonts), borders, corner radii, shadow treatments, and emotional tone.

> [!IMPORTANT]
> **MANDATORY CONFIRMATION GATE**: You must **ALWAYS** confirm with the user first before creating files or taking screenshots:
> 1. **Which Infographic Template** to use (from `layout/` or custom layout).
> 2. **Which Design Style** to apply (from `design/` — 34 production-ready styles).
> 3. **Why** you recommend this combination (rationale for layout structure + aesthetic match).
> 4. **The planned content & data outline** to be included on the 1-pager.
> **DO NOT** write code, create directories, or execute screenshots until the user has explicitly approved.

The workflow is:

1. **Plan & Confirm (MANDATORY GATE)** — Select infographic layout + design style, formulate rationale, outline content, and ask the user for approval. Stop calling tools and wait for confirmation.
2. **Author** — Once approved, adapt the chosen layout template and skin it with the chosen design style in `topics/<topic-slug>/index.html`.
3. **Screenshot** — Run Playwright Retina capture utility (`scripts/screenshot-retina.js`) to capture `output.png`.
4. **Verify** — Confirm the PNG exists and embed it in your reply.

---

## Repo root resolution

This skill is repo-local. All paths are relative to the **git repo root** that contains this skill file.

Resolve the repo root at runtime before running any command:

```bash
REPO_ROOT=$(git rev-parse --show-toplevel)
```

All visual output paths in this skill use `$REPO_ROOT` as the base. Never hardcode an absolute machine path.

---

## Folder convention

All visual work lives under:

```
$REPO_ROOT/topics/<topic-slug>/
├── index.html      the chart (self-contained)
└── output.png      full-page screenshot
```

**`topic-slug`** is a kebab-case name matching the subject (e.g. `huggingface-data-leaks`, `openai-model-benchmarks`). The user will often tell you the folder name directly. If they don't, derive it from the topic.

Create the folder before writing files:

```bash
REPO_ROOT=$(git rev-parse --show-toplevel)
mkdir -p "$REPO_ROOT/topics/<topic-slug>"
```

---

## Step 1 — Plan & Confirm with User (MANDATORY GATE)

Before writing any files, creating directories, or running commands, you **MUST STOP AND ASK FOR USER APPROVAL** with the following 4 elements:

1. **Infographic Template (Structure & Layout)**:
   - Identify the template from `layout/` (e.g., `executive-summary-report`, `business-plan-summary-report`, `enterprise-architecture-stack`, `financial-performance-report`, `monthly-social-media-report`, or explain if a custom layout is needed).
   - Check the template's `design.md` for specific content slots and layout rules.
2. **Design Style (Aesthetic & Skin)**:
   - Identify the design style from `design/` (e.g., `blue-professional`, `monochrome`, `neo-grid-bold`, `editorial-forest`, `bold-poster`, `cobalt-grid`, etc.).
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

> [!CAUTION]
> **DO NOT PROCEED TO STEP 2 UNTIL THE USER EXPLICITLY APPROVES.** Stop tool execution and wait for user feedback or approval.

---

## 1. Infographic Templates Library (`layout/`)

The repository includes **five production-ready layout templates**. Each folder contains the HTML source, a rendered PNG preview, and a comprehensive `design.md` detailing content slots, component dimensions, and data structures:

```
$REPO_ROOT/.agents/skills/infographic/layout/
├── business-plan-summary-report/
│   ├── design.md       ← layout specs, content slots & rationale guide
│   ├── index.html      ← ready-to-edit HTML
│   └── output.png      ← rendered preview
├── enterprise-architecture-stack/
│   ├── design.md
│   ├── index.html
│   └── output.png
├── executive-summary-report/
│   ├── design.md
│   ├── index.html
│   └── output.png
├── financial-performance-report/
│   ├── design.md
│   ├── index.html
│   └── output.png
└── monthly-social-media-report/
    ├── design.md
    ├── index.html
    └── output.png
```

### Infographic Layout Reference

| Template Folder | Format & Dimensions | Structural Layout | Best For |
|---|---|---|---|
| `business-plan-summary-report/` | A4 Portrait (900 × 1273 px) | Bold headline + top-right hanging brand banner · overview & findings · 3 blue goal cards with floating circular badges · audience segmentation table · 3-bar channel chart | Strategic business plans, GTM launches, 3-pillar commercial proposals |
| `enterprise-architecture-stack/` | 16:9 Landscape (1618 × 752 px) | Left boundary axis with dot markers · 4-tier horizontal stack (Apps, Capabilities, Services, Infrastructure) · 24+ structured component blocks | Enterprise IT architecture, AI platform stacks, microservices, cloud topologies |
| `executive-summary-report/` | A4 Portrait (900 × 1273 px) | Wave mesh watermark · signature rounded pill headers · balanced 2-column split: narrative & findings on left; 5 vertical goal items with icon circles + bar chart on right | Executive briefings, board reports, multi-objective program reviews |
| `financial-performance-report/` | A4 Portrait (900 × 1273 px) | Top corner wave arches · 3 navy highlight cards · full-width 4-metric dashed KPI banner · stacked column expense chart · icon performance notes · striped footer | Quarterly earnings, P&L updates, expense allocations, budget vs actuals |
| `monthly-social-media-report/` | A4 Portrait (900 × 1273 px) | Split navy/white header with cyan accent stripes · 2 KPI boxes · 3-platform weekly SVG trend line chart · 3 featured post cards with thumbnails · demographic progress bars · regional donut chart | Digital marketing performance, social audience growth, campaign engagement |

---

## 2. Design Styles Library (`design/`)

The repository includes **34 curated aesthetic design systems** in `design/`. Each folder provides a `design.md` (full color variables, typography hierarchy, component styling rules) and `template.json` (metadata, mood, typography pairing, palette).

### Design Style Taxonomy

#### A. Corporate, Consulting & Financial
| Style Slug | Mood & Vibe | Display Font | Body Font | Palette Highlights |
|---|---|---|---|---|
| `blue-professional` | Consulting-grade, modern, calm, trustworthy | Space Grotesk | Inter | Warm cream (`#fdfae7`), electric cobalt (`#1e2bfa`), dark ink (`#111111`) |
| `cobalt-grid` | Studious, design-research, architectural | Newsreader | Hanken Grotesk | Pure white, deep cobalt, structured slate gray borders |
| `emerald-editorial` | Prestige banking, wealth, confident | Bodoni Moda | Inter | Deep emerald green, champagne accents, crisp white |
| `signal` | Institutional, authoritative, considered | Source Serif 4 | DM Sans | Midnight navy (`#1c2644`), security orange, clean white |

#### B. Minimalist, Architectural & Swiss
| Style Slug | Mood & Vibe | Display Font | Body Font | Palette Highlights |
|---|---|---|---|---|
| `monochrome` | Swiss restraint, stark archival, high contrast | Lora | Jost | Archival pale parchment (`#fafadf`), deep black, gray tints |
| `cartesian` | Technical blueprint, mathematical, quiet | Playfair Display | Inter | High-contrast black & white, fine 1px grid rules |
| `mat` | Scandinavian matte, tactile, earth tones | Bricolage Grotesque | DM Sans | Deep matte slate-green (`#232e26`), soft moss, bone white |
| `studio` | Sleek creative studio, graphic, modern | Barlow | Barlow | Dark charcoal (`#1c1c1c`), pure white, subtle silver borders |
| `broadside` | Historic broadsheet, dramatic newspaper | Barlow | Barlow | Stark ink black (`#111111`), newsprint ivory |

#### C. Editorial & Literary
| Style Slug | Mood & Vibe | Display Font | Body Font | Palette Highlights |
|---|---|---|---|---|
| `editorial-forest` | Sustainable luxury, considered, organic | Serif Display | Sans Text | Deep pine forest green, warm cream, warm gold accents |
| `editorial-tri-tone` | Tri-color lithograph, intentional, print | Bricolage Grotesque | Sans Text | 3-ink strict palette (Navy, Ochre, Off-white) |
| `soft-editorial` | Gentle elegance, boutique editorial | Cormorant Garamond | Work Sans | Soft cashmere beige, warm charcoal, muted sage |
| `vellum` | Scholarly archival, antiquarian warmth | Cormorant Garamond | DM Sans | Deep parchment navy (`#2a3870`), antiquarian gold, vellum white |
| `biennale-yellow` | Contemporary art biennial, dramatic | Instrument Serif | Archivo | High-voltage yellow, gallery black, crisp white |

#### D. Punchy, Bold & Brutalist
| Style Slug | Mood & Vibe | Display Font | Body Font | Palette Highlights |
|---|---|---|---|---|
| `neo-grid-bold` | Neo-brutalist, punchy, sticker accents | Space Grotesk | Space Grotesk | Industrial gray (`#ecece8`), heavy 2px black borders, vivid pop chips |
| `bold-poster` | Swiss poster, loud, heroic headline | Shrikhand | Space Grotesk | Bright saturated primaries on clean stark white |
| `raw-grid` | Unfiltered wireframe, raw structural grid | System Monospace | System UI | Stark black/white, sharp unrounded corners, exposed borders |
| `block-frame` | Framed modular containers, poster geometry | Space Grotesk | Inter | Bold border frames, high contrast, clean grid blocks |
| `peoples-platform` | Grassroots activist, bold woodblock | Alfa Slab One | Sans Text | Solid heavy slab typography, deep brick red & ink |

#### E. Creative, Playful & Warm
| Style Slug | Mood & Vibe | Display Font | Body Font | Palette Highlights |
|---|---|---|---|---|
| `creative-mode` | Confident agency, energetic, playful | Archivo Black | Space Grotesk | High-contrast neon accents on deep ink canvas |
| `coral` | Warm, welcoming, modern consumer | Bebas Neue | Inter | Vibrant coral peach, terracotta, soft cream |
| `playful` | Bouncy geometry, approachable indie | Syne | Space Grotesk | Warm amber peach (`#f0c8a0`), indigo contrast |
| `daisy-days` | Cheerful, fresh, sunny, friendly | Fredoka One | Quicksand | Pastel yellow, soft sky blue, warm rounded cards |
| `scatterbrain` | Creative spark, dynamic, artistic | Shrikhand | Zilla Slab | Eclectic pastel accents, energetic layout hierarchy |
| `capsule` | Modern SaaS, pill-shaped futuristic | Bodoni Moda | Space Grotesk | Soft mist gray (`#f5f5f0`), capsule pill geometry |
| `long-table` | Culinary, hospitality, artisanal craft | Bricolage Grotesque | Fraunces | Rich warm terracotta, olive, linen white |

#### F. Craft, Tactile & Retro
| Style Slug | Mood & Vibe | Display Font | Body Font | Palette Highlights |
|---|---|---|---|---|
| `pin-and-paper` | Handmade bulletin, tactile paper craft | Caveat | Space Grotesk | Pinned card notes, kraft paper, soft shadow layers |
| `retro-zine` | Lo-fi risograph, indie fanzine, textured | Bebas Neue | Space Grotesk | Distressed warm newsprint (`#c8b99a`), monochrome ink |
| `retro-windows` | 90s vintage GUI, classic OS desktop | Press Start 2P | MS Sans Serif | Classic 90s gray window bevels, cyan/navy title bars |
| `8-bit-orbit` | Retro pixel arcade, cyberpunk sci-fi | Tektur | Chakra Petch | Dark terminal background, neon cyan & magenta |
| `stencil-tablet` | Industrial warehouse, rugged utilitarian | Bowlby One | Inter | Stencil display lettering, durable khaki & charcoal |
| `sakura-chroma` | Neo-Tokyo cyberpunk, kawaii-tech | Big Shoulders Display | Albert Sans | Neon magenta, cherry blossom pink, obsidian dark |
| `pink-script` | Nocturnal luxury, after-hours editorial | DM Serif Display | Inter | Deep midnight velvet, dusky rose pink accents |
| `grove` | Organic botanical, forest canopy | Playfair Display | Jost | Deep pine green (`#192b1b`), leafy sage, warm parchment |

---

## Step 2 — Author index.html (Synthesizing Structure + Design Style)

> **Prerequisite**: Only proceed with this step after the user has explicitly approved the proposed infographic template, design style, rationale, and content outline from Step 1.

### How to Combine Layout Structure and Design Style

When creating the 1-pager in `topics/<topic-slug>/index.html`:

1. **Start with the Infographic Template Structure**:
   Copy the chosen template from `layout/<template>/` or use its DOM hierarchy (header, cards, KPI grids, tables, charts).
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
   Fill in the user's specific titles, metrics, tables, chart bars/lines, and takeaway copy.
4. **Self-Contained File**:
   Ensure all CSS is inline in `<style>` and CDN scripts (if Chart.js/D3 are needed) are loaded directly. No external local file dependencies.

---

## Step 3 — Capture the Screenshot (High-DPI 2x Retina Standard)

Always use the bundled Retina capture utility (`scripts/screenshot-retina.js`) to capture crisp, high-density visuals.

```bash
REPO_ROOT=$(git rev-parse --show-toplevel)
SLUG="<topic-slug>"

# For A4 Portrait Templates (business-plan, executive-summary, financial-performance, monthly-social-media):
node "$REPO_ROOT/.agents/skills/infographic/scripts/screenshot-retina.js" \
  "$REPO_ROOT/topics/$SLUG/index.html" \
  "$REPO_ROOT/topics/$SLUG/output.png" \
  --scale 2 --width 900 --height 1273 --timeout 2000

# For 16:9 Landscape Stack (enterprise-architecture-stack):
node "$REPO_ROOT/.agents/skills/infographic/scripts/screenshot-retina.js" \
  "$REPO_ROOT/topics/$SLUG/index.html" \
  "$REPO_ROOT/topics/$SLUG/output.png" \
  --scale 2 --width 1618 --height 752 --timeout 2000

# For Custom Scrollable Web Infographics:
node "$REPO_ROOT/.agents/skills/infographic/scripts/screenshot-retina.js" \
  "$REPO_ROOT/topics/$SLUG/index.html" \
  "$REPO_ROOT/topics/$SLUG/output.png" \
  --scale 2 --width 1200 --full-page --timeout 2000
```

---

## Step 4 — Verify and Report

1. Confirm output file exists:
   ```bash
   REPO_ROOT=$(git rev-parse --show-toplevel)
   ls -lh "$REPO_ROOT/topics/<slug>/output.png"
   ```
2. Embed the rendered screenshot in your response using a markdown file link:
   `![Visual](file:///absolute/resolved/path/output.png)`
3. Briefly summarize the template structure used, the design style applied, and the key highlights.

---

## Pre-Capture Checklist

- [ ] User explicitly approved the **Infographic Template** AND **Design Style** selection in Step 1.
- [ ] `index.html` is completely self-contained (Google Fonts / CDNs only, no relative local imports).
- [ ] Design style palette (`--bg`, `--primary`, `--text`, `--border`) is cleanly applied.
- [ ] Font pairings match the chosen design style (display + body).
- [ ] Viewport dimensions in the capture command match the layout (`900×1273` for A4, `1618×752` for 16:9).
- [ ] All animations trigger on `DOMContentLoaded` (no scroll-triggered logic).
- [ ] Output screenshot verified at 2x Retina resolution with non-zero file size.

---

## Quick Reference

| Task | Command / Action |
|---|---|
| Resolve repo root | `REPO_ROOT=$(git rev-parse --show-toplevel)` |
| Inspect Layout Specs | View `$REPO_ROOT/.agents/skills/infographic/layout/<template>/design.md` |
| Inspect Style Specs | View `$REPO_ROOT/.agents/skills/infographic/design/<style>/design.md` |
| Create topic directory | `mkdir -p "$REPO_ROOT/topics/<slug>"` |
| Author visual | Write `topics/<slug>/index.html` combining layout + style |
| Capture A4 Retina (2x) | `node "$REPO_ROOT/.agents/skills/infographic/scripts/screenshot-retina.js" "$REPO_ROOT/topics/<slug>/index.html" "$REPO_ROOT/topics/<slug>/output.png" --scale 2 --width 900 --height 1273` |
| Capture 16:9 Retina (2x)| `node "$REPO_ROOT/.agents/skills/infographic/scripts/screenshot-retina.js" "$REPO_ROOT/topics/<slug>/index.html" "$REPO_ROOT/topics/<slug>/output.png" --scale 2 --width 1618 --height 752` |
| Embed visual | `![Preview](file:///resolved/path/topics/<slug>/output.png)` |
