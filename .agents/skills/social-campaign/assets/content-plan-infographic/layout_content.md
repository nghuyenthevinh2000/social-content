# Master Content Plan Infographic Layout (9:16 Portrait Canvas)

```text
720 × 1280 (9:16 Portrait Canvas)
+--------------------------------------------------------------+ [Y: 0]
| BAND 1: Executive Masthead & Identity            | H: 64px    |
+--------------------------------------------------------------+ [Y: 64]
| GAP: Margin                                      | H: 8px     |
+--------------------------------------------------------------+ [Y: 72]
| BAND 2: Hook Archetype Legend & Pacing Horizon    | H: 34px    |
+--------------------------------------------------------------+ [Y: 106]
| GAP: Margin                                      | H: 8px     |
+--------------------------------------------------------------+ [Y: 114]
| BAND 3: Unified 20-Post Master Editorial Table    | H: 1138px  |
|         (Weeks 1-4 Unified · Full Hook Content)              |
+--------------------------------------------------------------+ [Y: 1252]
| Canvas Padding Bottom                            | H: 28px    |
+--------------------------------------------------------------+ [Y: 1280]
```

## Specifications & Design Tokens

- **Orientation & Resolution:** 720 × 1280px (9:16 Portrait), 2× Retina capture (`1440 × 2560px`).
- **Brand Palette (Harvey Editorial):**
  - Canvas: `#FBFBF9` (Alabaster Paper)
  - Ink: `#0F172A` (Midnight Slate)
  - Accent: `#C25E2E` (Terracotta Ochre)
  - Container: `#F4F3EE`
  - Alternate Row: `#F9F8F5`
  - Grid / Border: `#E2DFD7`
- **Hook Badge Colors:**
  - `question-first`: Background `#FEF3C7`, Border `#FCD34D`, Text `#92400E`
  - `direct-consulting-teardown`: Background `#FEE2E2`, Border `#FCA5A5`, Text `#991B1B`
  - `lessons-from-models`: Background `#E0E7FF`, Border `#A5B4FC`, Text `#3730A3`
- **Typography:**
  - Masthead Title: `Instrument Serif`, 24px, color `#0F172A`, line-height 1.15
  - Table Headers: `JetBrains Mono`, 9px bold, uppercase, background `#0F172A`, text `#FFFFFF`
  - Table Hook Content: `Inter`, 9.5px, line-height 1.32, color `#0F172A`, font-weight 500
  - Target Audience: `Plus Jakarta Sans`, 8.5px, line-height 1.3, color `#0F172A`, font-weight 600
  - Week / Day Code: `JetBrains Mono`, 9.5px bold + `Inter` 8.5px muted

## Column Dimensioning (Width: 684px)

| Column | Class | Width | Content Description |
|---|---|---|---|
| Col 1 | `.col-day` | 66px | Week code (`W1 · #01`) + Day (`Thứ Hai`) |
| Col 2 | `.col-hook` | 114px | Canonical hook type badge pill |
| Col 3 | `.col-content` | 368px | Complete opening headline / hook text |
| Col 4 | `.col-meta` | 136px | Target persona / audience only |

## Week Segmentation
- Every 5 posts (Posts 5, 10, 15) end with `.week-end` featuring a `2.5px solid var(--accent)` divider line to clearly demarcate Weeks 1, 2, 3, and 4 inside a single unified table.
