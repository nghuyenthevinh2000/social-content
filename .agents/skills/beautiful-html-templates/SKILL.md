---
name: beautiful-html-templates
description: "Library of 34 curated HTML slide deck templates. Guides tone-first template selection, interactive previewing, content adaptation, and vector PDF export."
---

# HTML Slide Deck Creation & Adaptation

```text
Clarify Occasion & Mood -> Shortlist 3 Candidates -> Generate Previews -> User Gate -> Build Full Deck -> Review & Export PDF
```

## Core Workflow & Execution Gates

| Step | Phase | Action & Protocols | Gate / Requirement |
|---|---|---|---|
| 1 | Clarify Brief | Inquire: (1) Occasion (e.g., pitch, workshop, synthesis) and (2) Mood/vibe (e.g., punchy, literary, warm, technical). | Do not pick templates before receiving occasion and mood. |
| 2 | Shortlist Candidates | Search `index.json` matching `mood`, `tone`, `occasion`, `formality`. Select 3 stylistically distinct candidates. | Require 3 distinct styles (e.g., editorial, warm, wildcard). |
| 3 | Title-Slide Previews | Extract cover slide from each candidate `templates/<slug>/template.html`; populate with actual title, subtitle, author, date. | Save to `topics/<topic-slug>/previews/01-<slug>.html`. |
| 4 | Present Previews | Open previews in browser (`open <path>`); provide clickable file paths and concise tone descriptions. | **STRICT USER GATE:** Await user selection before building full deck. |
| 5 | Build Presentation | Copy selected template to `topics/<topic-slug>/`; replace content per adaptation rules; adjust slide counts (`NN / TT`). | Maintain design system; synthesize missing layouts from tokens. |
| 6 | Review & Deliver | Open finished presentation (`open topics/<topic-slug>/template.html`); share absolute file path and visual choices. | Ensure keyboard navigation and 16:9 stage layout render cleanly. |
| 7 | Export PDF (Optional) | Execute export script: `node scripts/export-pdf.mjs topics/<topic-slug>/template.html`. | Auto-detects `<deck-stage>` or step-by-step capture. |

## Skill Paths & Directory Structure

| Category | File / Directory Path | Purpose & Assets |
|---|---|---|
| Root & Catalog | `.agents/skills/beautiful-html-templates/index.json` | 34 templates indexed with mood, tone, formality, and slide count metadata. |
| Templates | `.agents/skills/beautiful-html-templates/templates/<slug>/` | Contains `template.html`, `template.json`, `design.md`, and local assets. |
| Shared Runtime | `.agents/skills/beautiful-html-templates/runtime/deck-stage.js` | Keyboard navigation (`←`/`→`, space, fullscreen) and stage layout runtime. |
| Export Tooling | `.agents/skills/beautiful-html-templates/scripts/export-pdf.mjs` | Universal 16:9 vector PDF export engine (Node.js + Chrome CDP). |
| Shell Wrapper | `.agents/skills/beautiful-html-templates/scripts/export-pdf.sh` | Shell executable wrapper around Node export script. |
| Project Output | `topics/<topic-slug>/` | Standard output destination for generated presentations and previews. |

## Template Adaptation Rules

| Area | Invariant Protocol | Elements & Actions |
|---|---|---|
| **Preserve (Design System)** | Strictly maintain visual tokens and structure. | Google Fonts imports, `:root` CSS variables, column grids, layout classes (`.slide`, `.layout-cover`), decorative badges/textures, and navigation scripts. |
| **Replace (User Content)** | Swap out all placeholder material. | Headlines (`<h1>`–`<h3>`), body copy (`<p>`, `<li>`), data metrics/stats, metadata (author, date, footer, pagination), and image placeholders. |
| **Extend (New Layouts)** | Synthesize unrepresented slide structures seamlessly. | Re-use typography hierarchy, CSS variables, card border styles, and spacing rhythm so new layouts look native. |

## Minimalism & Anti-Duplication Rules

| Anti-Pattern | LLM Failure Mode | Mandatory Invariant Standard |
|---|---|---|
| **Icon Inflation** | Slapping Lucide, FontAwesome, or SVG icons on every bullet, title, or card | **Forbid icon spam.** Keep only icons present in original template; max 1 icon or illustration per slide; never bullet with icons. |
| **Box-in-a-Box Nesting** | Wrapping every paragraph or item in bordered, shaded cards or containers | **Flatten hierarchy.** Prefer whitespace, CSS grid gap, and typographic scale over nested borders, boxes, and cards. |
| **Content Echo & Duplication** | Repeating title words in subtitle, section headers, or body bullets | **Zero content echoing.** Subtitles must state new info or be omitted. Never rephrase or duplicate points across slides. |
| **Badge / Chip Spam** | Adding category pills (`[FEATURE]`, `[PHASE]`, `[KEY]`) over every item | **Eliminate chip clutter.** Maximum 1 eyebrow tag per slide; never place redundant tags above every list or card item. |
| **Filler & AI Prose** | Adding introductory fluff, meta-announcements, or obvious summary points | **High signal density.** Cut filler phrases ("It is crucial to note", "In today's landscape"). Write punchy, verifiable assertions. |
| **Canvas Overcrowding** | Cramming extra elements into spare space rather than letting layout breathe | **Preserve negative space.** Maintain 30%+ breathing room. Do not invent new cards or sections to fill empty canvas space. |

## CLI Commands Reference

| Action | Command Syntax | Notes |
|---|---|---|
| Copy Template | `cp -r .agents/skills/beautiful-html-templates/templates/<slug>/ topics/<topic-slug>/` | Sets up project deck directory. |
| Preview Deck | `open topics/<topic-slug>/previews/01-<slug>.html` | Launches local preview in default browser. |
| Export PDF (Node) | `node .agents/skills/beautiful-html-templates/scripts/export-pdf.mjs topics/<topic-slug>/template.html` | Prints 16:9 PDF with engine auto-detection. |
| Export PDF (Shell) | `.agents/skills/beautiful-html-templates/scripts/export-pdf.sh topics/<topic-slug>/template.html [output.pdf]` | Convenience wrapper with optional custom filename. |

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
