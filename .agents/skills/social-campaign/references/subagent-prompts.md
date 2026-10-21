# Subagent Prompts and Dispatch Recipes

```text
Orchestrator -> Dispatch Drafting Subagents (Parallel) -> Consolidate -> Human Approval -> Sequential Execution -> Loop Register
```

## Subagent Role Specifications

| Role Name | Platform Target | Core Constraints | Required Subagent System Directives |
|---|---|---|---|
| Twitter Platform Specialist | `tools/twitter_agent/` | Max 280 chars; 1 image for `publish.py`; `--approved` flag required; 6/hr quota | Craft punchy, concise hooks; validate char limits; do not launch browser directly during drafting. |
| Facebook Platform Specialist | `tools/facebook_agent/` | Personal profile (`/me`) only; text required; max 1 optional image | Adapt into authentic first-person storytelling; enforce single image boundary. |
| LinkedIn Platform Specialist | `tools/linkedin_agent/` | Personal profile only; max 3,000 chars; **1 to 20 images strictly mandatory** | Structure frameworks and bulleted insights; reject text-only submissions. |
| Campaign Loop Operator | `tools/loop/` | Scoped to `local/<SLUG>`; audit 24h/7d checks; prepare review bundles | Analyze performance metrics; stage hypothesis iteration proposals; require human approval. |

## Subagent Dispatch Recipes

| Phase | Concurrency | Dispatch Template / Command Structure | Validation Check |
|---|---|---|---|
| Recipe 1: Parallel Drafting | Parallel across subagents | Prompt: `Adapt {SOURCE} for {PLATFORM} adhering to platform constraints. Return exact text and media paths. Do not run browser commands.` | Verify text non-empty, image counts, and platform limits before aggregating. |
| Recipe 2: Execution Dispatch | Strict sequential | Step 1 (FB): `uv run python -m tools.facebook_agent post --text "{TEXT}" --image "{IMG}"`<br/>Step 2 (LI): `uv run python -m tools.linkedin_agent post --text "{TEXT}" --image "{IMG}"`<br/>Step 3 (TW): `uv run python -m tools.twitter_agent.publish --account {ACC} --text "{TEXT}" --image "{IMG}" --approved` | Require exit code 0 and JSON `{"ok": true}` before triggering next platform. |
| Recipe 3: Loop Metrics Cycle | Sequential | Step 1: `python -m tools.loop --project {PATH} due`<br/>Step 2: `python -m tools.loop --project {PATH} cycle`<br/>Step 3: `python -m tools.loop --project {PATH} prepare-review --run {ID}`<br/>Step 4: `python -m tools.loop --project {PATH} approve-review --run {ID} --proposals {IDS}` | Present findings to user; do not auto-publish unapproved hypotheses. |

## Error Handoff Protocols

| Incident | Exit Code | Diagnostic Signature | Mandatory Remediation Procedure |
|---|---|---|---|
| CDP Offline / Lost | Code 3 | `browser_connection_failed` or `not_authenticated` | Instruct user to run `uv run python -m tools.common start-browser` and complete login. |
| Uncertain Post | Code 4 | `submission_uncertain` | **ABORT IMMEDIATELY.** Do not retry. Ask user to inspect open browser tab and live profile. |
| Input Parameter Fault | Code 2 | `invalid_arguments` or length excess | Correct text length or media format locally before rescheduling. |
