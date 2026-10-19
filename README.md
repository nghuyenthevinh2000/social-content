---
name: social-content
summary: AI agent toolkit for audience research, storytelling, visual assets, and supervised social publishing.
tags: [social-content, publishing, tools, agent-skills]
---

# Social Content & Agent Skills

> **Paste this to your agent to install:**
>
> ```text
> install https://github.com/nghuyenthevinh2000/social-content
> ```

A modular agent toolkit and operating system for end-to-end social content creation: audience research, storytelling frameworks, humanized copywriting, visual infographics/slides, video compositing, and guarded platform publishing (LinkedIn, X, Facebook).

---

## 🚀 Quickstart & Onboarding

> **Newcomer Agent Onboarding Guide:**
> Read **[`plans/newcomer-agent-onboarding-guide.md`](./plans/newcomer-agent-onboarding-guide.md)** for the complete walkthrough:
>
> - **4-Stage Content Engine**: The conceptual mental model connecting research, storytelling, rich visuals, and guarded publishing.
> - **Starter Flows to Try**:
>   1. *Authentic Storytelling & Copywriting* ([`story-engine`](./.agents/skills/story-engine/SKILL.md) ➔ [`humanizer`](./.agents/skills/humanizer/SKILL.md))
>   2. *Executive Visual Infographic / Slides* ([`infographic`](./.agents/skills/infographic/SKILL.md) / [`beautiful-html-templates`](./.agents/skills/beautiful-html-templates/SKILL.md))
>   3. *Creator Style DNA Analysis* ([`writing-style-analyzer`](./.agents/skills/writing-style-analyzer/SKILL.md))
> - **Advanced Capabilities**: End-to-end Brand OS, supervised social publishing, Reddit pain-point research, and video compositing.

## 🛠 Available Skills Catalog

All skills live in [`.agents/skills/`](./.agents/skills/) and can be loaded dynamically or pre-routed by the agent.

| Skill | Focus & Core Purpose |
| :--- | :--- |
| [`beautiful-html-templates`](./.agents/skills/beautiful-html-templates/SKILL.md) | 34+ production-ready HTML slide deck templates and presentation styling systems. |
| [`branding`](./.agents/skills/branding/SKILL.md) | End-to-end brand operating system (`brand.yaml`, identity, voice, positioning, guidelines). |
| [`documentation`](./.agents/skills/documentation/SKILL.md) | Technical documentation authoring following the Diátaxis framework. |
| [`file-conversion`](./.agents/skills/file-conversion/SKILL.md) | Bidirectional document conversions (PDF to Markdown, Markdown to PDF with Mermaid). |
| [`glasser`](./.agents/skills/glasser/SKILL.md) | 1,000+ paid and high-quality data endpoints (person/company search, enrichment, scraping). |
| [`humanizer`](./.agents/skills/humanizer/SKILL.md) | Rewrites AI-sounding prose into natural, rhythmic human language without changing meaning. |
| [`infographic`](./.agents/skills/infographic/SKILL.md) | Authors self-contained HTML visual infographics (16:9 / 9:16) with Playwright 2x Retina captures. |
| [`ponytail`](./.agents/skills/ponytail/SKILL.md) | Minimalist development ethos: standard libraries first, shortest path, zero unnecessary code. |
| [`social-platform-orchestrator`](./.agents/skills/social-platform-orchestrator/SKILL.md) | Orchestrates content across Twitter/X, Facebook, LinkedIn, and Reddit research. |
| [`story-engine`](./.agents/skills/story-engine/SKILL.md) | Unified storytelling engine: integrity checks + platform craft frameworks (LinkedIn, X). |
| [`twitter-reply-strategy`](./.agents/skills/twitter-reply-strategy/SKILL.md) | Discovers, scores, and drafts high-visibility Twitter/X replies. |
| [`typesafe-ai`](./.agents/skills/typesafe-ai/SKILL.md) | AI primitives and typed probability judgments (System One / Jev models). |
| [`video-editing`](./.agents/skills/video-editing/SKILL.md) | ffmpeg and OpenCV face-centered circular overlays, audio mixing, and video composition. |
| [`web-design`](./.agents/skills/web-design/SKILL.md) | Preview-first web design for landing pages, dashboards, and UI layouts. |
| [`writing-style-analyzer`](./.agents/skills/writing-style-analyzer/SKILL.md) | Reverse-engineers any creator's Style DNA from real writing samples. |

---

## 🤖 Local Automation Tools (`tools/`)

Deterministic local tools for supervised, human-in-the-loop social actions. Read more in [`tools/README.md`](./tools/README.md).

- [`tools/linkedin_agent/`](./tools/linkedin_agent/): Direct CLI for approved personal LinkedIn text and ordered image posts.
- [`tools/twitter_agent/`](./tools/twitter_agent/): Terminal-operated X DOM CLI for reply submission and approved image posting.
- [`tools/facebook_agent/`](./tools/facebook_agent/): Direct publishing to personal profile or named Fanpage with optional group sharing.
- [`tools/reddit-research-mcp/`](./tools/reddit-research-mcp/): Semantic community discovery and audience pain-point mining.
- [`tools/video_edit/`](./tools/video_edit/): Video watermark removal and OpenCV texture compositing.
- [`tools/common/`](./tools/common/): Shared browser startup, CDP diagnostics, and canonical unified post format ([`samples/post.json`](./tools/common/samples/post.json)).

---

## ⚡ Skill-Selection Router (Jev Hook)

A [TypeSafe](https://typesafe.ai)-backed PreInvocation hook automatically identifies and ranks the best skill and resource for every prompt before the agent executes.

- **Two-stage selection**: Determines which skill applies, then selects the exact resource/template inside that skill.
- **Multi-group support**: Independent rankings for combined needs (e.g., layout + aesthetic style).
- **Fails open**: Transparent fallback to standard LLM reasoning if anything errors or confidence is low.

Quick install into another workspace:

```bash
./scripts/install-skill-hook.sh /path/to/other/workspace
```

Run visual demo webapp:

```bash
uv run --project . python scripts/skill-selector-demo/server.py
# Open http://127.0.0.1:8765
```

See **[plans/skill-selection-router-hook-guide.md](./plans/skill-selection-router-hook-guide.md)** for detailed setup and architecture.

---

## 📁 Repository Structure

Refer to [`FRONTMATTER.md`](./FRONTMATTER.md) for full directory mapping and semantic routing.
