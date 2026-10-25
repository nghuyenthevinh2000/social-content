# Platform Matrix and CLI Reference

```text
Platform Config -> Doctor Check -> Approved Payload -> Platform Invocation -> Loop Registration
```

## Platform Technical Specifications

| Parameter / Constraint | Facebook (`tools/facebook_agent`) | LinkedIn (`tools/linkedin_agent`) | Twitter / X (`tools/twitter_agent`) | TikTok (`tools/taktik-bot`) | Loop Engine (`tools/loop`) |
|---|---|---|---|---|---|
| Account Target | Personal Profile only (`/me`) | Personal Profile only | Specific handle (`--account`) | Logged-in profile on physical Android phone | Project directory (`--project`) |
| Page / Group Scope | Personal feed only; no Groups/Pages | Personal feed only; no Company pages | User account timeline | Active mobile app account feed | Scoped to configured `page_id` |
| Text Requirement | Non-empty text required | Non-blank text required | Non-empty text required | Non-empty caption + hashtags | N/A (manages artifacts & hypotheses) |
| Text Length Limit | Facebook post limit | Max 3,000 characters | 280 characters standard | Max 2,200 characters | N/A |
| Media Requirement | Optional (0 or 1 image) | Mandatory (1 to 20 images) | Mandatory for `publish.py` (1 image) | Mandatory for `upload_post` (video file) | Stores assets in `brand-assets/` |
| Media MIME Types | PNG, JPEG, GIF, WebP | PNG, JPEG only | JPEG, PNG, GIF, WebP | MP4, MOV | Any format preserved on disk |
| Media Size Limits | Enforced by Facebook upload UI | Max 10 MiB per image file | Standard X image constraints | Standard TikTok mobile upload limits | File system limits |
| Text-Only Support | Supported | Unsupported (fails without image) | Supported via reply; unsupported in `publish.py` | Supported via `text_post` workflow | Supported in creative copy |
| Multi-Image Support | Unsupported (max 1 image) | Supported (1 to 20 ordered images) | Unsupported in `publish.py` | Supported via image slide mode | Supported in catalog |
| Approval Guardrail | Immediate publish on `post` | Immediate publish on `post` | Explicit `--approved` required | Explicit approval before `upload_post` commit | Explicit `approve-review` command |
| Submission Pacing | Manual pacing recommended | Manual pacing recommended | 6/hr, 20/24hr, 120s interval, 3/30m burst | Humanized pauses via `break_rhythm.py` | Automated 24h and 7d checkpoints |

## CLI Invocation Reference

| Tool Domain | Operation | Exact CLI Syntax | Expected Result / Note |
|---|---|---|---|
| Shared Browser | Profile Discovery | `uv run python -m tools.common profiles` | Inspects `tools/common/local/profiles.json` for target profile, port, and page_id. |
| Shared Browser | Start Dedicated Chrome | `uv run python -m tools.common start-browser --backend cdp -p <PORT> -d <DIR>` | Launches CDP on profile-specific port with mapped user data dir. |
| Shared Browser | Connection Doctor | `uv run python -m tools.common doctor --endpoint http://127.0.0.1:<PORT>` | Verifies active CDP socket on target profile port without touching tabs. |
| Facebook | Auth & DOM Doctor | `uv run python -m tools.facebook_agent doctor` | Confirms personal profile login state. |
| Facebook | Post Text Only | `uv run python -m tools.facebook_agent post --text "<TEXT>"` | Immediate DOM publication. |
| Facebook | Post Text + Image | `uv run python -m tools.facebook_agent post --text "<TEXT>" --image "<PATH>"` | Attaches single local image. |
| LinkedIn | Auth & DOM Doctor | `uv run python -m tools.linkedin_agent doctor` | Confirms personal profile session. |
| LinkedIn | Post Single Image | `uv run python -m tools.linkedin_agent post --text "<TEXT>" --image "<PATH>"` | Image is strictly mandatory. |
| LinkedIn | Post Carousel | `uv run python -m tools.linkedin_agent post --text "<TEXT>" --image "<P1>" --image "<P2>"` | Preserves sequential order (1 to 20 images). |
| Twitter / X | Auth Doctor | `uv run python -m tools.twitter_agent doctor` | Checks account credentials and session validity. |
| Twitter / X | Publish Image Tweet | `uv run python -m tools.twitter_agent.publish --account <ACC> --text "<TEXT>" --image "<PATH>" --approved` | Requires `--approved` flag; exactly 1 image. |
| Twitter / X | Search Discussions | `uv run python -m tools.twitter_agent search "<QUERY>" --limit 10 --window-minutes 60` | Locates candidate tweets for engagement. |
| Twitter / X | Reply Workflow | `uv run python -m tools.twitter_agent reply target <TWEET_ID>`<br/>`uv run python -m tools.twitter_agent reply draft <ID> --text "<T>"`<br/>`uv run python -m tools.twitter_agent reply submit <ID>` | Targets tweet, stages draft, and submits after review. |
| Reddit | Community Search | `uv run --directory tools/reddit-research-mcp python3 -c "import asyncio; from src.tools.discover import discover_subreddits; print(asyncio.run(discover_subreddits(query='<Q>', limit=5)))"` | Semantic vector search across 20k subreddits. |
| Reddit | Discussion Scraping | `python3 tools/reddit_agent/research.py --subreddit <SUB> --months 6 --output <DIR>` | Paginates posts without credentials into JSON. |
| TikTok Mobile | Device List | `cd tools/taktik-bot && uv run --with-requirements requirements.txt python -m taktik.cli.main device list` | Lists connected, authorized ADB Android devices. |
| TikTok Mobile | Launch App | `cd tools/taktik-bot && uv run --with-requirements requirements.txt python -m taktik.cli.main tiktok launch [-d <DEVICE_ID>]` | Launches Standard TikTok (`trill` / `musically`) on connected phone. |
| TikTok Mobile | Feed Warmup | `cd tools/taktik-bot && uv run --with-requirements requirements.txt python -m taktik.cli.main workflows run tiktok automation for_you [-d <DEVICE_ID>]` | Simulates human FYP browsing, video views, and randomized interactions. |
| TikTok Mobile | Hashtag Targeting | `cd tools/taktik-bot && uv run --with-requirements requirements.txt python -m taktik.cli.main workflows run tiktok automation hashtag [-d <DEVICE_ID>]` | Discovers and engages with videos matching target hashtag queries. |
| TikTok Mobile | Video Upload Post | `cd tools/taktik-bot && uv run --with-requirements requirements.txt python -m taktik.cli.main workflows run tiktok standalone upload_post [-d <DEVICE_ID>]` | Pushes video to phone, strips sound, types caption/hashtags, and publishes after approval. |
| Loop | Project Init | `python -m tools.loop --project local/<DIR> init --page-id <PAGE_ID>` | Scaffolds loop configs, catalog, and hypothesis files in `local/`. |

## TikTok Mobile Device Requirements & Safeguards

| Component | Prerequisite / Behavior | Operational Safeguard |
|---|---|---|
| **USB Configuration** | Default USB mode: **File Transfer / Android Auto** | Prevents Xiaomi HyperOS / MIUI from resetting the USB bus during automation. |
| **Wireless Fallback** | `adb tcpip 5555 && adb connect <PHONE_IP>:5555` | Eliminates USB cable micro-disconnects over local Wi-Fi. |
| **Media Permissions** | `READ_MEDIA_VIDEO`, `READ_MEDIA_IMAGES`, `CAMERA` | Pre-granted via `pm grant` to bypass system media permission dialogs. |
| **Gallery Filtering** | Automatic switch to **Videos** tab in media picker | Prevents accidental selection of temporary device screenshots or static images. |
| **UI Mode Support** | Handles v47.4.3+ direct **POST** mode | Automatically skips legacy camera upload button when gallery opens directly. |
| **Public Confirmation** | Handles `"Post Now"` / `"Post video publicly"` modal | Auto-confirms TikTok visibility dialog upon publication commit. |
| Loop | Publication Registration | `python -m tools.loop --project local/<DIR> register --post <ID> --url "<URL>" --published-at "<ISO_TS>"` | Records canonical post and freezes 24h/7d checks. |
| Loop | Checkpoint Audit | `python -m tools.loop --project local/<DIR> due` | Lists mature measurement windows. |
| Loop | Metric Ingestion | `python -m tools.loop --project local/<DIR> collect-insights`<br/>`python -m tools.loop --project local/<DIR> cycle` | Ingests receipts, standardizes metrics, runs stages. |
| Loop | Review & Approval | `python -m tools.loop --project local/<DIR> prepare-review --run <ID>`<br/>`python -m tools.loop --project local/<DIR> review --run <ID> --file <F>`<br/>`python -m tools.loop --project local/<DIR> approve-review --run <ID> --proposals <P>` | Stages proposals and records human decision. |

## Exit Codes and Status Handling

| Code | Status Classification | Meaning | Protocol & Action Required |
|---|---|---|---|
| 0 | `Success` | Post confirmed or check passed | Proceed to next pipeline stage or post registration. |
| 1 | `Internal Error` | Uncaught exception or CLI crash | Inspect stderr stack traces; verify browser state. |
| 2 | `Invalid Input` | Parameter violation or bad format | Fix input arguments; do not retry identical command. |
| 3 | `Browser / Auth Error` | CDP connection lost or challenge | Alert user for manual re-login; inspect port 9222. |
| 4 | `Uncertain Submission` | Submit clicked without DOM confirmation | **NEVER RETRY AUTOMATICALLY.** Preserve tab and verify profile manually. |
