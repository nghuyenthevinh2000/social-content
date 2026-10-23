---
name: Social Campaign
description: "Social media, social projects, social posts, content creation, drafting, captions, publishing, posting, campaigns, scheduling, distribution, engagement, audience research, performance metrics. Use for project or brand social content on Facebook, LinkedIn, Twitter/X, and Reddit research; single-platform and cross-platform workflows."
---

# Social Campaign

```text
Resolve project → Load policy → Research → Draft → Visual → Preflight → Human approval → Publish → Register → Measure
```

## Mandatory Project Routing

| Step | Required behavior |
|---|---|
| Resolve | Map the requested project/brand to its existing `local/<slug>/` directory. Ask only if missing or ambiguous; never initialize an existing project again. |
| Load | Explicitly read project `AGENTS.md`, `loop/config.json`, `loop/AGENTS.md`, product facts, selected hypothesis, brand manifest and guidelines. Do not rely on automatic nested instruction discovery. |
| Select | Treat `allowed_channels` as authoritative. Never infer channels from old drafts, a Page ID alone, or this skill's tool inventory. Missing channel policy requires clarification before drafting. |
| Research | Read [content gates](references/content-gates.md). Meet configured evidence requirements and obtain research review before drafting. Missing evidence blocks progression; never invent citations or cases. |
| Compose | Load `story-engine` before writing copy. Apply project voice/style references; draft only requested, configured channels. Existing facts take precedence over scaffold placeholders. |
| Visual | Load `infographic` or the appropriate visual skill only when needed. Read brand tokens first; inspect the actual rendered image. Do not substitute generic themes. |
| Validate | Run `python -m tools.loop --project <PROJECT> preflight --post <ID> --stage <STAGE>`. Stages: `research`, `draft`, `visual`, `publish`. Fix failures before continuing. |
| Approve | Present exact copy, media, destinations and limitations. Record a named human decision only after explicit confirmation. Successful preflight or a draft request does not authorize publication. |
| Publish | Invoke the public platform CLI directly; use `--text-file` for saved Facebook copy. Verify exact approved assets, project scope and active identity. Browser actions are sequential. Never retry uncertain submission automatically. |
| Measure | Register the confirmed URL, then follow [loop lifecycle](references/loop.md). Review-proposal approval is separate from content/publication approval. |

## Tools and Boundaries

| Tool | Invocation | Invariant |
|---|---|---|
| Campaign loop | `python -m tools.loop --project local/<SLUG> <COMMAND>` | Project-owned state; [lifecycle reference](references/loop.md). No publishing. |
| Browser profiles | `uv run python -m tools.common profiles` | Read profile registry to resolve Page, data directory and port. |
| Browser launch | `uv run python -m tools.common start-browser --backend cdp -p <PORT> -d <DIR>` | Reuse responsive browsers; never kill them. |
| Browser health | `uv run python -m tools.common doctor --endpoint <ENDPOINT>` | Retry transient errors at most three times with 2–3s delay. |
| Facebook | `uv run python -m tools.facebook_agent --cdp <ENDPOINT> post --project <PROJECT> --post <ID> --page-id <PAGE_ID> --text-file <COPY_FILE> [--image <PNG>]` | UTF-8 file input avoids quoting/truncation workarounds. Personal profile or explicitly identified active Page; project scope requires current approval. |
| LinkedIn | `uv run python -m tools.linkedin_agent post --text <TEXT> --image <IMAGE>` | Personal profile; 1–20 PNG/JPEG images, max 10MB each; nonblank text up to 3,000 characters. Only configured/requested channels. |
| Twitter/X | `uv run python -m tools.twitter_agent.publish --account <ACCOUNT> --text <TEXT> --image <IMAGE> --approved` | Exactly one image; 280-character standard posts; 6/hr, 20/day, 120s intervals, 3/30m burst. Only configured/requested channels. |
| Twitter replies | `uv run python -m tools.twitter_agent <search\|thread\|reply>` | Inspect before drafting; explicit human approval before `reply submit`. |
| Reddit discovery | `tools/reddit-research-mcp/` | Semantic community discovery; no account credentials. |
| Reddit extraction | `python3 tools/reddit_agent/research.py --subreddit <NAME> --months 6 --output <DIR>` | Research audience language and pain points; no Reddit publishing. |

| Operating constraint | Rule |
|---|---|
| Project location | Campaigns live under `local/`, never `projects/`. |
| Tooling | During campaign execution use public repository CLIs, never inline Python/subprocess wrappers, private-helper probes or raw CDP/Playwright/JS. Repository implementation/tests are separate from campaign execution. |
| Capability gaps | Inspect the relevant CLI `--help` and reference first. If capability is absent, stop and report it; extend repository tooling with tests only when requested. A missing flag, URL or failed gate never authorizes custom automation. |
| Saved copy | Prefer `post --text-file <COPY_FILE>` over shell quoting. Mutually exclusive with `--text`; UTF-8, LF-normalized, terminal newlines excluded, internal whitespace preserved. |
| Missing permalink | A confirmed post may still have `permalink: null`. Never repost or scrape with custom code. Use `content-library --page-id <PAGE_ID> --output <NEW_JSON>` on the same CDP endpoint, then verify exact content, author, time and original placement. Ambiguity requires manual inspection; never select solely by recency or fabricate a URL. |
| Profile isolation | Resolve `tools/common/local/profiles.json`; pass matching CDP endpoint to platform commands. |
| Facebook media | Text with optional single image or video, never both. Policy-validated visual workflow currently accepts SVG source plus PNG; do not bypass it with video. |
| Facebook identity | Supply expected Page ID; browser must already be switched into that Page. Run Facebook doctor with the same Page ID. |
| Sequential publishing | No concurrent CDP actions. A requested multi-platform campaign still publishes one approved destination at a time. |
| Delegation | Run directly by default. Delegate only when explicitly requested; every worker inherits project policy. Draft workers never access the browser; browser workers remain sequential. |
| Brand | Read `brand/brand.yaml`, guidelines and configured tokens. Reject generic dark/neon themes when project identity differs. Human inspection covers typography and rendered legibility. |

## Workflow Selection

| Request | Procedure |
|---|---|
| Existing-project post | Resolve → load → research gate → story/copy → visual → preflight → review. Never create unsolicited channel variants. |
| New campaign | Preview `init --page-id <ID> --dry-run`, then initialize only with authorization. Interview for missing goal, catalog, differentiation, personas and sales facts; never invent them. Set explicit channel and content policy. |
| Publish approved content | Follow [content gates](references/content-gates.md), verify browser/profile, then execute only approved destinations. Commands submit without another prompt. |
| Register | Use an observed permalink from the fresh confirmation, or verify a read-only Content Library/manual result. Then `python -m tools.loop --project <PROJECT> register --post <ID> --url <URL> --published-at <ISO_TS>`. Never guess URL or publish time. |
| Measure | `status`, `due`, `collect-insights`, `cycle`, `compare --run <ID>`; preserve evidence and actual observation ages. |
| Iterate | `prepare-review`, `review`, then explicit `approve-review`; this approves hypotheses/proposals, not publication. |

## Error Recovery

| Exit | Meaning | Response |
|---|---|---|
| 0 | Confirmed success | Verify returned payload before proceeding. |
| 1 | Internal error | Inspect state and logs before retry; determine whether any external action occurred. |
| 2 | Invalid content, arguments or policy gate | Repair input/evidence/approval before browser activity. |
| 3 | Browser, authentication or identity problem | Ask user to resolve login/challenge/Page selection; do not bypass. |
| 4 | Uncertain submission | Never retry automatically. Preserve tab and request manual inspection. |
