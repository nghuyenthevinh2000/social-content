---
name: html-visual-chart
description: "Use when: the user asks to create a visual chart or infographic, render data as a stunning HTML chart, produce a screenshot of a visual, or save chart output to a visual folder. This skill authors a self-contained HTML file with embedded chart logic, then captures a full-page screenshot using Playwright. All output goes to a dedicated folder under visual/<topic-slug>/."
---

# html-visual-chart: Author HTML charts and capture screenshots

## What this skill does

You produce a **self-contained, single-file HTML visual** (charts, infographics, data stories) — no build step, no external bundler. After writing the file, you capture a **full-page screenshot** with Playwright and save it alongside the HTML in the output folder.

The workflow is:

1. **Plan** — understand the data, visual goal, and folder target
2. **Author** — write `index.html` to `visual/<topic-slug>/`
3. **Screenshot** — run `npx playwright screenshot --full-page` to capture `output.png`
4. **Verify** — confirm the PNG exists and embed it in your reply

---

## Repo root resolution

This skill is repo-local. All paths are relative to the **git repo root** that contains this skill file.

Resolve the repo root at runtime before running any command:

```bash
REPO_ROOT=$(git rev-parse --show-toplevel)
```

All visual output paths in this skill use `$REPO_ROOT` as the base. Never hardcode an absolute machine path.

---

## Folder convention

All visual work lives under:

```
$REPO_ROOT/visual/<topic-slug>/
├── index.html      the chart (self-contained)
└── output.png      full-page screenshot
```

**`topic-slug`** is a kebab-case name matching the subject (e.g. `HuggingFace-data-leaks`, `openai-model-benchmarks`). The user will often tell you the folder name directly. If they don't, derive it from the topic.

Create the folder before writing files:

```bash
REPO_ROOT=$(git rev-parse --show-toplevel)
mkdir -p "$REPO_ROOT/visual/<topic-slug>"
```

---

## Step 1 — Plan the visual

Before writing any code, decide:

- **Chart type**: bar, line, area, pie/donut, heatmap, scatter, stat cards, infographic, etc.
- **Data**: what numbers/labels are you visualizing? Inline them if small; no external CSV fetches.
- **Story**: what is the one takeaway this visual communicates? State it in your title and a headline.
- **Aesthetic**: follow the design tokens in "Design system" below. Dark mode, glassmorphism, vibrant accent colors, animated counters.

---

## Infographic templates

The repo ships with **four production-ready A4 infographic templates**, each fully replicated as a self-contained HTML file. Before writing a chart from scratch, check whether one of these templates fits the user's request — if it does, copy the folder and adapt the content rather than starting fresh.

All templates (both the HTML source and the PNG preview) now live inside the skill folder itself:

```
$REPO_ROOT/.agents/skills/html-visual-chart/inforgraphic-templates/
├── business-plan-summary-report/
│   ├── index.html      ← ready-to-edit HTML
│   └── output.png      ← rendered preview
├── executive-summary-report/
│   ├── index.html
│   └── output.png
├── financial-performance-report/
│   ├── index.html
│   └── output.png
└── monthly-social-media-report/
    ├── index.html
    └── output.png
```

### Template reference

| Folder | Design style |
|---|---|
| `business-plan-summary-report/` | White A4 · bold navy headline + brand badge · 3 blue goal cards with floating icon bubbles · audience segmentation table · bar chart |
| `executive-summary-report/` | White A4 · full-width navy title · rounded navy pill section headers · wave mesh watermark · icon-list goals (5 items) · bar chart |
| `financial-performance-report/` | White A4 · blue curved corner wave accents · navy highlight cards · 4-column KPI grid · stacked bar chart · striped footer |
| `monthly-social-media-report/` | Split header (navy left / white right) · cyan accent stripe · KPI stat cards · multi-series line trend chart · featured post cards · donut chart · cyan-stripe footer |

### When to use a template

- User asks for a **business plan, executive summary, financial report, or social media report** → pick the matching folder.
- User wants a **new topic** in the same visual style → copy the closest folder as a base, then replace data, colors, and copy.

### How to adapt a template

```bash
REPO_ROOT=$(git rev-parse --show-toplevel)
TEMPLATE_DIR="$REPO_ROOT/.agents/skills/html-visual-chart/inforgraphic-templates"

# 1. Copy the closest template into the visual output area
cp -r "$TEMPLATE_DIR/executive-summary-report" "$REPO_ROOT/visual/<new-slug>"

# 2. Edit visual/<new-slug>/index.html with new data/colors

# 3. Re-shoot using the A4 viewport
npx playwright screenshot --viewport-size "900,1273" --wait-for-timeout 2000 \
  "file://$REPO_ROOT/visual/<new-slug>/index.html" \
  "$REPO_ROOT/visual/<new-slug>/output.png"
```

> **A4 viewport**: all templates are 900 × 1273 px. Always use `--viewport-size "900,1273"` (not `--full-page`) when re-shooting A4-style infographics.

---

## Step 2 — Author index.html

### File rules

- **Self-contained.** One .html file only. All CSS and JS inline (or loaded from public CDNs).
- **No build step.** The file must render correctly when opened in a browser or loaded by Playwright.
- **Fixed-width layout.** Target 1200px wide body (or 1100px max-width container). Playwright captures the full page height.
- **No scroll-dependent animations.** All animations must trigger on DOMContentLoaded, not on scroll, because Playwright renders without scrolling.
- **Chart libraries.** Load from CDN:
  - Chart.js: https://cdn.jsdelivr.net/npm/chart.js
  - D3: https://cdn.jsdelivr.net/npm/d3@7
  - ECharts: https://cdn.jsdelivr.net/npm/echarts/dist/echarts.min.js
  - Use Chart.js as the default; switch to D3 or ECharts when the chart type demands it.

### Design system

Use these CSS variables as a baseline. Adjust accent color per topic:

```css
:root {
  --bg:       #fdf8f2;          /* warm parchment */
  --card-bg:  #fffcf7;          /* warm white */
  --border:   rgba(160, 120, 80, 0.15);
  --text:     #2c1f0e;          /* warm dark ink */
  --muted:    #8a7060;          /* warm taupe */
  --accent:   #c2612a;          /* terracotta */
  --danger:   #b94040;          /* muted red */
  --warning:  #c28a1a;          /* warm amber */
  --teal:     #3a7d6e;          /* muted sage-teal */
  --success:  #4a7c59;          /* muted forest green */
}
```

Accent color guide by topic:
- Security / breach / leak: --accent: #b94040 (muted brick red)
- AI / ML / models: --accent: #7b5ea7 (dusty mauve-purple)
- Finance / revenue / growth: --accent: #4a7c59 (forest green)
- Data / analytics: --accent: #3a7d6e (sage teal)
- General / neutral: --accent: #c2612a (terracotta — default)

**Typography**: always load from Google Fonts:
```
Inter:wght@400;600;800;900 and JetBrains+Mono:wght@500;700;800
```

**Body**: warm parchment background (`#fdf8f2`), font-family Inter, padding 2rem, min-height 100vh.

**Cards**: warm white background, border 1px solid var(--border), border-radius 1rem, `box-shadow: 0 2px 16px rgba(120, 80, 40, 0.08)`. Warm amber-tinted shadow instead of cold gray.

**Stat numbers**: font-family JetBrains Mono, large (3-5rem), bold (800-900 weight), accent-colored.

**Accent tints** on stat cards — use a warm tinted background matching the accent:
```css
/* e.g. terracotta accent card */
background: #fef3ec;
border-left: 4px solid var(--accent);
```

### Animations

Trigger all animations from DOMContentLoaded (NOT scroll):

```js
function animateCounter(el, target, duration, prefix, suffix) {
  duration = duration || 1500;
  prefix = prefix || '';
  suffix = suffix || '';
  var start = performance.now();
  function update(now) {
    var progress = Math.min((now - start) / duration, 1);
    var eased = 1 - Math.pow(1 - progress, 3);
    el.textContent = prefix + Math.round(eased * target).toLocaleString() + suffix;
    if (progress < 1) requestAnimationFrame(update);
  }
  requestAnimationFrame(update);
}
```

Keep animation duration <= 1500ms. Use --wait-for-timeout 2000 in Playwright.

### Layout patterns

```css
.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; }
.grid-3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1.5rem; }
.grid-4 { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1.5rem; }
```

**Common sections order**:
1. Header (badge + headline + sub-headline + source attribution)
2. Stat cards grid (3-4 KPI numbers)
3. Main chart (full-width or split 2-column)
4. Secondary breakdowns (smaller charts or lists)
5. Footer / attribution

---

## Step 3 — Capture the screenshot

After writing index.html, resolve the repo root and run Playwright:

```bash
REPO_ROOT=$(git rev-parse --show-toplevel)
SLUG="<topic-slug>"

npx playwright screenshot \
  --full-page \
  --wait-for-timeout 2000 \
  "file://$REPO_ROOT/visual/$SLUG/index.html" \
  "$REPO_ROOT/visual/$SLUG/output.png"
```

Flags:
- --full-page: captures the entire page height
- --wait-for-timeout 2000: waits 2s for chart rendering to complete
- Arg 1: file:// URL (absolute path) of the HTML file
- Arg 2: absolute output PNG path

If Playwright browsers are not installed: npx playwright install chromium

### Error handling

| Symptom | Fix |
|---|---|
| Charts blank / canvas empty | Add --wait-for-timeout 3000 |
| Page cut off at the right | Ensure max-width <= 1200px |
| Animations incomplete | Shorten durations or add more wait time |
| File not found | Confirm REPO_ROOT resolved correctly with: echo $REPO_ROOT |

---

## Step 4 — Verify and report

```bash
REPO_ROOT=$(git rev-parse --show-toplevel)
ls -lh "$REPO_ROOT/visual/<slug>/output.png"
```

1. Confirm output.png exists with non-zero size
2. Embed in reply: ![Visual](file:///absolute/resolved/path/output.png)
3. Report: what the chart shows, the output folder (repo-relative), and design choices

---

## Pre-capture checklist

- [ ] index.html is self-contained (CDN only, no local imports)
- [ ] All animations use DOMContentLoaded (not scroll)
- [ ] Body is fixed-width (<= 1200px), no horizontal overflow
- [ ] Data is accurate and matches the user's request
- [ ] Color palette matches the topic
- [ ] Headline and badge clearly state the data story
- [ ] Source attribution present in footer or header

---

## Quick reference

| Task | Command / action |
|---|---|
| Resolve repo root | REPO_ROOT=$(git rev-parse --show-toplevel) |
| Create folder | mkdir -p "$REPO_ROOT/visual/<slug>" |
| Write HTML | write_to_file -> visual/<slug>/index.html (repo-relative) |
| Screenshot | npx playwright screenshot --full-page --wait-for-timeout 2000 "file://$REPO_ROOT/visual/<slug>/index.html" "$REPO_ROOT/visual/<slug>/output.png" |
| Verify | ls -lh "$REPO_ROOT/visual/<slug>/output.png" |
| Install browsers | npx playwright install chromium |
| View output | Embed with ![...](file:///resolved-absolute-path/output.png) |
