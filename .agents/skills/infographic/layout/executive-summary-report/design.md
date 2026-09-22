---
name: executive-summary-report
title: Executive Summary Report
format: A4 Portrait (900 × 1273 px)
retina_dimensions: 1800 × 2546 px (--scale 2)
category: Executive Briefing / Strategic Management / Operational Review
screenshot_command: node "$REPO_ROOT/.agents/skills/infographic/scripts/screenshot-retina.js" "$REPO_ROOT/topics/<slug>/index.html" "$REPO_ROOT/topics/<slug>/output.png" --scale 2 --width 900 --height 1273 --timeout 2000
---

# Executive Summary Report Template

## What This Template Serves

The **Executive Summary Report** is a balanced, two-column corporate briefing document designed for senior leadership, board directors, and executive stakeholders. It condenses complex business narratives, strategic pillars, and operational initiatives into a structured, easily scannable format.

Key structural highlights include:
1. **Pill-Badge Visual Rhythm**: Uses distinctive, fully rounded navy pill badges (`.section-pill`) for every section heading, creating an orderly, editorial cadence.
2. **Symmetrical 2-Column Split**: Distributes qualitative strategy (overview, findings, audience segmentation) on the left, and quantitative execution (5 vertical objective items + marketing mix bar chart) on the right.
3. **Five-Goal Capacity**: While other templates accommodate 3 goals, this template features 5 stacked goal items with circular icon markers, making it superior for multi-objective programs.
4. **Atmospheric Wave Mesh Watermark**: Elegant 3D SVG wave mesh background that communicates sophistication without impairing legibility.

### Ideal Use Cases
- **Quarterly & Annual Executive Briefings**: Highlighting departmental progress, strategic highlights, and key operational focus areas.
- **Commercial & Market Entry Proposals**: Presenting a business opportunity with 5 distinct objectives and targeted market segmentation.
- **Transformation & Reorganization Plans**: Summarizing change-management goals, key diagnostic findings, and channel/resource allocations.
- **Product Portfolio & Strategy Overviews**: Sharing strategic roadmaps where multiple objectives (e.g., retention, growth, awareness, partnerships) require equal visual weight.

### When NOT to Use
- Heavy financial metric reporting with multi-column KPI grids and P&L tables (use `financial-performance-report`).
- Pure system architecture diagrams or cloud tech stacks (use `enterprise-architecture-stack`).
- Social media channel performance tracking (use `monthly-social-media-report`).

---

## Agent Rationale Snippet (For Step 1 Confirmation)

When proposing this template during **Step 1 (Plan & Confirm Gate)**, adapt this rationale for the user:

> "I recommend the **Executive Summary Report** template. It features a balanced, two-column editorial layout anchored by signature navy pill headers. The left column provides a complete strategic narrative—combining an executive overview, bulleted recommendations, and an audience segmentation matrix—while the right column comfortably hosts up to 5 milestone objectives with circular icon badges and an allocation bar chart."

---

## Visual & Design Architecture

### Color Palette
| Variable / Token | Hex Code | Role & Usage |
|---|---|---|
| `--primary-navy` | `#15325f` | Main headline, table column headers, goal item titles, darkest bar series |
| `--navy-dark` | `#102649` | Hanging top-right brand banner background |
| `--pill-navy` | `#183b72` | Section pill heading backgrounds (`.section-pill`) |
| `--blue-bar-light`| `#9bc3fd` | Lightest bar series, legend accent dot |
| `--blue-bar-mid` | `#7398ee` | Mid bar series, legend accent dot |
| `--blue-bar-dark` | `#183b72` | Dark bar series, legend accent dot |
| `--text-dark` | `#1e293b` | Primary ink for headers and bullet points |
| `--text-body` | `#2c3e50` | Body paragraph text, list descriptions, table body |
| `--border-light`| `#e2e8f0` / `#cbd5e1` | Horizontal header rule, table row dividers |
| `Watermark Wave` | `#3b82f6` (2-12% op.) | Multi-curve undulating 3D wave mesh in SVG background |

### Typography
- **Primary Font**: `'Plus Jakarta Sans'`, sans-serif (Weights: 400, 500, 600, 700, 800, 900).
- **Main Headline**: 54px, Weight 900, Line-height 1.05, Letter-spacing `-0.02em`, Uppercase (`EXECUTIVE SUMMARY`).
- **Section Pill Headers**: 16px, Weight 800, White text on navy background, `border-radius: 9999px`, padding `8px 24px`.
- **Goal Names**: 16px, Weight 800, Color `#15325f`.
- **Body & List Copy**: 13.5px–14.2px, Weight 500, Line-height 1.48–1.65.

---

## Content Anatomy & Slot Breakdown

```
+-------------------------------------------------------------------------+
| [Headline: EXECUTIVE SUMMARY]                     [Brand Hanging Banner]|
| (Border-bottom divider rule)                                            |
+------------------------------------+------------------------------------+
| LEFT COLUMN (1fr)                  | RIGHT COLUMN (1fr)                 |
| [Pill: Overview]                   | [Pill: Goals and Objectives]       |
| Narrative paragraph (60-80 words)  | - Goal 1 (Icon Circle + Title + Tx)|
|                                    | - Goal 2 (Icon Circle + Title + Tx)|
| [Pill: Key Findings & Recomms]     | - Goal 3 (Icon Circle + Title + Tx)|
| 4 Bulleted discovery points        | - Goal 4 (Icon Circle + Title + Tx)|
|                                    | - Goal 5 (Icon Circle + Title + Tx)|
| [Pill: Target Audience & Segm.]    |                                    |
| 3-row matrix table:                | [Pill: Advertising and Promotion]  |
| - Segment 1 / Chars / Strategy     | Legend + 3-Bar CSS Chart           |
| - Segment 2 / Chars / Strategy     | (Digital / Social / Offline)       |
| - Segment 3 / Chars / Strategy     |                                    |
+------------------------------------+------------------------------------+
```

### 1. Header & Brand Banner
- **Header Left** (`.header-left`): 72% width with `EXECUTIVE SUMMARY` title underlined by a 2px `#cbd5e1` rule.
- **Brand Banner** (`.brand-banner`): 140px wide navy banner hanging from the top margin with corporate SVG emblem and company name.

### 2. Left Column: Strategy & Discovery
- **Overview Block** (`.overview-block`):
  - Header: `.section-pill` ("Overview").
  - Content: Justified paragraph (`.overview-text`) introducing mission, market context, and high-level strategy.
- **Key Findings and Recommendations** (`.findings-block`):
  - Header: `.section-pill` ("Key Findings and Recommendations").
  - Content: 4 bullet points (`.findings-list`) highlighting actionable takeaways.
- **Target Audience and Segmentation** (`.table-block`):
  - Header: `.section-pill` ("Target Audience and Segmentation").
  - Table (`.segment-table`): 3 columns (`Segment`, `Characteristics`, `Marketing Strategy`) across 3 distinct personas.

### 3. Right Column: Execution & Channels
- **Goals and Objectives** (`.goals-block`):
  - Header: `.section-pill` ("Goals and Objectives").
  - 5 Vertical Goal Items (`.goal-item`):
    - `.goal-icon-circle`: 52×52px circle with white SVG icon and soft shadow.
    - `.goal-name`: Bold title (e.g., Brand Awareness, Boost Sales, Market Expansion, Customer Retention, Develop Partnerships).
    - `.goal-desc`: 1-sentence quantitative or qualitative success target.
- **Advertising and Promotion** (`.promo-section`):
  - Header: `.section-pill` ("Advertising and Promotion").
  - Legend: 3 colored circular indicators.
  - CSS Bar Chart (`.chart-visual`): Y-axis scale (0–20) with 3 vertical percentage-height bars.

---

## How to Adapt This Template

1. **Copy Template Directory**:
   ```bash
   cp -r "$REPO_ROOT/.agents/skills/infographic/layout/executive-summary-report" "$REPO_ROOT/topics/<new-slug>"
   ```
2. **Customize Branding & Header**:
   - Update `.brand-banner` icon and name ("Ingoude Company" → User's brand).
   - Change `.headline` if a specific title is preferred (e.g., `Q3 STRATEGIC SUMMARY`).
3. **Populate Left Column Content**:
   - Replace `.overview-text` with topic context.
   - Adjust the 4 bullet items under `.findings-list`.
   - Update persona rows inside `.segment-table`.
4. **Customize the 5 Goal Items**:
   - Swap SVG icons inside `.goal-icon-circle` if needed (e.g., replace feather-style icons with relevant iconography).
   - Update `.goal-name` and `.goal-desc` for all 5 items.
5. **Set Promotion Bar Chart Heights**:
   - Adjust heights of `.bar-digital`, `.bar-social`, `.bar-offline` (e.g., `height: 45%;`, `70%;`, `90%;`).
6. **Capture High-DPI Retina Screenshot**:
   ```bash
   node "$REPO_ROOT/.agents/skills/infographic/scripts/screenshot-retina.js" \
     "$REPO_ROOT/topics/<new-slug>/index.html" \
     "$REPO_ROOT/topics/<new-slug>/output.png" \
     --scale 2 --width 900 --height 1273 --timeout 2000
   ```
