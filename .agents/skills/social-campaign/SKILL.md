---
name: Social Campaign
description: "Social media, social projects, social posts, content creation, drafting, captions, publishing, posting, campaigns, scheduling, distribution, engagement, audience research, performance metrics, viral content discovery, hashtag and keyword vocabulary validation, Reels recommendations, creator style analysis. Use for project or brand social content on Facebook, LinkedIn, Twitter/X, TikTok mobile automation via taktik-bot, and Reddit research; single-platform and cross-platform workflows."
---

# Social Campaign

```text
Resolve project → Load policy → Research → Draft → Visual → Preflight → Human approval → Publish → Register → Measure
```

## Mandatory Project Routing

| Step | Required behavior |
|---|---|
| Resolve | Map the requested project/brand to its existing `local/<slug>/` directory. Ask only if missing or ambiguous; never initialize an existing project again. |
| Load | Explicitly read project `AGENTS.md`, `loop/config.json`, `loop/AGENTS.md`, product facts, selected hypothesis, brand manifest and guidelines for drafting/publication. For viral/hashtag research, require only `product-marketing.json` (`marketing_goal`, `product.catalog`), plus optional past `sources/viral/` analyses for historical feedback. No brand, customer-profile, hypothesis, loop or scaffold dependency. |
| Select | Treat `allowed_channels` as authoritative for drafting/publication. Research platforms come from the explicit request and do not require publishing-channel setup. Never infer channels from old drafts, a Page ID alone, or this skill's tool inventory. |
| Research | Read [content gates](references/content-gates.md). Meet configured evidence requirements and obtain research review before drafting. Missing evidence blocks progression; never invent citations or cases. Audience, viral, creator-style or hashtag/keyword vocabulary research follows [viral research](references/viral-analyzer.md) and [hashtag validation](references/hashtag-validation.md), and stays bound to this campaign. |
| Viral run ownership | Assign one dedicated sub-agent to each `sources/viral/run-*/` directory. One run queries one platform across the full relevant hashtag/keyword set within its agreed limits; generation, verification, collection and reporting stay with that same worker. Never spawn one worker/run per hashtag or workflow step. The parent coordinates context, budget and acceptance. Use the same [per-run worker contract](references/viral-analyzer.md#per-run-sub-agent-contract) for successful, failed and zero-result platform runs. |
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
| Facebook Reels | `uv run python -m tools.facebook_agent --cdp <ENDPOINT> reels --page-id <PAGE_ID> --limit <1-50> --output <NEW_JSON>` | Read-only visible personalized recommendations; output path must not exist; Page ID from the resolved campaign. No query, region or date filters. |
| Hashtag prompt | `python3 -m tools.loop.viral_analyzer.hashtag_generate build-prompt --project local/<SLUG> --run <ID> --platform <P> --market-language <L> --application "<NEED>"` | Campaign-scoped, no network. Only product goal/catalog are required context; history is optional. Import only a saved JSON response with `import-response`; never hand-edit candidates. [Hashtag validation](references/hashtag-validation.md). |
| Hashtag verification | `python3 -m tools.loop.viral_analyzer.hashtag_verify <plan\|collect\|report\|build-review-prompt\|record-review\|history> --project local/<SLUG> --run <ID>` | `collect` previews without `--execute`; spend requires approval, `--execute --ceiling <USD>` and inspected schema/price. Executed collection writes a root report even for empty/error results; `report` regenerates it from saved receipts without network. `history` is read-only. [Hashtag validation](references/hashtag-validation.md). |
| Hashtag expansion | `python3 -m tools.loop.viral_analyzer.viral_scrape --project local/<SLUG> --run <ID> --schema <JSON> [--execute --ceiling <USD>]` | Refuses targets whose latest history decision is not `promising`/`limited_expand`. Preview by default; new runs write `artifacts/expansion/viral-candidates.json`. No untargeted trending. |
| TikTok Mobile | `cd tools/taktik-bot && uv run --with-requirements requirements.txt python -m taktik.cli.main <tiktok\|workflows> [OPTIONS]` | Physical Android device via ADB; Standard TikTok (`com.ss.android.ugc.trill` / `com.zhiliaoapp.musically`). No TikTok Lite. MIUI/HyperOS devices require USB debugging (Security settings). [Platform matrix](references/platform-matrix.md). |
| Video download | `uv run yt-dlp -o "<OUT_PATH>" -f "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best" "<URL>"` | Downloads video assets from supported platforms (Facebook Reels, TikTok, YouTube Shorts, X) for campaign staging or editing. |

| Operating constraint | Rule |
|---|---|
| Project location | Campaigns live under `local/`, never `projects/`. |
| Tooling | During campaign execution use public repository CLIs, never inline Python/subprocess wrappers, private-helper probes or raw CDP/Playwright/JS. Repository implementation/tests are separate from campaign execution. |
| Capability gaps | Inspect the relevant CLI `--help` and reference first. If capability is absent, stop and report it; extend repository tooling with tests only when requested. A missing flag, URL or failed gate never authorizes custom automation. |
| Hashtag evidence | Use only public `hashtag_generate`/`hashtag_verify` CLIs. Labels are agent judgments over inspected samples; report usage observed in the sample, never a platform-wide definition, popularity or approval. |
| Hashtag spend | `collect` and `viral_scrape` preview by default. Paid execution requires `--execute --ceiling <USD>`, an inspected schema/price file and explicit human spend approval. Never assume account balance. |
| Hashtag history | `sources/viral/hashtag-performance.json` is campaign-local and append-only through `record-review`. Never copy evaluations across campaigns or fabricate counts from old prose; identical retries no-op. |
| Viral result handoff | Every returned video must have its observed direct video permalink in both `report.md` and the final chat response, with platform/creator, observed metrics/time, relevance and access/evidence limitations. IDs, concepts, hashtags, search/profile links and local artifact paths are not substitutes. No permalink means no verified-video result; report a partial/blocked outcome rather than invent links or pad the requested count. Follow the [verifiable handoff contract](references/viral-analyzer.md#verifiable-video-handoff). |
| Viral run layout and closure | New run roots contain only `brief.md`, `report.md` and `artifacts/`; all JSON, prompts, schemas, receipts, raw data, reviews and creator analyses go under `artifacts/`. Every requested platform gets a report, including zero results, errors, blocked/stopped work and interrupted runs. Finalize the automatic collection report with evidence, costs and a scoped marketing recommendation; do not omit Instagram because TikTok succeeded or declare a platform dead from empty provider responses. Preserve legacy paths unless an explicit migration is requested. |
| Saved copy | Prefer `post --text-file <COPY_FILE>` over shell quoting. Mutually exclusive with `--text`; UTF-8, LF-normalized, terminal newlines excluded, internal whitespace preserved. |
| Missing permalink | A confirmed post may still have `permalink: null`. Never repost or scrape with custom code. Use `content-library --page-id <PAGE_ID> --output <NEW_JSON>` on the same CDP endpoint, then verify exact content, author, time and original placement. Ambiguity requires manual inspection; never select solely by recency or fabricate a URL. |
| Profile isolation | Resolve `tools/common/local/profiles.json`; pass matching CDP endpoint to platform commands. |
| Facebook media | Text with optional single image or video, never both. Policy-validated visual workflow currently accepts SVG source plus PNG; do not bypass it with video. |
| Facebook identity | Supply expected Page ID; browser must already be switched into that Page. Run Facebook doctor with the same Page ID. |
| Sequential publishing | No concurrent CDP actions. A requested multi-platform campaign still publishes one approved destination at a time. |
| Delegation | Each `sources/viral/run-*/` directory requires one dedicated sub-agent under the [worker contract](references/viral-analyzer.md#per-run-sub-agent-contract). The worker owns one platform's full relevant hashtag/keyword batch and all stages of that run—not one hashtag or step. Never combine multiple run directories in one worker or silently execute them in the parent. Other workflows run directly unless delegation is explicitly requested. Every worker inherits campaign policy; browser work remains sequential, and delegation never expands spend or publication authority. |
| Brand | For content/visual production, read `brand/brand.yaml`, guidelines and configured tokens. Not a viral-research prerequisite. Reject generic dark/neon themes when project identity differs. Human inspection covers typography and rendered legibility. |
| TikTok mobile automation | Driven via `tools/taktik-bot` on real Android devices. Requires authorized ADB device (`adb devices`) with Standard TikTok installed (`com.ss.android.ugc.trill` or `com.zhiliaoapp.musically`). Do not attempt on TikTok Lite (`com.zhiliaoapp.musically.go`) due to missing editor/sound nodes. Ensure USB debugging (Security settings) is enabled on Xiaomi/Redmi devices. Follow [platform matrix](references/platform-matrix.md). |

## Workflow Selection

| Request | Procedure |
|---|---|
| Existing-project post | Resolve → load → research gate → story/copy → visual → preflight → review. Never create unsolicited channel variants. |
| New campaign | Preview `init --page-id <ID> --dry-run`, then initialize only with authorization. Interview for missing goal, catalog, differentiation, personas and sales facts; never invent them. Set explicit channel and content policy. |
| Viral discovery (Reels, trends) | Resolve the existing campaign and requested research platforms first; never add platforms. Write the brief from the [viral templates](assets/viral-research/). For topic/hashtag discovery, start with offline `hashtag_generate build-prompt` → agent JSON → `import-response`, then the verification workflow below; absent history means generate new `generated_unverified` candidates, not search for a replacement database. No preliminary web-search loops. Missing context blocks collection, not offline proposals; report gaps after saving candidates. Follow [viral research](references/viral-analyzer.md) and [Reels selection](references/reels-selection.md) for review/shortlisting. |
| Hashtag validation | Resolve the campaign and read only `product-marketing.json` for goal/catalog. `hashtag_generate build-prompt` → agent JSON → `import-response` → `hashtag_verify plan` with a saved schema/price file → `collect` (preview; `--execute --ceiling` only after explicit spend approval) → `build-review-prompt` → agent labels → `record-review`. Follow [hashtag validation](references/hashtag-validation.md). Missing/invalid product goal/catalog blocks collection; missing brand/loop/customer/hypothesis files do not. |
| Hashtag expansion | Only after `record-review` marks targets `promising` or `limited_expand`: run `viral_scrape` in preview, then `--execute --ceiling` with approval. It refuses untested targets and writes `sources/viral/<RUN>/artifacts/expansion/viral-candidates.json` for new runs; feed those candidates into viral relevance review and finalize the root report even if expansion fails. |
| Creator style analysis | Same campaign resolution as viral research; require a campaign-relevant reason. Save `artifacts/creator-style-<slug>.md` and summarize/link it in root `report.md`, even for incomplete research. Creator records cannot be reused as viral references. |
| TikTok mobile automation / post | Verify ADB device (`taktik.cli.main device list`) → verify Standard TikTok (`trill`/`musically`) → execute approved workflow (`launch`, `automation for_you`, `upload_post`). Screen must remain unlocked and active during execution. |
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
