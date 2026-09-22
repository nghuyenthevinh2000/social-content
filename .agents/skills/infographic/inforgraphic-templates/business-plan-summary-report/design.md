---
name: business-plan-summary-report
title: Business Plan Summary Report
format: A4 Portrait (900 × 1273 px)
retina_dimensions: 1800 × 2546 px (--scale 2)
category: Strategic Planning / Corporate Strategy / GTM Launch
screenshot_command: node "$REPO_ROOT/.agents/skills/infographic/scripts/screenshot-retina.js" "$REPO_ROOT/topics/<slug>/index.html" "$REPO_ROOT/topics/<slug>/output.png" --scale 2 --width 900 --height 1273 --timeout 2000
---

# Business Plan Summary Report Template

## What This Template Serves

The **Business Plan Summary Report** is a high-impact, C-suite ready one-page executive brief designed to present a company's strategic roadmap, commercial plan, or go-to-market (GTM) initiative. 

It organizes information into four intuitive visual tiers:
1. **Header & Corporate Identity**: Bold typography with a distinctive top-right hanging brand banner.
2. **Strategic Context & Discoveries**: Side-by-side narrative overview and bulleted key market findings.
3. **Core Objectives (The Hero Zone)**: 3 high-contrast goal cards featuring floating circular icon badges that immediately draw the eye to core milestones.
4. **Execution & Allocation**: A structured segmentation table paired with a multi-channel allocation bar chart.

### Ideal Use Cases
- **Annual / Multi-Year Strategic Plans**: Summarizing strategic pivots, corporate visions, and target horizons (e.g., 12–24 month timelines).
- **Go-to-Market (GTM) & Product Launches**: Outlining the launch rationale, target user tiers, top 3 launch goals, and promotional spend mix.
- **Investor & Board Briefings**: Pitching a strategic initiative or business unit expansion on a single, print-perfect page.
- **Brand Repositioning or Commercial Strategy**: Demonstrating market opportunity findings, customer segment mapping, and campaign channel allocations.

### When NOT to Use
- Pure financial earnings breakdowns with dense tabular numbers (use `financial-performance-report` instead).
- Technical multi-tier software or infrastructure architectures (use `enterprise-architecture-stack` instead).
- Granular weekly/monthly social analytics with multi-series line graphs (use `monthly-social-media-report` instead).

---

## Agent Rationale Snippet (For Step 1 Confirmation)

When proposing this template during **Step 1 (Plan & Confirm Gate)**, adapt this rationale for the user:

> "I recommend the **Business Plan Summary Report** template. Its clean corporate aesthetic and A4 portrait layout are ideal for synthesizing high-level strategies into an executive one-pager. It balances strategic narrative and key findings up top, highlights 3 milestone objectives using floating icon badges in the center, and anchors the bottom with a customer segmentation table alongside an allocation bar chart."

---

## Visual & Design Architecture

### Color Palette
| Variable / Token | Hex Code | Role & Usage |
|---|---|---|
| `--primary-navy` | `#183b72` | Main headline, section headers, table headers, darkest bar series |
| `--navy-badge` | `#17386d` | Top brand banner background, goal badge circular icons |
| `--blue-card` | `#7398ee` | Goal card background fill, mid-tone chart bar |
| `--blue-bar-light`| `#9bc3fd` | Lightest bar series, legend accent dot |
| `--blue-bar-mid` | `#7398ee` | Mid bar series, legend accent dot |
| `--blue-bar-dark` | `#183b72` | Dark bar series, legend accent dot |
| `--text-dark` | `#1e293b` | Primary dark ink, segment table bold titles |
| `--text-body` | `#2d3748` / `#2b3545` | Paragraph body copy, bullet items, table content |
| `--border-light`| `#e2e8f0` | Table cell dividers, card borders |
| `Watermark Blue` | `#3b82f6` (5-12% op.) | Subtle SVG wireframe blueprint & polygon geometry in background |

### Typography
- **Primary Font**: `'Plus Jakarta Sans'`, sans-serif (Google Fonts weights: 400, 500, 600, 700, 800, 900).
- **Headline**: 58px, Weight 900, Line-height 1.02, Letter-spacing `-0.02em`, Uppercase (`BUSINESS PLAN / SUMMARY`).
- **Section Headings**: 22px, Weight 800, Color `#183b72`.
- **Goal Card Titles**: 18px, Weight 800, Color `#ffffff`.
- **Body & Bullet Text**: 14px, Weight 500, Line-height 1.48–1.58.
- **Table Text**: Header 14px bold; Cell content 13px, Line-height 1.42.

---

## Content Anatomy & Slot Breakdown

```
+-------------------------------------------------------------------------+
| [Headline: BUSINESS PLAN SUMMARY]                 [Brand Hanging Banner]|
+-------------------------------------------------------------------------+
| [Overview Paragraph]                 | [Key Findings Bullet List (3)]   |
+-------------------------------------------------------------------------+
| [Goal Card 1 (Badge)]     [Goal Card 2 (Badge)]     [Goal Card 3 (Badge)] |
| Brand Awareness           Boost Sales               Market Expansion    |
+-------------------------------------------------------------------------+
| [Target Audience Table (3 cols)]     | [Promotion Bar Chart + Legend]   |
| Segment | Chars | Strategy           | Digital / Social / Offline       |
+-------------------------------------------------------------------------+
```

### 1. Header & Brand Banner
- **Headline** (`.headline`): Two stacked uppercase lines (e.g., `BUSINESS PLAN` / `SUMMARY`).
- **Hanging Brand Banner** (`.brand-banner`): 130px wide, deep navy bookmark hanging from the top-right margin.
  - SVG Icon (48×48px): Architectural columns, crest, or brand symbol.
  - Company Name (`.brand-name`): Primary brand bold text + sub-descriptor.

### 2. Overview & Key Findings (`.overview-row`)
- **Left Column: Overview** (`.body-paragraph`): 60–90 words contextualizing business direction, timeframe, and macro objective.
- **Right Column: Key Findings** (`.findings-list`): 3 bullet points with custom circular bullet markers summarizing customer insights, market shifts, or competitor benchmarks.

### 3. Goals and Objectives (`.cards-row`)
- 3 uniform cards (`.goal-box`) with generous padding and soft blue drop shadow.
- **Floating Badge** (`.goal-badge`): An 82×82px circle overlapping the top card edge by -42px with a 4px solid white ring and centered white SVG icon.
  - *Slot 1*: Community / Customer / Awareness icon + Title + 1-2 sentence target.
  - *Slot 2*: Sales / Revenue / Growth icon + Title + 1-2 sentence target.
  - *Slot 3*: Expansion / Scale / Product icon + Title + 1-2 sentence target.

### 4. Bottom Grid: Audience & Channel Allocation (`.bottom-row`)
- **Left Column: Target Audience and Segmentation** (`.segment-table`):
  - Table with 3 columns:
    - `Segment` (22% width, bold) — e.g., "Segment 1", "Young Professionals".
    - `Characteristics` (38% width) — Demographics, behaviors, pain points.
    - `Marketing Strategy` (40% width) — Channels, offers, value proposition.
- **Right Column: Advertising and Promotion Chart** (`.chart-box`):
  - Legend container with 3 colored dots.
  - Y-axis scale markers (0 to 20).
  - 3 vertical CSS bars with heights set via percentage (e.g., `height: 38%`, `60%`, `85%`) and rounded top corners (`border-radius: 6px 6px 0 0`).

---

## How to Adapt This Template

1. **Copy Template Directory**:
   ```bash
   cp -r "$REPO_ROOT/.agents/skills/infographic/inforgraphic-templates/business-plan-summary-report" "$REPO_ROOT/topics/<new-slug>"
   ```
2. **Update Copy in `index.html`**:
   - Change `<title>` and `.headline`.
   - Update `.brand-banner` with the user's entity name and appropriate SVG icon.
   - Fill in `.overview-row` text and bullet points.
   - Customize the 3 `.goal-box` entries (titles, descriptions, SVGs).
   - Update `.segment-table` rows with relevant categories.
3. **Adjust Bar Chart Data**:
   - Update legend labels (`.legend-entry`).
   - Modify the CSS height percentages on `.bar-digital`, `.bar-social`, `.bar-offline` (or adjust classes).
   - Adjust Y-axis scale values if numbers differ from `0–20`.
4. **Capture Retina 2x Screenshot**:
   ```bash
   node "$REPO_ROOT/.agents/skills/infographic/scripts/screenshot-retina.js" \
     "$REPO_ROOT/topics/<new-slug>/index.html" \
     "$REPO_ROOT/topics/<new-slug>/output.png" \
     --scale 2 --width 900 --height 1273 --timeout 2000
   ```
