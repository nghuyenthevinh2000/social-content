---
name: beautiful-html-templates
description: "A library of 34+ reusable, production-ready HTML slide deck templates and styling systems. Use when the user asks to build, design, generate, or adapt an HTML slide presentation or pitch deck, convert topics into visual decks, or customize presentation templates with specific tones, aesthetics, and slide layouts."
metadata:
  tags: html, presentation, slides, pitch-deck, templates, design-system, visual-deck
---

# beautiful-html-templates: HTML Slide Deck Creation & Adaptation

A comprehensive collection of 34 curated, self-contained HTML slide deck templates spanning diverse aesthetics (editorial, brutalist, minimal, playful, retro, technical, bold). This skill guides agents through tone-first template selection, interactive previewing, and content adaptation into production-ready presentations.

---

## When to Use This Skill

Use this skill whenever:
- The user requests an HTML slide presentation, deck, pitch, keynote, or workshop slides.
- The user wants to adapt or convert researched topics/posts into a presentation format.
- The user asks to explore or browse presentation design templates.
- The user wants a custom visual slide deck with interactive keyboard navigation.

---

## Skill Paths & Structure

All paths are relative to the repository root:

- **Skill Root**: `.agents/skills/beautiful-html-templates/`
- **Catalog Index**: `.agents/skills/beautiful-html-templates/index.json` (34 templates with mood, tone, occasion, density, formality metadata)
- **Templates Directory**: `.agents/skills/beautiful-html-templates/templates/<template-slug>/`
  - `template.html`: Self-contained HTML presentation
  - `template.json`: Template metadata and color tokens
  - `design.md`: Design system documentation (typography, colors, components, layout specs)
  - `deck-stage.js` (if applicable): Keyboard and stage navigation runtime
- **Shared Runtime**: `.agents/skills/beautiful-html-templates/runtime/deck-stage.js`
- **Export Scripts**:
  - `.agents/skills/beautiful-html-templates/scripts/export-pdf.mjs`: Universal 16:9 PDF exporter (Node.js + Chrome CDP)
  - `.agents/skills/beautiful-html-templates/scripts/export-pdf.sh`: Shell executable wrapper
- **Output Directory**: Save final presentations under `topics/<topic-slug>/` (or as specified by user).

---

## The 6-Step Workflow

Follow this sequence for deck-building requests.

### Step 1 — Clarify Occasion & Mood

If not already specified by the user's brief, ask:
1. **What's the occasion?** (e.g. founder pitch, technical workshop, research synthesis, brand manifesto, quarterly review)
2. **What mood / vibe do you want?** (e.g. confident & punchy, quiet & literary, warm & playful, dark & technical)

### Step 2 — Search `index.json` & Shortlist 3 Candidates

Read `.agents/skills/beautiful-html-templates/index.json`. Match the user's occasion and mood against template attributes (`mood`, `tone`, `best_for`, `formality`, `scheme`):
- Pick **three distinct templates** that suit the tone.
- Ensure stylistic variety among the 3 candidates (e.g., one editorial, one warm/approachable, one bold/wildcard).

### Step 3 — Generate Title-Slide Previews

For each candidate:
1. Read `templates/<slug>/template.html` and its `design.md`.
2. Extract the first slide (cover / title slide).
3. Populate it with the user's real topic title, subtitle, author, and date.
4. Save preview files in a temporary location (e.g. `topics/<topic-slug>/previews/01-<slug>.html` or `scratch/previews/`). Include any needed runtime scripts or assets.

### Step 4 — Present Previews to User

Present the 3 choices with concise tone descriptions:
- Open preview files locally (`open <path>` on macOS) so the user can see them immediately.
- List clickable file paths and descriptions for the user to choose.

### Step 5 — Build Full Presentation

Once the template is selected:
1. Copy the selected template folder to the destination directory (e.g. `topics/<topic-slug>/`):
   ```bash
   cp -r .agents/skills/beautiful-html-templates/templates/<slug>/ topics/<topic-slug>/
   ```
2. Adapt all slides following the **Preserve / Replace / Extend** rules below.
3. If more slides are needed, duplicate existing slide layouts. If fewer slides are needed, remove trailing slides. Update slide page numbers (`NN / TT`).
4. If a required layout does not exist (e.g. comparison matrix, timeline), design it from scratch using the template's exact design system tokens.

### Step 6 — Review & Deliver

1. Open the finished deck in the browser (`open topics/<topic-slug>/template.html`).
2. Provide the absolute path to the user along with a concise summary of the visual choices.

### Step 7 — Export to PDF (Optional)

When the user requests a PDF version of the presentation:
1. Run the universal export script:
   ```bash
   node .agents/skills/beautiful-html-templates/scripts/export-pdf.mjs topics/<topic-slug>/template.html
   # Or using the shell wrapper:
   .agents/skills/beautiful-html-templates/scripts/export-pdf.sh topics/<topic-slug>/template.html [custom-output.pdf]
   ```
2. The script automatically detects the template engine:
   - `<deck-stage>` decks are printed in a single pass at 16:9 widescreen ratio.
   - Screen-only/interactive decks are automatically stepped through slide-by-slide via keyboard navigation and merged with `pdfunite`.
3. Open or link the resulting PDF for the user.

---

## Template Adaptation Rules

### Always Preserve (The Design System)
- **Fonts**: Keep exact Google Fonts imports and font families (`font-family`). Never substitute fonts.
- **Palette**: Keep `:root` CSS color variables. Never introduce arbitrary new colors.
- **Layout Grid**: Preserve column structures, flex hierarchies, margins, and paddings.
- **Slide Classes**: Retain layout classes (`.slide`, `.layout-cover`, `.s-toc`, etc.).
- **Decorative Elements**: Retain textures, corner brackets, paper grains, badges, dividers, and SVG ornaments.
- **Navigation Runtime**: Keep `deck-stage.js` or inline keyboard navigation intact.

### Always Replace (The User Content)
- Headlines (`<h1>`, `<h2>`, `<h3>`)
- Body paragraphs and bullet points (`<p>`, `<li>`)
- Stat numbers and metrics (`+45%`, `$2.4M`, etc.)
- Metadata: Authors, dates, topic slugs, footers, pagination
- Image placeholders: Replace with user graphics or maintain clean placeholder styling

### Extending Templates with Missing Layouts
When the user needs a slide type not present in the demo deck:
- Re-use typography hierarchy (same headline and body font styles).
- Re-use color tokens and component styling (cards, borders, badges).
- Re-use decorative rules and rhythm (same margins, padding, and spacing).
- Ensure the new slide integrates seamlessly into the navigation runtime.

---

## Template Catalog Overview

| Slug | Category | Key Characteristics |
|---|---|---|
| `8-bit-orbit` | Retro Tech / Arcade | Pixel art, neon on dark void, cyberpunk feel |
| `biennale-yellow` | Arts / Exhibition | Bold yellow & black, high contrast, cultural |
| `block-frame` | Structural / Modern | Heavy borders, framed blocks, crisp structure |
| `blue-professional` | Corporate / Enterprise | Clean navy & blue, executive clarity, reliable |
| `bold-poster` | High Impact / Graphic | Poster typography, punchy statements |
| `broadside` | Print / Editorial | Newspaper/broadsheet style, multi-column |
| `capsule` | Clean Tech / SaaS | Soft rounded cards, pill badges, clean UI |
| `cartesian` | Technical / Mathematical | Coordinate grid background, technical precision |
| `cobalt-grid` | Digital / Architectural | Vibrant cobalt on graph paper, pixel accents |
| `coral` | Warm / Energetic | Vibrant coral & cream, modern lifestyle |
| `creative-mode` | Portfolio / Agency | Expressive layouts, creative agency tone |
| `daisy-days` | Gentle / Warm | Soft pastels, friendly, human-centered |
| `editorial-forest` | Deep Editorial | Forest green & dusty pink, quiet quarterly review |
| `editorial-tri-tone` | Magazine / Journal | 3-color palette, classic serif elegance |
| `emerald-editorial` | Executive Publication | Deep emerald & gold accents, Bodoni serif |
| `grove` | Organic / Nature | Earthy greens, botanical, calm narrative |
| `long-table` | Academic / Scholarly | Bookish typography, dense informative layout |
| `mat` | Gallery / Minimal | Framed border matting, art gallery precision |
| `monochrome` | High Minimalist | Pure black & white, stark typography |
| `neo-grid-bold` | Neo-brutalist | Neon yellow on off-white, raw grid lines |
| `peoples-platform` | Community / Movement | Bold activist typography, warm social tone |
| `pin-and-paper` | Handcrafted / Studio | Yellow ruled paper, pin graphics, Caveat script |
| `pink-script` | Editorial / Playful | Dusty pink with elegant script accents |
| `playful` | Colorful / Approachable | Cheerful color blocks, friendly shapes |
| `raw-grid` | Brutalist / Technical | Monospace, exposed wireframe grid lines |
| `retro-windows` | 90s GUI / Nostalgic | Classic desktop OS window chrome, gray bevels |
| `retro-zine` | Indie / Underground | Halftone textures, photocopier zine vibe |
| `sakura-chroma` | Vintage Japanese Tech | Cassette aesthetic, rainbow striping, JIS spec |
| `scatterbrain` | Creative / Idea Board | Post-it style pins, brainstorm collage |
| `signal` | High-Tech / Telemetry | Terminal HUD, glowing cyan/amber telemetry |
| `soft-editorial` | Literary / Thought Leadership | Sage, blush & lemon with Cormorant Garamond |
| `stencil-tablet` | Archaeology / Earth | Stencil typography, stone tablet earth tones |
| `studio` | Architecture / Industrial | Swiss grid, Bauhaus precision, clean sans |
| `vellum` | Scholarly / Night | Deep navy with warm-yellow italic serifs |
