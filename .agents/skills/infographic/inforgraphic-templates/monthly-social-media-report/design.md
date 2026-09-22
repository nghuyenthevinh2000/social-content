---
name: monthly-social-media-report
title: Monthly Social Media Performance Report
format: A4 Portrait (900 × 1273 px)
retina_dimensions: 1800 × 2546 px (--scale 2)
category: Social Media Analytics / Growth Marketing / Campaign Performance
screenshot_command: node "$REPO_ROOT/.agents/skills/infographic/scripts/screenshot-retina.js" "$REPO_ROOT/topics/<slug>/index.html" "$REPO_ROOT/topics/<slug>/output.png" --scale 2 --width 900 --height 1273 --timeout 2000
---

# Monthly Social Media Performance Report Template

## What This Template Serves

The **Monthly Social Media Performance Report** is a modern, high-energy marketing dashboard designed for social media managers, growth marketers, agency teams, and digital brand leads. It synthesizes multi-platform social performance, content reach, audience demographics, and campaign ROI into a vibrant visual one-pager.

Key structural highlights include:
1. **Split Asymmetric Banner Header**: A high-contrast header pairing a solid dark-navy title box with an adjacent white narrative overview card, topped with an electric cyan accent stripe (`#00d2d3`).
2. **Engagement Stat Badges**: Mint-tinted growth chips (`↑ 16.4%`) with large 38px bold numerals inside soft-tinted cards (`#eef8f8`).
3. **Multi-Series Weekly Line Trend Chart**: A clean SVG line graph tracking up to 3 social platforms or campaign channels across 4 weekly intervals.
4. **Rich Content Performance Cards**: 3 featured post cards displaying image thumbnails, interaction counts, and growth chips to highlight viral or top-converting creative assets.
5. **Dual Demographics Breakdown**: Horizontal percentage progress bars for age tiers paired with a multi-segment SVG donut chart for geographic distribution.
6. **Cyan-Striped Footer**: Branded footer with social handles and website URL.

### Ideal Use Cases
- **Monthly & Quarterly Social Media Reporting**: Presenting follower growth, total interactions, engagement rates, and top creative posts across LinkedIn, Twitter/X, Instagram, YouTube, etc.
- **Creator & Influencer Campaign Recaps**: Summarizing paid partnerships, reach milestones, and top-performing sponsored posts for brand sponsors.
- **Community & Audience Growth Dashboards**: Tracking community expansion, demographic shifts, and regional adoption.
- **Product Marketing & Launch Campaign Reviews**: Evaluating digital buzz, hashtag traction, and referral traffic.

### When NOT to Use
- Heavy corporate business plans with customer persona matrices (use `business-plan-summary-report` or `executive-summary-report`).
- Detailed financial P&L, balance sheets, or expense breakdowns (use `financial-performance-report`).
- Technical microservice architectures or system stacks (use `enterprise-architecture-stack`).

---

## Agent Rationale Snippet (For Step 1 Confirmation)

When proposing this template during **Step 1 (Plan & Confirm Gate)**, adapt this rationale for the user:

> "I recommend the **Monthly Social Media Report** template. It is specifically designed for digital marketing and audience performance tracking. Its split cyan-and-navy header sets a vibrant, modern tone, while the layout integrates 6 distinct analytics components: engagement KPI cards, a weekly multi-line trend chart, channel-by-channel metrics, visual top-post cards with image thumbnails, demographic progress bars, and a regional donut chart."

---

## Visual & Design Architecture

### Color Palette
| Variable / Token | Hex Code | Role & Usage |
|---|---|---|
| `--primary-navy` | `#193b68` | Split header title block background, section titles, large metric numbers, footer bar |
| `--navy-dark` | `#122b4d` | Secondary dark navy accents |
| `--cyan-bright` | `#00d2d3` | Top accent border stripes on header cards and footer bar |
| `--teal-accent` | `#00cec9` | Auxiliary cyan/teal accent |
| `--blue-accent` | `#3b82f6` | Line chart Platform A, Donut chart primary segment |
| `--card-bg-light`| `#eef8f8` | Soft mint-cyan tint background for KPI stat boxes |
| `--badge-green-bg`| `#d1fae5`| Light green background for positive growth badges |
| `--badge-green-text`| `#065f46`| Dark green text for positive percentage chips (`↑ 16.4%`) |
| `Line Chart Colors`| `#1e3a8a` (Navy), `#f59e0b` (Amber), `#06b6d4` (Cyan) | 3-line trend chart series |
| `Donut Colors` | `#3b82f6`, `#38bdf8`, `#2dd4bf`, `#fbbf24` | 4-slice SVG donut segments |

### Typography
- **Primary Font**: `'Plus Jakarta Sans'`, sans-serif (Weights: 400, 500, 600, 700, 800, 900).
- **Main Title**: 44px, Weight 900, Line-height 1.06, Letter-spacing `-0.01em`, White text.
- **Section Headers**: 20px, Weight 800, Color `#193b68`.
- **Large Stat Numerals**: 38px, Weight 900, Color `#193b68`.
- **Channel Stat Numbers**: 22px, Weight 900.
- **Post Interaction Numbers**: 20px, Weight 900.
- **Body & Captions**: 12px–13.8px, Weight 500–600.

---

## Content Anatomy & Slot Breakdown

```
+-------------------------------------------------------------------------+
| [TITLE CARD (Navy + Cyan Top)]       | [OVERVIEW CARD (White + Cyan Top)]|
| Monthly / Social Media / Performance | Executive narrative summary       |
+--------------------------------------+----------------------------------+
| ROW 1: HIGHLIGHTS & GROWTH TREND                                        |
| [2 KPI Cards (Interactions / Eng %)] | [Multi-Line Chart (4 Weeks)]     |
| (Mint tint + Green Growth Badges)    | Platform A / Platform B / Platf C|
|                                      | Footer Badge: +2,870 followers   |
+--------------------------------------+----------------------------------+
| ROW 2: CHANNELS & TOP CREATIVE POSTS                                    |
| [Channel Performance (3 platforms)]  | [3 Featured Post Cards]          |
| - Platform A: 12.8k aud / 6.2% eng   | - Post 1: Image + 4.3k + Badge   |
| - Platform B: 9.4k aud / 7.1% eng    | - Post 2: Image + 3.9k + Badge   |
| - Platform C: 6.9k aud / 4.3% eng    | - Post 3: Image + 3.4k + Badge   |
+--------------------------------------+----------------------------------+
| ROW 3: AUDIENCE BREAKDOWN & REGIONAL SHARE                              |
| [Audience Breakdown by Age]          | [Regional Distribution]          |
| - Age 18–24: 34% (Progress Bar)      | - SVG Donut Chart (4 Segments)   |
| - Age 25–34: 39% (Progress Bar)      | - Legend List (Regions 1 to 4    |
| - Age 35–44: 17% (Progress Bar)      |   plus Other)                    |
| - Age 45+:   10% (Progress Bar)      |                                  |
+-------------------------------------------------------------------------+
| [Cyan Top Stripe] @handle                   www.reallygreatsite.com     |
+-------------------------------------------------------------------------+
```

### 1. Top Split Header (`.top-header-wrap`)
- **Left (Title Card)**: 410px wide, deep navy background with top 10px cyan bar. Three stacked lines: `Monthly`, `Social Media`, `Performance`.
- **Right (Overview Card)**: White background with top 10px cyan bar. Features "Overview" title and 2-3 sentence report summary.

### 2. Row 1: Engagement Highlights & Audience Growth (`.grid-2col`)
- **Left: Engagement Highlights** (`.stat-cards-stack`):
  - 2 soft-tinted cards (`.stat-box`):
    - Metric 1: Label ("Total Interactions"), green chip ("↑ 16.4%"), 38px number ("26,480").
    - Metric 2: Label ("Avg Engagement Rate"), green chip ("↑ 14%"), 38px number ("6.4%").
- **Right: Audience Growth** (`.growth-container`):
  - Subtitle: "New audience added this month:".
  - Legend: Platform A (Navy), Platform B (Amber), Platform C (Cyan).
  - SVG Line Chart (viewBox 0 0 460 130): 4 horizontal grid lines (0 to 2,000) with 3 polyline series across Weeks 1–4.
  - Footer Chip (`.growth-footer-badge`): Total audience increase ("↑ +2,870 new followers").

### 3. Row 2: Channel Performance & Content Performance (`.grid-2col`)
- **Left: Channel Performance** (`.channels-grid`):
  - Platform A: Name, Total Audience (22px bold), Engagement Rate.
  - Platform B: Name, Total Audience (22px bold), Engagement Rate.
  - Platform C (spans 2 columns): Name, Total Audience, Engagement Rate.
- **Right: Content Performance** (`.posts-grid`):
  - 3 Post Cards (`.post-card`), each with:
    - Post Image Thumbnail (`.post-img`, 85px height with background image or gradient).
    - Post Title (e.g. "Featured Post 1").
    - Interaction count (20px bold).
    - Green reach/impression badge (`↑ 36,200`).

### 4. Row 3: Audience Breakdown & Regional Distribution (`.grid-2col`)
- **Left: Audience Breakdown** (`.bars-stack`):
  - 4 horizontal progress bars with labels and percentages (e.g., Age 18–24: 34%, Age 25–34: 39%, Age 35–44: 17%, Age 45+: 10%).
- **Right: Regional Distribution** (`.regional-wrap`):
  - SVG Donut Chart (180×180px) using concentric SVG circles with `stroke-dasharray` and `stroke-dashoffset`.
  - Regional Legend List: Region 1 (37%), Region 2 (24%), Region 3 (19%), Region 4 (11%), Other (9%).

### 5. Footer (`.footer-bar`)
- Deep navy bar with top 6px cyan stripe.
- Left: Social handle (e.g., `@reallygreatsite`).
- Right: Domain URL (e.g., `www.reallygreatsite.com`).

---

## How to Adapt This Template

1. **Copy Template Directory**:
   ```bash
   cp -r "$REPO_ROOT/.agents/skills/infographic/inforgraphic-templates/monthly-social-media-report" "$REPO_ROOT/topics/<new-slug>"
   ```
2. **Update Header & Brand Info**:
   - Customize `.main-title` (e.g., `Q3 / LinkedIn & X / Performance`).
   - Rewrite `.overview-desc` to summarize the specific campaign or reporting cycle.
   - Change footer handles in `.footer-bar`.
3. **Populate KPIs & Channel Data**:
   - Update values in `.stat-box` and green chip percentages.
   - Adjust channel names and metrics in `.channel-item` (Platform A/B/C → LinkedIn, X/Twitter, Instagram, etc.).
4. **Update Post Cards**:
   - Swap thumbnail image URLs in `.post-img` (or use Unsplash / SVG placeholders).
   - Update titles, interaction numbers, and reach badges.
5. **Adjust Visual Charts**:
   - **Line Chart**: Edit `<polyline points="...">` coordinates in the SVG to reflect weekly growth trends.
   - **Demographic Bars**: Adjust `style="width: XX%;"` on `.bar-fill` divs.
   - **Donut Chart**: Adjust `stroke-dasharray` and `stroke-dashoffset` on SVG `<circle>` elements, or update the adjacent legend list.
6. **Capture High-DPI Retina Screenshot**:
   ```bash
   node "$REPO_ROOT/.agents/skills/infographic/scripts/screenshot-retina.js" \
     "$REPO_ROOT/topics/<new-slug>/index.html" \
     "$REPO_ROOT/topics/<new-slug>/output.png" \
     --scale 2 --width 900 --height 1273 --timeout 2000
   ```
