# Social Content & Agent Skills

[![Malware Scan](https://github.com/nghuyenthevinh2000/social-content/actions/workflows/malware-scan.yml/badge.svg)](https://github.com/nghuyenthevinh2000/social-content/actions/workflows/malware-scan.yml)
[![Supply Chain Scan](https://github.com/nghuyenthevinh2000/social-content/actions/workflows/supply-chain.yml/badge.svg)](https://github.com/nghuyenthevinh2000/social-content/actions/workflows/supply-chain.yml)
[![Prompt Injection Scan](https://github.com/nghuyenthevinh2000/social-content/actions/workflows/prompt-injection.yml/badge.svg)](https://github.com/nghuyenthevinh2000/social-content/actions/workflows/prompt-injection.yml)

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
>   3. *Campaign-Bound Viral & Creator Research* ([`social-campaign`](./.agents/skills/social-campaign/SKILL.md) → [viral research](./.agents/skills/social-campaign/references/viral-analyzer.md))
> - **1,000-Point Exploration Quest**: A gamified challenge rewarding agents/users for trying all 15 skills, video tools, brand OS, and guarded publishing CLIs.
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
| [`social-campaign`](./.agents/skills/social-campaign/SKILL.md) | Project-bound campaign workflow: research, drafting, visual assets, guarded publishing, performance loops, plus campaign-bound [viral discovery and creator Style DNA](./.agents/skills/social-campaign/references/viral-analyzer.md). |
| [`story-engine`](./.agents/skills/story-engine/SKILL.md) | Unified storytelling engine: integrity checks + platform craft frameworks (LinkedIn, X). |
| [`twitter-reply-strategy`](./.agents/skills/twitter-reply-strategy/SKILL.md) | Discovers, scores, and drafts high-visibility Twitter/X replies. |
| [`typesafe-ai`](./.agents/skills/typesafe-ai/SKILL.md) | AI primitives and typed probability judgments (System One / Jev models). |
| [`video-editing`](./.agents/skills/video-editing/SKILL.md) | ffmpeg and OpenCV face-centered circular overlays, audio mixing, and video composition. |
| [`viral-analyzer`](./.agents/skills/social-campaign/references/viral-analyzer.md) | Removed as a standalone skill. Its workflow now lives inside [`social-campaign`](./.agents/skills/social-campaign/SKILL.md) and requires an existing campaign. |
| [`web-design`](./.agents/skills/web-design/SKILL.md) | Preview-first web design for landing pages, dashboards, and UI layouts. |

---

## 🤖 Local Automation Tools (`tools/`)

Deterministic local tools for supervised, human-in-the-loop social actions. Read more in [`tools/README.md`](./tools/README.md).

- [`tools/loop/`](./tools/loop/): Project-agnostic metrics, review and guarded publication-state engine.
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

## 🛡️ Security, Supply Chain & AI Safety

<!-- SECURITY_STATUS_START -->
| Target | Scanner | Status | Last Scanned | Details |
| :--- | :--- | :--- | :--- | :--- |
| **Repo Malware** | ClamAV | ✅ Clean | 2026-10-29 05:48 UTC | 1167 files scanned, 0 threats (v1.5.4) |
| **Supply Chain** | GuardDog + uv & npm audit | ❌ Threats Detected | 2026-10-29 06:43 UTC | Supply chain audit failure (Py: 0, npm: 1, actions: 0) |
| **Prompt Injection** | LLM Safety Guard | ✅ Clean | 2026-10-29 07:52 UTC | All prompts, skills & files verified clean (0 injection findings) |
<!-- SECURITY_STATUS_END -->

---

## 📁 Repository Structure

Refer to [`local/index.json`](./local/index.json) for full directory mapping and Repomix configuration.
