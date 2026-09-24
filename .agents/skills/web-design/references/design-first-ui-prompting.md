---
name: design-first-ui-prompting
description: "Design-first UI prompting playbook and mindset by Meng To. Use when turning fuzzy UI ideas into rigorous, spec-driven design systems, prompts, and layout structures. Covers prompt skeleton, negative guardrails, hero-first workflows, typography rules, and anti-AI-slop principles."
tags:
  - ui-design
  - prompt-engineering
  - design-systems
  - meng-to
  - layout-architecture
---

# Design-First UI Prompting Playbook (Meng To Mindset)

> **"Prompt like a design system, not a wish."**
> — Meng To (`MengTo/Skills/agent-skills/ui/design-first-ui-prompting`)

AI doesn’t make great design by default. It makes **average design fast**. Your competitive edge is taste, craft, and architectural constraints.

---

## 1. Core Mindset & Principles

### 1) Screenshots Beat Prompts

One screenshot contains **fonts, spacing, colors, icons, and layout hierarchy**. Models comprehend visual references immediately.

- **Rule:** Stop writing 1,000-word vague descriptions. Start collecting and anchoring visual reference packs.
- Save local UI inspirations in `refs/` and point prompt specifications directly to concrete visual benchmarks.

### 2) The Hero Section Is Half the Job

The hero section is your visual anchor and cover image.

- **Workflow:** Lock the hero first. Nail layout, typography tension, and brand signal color.
- Build and iterate the rest **section-by-section**, not all at once.

### 3) Taste Is the Moat & Avoid AI Slop

AI elevates the baseline, so generic "AI slop" immediately cheapens a product. Avoid:

- ❌ Gratuitous purple/indigo gradient washes
- ❌ Generic Lucide/Feather icons scattered everywhere
- ❌ Bubbly floating cards with heavy blurred drop shadows
- ❌ Monotonous font scales and generic Inter defaults

**The Craft Fix:**

- Use disciplined neutral obsidian or warm paper backgrounds.
- Exactly **one vibrant signal accent** (e.g. laser cyan, emerald, international orange).
- Distinct icon curation (e.g. Iconify Solar outline/broken/duotone, Simple Icons for logos).
- Distinct typography moves: oversized tightly-tracked display titles paired with micro uppercase monospaced labels.

### 4) Negative Prompts as Architectural Guardrails

Lock working components using explicit negative boundaries:

- *"Do not alter the hero layout."*
- *"No floating cards with drop shadows."*
- *"No extra text or icons beyond provided specification."*
- *"No purple gradients or multi-colored pill buttons."*

### 5) Add Craft Signals

Small details that immediately elevate an interface from amateur to Linear / Apple caliber:

- `01 / 02 / 03` step numbering in monospace uppercase
- Visible container hairline boundary lines (`1px solid rgba(255,255,255,0.08)`)
- Subtle specular top highlights (`inset 0 1px 0 rgba(255,255,255,0.12)`)
- Corner coordinate stamps and crosshairs (`+ [1028×1920:Z01]`)

---

## 2. Master Spec-Driven Prompt Skeleton

Copy and fill this structural spec when commanding agents or crafting interfaces:

```text
GOAL
- What are we making? (e.g., landing page hero / developer dashboard / spatial telemetry plate)
- Who is it for? (persona / audience)
- Success criteria: (clarity, conversion, engineered aesthetic)

FORMAT
- Canvas size / Aspect ratio: (e.g., 1028x1920 portrait / 1440x900 desktop / 1280px container)
- Safe margins & padding: (e.g., clamp(24px, 4vw, 48px))

LAYOUT (Wireframe in words)
- Grid: (e.g., 12-column rigid grid / 50-50 split / 3-zone vertical plate)
- Placement: (e.g., oversized title left, telemetry KPIs right, terminal bottom)
- Visual Hierarchy: Hero Display Title → Subhead / Meta → Interactive Canvas → Status Bar

TYPE SYSTEM
- Primary Display: (e.g., SF Pro Display, Plus Jakarta Sans, Söhne - tight tracking -0.04em)
- Monospaced Metadata: (e.g., JetBrains Mono, SF Mono - 11px-13px uppercase, 0.10em tracking)
- Contrast: Stark scale tension between oversized headers (48px+) and microscopic labels (11px-13px)

COLOR + MATERIAL
- Foundation: (e.g., deep obsidian #07090b, matte charcoal #0f1318)
- Surfaces: (e.g., frosted glass with backdrop-filter: blur(24px))
- Borders: (Hairline 1px solid rgba(255,255,255,0.10) with specular top highlight)
- Signal Color: (Exactly ONE vibrant accent: Laser Cyan #00f0ff or Lime #00f5a0)

COPY (Render EXACTLY)
- Headline: [Exact text]
- Subtitle: [Exact text]
- Actions: [Exact button labels]

CONSTRAINTS (Change 1–2 variables only per iteration)
- FONT: [Designated font stack]
- ACCENT: [Single signal color]
- CONTAINER: [1px hairline border, zero drop shadow]

NEGATIVE PROMPT
- NO purple gradients
- NO soft floating bubble cards
- NO generic pill buttons
- NO unrequested decorative widgets or icons
- NO gibberish or truncated placeholder copy
```

---

## 3. Fast Iteration Checklist

When reviewing or refining an interface, evaluate against this checklist:

- [ ] **Spacing & Rhythm:** Are margins, card gaps, and baseline grids mathematically consistent?
- [ ] **Contrast & Luminance:** Does text pop cleanly against dark obsidian or light paper without muddy midtones?
- [ ] **One Accent Rule:** Is there strictly ONE vibrant signal color guiding the eye to the active state?
- [ ] **Typographic Tension:** Is there stark contrast between oversized hero display text and micro monospaced coordinates?
- [ ] **Physicality:** Do surfaces feel engineered (hairline borders, specular highlights) rather than generic web cards with blurry shadows?
