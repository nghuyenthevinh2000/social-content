---
name: social-platform-orchestrator
description: >
  Orchestrate and publish social content across Twitter/X, Facebook, and LinkedIn using the automation tools in tools/.
  Dispatches platform-specific subagents, enforces single-browser CDP concurrency locks, coordinates human approvals,
  and adapts content to platform-specific format and media requirements.
---

# Social Platform Orchestrator

This skill guides the agent in coordinating multi-platform social media operations across **Twitter/X**, **Facebook**, and **LinkedIn** using the three automation tools located in `tools/`:
- `tools/twitter_agent/`: Terminal-operated X DOM CLI with reply workflows and standalone approved image publishing.
- `tools/facebook_agent/`: Direct DOM publishing of approved text and an optional single image to personal Facebook profiles.
- `tools/linkedin_agent/`: Direct approved-input doctor and publishing CLI for personal LinkedIn profiles with repeatable ordered images.

---

## 1. Golden Architectural Rule: Shared Browser Serialization

All three tools connect to the **same dedicated Chrome browser** via Chrome DevTools Protocol (CDP):
- **Default CDP Port**: `http://127.0.0.1:9222`
- **Shared Chrome Profile**: `$HOME/chrome-twitter-profile`
- **Browser Launcher**: `bash tools/twitter_agent/launch_browser.sh` (or `tools/facebook_agent/launch_browser.sh` / `tools/linkedin_agent/launch_browser.sh`)

> [!CAUTION]
> **STRICT CDP MUTUAL EXCLUSION (SERIALIZATION)**
> Never run browser automation commands concurrently across multiple platforms against the same Chrome instance. Running simultaneous Playwright/CDP operations against the shared profile causes tab collisions, focus conflicts, and state corruption.
>
> - **Drafting & Content Adaptation**: Can run in **parallel** across subagents.
> - **Live Browser Execution (`doctor`, `post`, `publish`, `search`, `reply submit`)**: Must be executed **strictly sequentially** (one platform finishes before the next begins).

---

## 2. Multi-Agent Topology & Roles

When managing all three platforms, use a 2-tier agent architecture:

```mermaid
flowchart TD
    User([User]) <--> Orchestrator[Orchestrator Agent]
    Orchestrator -->|1. Draft in Parallel| TwitterAgent[Twitter Subagent]
    Orchestrator -->|1. Draft in Parallel| FacebookAgent[Facebook Subagent]
    Orchestrator -->|1. Draft in Parallel| LinkedInAgent[LinkedIn Subagent]
    
    TwitterAgent -->|Draft Content| Orchestrator
    FacebookAgent -->|Draft Content| Orchestrator
    LinkedInAgent -->|Draft Content| Orchestrator
    
    Orchestrator -->|2. Request Approval| User
    User -->|Approved| Orchestrator
    
    subgraph BrowserExecution["3. Sequential Browser Execution (CDP Port 9222)"]
        direction TB
        RunFB["Step A: Facebook Post"] --> RunLI["Step B: LinkedIn Post"] --> RunTW["Step C: Twitter Post"]
    end
    Orchestrator --> BrowserExecution
```

### Roles:
1. **Orchestrator Agent (Parent)**:
   - Serves as the primary contact with the user.
   - Accepts core topic, message, or campaign outline.
   - Dispatches platform subagents to draft tailored content.
   - Presents unified cross-platform review to the user for explicit approval.
   - Schedules and coordinates sequential browser calls to enforce the CDP concurrency lock.
   - Collects JSON execution results and reports overall status.

2. **Twitter Subagent (`twitter-platform-agent`)**:
   - Specializes in X mechanics: short hooks, 280-char boundaries, thread structures, reply discovery, and standalone image posts.
   - CLI Target: `tools/twitter_agent/` and `tools/twitter_agent/publish.py`.
   - Respects rate quotas (6/hour, 20/day, 120s spacing, 3 per 30m burst).

3. **Facebook Subagent (`facebook-platform-agent`)**:
   - Specializes in personal Facebook updates: conversational tone, storytelling, link formatting, single photo attachments.
   - CLI Target: `tools/facebook_agent/`.
   - Validates text (required) and optional single image (PNG/JPEG/GIF/WebP).

4. **LinkedIn Subagent (`linkedin-platform-agent`)**:
   - Specializes in professional LinkedIn posts: industry insight, framework breakdowns, ordered carousel/multi-image posts.
   - CLI Target: `tools/linkedin_agent/`.
   - **Crucial Rule**: LinkedIn tool **requires at least one image** (1–20 PNG/JPEG files, <= 10 MiB each). Text-only posts are unsupported in this tool.

---

## 3. Platform Capabilities & Validation Matrix

Always validate content against platform constraints **before** invoking browser tools:

| Feature / Rule | Twitter / X (`tools/twitter_agent`) | Facebook (`tools/facebook_agent`) | LinkedIn (`tools/linkedin_agent`) |
| :--- | :--- | :--- | :--- |
| **Account Type** | Specified account (`--account`) | Personal profile only (`/me`) | Personal profile only |
| **Text Requirement** | Required. Under 280 chars (unless long-form subscriber). | Non-empty text required. Multiline supported. | Required, non-blank, max 3,000 characters. |
| **Media Requirement** | Standalone publish requires exactly 1 image. | Optional: 0 or 1 image (PNG, JPEG, GIF, WebP). | **Mandatory: 1 to 20 images** (PNG or JPEG only, max 10MB each). |
| **Media Constraints** | Photo only. Video unsupported in CLI. | Single image only. Multi-image/video unsupported. | **Text-only unsupported**. GIF/WebP/video unsupported. |
| **Audience Control** | Public by default. | Inherited from Facebook composer setting. | Inherited from LinkedIn composer setting. |
| **Human Approval** | Explicit `--approved` flag required for `publish`. | Invoking `post` triggers immediate DOM publication. | Invoking `post` triggers immediate DOM publication. |
| **Quotas & Pacing** | 6/hr, 20/24hr, 120s between submissions, 3/30min. | None enforced in tool; manual pacing recommended. | None enforced in tool; manual pacing recommended. |

---

## 4. Standard Operating Workflows

### Workflow 1: Cross-Platform Campaign Broadcast

Use when publishing a single announcement, article, or insight across all three platforms.

#### Step 1: Pre-Flight Browser Health Check
Before drafting or attempting publication, check that Chrome is up and authenticated on all platforms. Run sequentially:
```bash
# Verify Chrome CDP is alive and each platform is logged in
uv run python -m tools.facebook_agent doctor
uv run python -m tools.linkedin_agent doctor
uv run python -m tools.twitter_agent doctor
```
If Chrome is not running, launch it:
```bash
bash tools/twitter_agent/launch_browser.sh
```

#### Step 2: Content Adaptation (Parallel Drafting)
Dispatch subagents to produce platform-adapted drafts from the source content:
- **Facebook Draft**: Casual, narrative-driven, full context, optional 1 image.
- **LinkedIn Draft**: Professional take, structural takeaways, 1–20 required images (e.g. infographic, slide cards, or cover image).
- **Twitter Draft**: Punchy hook, under 280 characters, accompanied by 1 image.

#### Step 3: Human-in-the-Loop Approval Gate (MANDATORY)
Present all three adapted drafts and image paths clearly to the user:
```markdown
### Cross-Platform Publishing Proposal

#### 1. Facebook Personal Profile
- **Text**: <exact text>
- **Image**: <path or None>

#### 2. LinkedIn Personal Profile
- **Text**: <exact text>
- **Image(s)**: <paths, 1-20 PNG/JPEG>

#### 3. Twitter / X (@Handle)
- **Text**: <exact text>
- **Image**: <single image path>
```
> [!IMPORTANT]
> **DO NOT CALL POST OR PUBLISH COMMANDS WITHOUT EXPLICIT USER APPROVAL.**
> The tools do not have an interactive confirmation prompt. Invoking the CLI publishes immediately.

#### Step 4: Sequential Publishing (Enforce Concurrency Lock)
Once the user explicitly confirms, execute the commands **sequentially**:

1. **Facebook**:
   ```bash
   uv run python -m tools.facebook_agent post \
     --text "Approved Facebook post text" \
     --image "/absolute/path/to/image.png"
   ```
   *Verify exit code 0 and JSON `{"ok": true}` before proceeding.*

2. **LinkedIn**:
   ```bash
   uv run python -m tools.linkedin_agent post \
     --text "Approved LinkedIn post text" \
     --image "/absolute/path/to/image.png"
   ```
   *Verify exit code 0 and JSON `{"ok": true}` before proceeding.*

3. **Twitter / X**:
   ```bash
   uv run python -m tools.twitter_agent.publish \
     --account <TwitterHandle> \
     --text "Approved tweet text" \
     --image "/absolute/path/to/image.png" \
     --approved
   ```
   *Verify exit code 0 and JSON `{"ok": true}`.*

---

### Workflow 2: Twitter / X Interactive Engagement

Use when finding high-signal conversations and drafting replies on X.

1. **Search Opportunities**:
   ```bash
   uv run python -m tools.twitter_agent search "AI engineering" --limit 10 --window-minutes 60 --min-score 80
   ```
2. **Inspect Target Thread**:
   ```bash
   uv run python -m tools.twitter_agent thread <TARGET_TWEET_ID_OR_URL>
   ```
3. **Queue Draft Reply**:
   ```bash
   uv run python -m tools.twitter_agent reply target <TARGET_TWEET_ID_OR_URL>
   uv run python -m tools.twitter_agent reply draft <DRAFT_ID> --text "Substantive reply text"
   ```
4. **Present Draft to User**: Show candidate tweet, reply angle, and draft text.
5. **Submit Upon Approval**:
   ```bash
   uv run python -m tools.twitter_agent reply submit <DRAFT_ID>
   ```

---

## 5. Result Codes & Recovery Protocol

All three tools output structured JSON to stdout and adhere to standard exit codes:

| Exit Code | Classification | Meaning | Action Required |
| :---: | :--- | :--- | :--- |
| **0** | `Success` | Post confirmed or doctor check passed. | Proceed to next task. |
| **1** | `Internal Error` | Unexpected internal exception or crash. | Check stderr logs and browser status. |
| **2** | `Invalid Input` | Argument parsing error, character limit violation, invalid image MIME/size. | Fix parameters before retrying. Does not touch browser. |
| **3** | `Browser / Auth Error` | CDP connection lost, not logged in, checkpoint/captcha challenge detected. | Ask user to resolve browser challenge or re-login. |
| **4** | `Uncertain Submission` | Submission button was clicked, but DOM confirmation was not verified. | **NEVER RETRY AUTOMATICALLY.** The browser tab remains open. Ask user to inspect the tab and profile manually. |

> [!WARNING]
> **EXIT CODE 4 RECOVERY**
> If any tool exits with code 4, publication may already have occurred. Retrying automatically risks duplicate posts and platform shadowbans. Halt automation and alert the user immediately.

---

## 6. Subagent Dispatching Instructions

When dispatching subagents (using `invoke_subagent`), follow these guidelines:

### Defining Subagent Tasks
- **Provide Self-Contained Context**: Pass the exact file paths, text payloads, and platform constraints directly in the subagent's prompt.
- **Enforce Output Formats**: Require subagents to return raw tool JSON results and exit codes.
- **Coordinate Browser Locking**: If dispatching subagents for live browser execution, invoke them **one at a time** (or pass instructions specifying that execution must await turn order).

### Example Subagent Invocation (Drafting Stage)
```python
# The orchestrator can invoke platform subagents in parallel to draft variants:
invoke_subagent(
    Subagents=[
        {
            "TypeName": "self",
            "Role": "Twitter Copywriter",
            "Prompt": "Adapt this product announcement for X into a punchy post under 280 characters with hook, takeaways, and call to action. Source content: <CONTENT>. Do not run publish commands."
        },
        {
            "TypeName": "self",
            "Role": "LinkedIn Copywriter",
            "Prompt": "Adapt this product announcement for LinkedIn into a structured post (max 3,000 chars) with executive summary, bullet points, and key takeaways. Formatted for accompanied carousel/image. Source content: <CONTENT>. Do not run post commands."
        },
        {
            "TypeName": "self",
            "Role": "Facebook Copywriter",
            "Prompt": "Adapt this product announcement for a personal Facebook profile in an authentic, conversational voice. Source content: <CONTENT>. Do not run post commands."
        }
    ]
)
```

### Example Subagent Invocation (Sequential Publishing Stage)
After user approves all three drafts, dispatch execution subagents sequentially:
```python
# 1. Execute Facebook first
invoke_subagent(
    Subagents=[{
        "TypeName": "self",
        "Role": "Facebook Publisher",
        "Prompt": "Execute Facebook post using: uv run python -m tools.facebook_agent post --text '<APPROVED_FB_TEXT>' --image '<IMAGE_PATH>'. Return the JSON output and exit code."
    }]
)
# (Wait for subagent completion and check exit code == 0 before dispatching LinkedIn, then Twitter)
```
