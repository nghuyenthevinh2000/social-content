---
name: web-design
summary: Preview-first web design workflow with project-specific hero comparisons, exact page-content wireframes, an explicit user-approval gate, and implementation guidance.
tags: [web-design, ui, ux, layouts, css, tailwind, grid, landing-page]
submodules:
  layouts: Curated collection of 28 modular web design layout systems with interactive demos and recreation prompts.
  references: Design-first guidance, a Node preview server, and JSON-driven comparisons with exact page-content wireframes.
  SKILL.md: Preview-first workflow requiring exact section content, a served project preview, and explicit user approval before implementation.
---

# Web Design Skill

A centralized skill for designing, structuring, and engineering modern web interfaces, landing pages, and interactive UI systems.

## Key Capabilities

- **Preview-First Workflow:** Create project-specific `wireframe_preview.html` and `wireframe_preview.json`, then show the working preview and wait for explicit user approval before building the full page.
- **Mathematical Layout Tokens:** Fluid clamp typography, 1px disciplined border grids, consistent gap scales.
- **Anti-Generic Taste Rules:** Avoids repetitive floating cards, blurred drop shadows, and non-semantic div containers.
- **28 Modular Layout Archetypes:** Stored in [`layouts/`](./layouts/) with full specs, token definitions, and zero-dependency interactive browser demos.
- **High-Conversion Narrative Frameworks:** Master structure for SaaS landing pages, pricing grids, and product proof walkthroughs.

## Directory Structure

```text
web-design/
├── README.md               # Folder frontmatter and overview
├── SKILL.md                # Preview-first web design workflow
├── references/             # Preview templates and design-spec guidance
└── layouts/                # Modular layout skills
    ├── README.md           # Layout library submodules frontmatter
    ├── framed-grid-layout/ # 12-col grid with visible boundaries & L-brackets
    ├── split-layout-technical/ # Dual-panel technical layout with mono metadata
    ├── landing-page/       # High-conversion single-offer architecture
    ├── pricing-page/       # SaaS pricing tiers and feature comparison matrix
    └── ... (28 layout systems total)
```

## How to Use

When building a web interface, follow [`SKILL.md`](./SKILL.md): create and show a project-specific browser preview from the templates in [`references/`](./references/), then wait for explicit user approval before implementing the finished page.
