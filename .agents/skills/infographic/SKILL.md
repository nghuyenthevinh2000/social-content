---
name: infographic
description: "Author self-contained HTML infographics, one-pagers, and charts in 16:9 or 9:16 canvases, fit to one viewport, and export to vector PDF by default. Image screenshots (2x Retina PNG via Playwright) are generated only when explicitly requested by the user."
---

# Infographic Authoring

```text
Confirm Wireframe -> Save layout_content.md -> Author index.html -> Export Vector PDF (Default) -> Verify
                                                                ↳ (Explicit Request Only) Capture Retina PNG
```

## Core Workflow & Mandatory Gates

| Step | Phase Name | Execution Protocol & Rules | Mandatory Gate Invariant |
|---|---|---|---|
| 1 | Plan & Confirm | Stop calling tools; present: (1) template selection, (2) design style from `design/`, (3) rationale, (4) content outline, (5) orientation, (6) dimensioned ASCII wireframe. | **STRICT USER GATE:** Never write code, create folders, or export files before explicit user approval. |
| 2 | Save Wireframe | Write `$OUTPUT_DIR/layout_content.md` containing the approved section order, exact data, and pixel-height bands. | Must sum exactly to 720px (landscape) or 1280px (portrait/custom) with no vertical gaps or overlaps. |
| 3 | Author HTML | Create self-contained `$OUTPUT_DIR/index.html` combining layout structure with design CSS variables, web fonts, and `@media print` rules. | Single-file output; inline CSS in `<style>`; must include `@media print` with exact page size and `margin: 0`; zero scrollbars. |
| 4 | Export Vector PDF (Default) | Run Playwright PDF export script: `node scripts/export-pdf.js <HTML> <PDF> --width <W> --height <H>`. | **Default deliverable.** Produces an exact-dimension, single-page vector PDF (`Pages: 1`) with zero margins. |
| 4b | Capture Retina PNG (Optional) | **ONLY when user explicitly requests image/screenshot/PNG**: `node scripts/screenshot-retina.js <HTML> <PNG> --scale 2 --width <W> --height <H>`. | Never run unless user specifically asks for PNG, image, or screenshot. |
| 5 | Verify & Link | Inspect PDF output with `pdfinfo "$OUTPUT_DIR/output.pdf"`; verify `Pages: 1` and exact page size; provide clickable markdown link `[output.pdf](file:///path/output.pdf)`. | Reject output if PDF has $> 1$ page or content clips. If PNG was explicitly requested, embed image. |

## Canvas Contract & Viewport Scaling

| Parameter | 16:9 Landscape | 9:16 Portrait | Custom / A4 Portrait |
|---|---|---|---|
| Design Width | `1280px` | `720px` | e.g. `900px` |
| Design Height | `720px` | `1280px` | e.g. `1273px` |
| Default Output | Vector PDF (`1280 × 720px` / `960 × 540pt`) | Vector PDF (`720 × 1280px` / `540 × 960pt`) | Vector PDF (Exact canvas size) |
| Retina Scale (When PNG requested) | 2x (`2560 × 1440px`) | 2x (`1440 × 2560px`) | 2x (`1800 × 2546px`) |
| Centering CSS | `#canvas { position: absolute; left: 50%; top: 50%; transform-origin: center center; }` | Same | Same |
| Uniform Fit Script | `const scale = Math.min(innerWidth / W, innerHeight / H, 1); canvas.style.transform = "translate(-50%, -50%) scale(" + scale + ")";` | Same | Same |
| Print CSS Contract | `@media print { @page { size: <W>px <H>px; margin: 0; } html, body { width: <W>px; height: <H>px; margin: 0; padding: 0; overflow: hidden; background: var(--bg); } #canvas { position: static !important; transform: none !important; width: <W>px !important; height: <H>px !important; } }` | Same | Same |
| Overflow Policy | Zero scrolling; `html, body { width: 100%; height: 100%; margin: 0; overflow: hidden; }` | Same | Same |

## Content Simplicity & Typography Floor Rules

| Visual Element | Minimum Typography Floor | Formatting & Style Standard | Anti-Inflation Invariant |
|---|---|---|---|
| Primary Title | Minimum **22px – 32px** | Display font (`var(--font-display)`), bold or medium weight, tight tracking. | Single-line preferred; maximum 2 lines; no multi-tiered subtitle stacks. |
| Section Headings | Minimum **18px – 24px** | Display or sans font; clean semantic hierarchy. | Descriptive and concise; avoid long bureaucratic labels. |
| Core Body Copy | Minimum **13.5px – 16px** | Line-height `1.55 – 1.70`; high-contrast text color (`var(--text)`). | Prohibits dense bullet lists (`→`, `•`); 1–2 strong narrative sentences beat 4–5 bullet items. |
| Badges & Tags | Minimum **10px – 11.5px** | Monospace or uppercase sans; tracking `+0.04em`; padding `2px 8px`. | Never smaller than 10px; eliminate redundant competing category pills. |
| SVG Node Titles | Minimum **14px – 16px** | Prominent serif or bold sans; centered inside node rectangles. | Strictly forbid micro-labels; ensure 15px+ safe margin from node borders. |
| SVG Node Subtext | Minimum **10.5px – 12px** | Clean sans-serif; 2 lines maximum per node container. | No text smaller than 10px anywhere in SVG diagrams or data charts. |
| Negative Space | Minimum **30% – 40%** | Reserved breathing room across layout margins, card padding, and band gaps. | Spare canvas space must enlarge existing typography, never pack new filler items. |
| Header Height | Maximum **60px – 75px** | Single-row flexbox: `Brand / Tag` + `Title` + `Context`. | No 5-badge stacks or oversized mastheads. |
| Footer Height | Maximum **30px – 40px** | Single-row hairline divider with brand signature and contact info. | No heavy boxed cards or philosophical quotes. |

## CLI Commands Reference

| Operation | Command Syntax | Required Flags / Preconditions | Output & Handoff |
|---|---|---|---|
| Resolve Repo Root | `REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)` | Run in bash session before executing relative paths. | Base directory for skill assets and scripts. |
| Create Folder | `mkdir -p "$OUTPUT_DIR"` | Provide absolute path conforming to project conventions. | Target directory for wireframe, HTML, and PDF. |
| **Export Vector PDF (Default)** | `node "$REPO_ROOT/.agents/skills/infographic/scripts/export-pdf.js" "$OUTPUT_DIR/index.html" "$OUTPUT_DIR/output.pdf" --width <W> --height <H>` | Requires Node.js and Playwright; matches canvas dimensions. | **Primary deliverable.** Produces 1-page vector PDF. |
| Verify PDF Output | `pdfinfo "$OUTPUT_DIR/output.pdf" \| grep -E "Pages\|Page size"` | `Pages:` must be exactly `1`. | Confirms single-page vector output without overflow. |
| Capture Portrait PNG (Explicit only) | `node "$REPO_ROOT/.agents/skills/infographic/scripts/screenshot-retina.js" "$OUTPUT_DIR/index.html" "$OUTPUT_DIR/output.png" --scale 2 --width 720 --height 1280` | Run ONLY when user explicitly asks for PNG/image. | Produces 1440×2560px Retina screenshot. |
| Capture Landscape PNG (Explicit only) | `node "$REPO_ROOT/.agents/skills/infographic/scripts/screenshot-retina.js" "$OUTPUT_DIR/index.html" "$OUTPUT_DIR/output.png" --scale 2 --width 1280 --height 720` | Run ONLY when user explicitly asks for PNG/image. | Produces 2560×1440px Retina screenshot. |
| Capture Custom PNG (Explicit only) | `node "$REPO_ROOT/.agents/skills/infographic/scripts/screenshot-retina.js" "$OUTPUT_DIR/index.html" "$OUTPUT_DIR/output.png" --scale 2 --width <W> --height <H>` | Run ONLY when user explicitly asks for PNG/image. | Produces custom 2x Retina screenshot. |

## Pre-Export Checklist

| Verification Category | Check Condition | Enforcement Protocol |
|---|---|---|
| User Approval Gate | User explicitly approved template, style, outline, and wireframe. | Block all execution if user has not explicitly confirmed Step 1. |
| Output Format Gate | Default to vector PDF (`output.pdf`). Do not capture PNG unless explicitly asked. | Export PDF via `export-pdf.js`; skip image capture by default. |
| Single-Page Invariant | `pdfinfo "$OUTPUT_DIR/output.pdf"` reports `Pages: 1`. | Reject output if content spills onto page 2. Fix `@media print` rules. |
| Wireframe Parity | HTML sections and Y bands match `$OUTPUT_DIR/layout_content.md`. | Heights sum to canvas total; no overlaps, gaps, or clipping. |
| Self-Contained Asset | Inline CSS in `<style>`; Google Fonts and CDNs loaded via HTTPS. | Zero relative local imports; self-contained in single file. |
| Brand Token Fidelity | Uses brand manifest tokens (`--bg`, `--primary`, `--accent`) when project brand exists. | Never default to generic library styles when `brand/` directory exists. |
| Typography Floors | No text $<$ 10px on canvas; body $\ge$ 13.5px; headings $\ge$ 18px; SVG $\ge$ 10.5px. | Enforce minimum font sizes across all elements and SVG charts. |
| Anti-Inflation Check | No maximal filling; no dense bullet lists; 30%+ negative space. | Convert spare space into larger typography and line-heights. |
| Header & Footer Bounds | Header $\le$ 75px; Footer $\le$ 40px; both single-row minimal components. | Eliminate stacked pills and heavy quote cards. |

## Asset Discovery & References

| Resource Category | File Location / Path | Purpose & Content |
|---|---|---|
| **PDF Export Utility (Default)** | `scripts/export-pdf.js` | Authoritative Playwright vector PDF export utility (single-page, custom dimensions, font preloading). |
| Screenshot Utility (Optional) | `scripts/screenshot-retina.js` | Playwright Retina screenshot capture utility (run only when explicitly requested). |
| Layout Index | `layout/README.md` | Catalog of structural templates, DOM hierarchies, and content slots. |
| Layout Specs | `layout/<template>/design.md` | Content specifications and dimension allocations per template. |
| Design Style Index | `design/README.md` | 34 curated visual styles, color moods, and typography pairings. |
| Design Style Specs | `design/<style>/design.md` & `template.json` | CSS variables, Google Fonts URLs, and shadow/border radius tokens. |
| Wireframe Previews | `references/README.md` | Interactive preview script and JSON-driven wireframe reference models. |
