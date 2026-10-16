---
name: Lạc Hồng — Hook Loop Design Kit
version: 1.0.0
target-platform: Desktop (1440px) & Mobile (390px)
design-language: "Editorial Experiment Control Room (Anti-Slop / High-Agency)"
project-id: "9564803020487326123"
colors:
  warm-canvas: "#F7F8F5"
  paper-white: "#FFFFFF"
  ink-charcoal: "#17241F"
  forest-action: "#176346"
  quiet-sage: "#E9F2EC"
  slate-secondary: "#526159"
  mist-border: "#D7DFD9"
  evidence-blue: "#245DB0"
  caution-ochre: "#875500"
  caution-bg: "#FFF3DA"
  stop-crimson: "#B42332"
  stop-bg: "#FFF0F0"
typography:
  font-family-primary: "Be Vietnam Pro, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
  font-family-mono: "JetBrains Mono, SFMono-Regular, Menlo, monospace"
---

# Lạc Hồng (Hook Loop) — Design Kit & Semantic Design System

> **Aesthetic Archetype:** *Editorial Experiment Control Room.*
> High-agency, disciplined, data-dense without clutter. Built for Southeast Asian growth teams, TikTok Shop sellers, indie founders, and creators. Replaces speculative AI visual tropes with calm, authoritative precision.

---

## 1. Visual Atmosphere & Philosophy

- **Density:** *Balanced Cockpit (Level 7/10)*. High information density for experiment metrics, Bayesian confidence intervals, and video timelines, balanced with generous negative space around primary decisions.
- **Variance:** *Offset Asymmetric (Level 6/10)*. Setup flows feature asymmetrical two-column workspaces (60% form control / 40% live preview), keeping actionable inputs grounded while previews provide instant tactile reassurance.
- **Motion:** *Weighted & Functional (Level 5/10)*. Spring physics (`stiffness: 120, damping: 22`) for interactive controls. No gratuitous decorative animations; motion is strictly reserved for state changes (e.g. video scrub, stage rail step advancement, metric maturity timers).
- **Cognitive Ergonomics & Progressive Disclosure:** Never overwhelm first-time users with technical controls, Bayesian parameters, or compliance checklists. Onboarding asks **one simple question per screen** with pre-configured safe defaults. Power-user controls (custom regex, time-slot scheduling, multi-account rotation) are unlocked progressively as users run subsequent rounds.
- **Tone:** Authoritative, transparent, and legally conservative. Always honest about platform limitations (e.g., TikTok audit status, organic statistical variance).

---

## 2. Color Palette & Functional Roles

Every color has an exact functional role. The AI purple/neon gradient aesthetic is strictly banned.

| Token Name | Hex Code | Purpose / Application | Contrast Ratio (vs BG) |
| :--- | :--- | :--- | :--- |
| `warm-canvas` | `#F7F8F5` | Global background canvas. Warm, paper-like warmth that reduces eye fatigue. | Base |
| `paper-white` | `#FFFFFF` | Elevated surfaces: cards, modals, input containers, active preview tiles. | 1.07:1 (on canvas) |
| `ink-charcoal` | `#17241F` | Primary typography, active icons, selected navigation markers. | 15.2:1 (AAA) |
| `forest-action` | `#176346` | Primary action button, completed state checkmarks, brand accent. | 6.8:1 (AA) |
| `quiet-sage` | `#E9F2EC` | Active navigation background, subtle highlight pills, selected item tints. | 1.15:1 (on canvas) |
| `slate-secondary`| `#526159` | Secondary captions, helper text, inactive step labels, placeholder icons. | 5.6:1 (AA) |
| `mist-border` | `#D7DFD9` | 1px card boundaries, table cell dividers, inactive input borders. | Structural |
| `evidence-blue` | `#245DB0` | Hyperlinks, verified platform links, Bayesian credible interval brackets. | 6.4:1 (AA) |
| `caution-ochre` | `#875500` | Text/icon for `Leaning` results, pending audits, non-blocking warnings. | 6.2:1 (on #FFF3DA) |
| `caution-bg` | `#FFF3DA` | Background container for caution alerts and leaning confidence chips. | Container |
| `stop-crimson` | `#B42332` | Emergency Kill Switch, policy violations, revoked OAuth, critical alerts. | 6.5:1 (on #FFF0F0) |
| `stop-bg` | `#FFF0F0` | Container for destructive actions, emergency pause status bar, error alerts. | Container |

### Palette Constraints:
- Maximum 1 primary action accent (`forest-action`).
- No pure black (`#000000`). All dark text uses `#17241F`.
- Never use color alone to convey status: pair color with descriptive copy and icons (e.g. `Stop Crimson` + `[Octagon Pause]` + `"Paused: TikTok API Cap reached"`).

---

## 3. Typographic Architecture

The typography is built around **Be Vietnam Pro** for native SEA Latin script and flawless Vietnamese diacritic rendering (`ơ, ư, ế, ặ`), paired with **JetBrains Mono** for experiment timestamps, Hook Scores, and statistical values.

| Token | Family | Size | Weight | Line Height | Tracking | Usage |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `title-display` | Be Vietnam Pro | 32px | Semibold (600) | 40px | -0.02em | Onboarding screen titles, hero headers |
| `title-section` | Be Vietnam Pro | 22px | Semibold (600) | 28px | -0.01em | Panel group titles, step headers |
| `title-card` | Be Vietnam Pro | 18px | Medium (500) | 24px | 0 | Card headings, variant card labels |
| `preview-hook` | Be Vietnam Pro | 20px | Medium (500) | 28px | -0.01em | On-screen hook overlay preview in 9:16 frame |
| `body-default` | Be Vietnam Pro | 14px | Regular (400) | 21px | 0 | Primary paragraph text, form descriptions |
| `body-strong` | Be Vietnam Pro | 14px | Medium (500) | 21px | 0 | Form labels, table header titles |
| `caption` | Be Vietnam Pro | 12px | Regular (400) | 16px | +0.01em | Timestamps, platform capability notes |
| `code-score` | JetBrains Mono | 16px | Medium (500) | 20px | 0 | Hook Scores (0–100), Bayesian intervals |
| `code-meta` | JetBrains Mono | 12px | Regular (400) | 16px | 0 | Video duration (`00:03.00`), Variant IDs |

---

## 4. Core Component Library

### 4.1 Collapsible Project Rail & Drawer (Left Rear)
- **Geometry:** 
  - *Collapsed state:* Vertical floating edge tab `left: 0, top: 48%` with 🗂 glyph, plus header toggle button `[≡ Dự án]`.
  - *Expanded drawer:* 310px width (`max-width: 85vw`), off-canvas slide-in with `z-index: 50` and semi-transparent backdrop.
- **States & Actions:**
  - *Active Project:* Pill item with green marker `●` and `Đang mở` badge.
  - *Inactive Project:* Muted marker `○`, hover background highlight `#FFFFFF`.
  - *Project Creation:* Outlined button `+ Tạo dự án mới` for instantaneous project scaffolding without losing current context.

### 4.2 View Switch: Human Curation (1 & 2) vs AI Loop (3 & 4)
- **Geometry:** Segmented pill container (`#E8ECE5` background, `#D4DED0` border, 10px radius).
- **Two Distinct Paradigms:**
  - *Human Curation (Stages 01 & 02):* User owns creative control (Hook suggestion & Video creation/review). Chat 30% acts as creative interviewer. Handoff notice informs that telemetry requires real-world distribution time (2h, 6h, 24h, 48h, 72h).
  - *AI Loop (Stages 03 & 04):* System owns automated telemetry (Metrics ingestion & Loop results/insights). Chat 30% acts as data analyst & strategy advisor. Cycle handoff button transitions back to Human Curation for Loop 02.
- **Interactive Behavior:** Toggling the switch smoothly transitions between stage pairs, updating eyebrow labels and highlighting the active part in the stage tabs rail.

### 4.3 Stage Rail (Navigation & Progress)
- **Geometry:** 4 interconnected stage tabs organized into two semantic groups (`Human Curation` and `AI Loop (Tự động)`).
- **States:**
  - *Completed:* `#176346` circle with white checkmark `✓`, title in `#17241F`.
  - *Active:* 2px `#176346` ring with white center, bold title, `#E9F2EC` highlight pill.
  - *Upcoming:* 1px `#D7DFD9` border, title in `#526159`.
  - *Blocked/Paused:* `#B42332` warning icon with tooltip explaining blockers.

### 4.2 9:16 Video Preview Card
- **Aspect Ratio:** Fixed 9:16 vertical ratio (270px × 480px on desktop setup).
- **Surface:** `#0F1713` dark foundation with muted frame border.
- **Hook Isolation Zone:** Visual 0–3s timeline overlay with a scrub head. The first 3 seconds are tinted `#E9F2EC` (the Hook Window), while seconds 3.01+ are labeled `#526159` "Locked Base Body".
- **Hook Overlay Text:** Rendered in `preview-hook` typography with slight drop shadow (`rgba(0,0,0,0.65)`) to guarantee readability over varying video backgrounds.

### 4.3 Archetype & Feature Tags
- **Pill Geometry:** 6px radius, 4px vertical / 8px horizontal padding.
- **Archetype Chips:** `#E9F2EC` background, `#176346` text, e.g. `Pain-Point Callout`, `Curiosity Gap`, `POV / Relatable`.
- **Feature Indicator:** Mono font tags, e.g. `[#Has_Number]`, `[?Question]`, `[VI+EN Code-mix]`, `[2.1s Duration]`.

### 4.4 Form Inputs with AI Draft Indicators
- **Standard Input:** 8px border radius, `#FFFFFF` background, 1px `#D7DFD9` border, 44px minimum height.
- **AI Draft Badge:** When fields are auto-populated from URL extraction, an inline chip displays `AI Draft — review before continuing` in `evidence-blue` (`#245DB0`) on `#F0F4FA`. The chip clears once the user edits or confirms the field.

### 4.5 Capability Honesty Matrix (Social Accounts)
- Each platform card explicitly separates 3 distinct capability vectors:
  1. **OAuth Connection:** `Connected` / `Disconnected`.
  2. **Auto-Post Capability:** `Public Autopilot Ready` (YouTube Shorts, FB Pages, IG Creator) vs `Draft Mode Only — App Audit Pending` (TikTok).
  3. **Metric Granularity:** `3s Retention Curve Available` vs `Aggregate Plays Only`.

### 4.6 Buttons & Action Hierarchy
- **Primary:** `#176346` background, `#FFFFFF` text, 8px radius. Active state: slight 1px downward translation, no glow.
- **Secondary / Outlined:** 1px `#D7DFD9` border, `#17241F` text, `#FFFFFF` background.
- **Emergency Kill Switch:** `#B42332` background, white text, prominent warning triangle icon. Always accessible without modal nesting.

---

## 5. Layout Grid & Spatial Rhythm

- **Base Unit:** 8px rhythm (8, 16, 24, 32, 48, 64px).
- **Desktop (1440px):**
  - Left Navigation / Progress Sidebar: 240px fixed.
  - Central Setup Canvas: 760px fluid.
  - Live Inspector / Context Drawer: 380px fixed.
  - Outer Gutters: 32px.
- **Mobile (390px):**
  - Single column with sticky bottom action tray (`min-h-[44px]` tap target).
  - Video preview docks in a compact horizontal carousel or expandable bottom sheet.

---

## 6. Anti-Patterns & Strict Rules

1. **NO "AI Purple / Blue Gradients":** Strictly banned. Use pure, tactile, editorial surfaces.
2. **NO Fake Autonomy:** Never promise "100% Autopilot" on TikTok until developer audit approval is granted. Explicitly mark it as "Draft In-Box Mode".
3. **NO Circular Spinners:** Use skeleton loaders matching exact component dimensions.
4. **NO Premature Winner Claims:** In onboarding, sample hooks are explicitly marked "Hypothesis: Untested".
5. **NO Unanchored Metric Lift:** Never show hypothetical "+300% Viral Growth" graphics. Show actual account baseline or state "Baseline building (0/3 rounds)".
