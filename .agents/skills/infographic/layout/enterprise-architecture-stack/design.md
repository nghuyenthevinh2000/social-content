---
name: enterprise-architecture-stack
title: Enterprise Architecture Stack
format: Landscape 16:9 Widescreen (1618 × 752 px)
retina_dimensions: 3236 × 1504 px (--scale 2)
category: Enterprise Architecture / System Design / Technology Stack
screenshot_command: node "$REPO_ROOT/.agents/skills/infographic/scripts/screenshot-retina.js" "$REPO_ROOT/topics/<slug>/index.html" "$REPO_ROOT/topics/<slug>/output.png" --scale 2 --width 1618 --height 752 --timeout 2000
---

# Enterprise Architecture Stack Template

## What This Template Serves

The **Enterprise Architecture Stack** is a specialized, widescreen landscape infographic engineered to map complex, multi-tiered enterprise software systems, cloud architectures, and capability frameworks onto a single coherent visual canvas.

Unlike document-style report templates, this template uses a **system layer model** inspired by TOGAF, C4 architecture models, and modern enterprise IT landscapes:
1. **Vertical Boundary Axis (Left Sidebar)**: A structural axis line with circular junction markers that clearly categorizes the horizontal layers of the stack.
2. **Horizontal Dotted Guidelines**: Subtle demarcation lines ensuring clear separation of technical responsibilities.
3. **Four Color-Coded Architectural Tiers**:
   - **Layer 1 (Deep Navy - Applications & Channels)**: User touchpoints, portal interfaces, and client applications.
   - **Layer 2 (Mid Blue - Business Capabilities & Domains)**: High-density 12-block grid representing functional capabilities, domain logic, and business workflows.
   - **Layer 3 (Sky Blue - Shared Services & Middleware)**: Microservices, integration middleware, and reusable APIs.
   - **Layer 4 (Primary Navy - Platform & Infrastructure)**: Foundational compute, security, cloud fabric, and data storage foundations.

### Ideal Use Cases
- **Enterprise Architecture Blueprints**: Mapping an organization's full IT topology from frontend client apps down to underlying cloud infrastructure.
- **AI / LLM Platform Stacks**: Visualizing modern AI architectures (e.g., UI apps → Agent Orchestration & Prompting → Model APIs & Vector DBs → GPU compute & Cloud hosting).
- **Modern Data Stack (MDS) Overviews**: Showcasing Ingestion, Transformation, Storage, and BI / Consumption layers.
- **SaaS / Platform Capability Maps**: Presenting the full technical breadth of a software suite for investors, enterprise buyers, or technical due diligence.
- **System Migration & Modernization Roadmaps**: Demonstrating target-state architecture vs legacy tiers.

### When NOT to Use
- Narrative executive summaries requiring long text explanations (use `executive-summary-report`).
- Financial metrics, quarterly earnings, and profit/loss statements (use `financial-performance-report`).
- Marketing campaign metrics and social media engagement stats (use `monthly-social-media-report`).

---

## Agent Rationale Snippet (For Step 1 Confirmation)

When proposing this template during **Step 1 (Plan & Confirm Gate)**, adapt this rationale for the user:

> "I recommend the **Enterprise Architecture Stack** template. Its 16:9 widescreen landscape format is purposefully designed for technical system maps and technology stacks. It organizes components into 4 distinct architectural layers (Channels, Capabilities, Services, Infrastructure) anchored by a left boundary axis with dot markers, offering 24+ structured block slots to map your entire system ecosystem cleanly without visual clutter."

---

## Visual & Design Architecture

### Color Palette
| Variable / Token | Hex Code | Role & Usage |
|---|---|---|
| `--bg` | `#ffffff` | Clean white canvas background |
| `--navy-dark` | `#102649` | Layer 1 background container, deepest architectural tier |
| `--primary-navy` | `#183b72` | Left sidebar layer labels, Layer 4 platform foundation blocks |
| `--blue-mid` | `#4a7ad8` | Layer 2 domain capability blocks (upper & lower rows) |
| `--blue-card` | `#7398ee` | Layer 3 service & middleware blocks |
| `--blue-light` | `#9bc3fd` | Accent & hover state highlights |
| `--card-border` | `rgba(255, 255, 255, 0.88)` | Outlined card slot borders inside Layer 1 |
| `--axis-gray` | `#94a3b8` | Vertical axis line and boundary junction dots |
| `--divider-color`| `#cbd5e1` | Horizontal dotted divider guidelines |

### Typography
- **Font Stack**: `'Plus Jakarta Sans'`, `'Inter'`, sans-serif.
- **Left Layer Category Labels** (`.layer-label-item`): 16px, Weight 700, Line-height 1.25, Color `--primary-navy`, Right-aligned.
- **Component Blocks** (`.block`): 14px, Weight 600, Line-height 1.35, Color `#ffffff`, Centered, `user-select: none`.

---

## Content Anatomy & Slot Breakdown

```
+-------------------------------------------------------------------------------------------------------------+
| [LAYER 1 LABEL] |  [ Card 1 (3x) ]     [ Card 2 (3x) ]     [ Card 3 (3x) ]     [ Card 4 (Compact 1x) ]      |
| Axis + Markers  |-------------------------------------------------------------------------------------------|
| [LAYER 2 LABEL] |  [8 Upper Capability Blocks (1fr x 8)]                                                    |
|                 |  [4 Lower Wide Capability Blocks (1fr x 4)]                                               |
|.................|...........................................................................................|
| [LAYER 3 LABEL] |  [Col 1 Tall] | [Col 2 Top / Bottom] | [Col 3 Tall] | [Col 4 Top-Wide / Bottom 2-Split]   |
|.................|...........................................................................................|
| [LAYER 4 LABEL] |  [Bar Full Width - Top]                                                                   |
|                 |  [Col Left (878px)]                   | [Col Mid (258px)] | [Col Right (1fr)]              |
|                 |  [Bar Full Width - Bottom]                                                                |
+-------------------------------------------------------------------------------------------------------------+
```

### 1. Left Sidebar Navigation (`.sidebar-left`)
- **Axis Line** (`.axis-line`): Vertical rule at `x = 185px` running the full height of the stack.
- **Layer Markers** (`.axis-marker`): 8 circular dots pinpointing the exact top and bottom bounds of each tier (`marker-l1-top`, `marker-l1-bottom`, etc.).
- **Category Labels**:
  - `label-l1` (Top 37px, Height 114px): e.g., "Presentation & Channels" / "Experience Layer"
  - `label-l2` (Top 175px, Height 266px): e.g., "Business Capabilities" / "Core Domains"
  - `label-l3` (Top 449px, Height 130px): e.g., "Services & Integration" / "Middleware APIs"
  - `label-l4` (Top 585px, Height 130px): e.g., "Platform & Foundation" / "Cloud Infrastructure"

### 2. Layer 1 — Deep Navy Container & Outlined Cards (`.layer-1`)
- Deep navy backdrop (`--navy-dark`) spanning 1395px.
- 4 Outlined Card Slots:
  - `slot-1-1` (flex: 3): e.g., "Mobile & Web Portals"
  - `slot-1-2` (flex: 3): e.g., "Partner APIs & SDKs"
  - `slot-1-3` (flex: 3): e.g., "Admin & Operator Console"
  - `slot-1-4` (flex: 1, compact): e.g., "IoT & Edge"

### 3. Layer 2 — Mid Blue Capability Blocks (`.layer-2`)
- 2-row grid of mid-blue (`--blue-mid`) blocks:
  - **Upper Row (`.row-upper`)**: 8 high-density slots (`slot-2-1` through `slot-2-8`) for granular business capabilities (e.g., Billing, Identity, Catalog, Orders, Notifications, Search, Analytics, Audit).
  - **Lower Row (`.row-lower`)**: 4 wide slots (`slot-2-9` through `slot-2-12`) for broader cross-cutting domains (e.g., Customer Lifecycle, Supply Chain Engine, Compliance Engine, Intelligence Engine).

### 4. Layer 3 — Sky Blue Services Grid (`.layer-3`)
- Asymmetric 4-column layout (`--blue-card` fill) matching real-world distributed architectures:
  - **Col 1 (`slot-3-1`)**: Full-height vertical service block.
  - **Col 2 (`slot-3-2`, `slot-3-3`)**: 2 vertically stacked service blocks.
  - **Col 3 (`slot-3-4`)**: Full-height vertical service block.
  - **Col 4 (`slot-3-5`, `slot-3-6`, `slot-3-7`)**: Top wide bar + bottom 2-column split.

### 5. Layer 4 — Primary Navy Platform Infrastructure (`.layer-4`)
- Grounding platform layer (`--primary-navy`):
  - **Top Bar (`slot-4-1`)**: Cross-cutting foundation (e.g., "Event Streaming & Message Broker").
  - **Mid Row (`slot-4-2`, `slot-4-3`, `slot-4-4`)**: Asymmetric 3-column split (e.g., "Container Orchestration & Kubernetes", "Multi-Region Storage", "Identity & IAM").
  - **Bottom Bar (`slot-4-5`)**: Physical/cloud substrate (e.g., "Global Cloud Infrastructure & Edge CDN").

---

## How to Adapt This Template

1. **Copy Template Directory**:
   ```bash
   cp -r "$REPO_ROOT/.agents/skills/infographic/layout/enterprise-architecture-stack" "$REPO_ROOT/topics/<new-slug>"
   ```
2. **Populate Sidebar Category Names**:
   Insert the text directly inside `.layer-label-item` elements (or via inner text in HTML):
   ```html
   <div class="layer-label-item label-l1">Client &<br>Experience</div>
   <div class="layer-label-item label-l2">Core Business<br>Capabilities</div>
   <div class="layer-label-item label-l3">Platform APIs<br>& Services</div>
   <div class="layer-label-item label-l4">Infrastructure<br>& Data Layer</div>
   ```
3. **Populate Component Blocks**:
   Insert concise 2–5 word component names inside each `data-slot` block:
   ```html
   <div class="block" data-slot="2-1">Identity & Access</div>
   ```
4. **Capture Widescreen Retina Screenshot**:
   > [!IMPORTANT]
   > Note the distinct viewport size: **1618 × 752 px** (not A4 portrait).
   ```bash
   node "$REPO_ROOT/.agents/skills/infographic/scripts/screenshot-retina.js" \
     "$REPO_ROOT/topics/<new-slug>/index.html" \
     "$REPO_ROOT/topics/<new-slug>/output.png" \
     --scale 2 --width 1618 --height 752 --timeout 2000
   ```
