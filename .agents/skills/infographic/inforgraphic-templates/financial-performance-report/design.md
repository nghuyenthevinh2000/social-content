---
name: financial-performance-report
title: Financial Performance Report
format: A4 Portrait (900 × 1273 px)
retina_dimensions: 1800 × 2546 px (--scale 2)
category: Financial Analytics / Earnings Review / Corporate Finance
screenshot_command: node "$REPO_ROOT/.agents/skills/infographic/scripts/screenshot-retina.js" "$REPO_ROOT/topics/<slug>/index.html" "$REPO_ROOT/topics/<slug>/output.png" --scale 2 --width 900 --height 1273 --timeout 2000
---

# Financial Performance Report Template

## What This Template Serves

The **Financial Performance Report** is an authoritative, high-density financial briefing template crafted for CFOs, financial controllers, investor relations, and executive committees. It converts complex financial metrics, budget variances, and expense ratios into an elegant, publication-grade one-pager.

Key structural highlights include:
1. **Curved Corner Wave Accents**: Distinctive dual-tone royal/navy blue SVG wave arches anchoring the top corners.
2. **Tri-Card Qualitative Highlights**: 3 dark navy cards for concise executive commentary on revenue, cost efficiency, and profitability.
3. **Four-Metric Dashed KPI Box**: A high-contrast dark navy ribbon showcasing 4 headline financial metrics separated by dashed boundary dividers.
4. **Stacked Category Bar Chart**: A clean, multi-series stacked column chart with custom legends, designed specifically for expense distribution, revenue mix, or budget utilization.
5. **Observation Notes & Striped Accent Footer**: An icon-supported summary list followed by dynamic skewed accent stripes and an attribution footer.

### Ideal Use Cases
- **Quarterly Earnings & P&L Reviews**: Communicating quarterly revenue, EBITDA margins, operating expenses, and net profit.
- **Budget vs. Actual Variance Reports**: Comparing departmental spend allocations across multiple budget periods.
- **Cost Reduction & Efficiency Briefings**: Analyzing expense distributions, cost-cutting initiatives, and margin expansion.
- **Investor & Shareholder Updates**: Distributing a polished monthly or quarterly commercial update to investors and board members.

### When NOT to Use
- Broad multi-objective strategic plans with persona customer segmentation tables (use `business-plan-summary-report` or `executive-summary-report`).
- Enterprise software or cloud architecture stacks (use `enterprise-architecture-stack`).
- Social media platform and engagement tracking (use `monthly-social-media-report`).

---

## Agent Rationale Snippet (For Step 1 Confirmation)

When proposing this template during **Step 1 (Plan & Confirm Gate)**, adapt this rationale for the user:

> "I recommend the **Financial Performance Report** template. It is engineered specifically for financial updates and earnings reviews. It highlights narrative context across 3 dark navy cards, presents 4 core metrics in a dedicated high-contrast KPI banner with dashed dividers, includes a stacked bar chart for expense or revenue breakdown, and concludes with bulleted performance observations and an executive attribution footer."

---

## Visual & Design Architecture

### Color Palette
| Variable / Token | Hex Code | Role & Usage |
|---|---|---|
| `--primary-blue` | `#0b51bf` | Primary headline, section title underlines, top wave accents, footer bar |
| `--navy-card` | `#082657` | Background fill for highlights cards and KPI overview box |
| `--navy-dark` | `#05193b` | Dark secondary top wave curve, darkest stacked chart segment (`#05142b`) |
| `Mid Chart Blue` | `#0b3475` | Middle segment of stacked bar chart |
| `--text-dark` | `#1e293b` | Sub-brand text, note item text |
| `--text-body` | `#334155` / `#2b3545` | Paragraph text, axis markers, expense text |
| `Accent Amber` | `#eab308` | Accent icon color for growth trend observation |
| `Divider Dashed` | `rgba(255, 255, 255, 0.6)` | Vertical dashed dividers between KPI columns |

### Typography
- **Primary Font**: `'Plus Jakarta Sans'`, sans-serif (Weights: 400, 500, 600, 700, 800, 900).
- **Main Header Title**: 42px, Weight 900, Line-height 1.1, Letter-spacing `0.04em`, Uppercase (`FINANCIAL / PERFORMANCE REPORT`).
- **Section Titles**: 18px, Weight 900, Uppercase with 3.5px solid `--primary-blue` underline.
- **KPI Large Numbers**: 28px, Weight 900, Color `#ffffff`.
- **Card Titles**: 14.5px, Weight 800, Color `#ffffff`.
- **Body & Commentary**: 11.5px–12.8px, Weight 400–500.

---

## Content Anatomy & Slot Breakdown

```
+-------------------------------------------------------------------------+
| (Top Corner Curves)              HEADER AREA        (Top Corner Curves) |
|                            FINANCIAL PERFORMANCE REPORT                 |
|                                                     [WARNER & SPENCER]  |
+-------------------------------------------------------------------------+
| FINANCIAL HIGHLIGHTS                                                    |
| [ Highlight Card 1 ]       [ Highlight Card 2 ]    [ Highlight Card 3 ] |
| Revenue Growth             Cost Efficiency         Profitability Trend  |
+-------------------------------------------------------------------------+
| KPI OVERVIEW                                                            |
| +-------------------+-------------------+-------------------+---------+ |
| | Sales Target:2.7M | Growth Proj:+55.5%| Margin Target:+78%| Ach.:75%| |
| +-------------------+-------------------+-------------------+---------+ |
+-------------------------------------------------------------------------+
| EXPENSE DISTRIBUTION                                                    |
| [ Narrative Context Text ]      | [ Stacked Bar Chart (4 columns) ]     |
|                                 |   Item 1 | Item 2 | Item 3 | Item 4   |
|                                 |   Series 1 / Series 2 / Series 3      |
+-------------------------------------------------------------------------+
| PERFORMANCE NOTES                                                       |
| [Scale Icon]  - Healthy liquidity and stable profitability              |
| [Trend Icon]  - Revenue growth driven by sales execution                |
| [Coin Icon]   - Optimization opportunities in marketing spend           |
+-------------------------------------------------------------------------+
| (/// Skewed Accent Stripes)                                             |
| Prepared by: Finance & Strategy Team                                    |
+-------------------------------------------------------------------------+
```

### 1. Header Area (`.header-area`)
- Top corner wave SVGs (`.top-decor`) framing the page.
- Centered 2-line title (`FINANCIAL / PERFORMANCE REPORT`).
- Sub-brand metadata on bottom-right (`.sub-brand`, e.g., corporate division or company name).
- Underlined by a 2px `--primary-blue` border.

### 2. Financial Highlights (`.highlights-grid`)
- 3 uniform dark navy cards (`.highlight-card`):
  - **Card 1**: Top-line revenue trajectory commentary.
  - **Card 2**: Operating cost & efficiency commentary.
  - **Card 3**: Net margins & profitability trends.

### 3. KPI Overview Box (`.kpi-container`)
- Full-width dark navy box (`.kpi-box`) split into 4 equal columns with dashed vertical separators:
  - `kpi-col 1`: Metric label, 28px bold stat (e.g. `2.7M`), sub-annotation (`Achieved: 76%`).
  - `kpi-col 2`: Metric label, 28px bold stat (e.g. `+55.5%`), sub-annotation (`Forecast: Q2 momentum`).
  - `kpi-col 3`: Metric label, 28px bold stat (e.g. `+78%`), sub-annotation (`Net Profit: $2M`).
  - `kpi-col 4`: Metric label, 28px bold stat (e.g. `75%`), sub-annotation (`Cash Flow Ratio`).

### 4. Expense Distribution (`.expense-container`)
- **Left**: Detailed narrative paragraph (`.expense-text`) explaining cost drivers, seasonal factors, or capital expenditures.
- **Right**: Stacked Column Chart (`.chart-panel`):
  - Legend: Series 1 (`#05142b`), Series 2 (`#0b3475`), Series 3 (`#0b51bf`).
  - Y-Axis scale (0 to 50).
  - 4 stacked columns, each containing 3 proportional segment divs (`.seg-1`, `.seg-2`, `.seg-3`) with heights specified in CSS pixels (e.g., `height: 18px`, `15px`, `15px`).
  - X-Axis category labels (`Item 1` through `Item 4`).

### 5. Performance Notes & Footer
- **Performance Notes** (`.notes-list`): 3 bullet items paired with colored SVG line icons:
  - Balance scale icon (Blue).
  - Growth arrow icon (Amber/Yellow `#eab308`).
  - Money/target icon (Blue).
- **Footer Decor** (`.footer-decor`):
  - 4 skewed diagonal stripes (`transform: skewX(-30deg)`).
  - Solid blue footer bar with author/team attribution (`Prepared by: Finance & Strategy Team`).

---

## How to Adapt This Template

1. **Copy Template Directory**:
   ```bash
   cp -r "$REPO_ROOT/.agents/skills/infographic/inforgraphic-templates/financial-performance-report" "$REPO_ROOT/topics/<new-slug>"
   ```
2. **Update Company Branding**:
   - Update `.sub-brand` text (e.g., `WARNER & SPENCER` → `ACME CORP FINANCIAL`).
   - Customize `.footer-bar` author attribution.
3. **Populate Highlights Cards & KPI Overview**:
   - Update titles and paragraphs inside the 3 `.highlight-card` elements.
   - Adjust labels, large metric values (`.kpi-num`), and subtext (`.kpi-sub`) across the 4 KPI columns.
4. **Configure Stacked Chart Data**:
   - Update `.legend-item` text to reflect cost or revenue categories.
   - Adjust `height: XXpx` inline styles on `.seg-1`, `.seg-2`, `.seg-3` for each of the 4 columns.
   - Update X-axis label text (`Item 1` to `Item 4` → e.g., `Q1`, `Q2`, `Q3`, `Q4` or departmental names).
5. **Adjust Performance Observations**:
   - Tailor the 3 `.note-text` strings to describe key takeaways or risks.
6. **Capture High-DPI Retina Screenshot**:
   ```bash
   node "$REPO_ROOT/.agents/skills/infographic/scripts/screenshot-retina.js" \
     "$REPO_ROOT/topics/<new-slug>/index.html" \
     "$REPO_ROOT/topics/<new-slug>/output.png" \
     --scale 2 --width 900 --height 1273 --timeout 2000
   ```
