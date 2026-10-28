# Content Plan Infographic Layout & Rendering Reference

```text
Target Month (20 Posts) ➔ Canvas Pixel Budget (720 × 1280) ➔ Harvey Editorial Tokens ➔ Unified Master Table ➔ 2× Retina Screenshot
```

## 1. Overview & Purpose
This guide defines the standardized 9:16 portrait infographic layout for publishing a 1-month (20-post, 4-week Monday–Friday) campaign content plan. It eliminates arbitrary footer clutter and separate pillar blocks, maximizing usable space to print full hook opening headlines, canonical hook badges, and persona targeting.

Template assets are located in:
- Wireframe: `assets/content-plan-infographic/layout_content.md`
- HTML Template: `assets/content-plan-infographic/template.html`

---

## 2. Dimensional Budget (720 × 1280px)

The canvas must adhere to strict pixel budgeting so the entire graphic fits on screen with zero vertical scrolling or clipped elements:

| Band | Y-Range | Height | Component | Description |
|---|---|---|---|---|
| **Band 1** | 0 – 64px | 64px | Executive Masthead | Brand badge, channel/Page ID, hotline, and campaign title (`Instrument Serif` 24px). |
| **Gap 1** | 64 – 72px | 8px | Margin Bottom | Spacing between masthead and legend bar. |
| **Band 2** | 72 – 106px | 34px | Hook Legend Bar | Pacing title (`LỘ TRÌNH 20 BÀI · 4 TUẦN`) and hook count pills without symbols (`Question-First: 7 bài`). |
| **Gap 2** | 106 – 114px | 8px | Margin Bottom | Spacing between legend and table. |
| **Band 3** | 114 – 1252px | 1138px | Unified Table Container | Complete 20-post master table with 28px header and 20 rows (~55.5px each). |
| **Padding** | 1252 – 1280px | 28px | Outer Canvas Padding | 14px top, 14px bottom outer canvas margins. |

---

## 3. Table Column Layout (Total Width: 684px)

Inside `#canvas` (720px wide with 18px left/right padding), the table fills exactly 684px:

| Column | Width | CSS Class | Contents | Typography |
|---|---|---|---|---|
| **Tuần / Ngày** | 66px | `.col-day` | Week code + Day of week | `JetBrains Mono` 9.5px bold + `Inter` 8.5px |
| **Định Dạng Hook** | 114px | `.col-hook` | Canonical hook badge pill | `JetBrains Mono` 8px bold uppercase |
| **Nội Dung Hook** | 368px | `.col-content` | Full opening hook headline (quoted) | `Inter` 9.5px, line-height 1.32, 3-line clamp |
| **Đối Tượng** | 136px | `.col-meta` | Target persona / audience only | `Plus Jakarta Sans` 8.5px, line-height 1.3, 3-line clamp |

---

## 4. Visual Styling & Color Tokens (Harvey Editorial)

```css
:root {
  --canvas: #FBFBF9;       /* Warm alabaster paper */
  --ink: #0F172A;          /* Deep midnight slate */
  --accent: #C25E2E;       /* Terracotta ochre */
  --surface: #FFFFFF;      /* Clean white card surface */
  --container: #F4F3EE;    /* Soft neutral container */
  --alt-row: #F9F8F5;      /* Subtle zebra striping */
  --grid: #E2DFD7;         /* Delicate table hairline border */
  --border: #D8D4C9;       /* Card border */
  --muted: #64748B;        /* Supporting text */
  
  /* Hook Badge Palette */
  --qf-bg: #FEF3C7;  --qf-border: #FCD34D;  --qf-text: #92400E; /* Question-First (Amber) */
  --dct-bg: #FEE2E2; --dct-border: #FCA5A5; --dct-text: #991B1B; /* Direct Teardown (Coral) */
  --lfm-bg: #E0E7FF; --lfm-border: #A5B4FC; --lfm-text: #3730A3; /* Lessons from Models (Indigo) */
}
```

---

## 5. Rendering Procedure with Playwright

To capture a pixel-perfect 2× Retina PNG (`1440 × 2560px`):

```bash
.venv/bin/python -c "
import os
from playwright.sync_api import sync_playwright

html_path = os.path.abspath('local/<SLUG>/brand/content-plan-infographic/index.html')
png_path = os.path.abspath('local/<SLUG>/brand/content-plan-infographic/output.png')

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(
        viewport={'width': 720, 'height': 1280},
        device_scale_factor=2
    )
    page.goto(f'file://{html_path}')
    page.wait_for_timeout(1000)
    page.screenshot(path=png_path)
    browser.close()
"
```

### Critical Guardrails:
1. **No Canvas Centering Transforms:** Do not use `position: absolute; left: 50%; top: 50%; transform: translate(-50%, -50%)`. When viewport is 720 × 1280, set `body` and `#canvas` to `position: relative; margin: 0; width: 720px; height: 1280px;`.
2. **Legend Pills Formatting:** Do not include brackets (`[?]`) or week range tags (`(T1-T2)`). Use clean labels: `<Hook Type>: <Count> bài`.
3. **Audience Column Exclusivity:** Display only the target persona/audience. Do not combine angle and audience in the same column.
4. **Week Demarcation:** Add `class="week-end"` to rows 5, 10, and 15 (`border-bottom: 2.5px solid var(--accent)`) to visually separate weekly blocks.
