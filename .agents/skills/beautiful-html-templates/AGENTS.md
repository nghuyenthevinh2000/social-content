# Agent Operating Manual: beautiful-html-templates

```text
Clarify (Occasion + Mood) ──> Shortlist 3 Candidates ──> Generate & Open Previews ──> User Gate ──> Build Deck ──> Deliver
```

## Mission & Mandatory Workflow Gates

| Step | Phase | Protocol & Operational Rules | Invariant Gate / Validation |
|---|---|---|---|
| 0 | Agent Mission | Pick appropriate template, clone into project workspace, and adapt user content into production-ready HTML deck. | Read operating manual before deck generation. |
| 1 | Clarify Brief | Inquire: (1) Occasion (e.g. founder pitch, research synthesis, brand manifesto) and (2) Mood/vibe (e.g. punchy, literary, warm, dark). | **MANDATORY STOP GATE:** Do not shortlist or inspect templates before receiving user response. |
| 2 | Shortlist 3 Candidates | Query `index.json` against occasion + mood. Select 3 stylistically distinct templates (e.g. 1 editorial, 1 warm, 1 wildcard). | Must offer real stylistic variety; never select 3 similar templates. |
| 3 | Author Previews | For each candidate, extract cover slide from `template.html`, populate with actual title/subtitle/author/date, and save to `previews/01-<slug>.html`. | Must be standalone and fully functional with runtime assets intact. |
| 4 | Deliver Previews | Launch all 3 in default browser (`open <path>`); provide clickable file paths with one-line tone descriptions in chat. | **STRICT USER SELECTION GATE:** Wait for explicit user pick before building full deck. |
| 5 | Build Full Deck | Clone template folder into workspace (`topics/<topic-slug>/`); replace content per adaptation rules; add or drop slides (`NN / TT`). | Missing layouts must be synthesized using template design tokens. |
| 6 | Browser Review & Output | Open final deck (`open topics/<topic-slug>/template.html`); send clickable absolute path, 1-line tone rationale, and caveats. | Never dump process logs; always open browser and send file path. |

## Catalog Schema & Tone-First Matching

| Field / Topic | Definition / Heuristic | Operational Usage Protocol |
|---|---|---|
| `mood` | Emotional feeling keywords | Primary filter: match against user's desired emotional tone (e.g., confident, quiet, playful). |
| `tone` | Personality and voice descriptors | Match against delivery style (e.g., bold, minimal, literary, graphic). |
| `occasion` | Example use-case scenarios | Soft signal only; do not treat as an exclusive industry/topic whitelist. |
| `formality` | Audience calibration (`low` to `high`) | Sanity-check against user's target audience (e.g., avoid low formality for board pitches). |
| `density` | Information capacity per slide | Match to volume of user data (e.g., high density for data reviews, low for keynotes). |
| `scheme` | Color mode (`light` / `dark` / `mixed`) | Strict filter when user explicitly specifies a light or dark aesthetic. |
| `best_for` | Ideal feeling and context description | Use as primary rationale when pitching candidate templates to the user. |
| `avoid_for` | Clashing tones and anti-contexts | Soft warning only; user's explicit aesthetic preference overrides `avoid_for`. |
| `slide_count` | Number of slides in demo deck | Indicates layout diversity provided in the demo deck. |
| Tone vs Industry | Templates possess visual tones, not industry boundaries | Editorial can fit tech; playful can fit finance if user rejects traditional corporate look. |

## Template Adaptation & Extension Rules

| Category | Scope / Elements | Enforcement Invariants |
|---|---|---|
| **Always Preserve** | Google Fonts imports, font families, `:root` CSS variables, layout grids, slide classes, decorative SVGs, grain, runtime (`deck-stage.js`) | **The Design System:** Never substitute fonts, recolor accents, alter column grids, or remove signature ornaments. |
| **Always Replace** | Headlines (`<h1>`–`<h3>`), body copy (`<p>`, `<li>`), stats/metrics, author/date/citations, section chrome labels, image placeholders | **User Content:** Replace all demo text; insert real images at identical dimensions to avoid layout breakage. |
| **Slide Count Adjustments** | Adding or removing slides | Duplicate existing layout templates to expand; drop trailing slides to trim; update slide counters (`NN / TT`). |
| **Missing Layouts (Fonts)** | Synthesizing non-existent slide types | Use identical `font-family`, font weights, letter-spacing, and line-heights. |
| **Missing Layouts (Palette)** | Color application in new layouts | Confine styling to existing `:root` variables; map new elements to closest existing accent. |
| **Missing Layouts (Components)** | New cards, tables, timelines, or grids | Reuse template's component grammar (e.g., stat card structure: big number $\to$ label $\to$ body $\to$ mono caption). |
| **Missing Layouts (Chrome & Spacing)** | Slide padding, gutter, and headers/footers | Maintain exact slide padding (e.g. 64px), grid gutters, corner marks, top labels, and pagination. |
| **Navigation Integration** | Runtime integration for new slides | Ensure new slide elements register seamlessly with `deck-stage.js` or inline handlers. |

## Minimalism & Anti-Duplication Invariants

| Anti-Pattern | LLM Failure Mode | Mandatory Invariant Standard |
|---|---|---|
| **Icon Inflation** | Slapping FontAwesome, Lucide, or SVG icons on every bullet, header, or card | **Forbid icon spam.** Keep only icons in original template; maximum 1 hero icon/illustration per slide; never bullet with icons. |
| **Box-in-a-Box Nesting** | Wrapping every paragraph or item in bordered, shaded cards or containers | **Flatten hierarchy.** Prefer whitespace, CSS grid gap, and typographic scale over nested borders, boxes, and cards. |
| **Content Echo** | Repeating slide title words in subtitle, section headers, or bullet points | **Zero content echoing.** Subtitles must state new info or be omitted. Never rephrase or duplicate points across slides. |
| **Badge / Chip Spam** | Adding category pills (`[STRATEGY]`, `[METRIC]`, `[PHASE]`) over every item | **Eliminate chip clutter.** Maximum 1 eyebrow tag per slide; never place redundant tags above every list or card item. |
| **Filler & AI Prose** | Adding introductory fluff, meta-announcements, or obvious summary points | **High signal density.** Cut filler phrases ("It is crucial to note", "In today's landscape"). Write punchy, verifiable assertions. |
| **Canvas Overcrowding** | Cramming extra elements into spare space rather than letting layout breathe | **Preserve negative space.** Maintain 30%+ breathing room. Do not invent new cards or sections to fill empty canvas space. |

## Pitfalls & Output Contract

| Requirement | Guard / Pitfall | Operational Protocol |
|---|---|---|
| **Step 1 Skip Guard** | Bypassing brief clarification | Never pick templates without asking occasion and mood; user taste cannot be inferred from content alone. |
| **Step 4 Skip Guard** | Skipping title-slide previews | Always show real candidate cover slides in browser before proceeding to full deck build. |
| **Template Mashing** | Combining layouts from different templates | Strictly forbidden; each template is a closed visual system. Extend within the selected template only. |
| **Modernization Trap** | Altering vintage or brutalist designs | Do not modernise or clean up intentional aesthetic quirks; if style mismatches, pick another template. |
| **Browser Execution** | Forgetting to open generated files | Execute `open <path>` for every preview, draft, and final presentation immediately upon creation. |
| **Deliverable Message** | Emitting excessive log transcripts | Send clickable absolute file path, one-line tone rationale, and any custom layout notes. Omit raw process transcripts. |
