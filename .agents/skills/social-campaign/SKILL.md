---
name: social-platform-orchestrator
description: "Orchestrate social campaigns across Twitter/X, Facebook, and LinkedIn, Reddit audience discovery, and hypothesis-driven metrics cycles via tools/loop."
---

# Social Platform Orchestrator

```text
Loop Init -> Subagent Drafts -> Approval -> Sequential Publish -> Register -> Checkpoints -> Cycle -> Review -> Approval
```

## Tool Inventory

| Tool Directory | Responsibility | Primary Command(s) | Operational Invariant |
|---|---|---|---|
| `tools/loop/` | Project campaign scaffolding, publication tracking, checkpoint scheduling (24h/7d), metrics normalization, creative comparison, and review workflows | `python -m tools.loop --project local/<SLUG> <CMD>` | Authoritative campaign engine; requires `--project local/<SLUG>`; see [`references/loop.md`](references/loop.md) for full stage spec. |
| `tools/common/` | Dedicated Chrome browser launch, CDP connectivity diagnostics, and connection cleanup | `uv run python -m tools.common [start-browser\|doctor]` | Does not authenticate or navigate platforms; manages shared CDP endpoint (`9222`). |
| `tools/twitter_agent/` | Terminal-operated X DOM automation for search, thread inspection, reply queuing, and approved single-image posting | `uv run python -m tools.twitter_agent <CMD>`<br/>`uv run python -m tools.twitter_agent.publish` | Publishing requires explicit `--approved` flag and exactly 1 image; strictly respects rate quotas. |
| `tools/facebook_agent/` | Direct personal profile DOM posting for text with optional single image | `uv run python -m tools.facebook_agent post --text <T> [--image <I>]` | Personal profile (`/me`) only; invocation triggers immediate submission without prompt. |
| `tools/linkedin_agent/` | Direct personal profile posting for text with 1 to 20 ordered images | `uv run python -m tools.linkedin_agent post --text <T> --image <I>...` | Personal profile only; requires at least 1 image (max 20); text-only posts are rejected. |
| `tools/reddit-research-mcp/` | Semantic vector search across 20,000+ communities for niche discovery | `uv run --directory tools/reddit-research-mcp python3 -c "..."` | Discover high-affinity communities without Reddit account credentials. |
| `tools/reddit_agent/` | Chronological discussion pagination and post extraction into local JSON | `python3 tools/reddit_agent/research.py --subreddit <S> --months <M>` | Zero-credential research CLI; extracts authentic audience phrases, pain points, and hooks. |

## Configuration and Browser Control

| Config Parameter | Env Variable / CLI Option | Default | Enforcement Rule |
|---|---|---|---|
| Profile Registry | `tools/common/local/profiles.json` | Run `tools.common profiles` | Inspect registry to map campaign to dedicated profile name, data dir, port, and page_id. |
| CDP Endpoint | `CDP_ENDPOINT` / `--cdp` | `http://127.0.0.1:<PORT>` | Derived from profile's configured port; platform tools must receive matching `--cdp`. |
| Chrome User Data | `CHROME_USER_DATA_DIR` / `--data-dir` | Profile `data_dir` in `profiles.json` | Use profile-specific directory (e.g. `/Users/thevinhnguyen/chrome-block-lc`). |
| Launch Command | `uv run python -m tools.common start-browser --backend cdp -p <PORT> -d <DIR>` | Exit 0 (`ok: true`) | Reuses responsive browser without restart; never kill responsive processes. |
| Health Diagnostic | `uv run python -m tools.common doctor --endpoint http://127.0.0.1:<PORT>` | Timeout 30000ms | Run after launch; retry transient errors max 3 times with 2-3s delay. |
| Concurrency Lock | Strict sequential execution | No parallel CDP actions | Live browser commands across all platforms must run sequentially to avoid state corruption. |
| Campaign Root | Mandatory directory | `local/<project-slug>/` | All social campaigns must reside in `local/`; never initialize or move campaigns into `projects/`. |
| Strict Tooling | Existing repository tools only | No ad-hoc scripts | Prohibits writing one-off Python scripts, ad-hoc automation, or raw DOM snippets. |

## Multi-Agent Topology

| Agent Role | Specialty | CLI Target | Responsibility Boundary |
|---|---|---|---|
| Orchestrator (Parent) | Campaign supervisor & brand coordinator | `tools.loop`, `tools.common` | Scaffolds campaigns, coordinates branding with visual tools, sequences browser posting, audits loop. |
| Twitter Subagent | X mechanics & short-form hooks | `tools/twitter_agent/` | Formats copy <= 280 chars, selects single image, respects quotas (6/hr, 20/day). |
| Facebook Subagent | Authentic narrative copy | `tools/facebook_agent/` | Formats narrative copy, validates single image boundary, personal profile target. |
| LinkedIn Subagent | Professional insight & framework carousels | `tools/linkedin_agent/` | Formats copy <= 3,000 chars, enforces mandatory 1–20 image requirement. |
| Campaign Loop Operator | Metric analysis & iteration review | `tools/loop/` | Audits due checkpoints, runs cycles, prepares review bundles, presents iteration proposals. |

## Platform Validation Matrix

| Constraint | Twitter / X (`tools/twitter_agent`) | Facebook (`tools/facebook_agent`) | LinkedIn (`tools/linkedin_agent`) |
|---|---|---|---|
| Target Destination | Configured handle (`--account`) | Personal profile only (`/me`) | Personal profile only |
| Text Requirement | Required; <= 280 chars (unless long-form) | Non-empty text required | Required; non-blank; max 3,000 characters |
| Image Requirement | Exactly 1 photo required for `publish.py` | Optional: 0 or 1 image (PNG, JPEG, GIF, WebP) | Mandatory: 1 to 20 images (PNG or JPEG only, max 10MB each) |
| Text-Only Capability | Supported via reply CLI; unsupported in `publish.py` | Supported | Unsupported (fails validation without image) |
| Multi-Image Capability | Unsupported (max 1 photo) | Unsupported (max 1 image) | Supported (1 to 20 ordered images) |
| Approval Gate | Requires explicit `--approved` flag | Immediate publish on `post` invocation | Immediate publish on `post` invocation |
| Rate Pacing | 6/hr, 20/day, 120s intervals, 3/30m burst | Manual pacing recommended | Manual pacing recommended |

## Standard Operating Workflows

| Workflow | Phase / Step | CLI Invocation | Validation & Handoff |
|---|---|---|---|
| 0. Campaign Scaffolding | Pre-flight Dry-Run | `python -m tools.loop --project local/<SLUG> init --page-id <PAGE_ID> --dry-run` | Confirms planned directory creation and Schema v2 state. Full lifecycle: [`references/loop.md`](references/loop.md). |
| 0. Campaign Scaffolding | Execution | `python -m tools.loop --project local/<SLUG> init --page-id <PAGE_ID>` | Creates `loop/`, `product-marketing.json`, `posts/hypothesis.json`, and metrics dirs. |
| 0. Campaign Scaffolding | Discovery Interview Gate | Interview user across: 1. Goal, 2. Catalog & Unique, 3. Personas, 4. Sales/Pricing | **Strict Rule:** Never invent or guess catalog or customer facts; populate `product-marketing.json` only from user answers. |
| 1. Cross-Platform Broadcast | Pre-Flight Health | `uv run python -m tools.common start-browser --backend cdp -p <PORT> -d <DIR>`<br/>`uv run python -m tools.common doctor --endpoint http://127.0.0.1:<PORT>`<br/>`uv run python -m tools.facebook_agent --cdp http://127.0.0.1:<PORT> doctor` | Resolve profile in `profiles.json`; verify port and session readiness sequentially before posting. |
| 1. Cross-Platform Broadcast | Parallel Drafting | Dispatch subagents with source content and platform constraints | Collect adapted texts and image paths; do not invoke browser. |
| 1. Cross-Platform Broadcast | User Approval Gate | Present unified review markdown with text, media paths, and platforms | Block execution until user gives explicit confirmation. |
| 1. Cross-Platform Broadcast | Step A: Facebook Post | `uv run python -m tools.facebook_agent post --text "<TEXT>" [--image "<PATH>"]` | Verify exit code 0 and JSON `{"ok": true}` before starting LinkedIn. |
| 1. Cross-Platform Broadcast | Step B: LinkedIn Post | `uv run python -m tools.linkedin_agent post --text "<TEXT>" --image "<PATH>"` | Verify exit code 0 and JSON `{"ok": true}` before starting Twitter. |
| 1. Cross-Platform Broadcast | Step C: Twitter Post | `uv run python -m tools.twitter_agent.publish --account <ACC> --text "<TEXT>" --image "<PATH>" --approved` | Verify exit code 0 and JSON `{"ok": true}`. |
| 1. Cross-Platform Broadcast | Step D: Register Post | `python -m tools.loop --project local/<SLUG> register --post <ID> --url "<URL>" --published-at "<ISO_TS>"` | Adds entry to `loop/publications.json` and arms 24h/7d checkpoints. |
| 2. Twitter Engagement | Search & Inspect | `uv run python -m tools.twitter_agent search "<QUERY>" --limit 10`<br/>`uv run python -m tools.twitter_agent thread <TWEET_ID>` | Identify high-signal conversation targets within time window. |
| 2. Twitter Engagement | Draft & Submit Reply | `uv run python -m tools.twitter_agent reply target <TWEET_ID>`<br/>`uv run python -m tools.twitter_agent reply draft <ID> --text "<TEXT>"`<br/>`uv run python -m tools.twitter_agent reply submit <ID>` | Draft requires human approval before invoking `reply submit`. |
| 3. Reddit Research | Niche Discovery | `uv run --directory tools/reddit-research-mcp python3 -c "import asyncio; from src.tools.discover import discover_subreddits; print(asyncio.run(discover_subreddits(query='<Q>', limit=5)))"` | Rank candidate communities by subscriber count and match tier. |
| 3. Reddit Research | Discussion Extraction | `python3 tools/reddit_agent/research.py --subreddit <NAME_OR_URL> --months 6 --output <DIR>` | Export JSON discussions to extract authentic vocabulary and hooks. |
| 4. Loop Measurement | Status & Due Audit | `python -m tools.loop --project local/<SLUG> status`<br/>`python -m tools.loop --project local/<SLUG> due` | Inspect pipeline state and list mature 24h/7d windows. Stage reference: [`references/loop.md`](references/loop.md). |
| 4. Loop Measurement | Metric Collection | `python -m tools.loop --project local/<SLUG> collect-insights`<br/>`python -m tools.loop --project local/<SLUG> cycle` | Browser captures Insights dashboards; runs normalize and eligibility stages. |
| 4. Loop Measurement | Creative Comparison | `python -m tools.loop --project local/<SLUG> compare --run <RUN_ID>` | Generates creative matrix, outlier flags, and exclusion diagnostics. |
| 4. Loop Measurement | Strategic Review | `python -m tools.loop --project local/<SLUG> prepare-review --run <RUN_ID>`<br/>`python -m tools.loop --project local/<SLUG> review --run <RUN_ID> --file <REVIEW.json>` | Packages observations and test suggestions into structured review log. |
| 4. Loop Measurement | Human Approval Gate | `python -m tools.loop --project local/<SLUG> approve-review --run <RUN_ID> --proposals <IDS>` | Records approval; unlocks formulation of next post hypothesis in `posts/`. |

## Error Recovery Protocol

| Code | Status | Meaning | Recovery Action |
|---|---|---|---|
| 0 | `Success` | Post confirmed or diagnostic passed | Continue to next scheduled pipeline step. |
| 1 | `Internal Error` | Unhandled exception or runtime crash | Check stderr logs and verify browser state before retry. |
| 2 | `Invalid Input` | Parameter parsing, length limit, or bad image format | Fix CLI parameters; do not touch browser or repeat same arguments. |
| 3 | `Browser / Auth Error` | CDP connection lost, unauthenticated, or challenge | Ask user to resolve manual login/challenge; verify endpoint and restart browser. |
| 4 | `Uncertain Submission` | Submit clicked but confirmation not verified | **NEVER RETRY AUTOMATICALLY.** Preserve browser tab and request manual inspection. |

## Subagent Dispatching Rules

| Dispatch Mode | Allowed Operations | Forbidden Operations | Expected Output |
|---|---|---|---|
| Drafting Dispatch | Parallel execution; content adaptation; format checks | No Chrome launching; no CDP connections; no posting | Exact text, ordered media paths, character counts, validation status. |
| Publishing Dispatch | Strict sequential execution; one platform worker at a time | No concurrent browser workers; no automatic retry on code 4 | Command exit code, JSON response payload, canonical published URL. |
| Measurement Dispatch | Checkpoint auditing (`due`), cycle execution, review drafting | No automatic publication; no unapproved hypothesis promotion | Stage run ID, comparison summary, structured review proposals. |

## Brand and Visual Asset Coordination

| Orchestration Stage | Downstream Tool | Responsibility & Operating Protocol | Invariant Enforcement |
|---|---|---|---|
| 1. Token Ingestion | `branding` skill / manifest | Read `brand/brand.yaml` and `brand/guidelines.md` for exact 60-30-10 palette, typography, and SVG marks. | Prohibits guessing or assuming default dark/crypto aesthetics. |
| 2. Visual Injection | `infographic` skill | Inject extracted CSS tokens (`--bg-page`, `--text-hero`, `--accent`) into dimensioned layout wireframe. | Prohibits selecting generic library themes when project brand exists. |
| 3. Pre-Publish Audit | Orchestrator validation | Inspect rendered PNG against master palette before presenting to user or registering into loop. | Rejects off-brand colors and typography before user approval gate. |
