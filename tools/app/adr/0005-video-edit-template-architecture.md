# ADR-0005: Video Edit Template Architecture

```text
Built-in *.template.json ──(startup sync)──► video_templates (PostgreSQL) ◄──(save / owner delete)──┐
                                                     │                                              │
                                          GET /api/videos/templates                                 │
                                                     │                                              │
                                        VideoTab (portrait preview + picker)                        │
                                                     │                                              │
                              POST /api/videos/edit[-plan] (template_id)                            │
                                                     │                                              │
                              edit.py (style-only prompt) ──► edit_config.json                      │
                                                     │                                              │
                              extract_template_from_edit_config() ──► video_jobs.produced_template_json
```

| Field | Decision |
|---|---|
| Status | Accepted (2026-11-28) |
| Core Principle | Treat every video edit as producing a sanitized, declarative style template (`produced_template_json`) that users can optionally save to a shared `video_templates` catalog (`public` or `private`) with no remix-lineage graph. |
| Scope | `tools/app/backend/` (`schema.sql`, `video_engine/templates.py`, `video_engine/edit.py`, `video_engine/jobs.py`, `server.py`, `Dockerfile`, `Dockerfile.dockerignore`) and `tools/app/browser-app/src/` (`components/VideoTab.tsx`, `components/VideoTab.css`, `videoEditDraft.ts`, `pages/Home.tsx`, `locales/en.ts`, `locales/vi.ts`). |

## 1. Context & Requirements

| Driver | Requirement | Implication |
|---|---|---|
| Preset & community styles | Display built-in templates (`.agents/skills/video-editing/scripts/video_engine/templates/*.template.json`) and user-shared templates in `VideoTab`. | Unified `video_templates` table seeded at startup (`author_id IS NULL`) alongside user rows (`author_id IS NOT NULL`). |
| Zero-lineage remixing | Every edit produces a self-contained style JSON; users opt in to save it for reuse or sharing. | Drop `parent_template_id` / remix trees; `extract_template_from_edit_config()` captures all active visual/audio style layers (`color_grade`, `hook_card_style`, `step_anchor_style`, `cta_style`, `subtitle_style`, `punch_zoom_*`, `step_sfx`/`cta_sfx`). |
| Ownership & safety | Only the template owner can delete their template; untrusted template JSON must not inject paths or prompts. | Strict `ALLOWED_TEMPLATE_KEYS` + `STRIP_STYLE_KEYS` allowlist in `sanitize_template_config()`; `delete_template()` checks `author_id == user_id` (`403` for non-owners and built-ins). |
| Visual clarity | Users need to see how an edit looks before applying it. | Card preview renders a 9:16 human face anchor (user profile photo or fallback SVG) with `color_grade` filter and live style overlays (`HOOK`, `01 · STEP`, `subtitle_style` / `CTA`), plus name-only footer. |

## 2. Architecture & Data Flow

| Layer | Component | Responsibility |
|---|---|---|
| Persistence | `video_templates` & `video_jobs` (`schema.sql`) | `video_templates` stores `{id, slug, name, author_id, visibility, config_json, created_at, updated_at}`; `video_jobs` stores `template_id` and `produced_template_json`. |
| Sanitizer & extractor | `video_engine/templates.py` (`TEMPLATE_STORE`) | `sync_builtin_templates()` upserts disk presets; `extract_template_from_edit_config()` strips timing/content/file paths and extracts style dictionaries including `subtitle_style`; `create_template()` / `delete_template()` enforce validation and ownership. |
| Planner & runner | `video_engine/edit.py`, `video_engine/jobs.py` | Loads `template_id` config into `build_video_edit_acp_prompt()` as declarative style parameters only; persists `produced_template_json` via `mark_completed()`. |
| HTTP API | `server.py` | `GET /api/videos/templates`, `POST /api/videos/templates` (re-extracts from `edit_config.json` in blobs when `job_id` is supplied), `POST /api/videos/templates/<id>/delete`, and optional `template_id` on `POST /api/videos/edit[-plan]` (allowing empty prompt). |
| Frontend UI | `VideoTab.tsx`, `videoEditDraft.ts` | Fetches templates on auth, persists `templateId` in draft state, renders portrait preview cards with owner-only trash button, and places a `bookmarkOutline` save-template icon action in the history card header. |

## 3. Alternatives, Verification & Rollback

| Aspect | Detail |
|---|---|
| Alternatives rejected | Reading filesystem JSON directly without DB (blocks user uploads/sharing); maintaining `parent_template_id` remix trees (unnecessary because every edit outputs a complete template); static thumbnail PNGs (stale when community templates are saved dynamically). |
| Verification | `.venv/bin/pytest tools/app/backend/tests/test_video_edit_engine.py -q` (15 passed) and `npx vitest run src/VideoTab.test.tsx src/locales/locale.test.tsx && npm run build` (16 passed, 2 test files). |
| Rollback | Leave `template_id` omitted in `VideoTab.tsx` or disable `GET/POST /api/videos/templates` routes; freeform prompt and reference-URL video edits remain unaffected. |
