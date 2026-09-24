---
name: layouts
summary: Curated collection of 28 modular web design layout systems, container frameworks, and interactive demos.
tags: [layouts, grid, containers, wireframe, responsive, web-design]
submodules:
  agency-grid-layout-minimal: Minimal agency design system with disciplined editorial grid and oversized typography.
  blue-laser-clean-glass-layout: Dark glass layout system with blue laser accents and frosted shells.
  book-serif-index: Archival book-reader design system with serif-led pages and mono index navigation.
  bright-green-tech-system-webgl: Technical design system with structured split layouts and hard-framed containers.
  clean-minimal-beige-light-mode: Clean minimal beige light-mode system with warm neutral shells.
  container-lines: Vertical container guide lines with mini corner squares for structured layouts.
  corner-diagonals: Diagonal-cut corners and chamfered edges for buttons, panels, and frames.
  dark-blue-contrasting-clean: High-contrast dark-blue design system with cobalt feature blocks.
  dark-glass-clean-layout: Dark glass layout system with frosted shells and clean multi-column workflows.
  documentary-brutalist-agency: Brutalist agency and studio portfolio layout with raw structural borders.
  editorial-portfolio-chapters: Chapter-based portfolio layout for studios, artists, and case studies.
  editorial-service-booking: Editorial appointment and service booking layout.
  editorial-tech: Editorial magazine composition blended with precision product-tech detailing.
  framed-grid-layout: Minimal framed grid layout with visible boundary lines, L-brackets, and diagonal texture.
  framed-tech-dark-border-gradient: Dark technical layout system with gradient-border shells and asymmetrical grid.
  funky-purple-container-tech: Dark container-led technical layout with fuchsia-purple accents.
  image-first-grid-layout: Image-led grid design system with full-bleed imagery and structural guide lines.
  landing-page: High-converting single-offer landing page architecture and copy hierarchy.
  light-mode-paper-technical: Tactile paper-textured light-mode technical layout with engineered specs.
  nested-container-clean-agency: Clean agency layout with nested container boxes and generous whitespace.
  nested-container-frames: Container-in-container layout system with centered inner content shells.
  operational-enterprise-ai: Enterprise AI, security, and operations dashboard and page layout.
  orange-clean-paper-saas: Clean paper texture paired with vibrant orange accents for modern SaaS.
  pricing-page: High-converting SaaS pricing page layout with tier cards and feature comparison matrix.
  product-proof-saas: Proof-focused SaaS landing layout with workflow previews and evidence blocks.
  split-layout-technical: Technical split-screen layout with dual panels, fine frame lines, and mono metadata.
  tech-green-dark-mode-modern: Modern dark-mode technical layout with matte-black surfaces and emerald status lines.
  technical-wireframe-info-layout: Monochrome technical wireframe layout with exploded 3D structure and connection callouts.
---

# Web Design Layout Library

This directory contains 28 production-ready, modular web design layout systems derived from real-world high-end agency and modern SaaS aesthetics.

## Folder Structure

Each layout folder contains:
- `SKILL.md`: The layout specification, CSS tokens, structural patterns, and taste rules.
- `demo/index.html`: Fully self-contained runnable browser demo.
- `demo/preview.jpg`: 1280x720 rendered browser preview.
- `demo/PROMPT.md`: Exact prompt to recreate or remix the layout.
- `demo/source.json`: Provenance metadata.

## Quick Preview & Testing

Run any layout demo locally:
```bash
python3 -m http.server 8000 -d .agents/skills/web-design/layouts/<layout-folder>/demo
```
