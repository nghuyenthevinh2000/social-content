# Browser-app design system plan

Scope: `tools/app/browser-app/src` (React + Ionic). Out of scope: `public/wireframe_preview.html`.

| Problem (audited) | Evidence |
|---|---|
| Text size | 16 distinct sizes, 10–36px |
| Spacing | About 12 values, off the 4px grid |
| Radius | 15 values |
| Control and box height | About 12 values, 22–72px |
| Color | 59 hex values and 21 rgba values, with 3 reds and 3 greys |
| Font | 4 font-family declarations, Inter not explicitly loaded |
| Weight | 500, 600 and 700 used about evenly |
| Inline styles | 46 `style={{}}` uses |

## Target tokens (`src/theme/variables.css`)

| Group | Tokens |
|---|---|
| Text size | `--text-xs` 11, `--text-sm` 13, `--text-md` 15, `--text-lg` 18, `--text-xl` 24 |
| Space | `--space-1` 4, `--space-2` 8, `--space-3` 12, `--space-4` 16, `--space-5` 24 |
| Radius | `--radius-sm` 6, `--radius-md` 12, `--radius-lg` 16, `--radius-pill` 999 |
| Control height | `--control-sm` 32, `--control-md` 44, `--control-lg` 52 |
| Surface | `--color-bg`, `--color-surface`, `--color-surface-alt` |
| Text color | `--color-text`, `--color-text-muted`, `--color-text-inverse` |
| Border | `--color-border` |
| Brand | `--color-accent`, `--color-accent-soft` |
| Status | `--color-success`, `--color-warning`, `--color-danger`, each with a `-soft` variant |
| Platform | `--color-facebook` and similar, for logos only |
| Font | `--font-sans` (Inter stack), `--font-mono`; set `--ion-font-family` to `--font-sans` |
| Weight | `--weight-regular` 400, `--weight-medium` 500, `--weight-bold` 700 |

Legacy aliases are kept until the end: `--line`, `--paper`, `--card`, `--ink`, `--muted`, `--green`, `--blue`, `--radius`.

## Flow

```text
0 Baseline -> 1 Tokens -> 2 Primitives -> 3 Pilot AuthModal -> 4 Migrate rest -> 5 Inline styles -> 6 Lint guard -> 7 Remove aliases
```

## Steps

| # | Step | Files | Done when |
|---|---|---|---|
| 0 | Capture Playwright screenshot baseline and run `npm test` | `e2e/` | Baseline stored, tests green |
| 1 | Add all tokens plus legacy aliases. Add the Inter `@font-face` or `<link>`. | `theme/variables.css`, `index.html` | `npm run build` passes |
| 2 | Add `theme/primitives.css` with `.card`, `.btn` (sm, md), `.field`, `.chip` and `.stack-*` gap helpers. Import it in `main.tsx`. | `theme/primitives.css` | Primitives render in one page |
| 3 | Pilot on `AuthModal.css` (151 lines). Snap values and review the screenshot diff. | `components/AuthModal.css` | Diff is 2px or less and approved |
| 4 | Migrate in order: `Tour` (45), `MediaPanel` (262), `VideoTab` (403), `Home` (1,505). Snap rules are in the next table. | `components/*.css`, `pages/Home.css` | Zero raw px or hex outside the token files, per file |
| 5 | Move the 46 inline styles to classes: `VideoTab` 25, `MediaPanel` 14, `Home` 6, `Tour` 1. Leave only dynamic values. | `*.tsx` | `grep "style={{"` shows only dynamic styles |
| 6 | Add stylelint and wire it into `npm run lint`. | `.stylelintrc`, `package.json` | Raw values fail lint |
| 7 | Delete the legacy aliases and re-run the full test suite | `variables.css` | No alias references remain |

## Snap rules

| Raw value | Snap to |
|---|---|
| font 10–11 | `--text-xs` |
| font 12, 12.5, 13 | `--text-sm` |
| font 14, 15, 16, 0.9rem | `--text-md` |
| font 17–20 | `--text-lg` |
| font 22–36 | `--text-xl` (36 may need a `--text-display` token; ask) |
| space 2, 3, 4, 6 | `--space-1` (or `--space-2` for 6) |
| space 10, 12, 14 | `--space-3` |
| space 16, 18, 20 | `--space-4` |
| space 22, 24 | `--space-5` |
| radius 4–8 | `--radius-sm` |
| radius 9–14 | `--radius-md` |
| radius 16–24 | `--radius-lg` |
| radius 999 or 50% | `--radius-pill` or `50%` (circles) |
| weight 600 | 700 for headings, 500 for labels |
| reds (`#c92a2a`, `#b42318`, `#e03131`) | `--color-danger` |
| greys (`#444`, `#6b7280`, `#888`) | `--color-text` or `--color-text-muted` |
| `#fff` | `--color-text-inverse` or `--color-surface` by context |

## Lint guard

```json
{
  "rules": {
    "color-no-hex": true,
    "function-disallowed-list": ["rgb", "rgba"],
    "declaration-property-value-disallowed-list": {
      "/^(font-size|padding|margin|gap|border-radius)/": ["/\\d+px/"]
    }
  },
  "overrides": [{ "files": ["src/theme/variables.css"], "rules": { "color-no-hex": null, "function-disallowed-list": null } }]
}
```

## Risks and decisions

| Item | Handling |
|---|---|
| 1–2px layout shifts | Screenshot diff per file; fix by choosing the neighbouring token, not a new one |
| Ionic overrides tokens | Map `--ion-*` variables to tokens in `variables.css` |
| Ambiguous colors | Review the grey, red and orange mapping before bulk replace |
| Decision: 36px display size | Add `--text-display` or snap to `--text-xl` |
| Decision: font loading | Bundle Inter locally (offline-safe, for Capacitor) or use a CDN link |
| Decision: lint guard | Include step 6 (recommended) or skip |
