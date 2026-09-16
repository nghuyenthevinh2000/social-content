---
name: branding
description: Comprehensive end-to-end brand operating system covering strategy, identity, naming, positioning, messaging, voice, guidelines, audience research, audits, architecture, and rebranding. Use when the user asks for anything related to branding — brand strategy ("create a brand report", "brand questionnaire", "brand strategy document"), naming ("name a product", "name a SaaS", "brand name", "rename", "check name availability"), brand positioning ("positioning statement", "market differentiation", "what space do we own"), brand messaging ("tagline", "value proposition", "messaging hierarchy", "elevator pitch"), brand story ("origin story", "founder story", "why we exist", "about us"), target audience ("ICP", "ideal customer profile", "customer persona", "audience research"), brand voice ("tone of voice", "copywriting style guide", "verbal identity"), brand identity ("visual identity brief", "logo direction", "color palette", "typography pairings"), brand guidelines ("brand book", "style guide", "brand standards", "brand toolkit"), brand audit ("brand review", "brand health check", "is our brand consistent", "brand diagnosis"), brand architecture ("portfolio structure", "sub-brand", "master brand", "house of brands", "branded house"), rebranding ("brand refresh", "brand transformation", "modernize brand"), or brand package management ("set brand context", "init brand", "brand context file", "save brand info").
compatibility: Availability checks optionally use bash, whois, curl, and npm (gracefully degrades when absent).
allowed-tools: Read, Grep, Glob, Bash(whois *), Bash(curl *), Bash(npm view *), Bash(gh repo view *), WebSearch, WebFetch
argument-hint: [describe branding task: e.g. "strategy for new client", "name our developer tool", "brand audit", "positioning statement"]
metadata:
  version: 2.0.0
---

# Unified Branding Suite

A comprehensive brand operating system for founders, consultants, strategists, and designers. Instead of scattered, ephemeral chat notes, this skill manages brands as **structured, persistent packages on disk** (`brand.yaml` + markdown artifacts + assets) and guides you through 15 specialized branding workflows across 5 distinct phases.

---

## The Persistence Model (Brand Package)

Every brand managed by this skill lives as a versioned, queryable package on disk:

```
<brand-directory>/       # ./brand/ (in-situ) · brands/<slug>/ (portfolio) · <product>/brand/
  brand.yaml             # Manifest & queryable state (name, one-liner, status, artifact flags)
  context.md             # Core brand DNA (audience, values, mission, positioning baseline)
  strategy.md            # Full brand strategy report (vision, pillars, archetype, goals)
  positioning.md         # Market position, category framing, differentiation matrix
  audience.md            # Deep ICP, customer personas, psychographics, jobs-to-be-done
  competitors.md         # Competitive brand landscape, perceptual mapping, white space
  naming.md              # Naming brief, metaphor territories, vetting & scored finalists
  story.md               # Origin story, founder narrative, "Why we exist"
  messaging.md           # Taglines, elevator pitch, value props, proof points
  voice.md               # Verbal identity, tone spectrum, writing rules & vocabulary
  identity.md            # Visual identity brief, logo, color palette, typography pairing
  guidelines.md          # Master brand standards book consolidating all decisions
  audit.md               # Health check, touchpoint consistency scores, gap analysis
  architecture.md        # Portfolio relationship model & naming taxonomy
  rebranding.md          # Transformation roadmap & change scope (refresh vs reboot)
  assets/                # Logos, color swatches, typography files, exports
```

### Discovery Contract
Before asking the user redundant questions:
1. **Check for an existing package:** Look for `brand.yaml` in `./`, `./brand/`, or `brands/<slug>/`.
2. **If found:** Read `brand.yaml` and `context.md` (plus any relevant sibling file). Do NOT re-ask questions that are already answered in the package.
3. **If not found:** Run **Workflow 01 (Brand Init)** to scaffold the package with `scripts/brand.sh`.
4. **When completing any workflow:** Write or update the corresponding `.md` file inside the brand package and flip its flag in `brand.yaml` (`artifacts.<artifact>: true`).

---

## Fast Routing Matrix

Match the user's prompt to the appropriate workflow and reference document:

| User Intent / Trigger | Phase | Primary Workflow | Detailed Reference | Output Artifact |
| :--- | :--- | :--- | :--- | :--- |
| "Start new brand", "Set up brand", "Init package" | Phase 0 | **Workflow 01: Brand Init** | [`references/01-brand-init.md`](references/01-brand-init.md) | `brand.yaml` |
| "Save brand info", "Set brand context", "Brand DNA" | Phase 0 | **Workflow 02: Brand Context** | [`references/02-brand-context.md`](references/02-brand-context.md) | `context.md` |
| "Target audience", "Customer persona", "ICP", "Audience research" | Phase 1 | **Workflow 03: Target Audience** | [`references/03-target-audience.md`](references/03-target-audience.md) | `audience.md` |
| "Competitor brand analysis", "How do competitors position" | Phase 1 | **Workflow 04: Competitor Landscape** | [`references/04-competitor-branding.md`](references/04-competitor-branding.md) | `competitors.md` |
| "Brand audit", "Something feels off", "Brand review", "Health check" | Phase 1 | **Workflow 05: Brand Audit** | [`references/09-brand-audit.md`](references/09-brand-audit.md) | `audit.md` |
| "Brand strategy", "Brand report", "Client questionnaire" | Phase 2 | **Workflow 06: Brand Strategy** | [`references/05-brand-strategy.md`](references/05-brand-strategy.md) | `strategy.md` |
| "Brand positioning", "Positioning statement", "Differentiation" | Phase 2 | **Workflow 07: Brand Positioning** | [`references/06-brand-positioning.md`](references/06-brand-positioning.md) | `positioning.md` |
| "Brand architecture", "Sub-brand", "House of brands", "Portfolio" | Phase 2 | **Workflow 08: Brand Architecture** | [`references/07-brand-architecture.md`](references/07-brand-architecture.md) | `architecture.md` |
| "Rebrand", "Brand refresh", "Modernize brand", "Outgrown our brand" | Phase 2 | **Workflow 09: Rebranding** | [`references/08-rebranding.md`](references/08-rebranding.md) | `rebranding.md` |
| "Name product", "Find brand name", "Check availability" | Phase 3 | **Workflow 10: Naming & Availability** | [`references/10-naming.md`](references/10-naming.md) | `naming.md` |
| "Brand story", "Origin story", "Founder story", "About us" | Phase 3 | **Workflow 11: Brand Story** | [`references/11-brand-story.md`](references/11-brand-story.md) | `story.md` |
| "Brand messaging", "Value proposition", "Tagline", "Elevator pitch" | Phase 3 | **Workflow 12: Brand Messaging** | [`references/12-brand-messaging.md`](references/12-brand-messaging.md) | `messaging.md` |
| "Brand voice", "Tone of voice", "Copywriting guidelines" | Phase 3 | **Workflow 13: Brand Voice** | [`references/13-brand-voice.md`](references/13-brand-voice.md) | `voice.md` |
| "Visual identity", "Logo brief", "Color palette", "Typography" | Phase 4 | **Workflow 14: Visual Identity** | [`references/14-brand-identity.md`](references/14-brand-identity.md) | `identity.md` |
| "Brand guidelines", "Brand book", "Brand standards", "Style guide" | Phase 4 | **Workflow 15: Brand Guidelines** | [`references/15-brand-guidelines.md`](references/15-brand-guidelines.md) | `guidelines.md` |

---

## Progressive Disclosure & Reference Loading

> [!TIP]
> **Context Budget:** Do NOT load all references into context simultaneously.
> 1. Read the brand's `brand.yaml` and `context.md` first.
> 2. Open **only the specific reference file** for the current workflow.
> 3. For naming tasks, consult [`references/10-naming.md`](references/10-naming.md), which selectively pulls sub-modules in `references/naming/` as needed.

---

## Phase 0: Persistence & Foundations

### Workflow 01: Brand Init
- **Goal:** Initialize the brand folder, `brand.yaml` manifest, and `assets/` directory.
- **Reference:** [`references/01-brand-init.md`](references/01-brand-init.md) and [`references/brand-package-spec.md`](references/brand-package-spec.md).
- **Tooling:** Pure bash script at `scripts/brand.sh`:
  ```bash
  # Initialize a new brand package
  bash <path-to-branding-skill>/scripts/brand.sh init --name "Acme" --one-liner "Developer tools for AI" --out brand --date "$(date +%F)"

  # Multi-brand portfolio registry
  bash <path-to-branding-skill>/scripts/brand.sh init --name "Acme" --register brands/registry.yaml
  bash <path-to-branding-skill>/scripts/brand.sh list --registry brands/registry.yaml
  ```

### Workflow 02: Brand Context
- **Goal:** Capture the foundational brand DNA into `<package>/context.md`.
- **Reference:** [`references/02-brand-context.md`](references/02-brand-context.md).
- **Captures:**
  1. Brand basics (name, one-liner, industry, stage, website).
  2. Target audience basics (who, problem, customer language).
  3. Positioning basics (core differentiator, top competitors, market segment).
  4. Brand personality (3-5 adjectives, formal vs casual, playful vs serious).
  5. Values and mission statement.
  6. 12-month business goals and key metrics.

---

## Phase 1: Research & Discovery

### Workflow 03: Target Audience
- **Goal:** Build deep psychographic personas and Jobs-to-be-Done (JTBD) profiles.
- **Reference:** [`references/03-target-audience.md`](references/03-target-audience.md).
- **Core Methodology:** Move beyond flat demographics to psychographics, behavioral triggers, decision criteria, and verbatim customer vocabulary.
- **Output:** Writes to `<package>/audience.md`.

### Workflow 04: Competitor Brand Landscape
- **Goal:** Unpack how competitors communicate, look, and position, finding untapped white space.
- **Reference:** [`references/04-competitor-branding.md`](references/04-competitor-branding.md).
- **Core Methodology:** Competitor teardowns across positioning, messaging, visual tone, audience targeting, and perceptual 2x2 mapping.
- **Output:** Writes to `<package>/competitors.md`.

### Workflow 05: Brand Audit & Diagnosis
- **Goal:** Comprehensive brand health check when "something feels off", "brand feels outdated", or after scaling.
- **Reference:** [`references/09-brand-audit.md`](references/09-brand-audit.md).
- **Core Methodology:** Audit 6 dimensions (Strategic Clarity, Visual Consistency, Verbal Consistency, Experience & Touchpoints, Market Perception, Brand Governance). Evaluates declared (docs) vs real (live touchpoints) drift.
- **Output:** Scored scorecard + prioritized roadmap written to `<package>/audit.md`.

---

## Phase 2: Strategy & Architecture

### Workflow 06: Brand Strategy Report
- **Goal:** Senior brand strategist workflow for consulting clients or comprehensive company strategy.
- **Reference:** [`references/05-brand-strategy.md`](references/05-brand-strategy.md).
- **Modes:**
  - *Fresh Start:* Present the 5-part questionnaire (The Basics, Audience & Market, Values & Personality, Personality Sliders 1-8, Goals).
  - *Filled Brief:* Immediately generate the 12-section editorial Brand Strategy Report (Origin, Vision, Mission, Values, Goals, Target Personas, Personality, Archetype, Attributes, Tagline Options, Positioning, Value Proposition).
- **Output:** Writes to `<package>/strategy.md`.

### Workflow 07: Market Positioning
- **Goal:** Carve out a distinct, defensible market position relative to competitors.
- **Reference:** [`references/06-brand-positioning.md`](references/06-brand-positioning.md).
- **Core Methodology:** Category definition/reframing, differentiation pillars, competitive territory mapping, the canonical Positioning Statement formula, and "What this brand refuses to be."
- **Output:** Writes to `<package>/positioning.md`.

### Workflow 08: Brand Architecture
- **Goal:** Structure multi-product portfolios, sub-brands, or parent company relations.
- **Reference:** [`references/07-brand-architecture.md`](references/07-brand-architecture.md).
- **Core Models:** Branded House (Masterbrand) vs House of Brands vs Endorsed Brands vs Hybrid. Product naming taxonomy and brand extension decision matrix.
- **Output:** Writes to `<package>/architecture.md`.

### Workflow 09: Rebranding & Transformation
- **Goal:** Plan a structured brand evolution (Refresh vs Reposition vs Full Reboot).
- **Reference:** [`references/08-rebranding.md`](references/08-rebranding.md).
- **Core Methodology:** Diagnostic assessment, equity preservation audit, defining the strategic shift, change scope determination, and phased internal/external rollout plan.
- **Output:** Writes to `<package>/rebranding.md`.

---

## Phase 3: Verbal Identity & Naming

### Workflow 10: Naming & Availability Verification
- **Goal:** Metaphor-driven, high-calibre naming process that avoids AI clichés and verifies real-world availability.
- **Reference:** [`references/10-naming.md`](references/10-naming.md) (uses modular files in [`references/naming/`](references/naming/)).
- **7-Step Process:**
  1. *Naming Brief:* Establish functional, tonal, locale, and competitive calibre constraints (use [`templates/naming-brief.md`](templates/naming-brief.md)).
  2. *Metaphor Exploration:* 6 metaphor-finding questions across domain, emotion, contrast, and action ([`references/naming/metaphor-mapping.md`](references/naming/metaphor-mapping.md)).
  3. *Candidate Generation:* 40+ raw ideas across distinct territories.
  4. *Anti-Pattern & Phonosemantic Screening:* Filter vowel/consonant feel and purge tech clichés ([`references/naming/anti-patterns.md`](references/naming/anti-patterns.md), [`references/naming/phonosemantics.md`](references/naming/phonosemantics.md)).
  5. *Availability Check:* Run `scripts/check-availability.sh [name] domain npm github pypi telegram` to check live namespace availability.
  6. *Objective Scoring:* Score candidates against the 8-criteria rubric ([`references/naming/evaluation.md`](references/naming/evaluation.md)).
  7. *Presentation:* Present top 4-6 finalists with metaphor rationales, scores, and exact availability status.
- **Output:** Writes to `<package>/naming.md`.

### Workflow 11: Brand Story
- **Goal:** Craft the origin story, founder journey, and "Why We Exist" narrative.
- **Reference:** [`references/11-brand-story.md`](references/11-brand-story.md).
- **Narrative Arc:** The Spark / Problem -> The Turning Point -> The Conviction / Belief -> The Reality Today. Includes website "About Us" page copy.
- **Output:** Writes to `<package>/story.md`.

### Workflow 12: Brand Messaging Hierarchy
- **Goal:** Clear, consistent messaging frameworks across customer journey stages.
- **Reference:** [`references/12-brand-messaging.md`](references/12-brand-messaging.md).
- **Hierarchy:** Tagline options (direct, evocative, provocative), 10-second elevator pitch, core value propositions (Benefit + Mechanism + Proof), and audience-specific message maps.
- **Output:** Writes to `<package>/messaging.md`.

### Workflow 13: Verbal Identity & Brand Voice
- **Goal:** Actionable copy guidelines so any writer sounds unmistakably like the brand.
- **Reference:** [`references/13-brand-voice.md`](references/13-brand-voice.md).
- **Voice Guide:** 3-4 voice traits with "This, Not That" examples, tone spectrum across contexts (marketing, UI, customer support, error states), vocabulary dos and don'ts, and punctuation/formatting rules.
- **Output:** Writes to `<package>/voice.md`.

---

## Phase 4: Visual Identity & Master Standards

### Workflow 14: Visual Identity Brief
- **Goal:** Complete creative brief for logo designers, typographers, and design systems.
- **Reference:** [`references/14-brand-identity.md`](references/14-brand-identity.md).
- **Components:** Logo direction & concept metaphors, primary/secondary/accent color palette with hex/RGB/CMYK and emotional rationale, typography hierarchy (display, body, mono pairings), imagery and art direction guidelines.
- **Output:** Writes to `<package>/identity.md`.

### Workflow 15: Master Brand Guidelines
- **Goal:** Codify all strategic, verbal, and visual decisions into a single master brand book.
- **Reference:** [`references/15-brand-guidelines.md`](references/15-brand-guidelines.md).
- **Document Structure:**
  - Part 1: Brand Foundation (Essence, Mission, Vision, Values, Positioning).
  - Part 2: Visual Identity (Logo rules, clearspace, sizing, color specs, typography scale, iconography, UI tokens).
  - Part 3: Verbal Identity & Messaging (Tone spectrum, copy examples, taglines, elevator pitch).
  - Part 4: Touchpoint Applications (Web, presentation decks, social media, merchandise, documentation).
  - Part 5: Brand Governance & Compliance (Do's and Don'ts, asset library index).
- **Output:** Writes to `<package>/guidelines.md`.

---

## Internationalization & Spanish / LATAM Branding

When working with Spanish-speaking or Latin American markets:
- Consult [`references/localization-es-latam.md`](references/localization-es-latam.md).
- Enforce Spanish phonosemantics (silent 'h', 'j' /x/ sound, 'v'/'b' homophony, English digraph failures).
- Screen candidate names against regional slang across Mexico, Colombia, Argentina, Peru, and Chile.
- Check gendered article alignment ("el" vs "la") and diminutive resonance ("-ito/-ita").
