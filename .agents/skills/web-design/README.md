---
name: web-design
summary: Web design and UI engineering skill covering grids, responsive layouts, conversion patterns, and a mandatory hero preview showcase for every design task.
tags: [web-design, ui, ux, layouts, css, tailwind, grid, landing-page]
submodules:
  layouts: Curated collection of 28 modular web design layout systems with interactive demos and recreation prompts.
  references: Design-first prompting guidance and a JSON-driven hero comparison tool with full specifications.
  SKILL.md: Master web design playbook with a mandatory hero preview showcase before selecting a direction.
---

# Web Design Skill

A centralized skill for designing, structuring, and engineering modern web interfaces, landing pages, and interactive UI systems.

## Key Capabilities

- **Mathematical Layout Tokens:** Fluid clamp typography, 1px disciplined border grids, consistent gap scales.
- **Anti-Generic Taste Rules:** Avoids repetitive floating cards, blurred drop shadows, and non-semantic div containers.
- **28 Modular Layout Archetypes:** Stored in [`layouts/`](./layouts/) with full specs, token definitions, and zero-dependency interactive browser demos.
- **High-Conversion Narrative Frameworks:** Master structure for SaaS landing pages, pricing grids, and product proof walkthroughs.

## Directory Structure

```text
web-design/
├── README.md               # Folder frontmatter and overview
├── SKILL.md                # Master agent execution instructions & catalog
└── layouts/                # Modular layout skills
    ├── README.md           # Layout library submodules frontmatter
    ├── framed-grid-layout/ # 12-col grid with visible boundaries & L-brackets
    ├── split-layout-technical/ # Dual-panel technical layout with mono metadata
    ├── landing-page/       # High-conversion single-offer architecture
    ├── pricing-page/       # SaaS pricing tiers and feature comparison matrix
    └── ... (28 layout systems total)
```

## How to Use

When building or reviewing web interfaces, consult [`SKILL.md`](./SKILL.md) to select an appropriate layout archetype, extract base CSS tokens, and follow the step-by-step layout engineering workflow.
