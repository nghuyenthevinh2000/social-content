---
name: business
summary: B2B playbook lessons (JSON), a reusable trap/solution infographic template, and a workflow that renders infographics and stages LinkedIn posts.
tags:
- business
- b2b-marketing
- infographics
- linkedin-workflow
submodules:
  lessons/: Source lessons (*.json) read by the workflow.
  infographics/: `template.html` plus one rendered output folder per lesson.
  linkedin/: `results.json` audit trail of staged/published posts.
  workflow.py: Reads lessons/*.json, renders infographics, stages (or publishes) LinkedIn posts.
---

# Business (`topics/business`)

## Layout

```
topics/business/
├── lessons/        <slug>.json (workflow input)
├── infographics/   template.html, <slug>/output.png
├── linkedin/       results.json
└── workflow.py
```

## How to run the workflow

Run from the repository root.

```bash
# Dry run: render infographics, build post text, write linkedin/results.json (nothing is posted)
uv run python topics/business/workflow.py

# One lesson only (file name or stem)
uv run python topics/business/workflow.py --file conference-roi-playbook-pre-booking-meetings

# Post to LinkedIn via tools.linkedin_agent
uv run python topics/business/workflow.py --file conference-roi-playbook-pre-booking-meetings --publish
```

For each `lessons/<slug>.json` the workflow:

1. Renders `infographics/template.html` with the lesson data into `infographics/<slug>/output.png` (2x resolution).
2. Builds the post text: title, subtitle, the first 4 trap → solution pairs, and hashtags.
3. Posts the text and image only when `--publish` is passed.
4. Writes the status, post text, and image path to `linkedin/results.json`.

## How to add a lesson

Create `lessons/<slug>.json` and re-run the workflow. Any number of pairs works; the template adjusts font size and spacing to fit.

## Reference: lesson JSON schema

| Field | Type | Required | Description |
| :--- | :--- | :-: | :--- |
| `title` | string | yes | Infographic headline and first line of the LinkedIn post |
| `subtitle` | string | no | Line under the headline; also used in the post |
| `source` | string | no | Path of the writeup the data came from |
| `pairs` | array | yes | One entry per mental trap and its solution |
| `pairs[].trap` | object | yes | `title`, `description`, optional `tag` (short pill label) |
| `pairs[].solution` | object | yes | `title`, `description`, optional `tag` |

## Reference: template

`infographics/template.html` takes its data from `window.__DATA__` (set by the workflow through Playwright), or from `?data=<path>` when served over HTTP. `fetch` is blocked on `file://`, so opening the template directly shows nothing.

## Lessons

| Lesson | JSON (workflow input) |
| :--- | :-: |
| [`conference-roi-playbook-pre-booking-meetings`](lessons/conference-roi-playbook-pre-booking-meetings.json) | ✅ |
| [`b2b-lead-generation-qualification-playbook`](lessons/b2b-lead-generation-qualification-playbook.json) | ✅ |
| [`marketing-agency-client-acquisition-playbook`](lessons/marketing-agency-client-acquisition-playbook.json) | ✅ |
| [`solo-founder-market-research-playbook`](lessons/solo-founder-market-research-playbook.json) | ✅ |
