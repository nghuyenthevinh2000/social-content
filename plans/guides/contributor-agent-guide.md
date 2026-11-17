---
name: contributor-agent-guide
summary: Zero-jargon guide for non-technical users and their agents to compare workflows against skills and tools, write to plans/comparison, and open a PR.
---

# Contributor Agent Guide

```text
Paste 1 Prompt ──> Agent Interviews You ──> Compares .agents/skills & tools ──> Writes plans/comparison/<name>.md ──> Commits & Opens PR
```

| For the Human User (Zero Technical Setup Needed) | What You Do | What Happens Next |
|---|---|---|
| 1. Copy & Paste One Prompt | Copy the prompt from the table below and paste it into your AI agent chat. | Your agent reads this repository and takes care of every technical step for you. |
| 2. Answer Plain-English Questions | Tell your agent how you normally create posts, research topics, make visuals/videos, or publish content. | Your agent compares your daily habits with this repo's playbooks ([`.agents/skills/`](../../.agents/skills/)) and automation machines ([`tools/`](../../tools/)). |
| 3. Approve Sharing | Say "yes" when your agent shows you the summary report. | Your agent saves the report in `plans/comparison/`, commits the change, and opens a Pull Request automatically. |

| Copy-Paste Prompt for Your Agent | Exact Message to Send |
|---|---|
| **One-Click Contribution Prompt** | `Read plans/guides/contributor-agent-guide.md. Assume I have zero technical background. Interview me in plain language about how I currently do my social content tasks, compare my workflow against this repo's .agents/skills and tools, write the comparison report to plans/comparison/, and then commit and create a pull request for me.` |

| Plain-English Concept | How Other Users Usually Work | [`.agents/skills/`](../../.agents/skills/) (This Repo's "Brain & Playbooks") | [`tools/`](../../tools/) (This Repo's "Hands & Machines") |
|---|---|---|---|
| **What It Is** | Manual habits, scattered notes, or typing one-off requests into ChatGPT from scratch each time. | Reusable instruction manuals and design templates that teach the AI *how to think, write, and style*. | Deterministic programs and safety checks that perform *exact, repeatable actions* on files or browsers. |
| **Finding Ideas & Research** | Manually scrolling social feeds, guessing hashtags, or copying competitor posts by hand. | [`social-campaign`](../../.agents/skills/social-campaign/SKILL.md) and [`glasser`](../../.agents/skills/glasser/SKILL.md) define how to research audience pain points and creator styles. | [`tools/app/`](../../tools/app/), [`tools/loop/viral_analyzer/`](../../tools/loop/viral_analyzer/), [`tools/reddit-research-mcp/`](../../tools/reddit-research-mcp/), and [`tools/reddit_agent/`](../../tools/reddit_agent/) crawl, verify, and score real data with budget guards. |
| **Writing Stories & Captions** | Asking an AI "write a post about X" and getting generic, robotic-sounding text. | [`story-engine`](../../.agents/skills/story-engine/SKILL.md), [`humanizer`](../../.agents/skills/humanizer/SKILL.md), and [`branding`](../../.agents/skills/branding/SKILL.md) interview for real tension, apply proven frameworks, and strip AI fluff. | [`tools/common/samples/post.json`](../../tools/common/samples/post.json) stores the finished, approved caption and media list in one standard format. |
| **Making Visuals, Slides & Video** | Manually dragging boxes in Canva/PowerPoint or editing video overlays clip by clip. | [`infographic`](../../.agents/skills/infographic/SKILL.md), [`beautiful-html-templates`](../../.agents/skills/beautiful-html-templates/SKILL.md), and [`video-editing`](../../.agents/skills/video-editing/SKILL.md) pick layouts, typography, and visual structure. | [`tools/video_edit/`](../../tools/video_edit/), [`tools/app/`](../../tools/app/) (`video_engine.py`), and [`tools/tribeV2_ViralAnalyser/`](../../tools/tribeV2_ViralAnalyser/) run watermark removal, 15s AI video generation, and video/landing-page attention scoring. |
| **Publishing & Tracking Results** | Copy-pasting text into each social network by hand or using risky unattended auto-posters. | [`social-campaign`](../../.agents/skills/social-campaign/SKILL.md) and [`twitter-reply-strategy`](../../.agents/skills/twitter-reply-strategy/SKILL.md) enforce human-approval gates and reply angle rules before anything goes live. | [`tools/linkedin_agent/`](../../tools/linkedin_agent/), [`tools/twitter_agent/`](../../tools/twitter_agent/), [`tools/facebook_agent/`](../../tools/facebook_agent/), [`tools/taktik-bot/`](../../tools/taktik-bot/), and [`tools/loop/`](../../tools/loop/) check readiness (`doctor`), publish approved drafts, and log metrics. |
| **When to Contribute Here** | You have a personal workflow or domain trick you currently do by hand. | Add or improve a **Skill** when the AI needs better *judgment, writing rules, templates, or step-by-step playbooks*. | Add or improve a **Tool** when the AI needs a *reliable script, CLI command, browser check, or data pipeline*. |

| Agent Execution Protocol (For the AI Agent) | Required Agent Action | Zero-Jargon Rule for the Human |
|---|---|---|
| **Step 1: Plain-Language Interview** | Ask the user 3–5 simple questions about their daily workflow: (1) What content or task do they do? (2) What steps do they do manually or with other tools today? (3) Where do they lose the most time or quality? | Never ask the user about Git, branches, JSON schemas, CLI flags, or file paths. Translate their plain-language answers yourself. |
| **Step 2: Map Against `.agents/skills/` & `tools/`** | Inspect [`.agents/skills/`](../../.agents/skills/) and [`tools/README.md`](../../tools/README.md). Classify each part of the user's workflow into: (a) already handled by an existing skill/tool, (b) done differently by the user, or (c) a missing skill playbook vs. missing tool automation. | Summarize findings for the user in everyday language ("Playbooks vs. Automated Actions") before saving. |
| **Step 3: Write Report to `plans/comparison/`** | Create `plans/comparison/<topic-or-user-slug>.md` following [`.agents/skills/structured-writing/SKILL.md`](../../.agents/skills/structured-writing/SKILL.md) (table-first, one plain-text flow diagram, <=100 words outside tables). Include the 4 comparison tables defined below. | Show the user a short, friendly summary of what was written and ask if they are ready to share it. |
| **Step 4: Commit & Create Pull Request** | Run: (1) `git checkout -b docs/comparison-<slug>`, (2) `git add plans/comparison/<slug>.md`, (3) `git commit -m "docs(comparison): add <slug> workflow comparison"`, (4) push to origin (or fork via `gh repo fork --remote` if no write access), and (5) `gh pr create --title "docs(comparison): <slug> workflow vs skills and tools" --body "<summary>"`. | Never ask the user to type Git commands. If GitHub login is missing, guide them through `gh auth login --web` with a single click code. |
| **Step 5: Privacy & Safety Check** | Verify with `git diff --cached` that no `.env` secrets, personal tokens, account cookies, or private `local/` campaign data are staged. | Confirm to the user that only the workflow comparison document was shared and provide the clickable Pull Request link. |

| Required Sections in `plans/comparison/<slug>.md` | What the Agent Must Record |
|---|---|
| **1. Workflow Overview Table** | Task goal, how the user currently does it step by step, time/effort bottlenecks, and desired outcome. |
| **2. User Workflow vs. `.agents/skills/` (Playbooks)** | Side-by-side comparison of the user's decision/creative rules versus existing skills in `.agents/skills/`, highlighting what matches and what new rules/templates are needed. |
| **3. User Workflow vs. `tools/` (Automation)** | Side-by-side comparison of the user's manual/software actions versus deterministic CLIs in `tools/`, highlighting what is automated vs. manual. |
| **4. Contribution Recommendations** | Concrete next steps labeled clearly as either **New/Updated Skill** (in `.agents/skills/`) or **New/Updated Tool** (in `tools/`), ordered by impact. |
