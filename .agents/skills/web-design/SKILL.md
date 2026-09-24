---
name: web-design
description: "Comprehensive web design and UI engineering skill covering grid systems, framing, responsive layouts, conversion architecture, and modern visual design patterns. Use when asked to design, build, or refactor web layouts, landing pages, agency portfolios, split-screen technical interfaces, pricing pages, or structured containers."
---

# Web Design & Layout Engineering Skill

A comprehensive, production-grade web design skill combining disciplined grid architecture, high-conversion page structures, and agency-level visual craft.

---

## Core Philosophy & Governing Mindset

### 1. The Design-First Mindset (Meng To Playbook)
This skill is governed by the **Design-First UI Prompting** mindset ([full reference](references/design-first-ui-prompting.md)):
> **"Prompt like a design system, not a wish."**

AI does not make great design by default; it makes **average design fast**. Visual craft and taste are the moat. All layout and UI tasks must execute through these governing rules:
- **Screenshots Beat Prompts:** Stop writing 1,000-word ambiguous descriptions. Curate concrete visual references (layouts, spacing, materials) first.
- **The Hero Section Is Half the Job:** Always lock the hero section first (layout, typography tension, single signal color). Once locked, build the rest **section-by-section**, never full-page at random.
- **Negative Prompts as Guardrails:** Explicitly bound the model to prevent drift (e.g., *"Do not alter the hero layout"*, *"No floating cards with drop shadows"*, *"No extra widgets beyond spec"*).
- **Add Craft Signals:** Milled 1px hairline container lines, micro-monospaced coordinate labels (`+ [Z01]`), `01/02/03` section markers, and subtle specular edge highlights (`inset 0 1px 0 rgba(255,255,255,0.12)`).
- **Spec-Driven Prompt Skeleton:** Define interfaces through structural specs: **GOAL**, **FORMAT**, **LAYOUT**, **TYPE SYSTEM**, **COLOR + MATERIAL**, **COPY**, **CONSTRAINTS**, and **NEGATIVE PROMPT**.

### 2. Specs Beat Vibes
Never rely on subjective terms like *"make it modern"* or *"make it sleek"*. Build interfaces with explicit mathematical constraints:
- Unified token scales (`1px` borders, clamp-based padding, strict gap scales).
- Fixed aspect ratios, rigid column spans, and aligned horizontal/vertical grid baselines.
- Explicit typography pairing (e.g. tightly tracked sans display headlines + tiny monospaced uppercase metadata).

### 3. The "Anti-Generic" Taste Rules (Avoid List)
Standard AI coding agents generate generic "AI slop". Strictly enforce these anti-patterns:
- **NO floating cards with heavy blurred drop shadows:** The visible frame, hairline border, or subtle tonal surface *is* the structure.
- **NO mixed border weights:** Do not combine `1px`, `2px`, and `3px` borders across adjacent containers. Pick one border scale (usually `1px`) and stick to it.
- **NO gratuitous purple/indigo gradients or generic pill buttons:** Use disciplined neutral palettes with deliberate, single-accent highlights.
- **NO crammed white space:** Do not feel compelled to fill empty gaps with icons or cards. Intentional negative space creates premium hierarchy.
- **NO non-semantic div soup:** Use `<header>`, `<main>`, `<section>`, `<aside>`, `<nav>`, `<article>`, and `<footer>` with explicit CSS grid spans.


---

## Layout Architecture Catalog

All layout systems are modularly stored under `layouts/<layout-name>/`. Each layout folder contains its dedicated `SKILL.md` specification and a runnable browser demo in `demo/index.html`.

### 1. Structural Grids & Framed Boxes
| Layout | Description & Best Use Case |
| :--- | :--- |
| [`framed-grid-layout`](layouts/framed-grid-layout/SKILL.md) | **Minimal Framed Grid:** Strict 12-column layout with visible 1px boundary lines, pure-CSS L-shaped corner brackets, and faint diagonal line texture (<0.05 opacity). Ideal for developer tools, technical products, and structured portfolios. |
| [`agency-grid-layout-minimal`](layouts/agency-grid-layout-minimal/SKILL.md) | **Editorial Agency Grid:** Large open spans, oversized typography with tight tracking, small uppercase utility labels, and architectural negative space. |
| [`image-first-grid-layout`](layouts/image-first-grid-layout/SKILL.md) | **Visual-Led Grid:** Full-bleed architectural imagery, asymmetric grid spans, and minimalist framing lines. |
| [`container-lines`](layouts/container-lines/SKILL.md) | **Guide-Line System:** Vertical container-width guide lines with micro corner squares to anchor content flow. |
| [`corner-diagonals`](layouts/corner-diagonals/SKILL.md) | **Chamfered / Diagonal Corners:** High-precision angled cuts on cards, buttons, and panels for cyber/tactical aesthetics. |

### 2. Nested Containers & Boundary Shells
| Layout | Description & Best Use Case |
| :--- | :--- |
| [`nested-container-frames`](layouts/nested-container-frames/SKILL.md) | **Container-in-Container:** Multi-layered frame hierarchy (outer shell $\rightarrow$ middle framing gutter $\rightarrow$ inner content canvas) creating depth without drop shadows. |
| [`nested-container-clean-agency`](layouts/nested-container-clean-agency/SKILL.md) | **Agency Nesting:** Clean nested boxes with tonal background shifts and quiet divider lines. |
| [`framed-tech-dark-border-gradient`](layouts/framed-tech-dark-border-gradient/SKILL.md) | **Gradient Border Frames:** Dark technical shells using 1px gradient borders and asymmetrical split columns. |
| [`funky-purple-container-tech`](layouts/funky-purple-container-tech/SKILL.md) | **Vibrant Accent Containers:** Deep dark container shells accented with precision fuchsia/purple highlights. |

### 3. Split-Screen & Technical Layouts
| Layout | Description & Best Use Case |
| :--- | :--- |
| [`split-layout-technical`](layouts/split-layout-technical/SKILL.md) | **Dual-Panel Technical Split:** 50/50 desktop split (hero visual/canvas on one side, specs/documentation on the other) with mono status rails. |
| [`technical-wireframe-info-layout`](layouts/technical-wireframe-info-layout/SKILL.md) | **Exploded Wireframe / Blueprint:** Blueprint grid, crosshair markers, coordinate annotations, and callout labels. |
| [`operational-enterprise-ai`](layouts/operational-enterprise-ai/SKILL.md) | **Enterprise AI & Infrastructure:** High-density status ribbons, metric bars, live pipeline visualizers, and security tables. |

### 4. High-Conversion Page Structures
| Layout | Description & Best Use Case |
| :--- | :--- |
| [`landing-page`](layouts/landing-page/SKILL.md) | **High-Conversion Single-Offer Page:** Master framework covering Above-the-fold Hero, Problem $\rightarrow$ Solution narrative, Outcome benefits, How it Works, Proof strip, Objection-handling FAQ, and Risk-reversal CTA. |
| [`pricing-page`](layouts/pricing-page/SKILL.md) | **SaaS Pricing Table:** Tier comparison cards, billing frequency toggles, featured plan callouts, and comprehensive feature matrix. |
| [`product-proof-saas`](layouts/product-proof-saas/SKILL.md) | **Evidence-Driven SaaS:** Interactive workflow walkthroughs, live product teasers, and verifiable customer metric blocks. |

### 5. Editorial, Typography & Brutalist Layouts
| Layout | Description & Best Use Case |
| :--- | :--- |
| [`editorial-tech`](layouts/editorial-tech/SKILL.md) | **Magazine Tech:** Blends high-end publication typography (editorial serifs or elegant sans) with technical product callouts. |
| [`book-serif-index`](layouts/book-serif-index/SKILL.md) | **Archival Index:** Serif-led reading layout with marginalia notes, chapter numbers, and monospaced index navigation. |
| [`editorial-portfolio-chapters`](layouts/editorial-portfolio-chapters/SKILL.md) | **Case-Study Chapters:** Chapter-driven layout with full-bleed media and numbered narrative acts. |
| [`editorial-service-booking`](layouts/editorial-service-booking/SKILL.md) | **Service Booking:** High-end hospitality and appointment scheduling flow with structured pricing and service breakdowns. |
| [`documentary-brutalist-agency`](layouts/documentary-brutalist-agency/SKILL.md) | **Documentary Brutalism:** Monochromatic, heavy typography, exposed grid wireframes, and raw structural dividers. |

### 6. Thematic Aesthetic Environments
| Layout | Description & Best Use Case |
| :--- | :--- |
| [`dark-glass-clean-layout`](layouts/dark-glass-clean-layout/SKILL.md) | Frosted dark glass shells, subtle backdrop blurs (`backdrop-filter: blur(12px)`), and thin white borders. |
| [`blue-laser-clean-glass-layout`](layouts/blue-laser-clean-glass-layout/SKILL.md) | Dark glass panels energized by ultra-thin cyan/cobalt laser atmospheric lines. |
| [`clean-minimal-beige-light-mode`](layouts/clean-minimal-beige-light-mode/SKILL.md) | Warm beige surfaces (`#f7f6f2`), quiet charcoal typography, and museum-like restraint. |
| [`light-mode-paper-technical`](layouts/light-mode-paper-technical/SKILL.md) | Tactile paper-textured surfaces paired with engineered technical data tables and mono metadata. |
| [`orange-clean-paper-saas`](layouts/orange-clean-paper-saas/SKILL.md) | Warm paper-tone canvas energized with crisp safety-orange action buttons and badges. |
| [`tech-green-dark-mode-modern`](layouts/tech-green-dark-mode-modern/SKILL.md) | Matte-black background paired with emerald-green status indicators and terminal accents. |
| [`dark-blue-contrasting-clean`](layouts/dark-blue-contrasting-clean/SKILL.md) | Deep navy-blue canvas with high-contrast electric cobalt accent panels. |

---

## Workflow: How to Apply a Layout to a Project

### Mandatory preview showcase

For **every web-design task**, always showcase the hero preview before locking the visual direction or building out the page:

1. Populate the `directions` array in [`references/design_hero_preview.json`](references/design_hero_preview.json) with project-specific visual choices. Fill all eight `spec` sections from the design-first prompt skeleton (GOAL, FORMAT, LAYOUT, TYPE SYSTEM, COLOR + MATERIAL, COPY, CONSTRAINTS, NEGATIVE PROMPT) for each direction. Keep the design tokens and visual consistent with the written spec.
2. Serve [`references/design_hero_preview.html`](references/design_hero_preview.html) over local HTTP and **show the user how to open the preview** (URL or rendered screenshot), including how to switch between directions. See [`references/README.md`](references/README.md) for setup. Do not merely mention that a preview file exists.
3. Use the showcased preview to select or refine a direction before carrying its choices into the rest of the design. If the user already specified a direction, still populate and showcase its preview.

When tasked with creating or redesigning a webpage:

### Step 1: Clarify Offer & Layout Archetype
Select the best-matching archetype based on the user's intent:
- **SaaS / Web App:** Start with `landing-page` structure + `framed-grid-layout` or `product-proof-saas`.
- **Developer Tool / Infrastructure:** Use `split-layout-technical` or `technical-wireframe-info-layout`.
- **Agency / Portfolio / Studio:** Use `agency-grid-layout-minimal` or `editorial-portfolio-chapters`.
- **E-Commerce / Pricing:** Use `pricing-page` or `editorial-service-booking`.

### Step 2: Establish Base Design Tokens
Declare the base variables in the root container:
```css
:root {
  --bg-color: #0c0d0e;
  --surface-color: rgba(255, 255, 255, 0.04);
  --border-subtle: rgba(255, 255, 255, 0.08);
  --border-strong: rgba(255, 255, 255, 0.18);
  --accent-color: #3b82f6;
  --text-primary: #f3f4f6;
  --text-secondary: #9ca3af;
  --text-mono: 'JetBrains Mono', 'SF Mono', monospace;
  --font-sans: 'Inter', system-ui, -apple-system, sans-serif;
  --container-max: 1280px;
  --grid-gap: clamp(16px, 2vw, 24px);
  --section-pad: clamp(48px, 8vw, 96px);
}
```

### Step 3: Implement Grid Spans & Container Hierarchy
Use modern CSS grid with fluid clamp spacing:
```html
<main class="grid-shell">
  <header class="span-12 frame">...</header>
  <section class="span-8 frame">...</section>
  <aside class="span-4 frame">...</aside>
</main>
```
Responsive rules:
```css
.grid-shell {
  max-width: var(--container-max);
  margin: 0 auto;
  display: grid;
  grid-template-columns: repeat(12, minmax(0, 1fr));
  gap: var(--grid-gap);
  padding: 0 var(--grid-gap);
}

@media (max-width: 840px) {
  .grid-shell {
    grid-template-columns: 1fr;
  }
  .span-12, .span-8, .span-6, .span-4 {
    grid-column: 1 / -1;
  }
}
```

### Step 4: Add Structural Micro-Details
Enhance the layout with authentic details:
- **Corner Brackets:** Use multi-background gradients on `.frame-brackets` to draw crisp `18px` corners.
- **Metadata Rails:** Add mono utility labels (`[SYS: READY]`, `SEC // 01`, `TIMESTAMP`) at container headers.
- **Edge Fades / Masks:** Use CSS `mask-image: linear-gradient(...)` to softly fade edge content.

---

## Running Layout Demos Locally

Every layout in `layouts/` has a fully functional, zero-dependency demo. To view any demo in your browser:

```bash
# Run local HTTP server in any layout demo folder
python3 -m http.server 8000 -d .agents/skills/web-design/layouts/framed-grid-layout/demo
# Then open http://localhost:8000 in your browser
```
