---
name: newcomer-agent-onboarding-guide
summary: Onboarding guide and repository exploration challenge with point system for newcomer agents.
---

# Newcomer Agent Onboarding Guide

```text
1. Research & Style  ──>  2. Story & Copy  ──>  3. Rich Visuals  ──>  4. Guarded Publish
Explorer (150 pts)   ──>  Creator (400 pts) ──> Publisher (750 pts) ──> Grandmaster (1,000 pts)
```

| Step | Instruction | Details & Purpose |
|---|---|---|
| 1. Install | `install https://github.com/nghuyenthevinh2000/social-content` | Equips the agent with specialized content skills, research tools, visual generators, and guarded publishing CLIs. |
| 2. Concept | 4-Stage Content Engine | Organizes creation into Research -> Story/Copy -> Visual Assets -> Guarded Distribution. |
| 3. Practice | Test 3 Starter Flows | Run basic copy-paste prompts below to build an immediate mental model before exploring advanced tools. |
| 4. Challenge | 1,000-Point Exploration Quest | Complete hands-on missions across all 4 tracks to unlock mastery badges and master the entire repo. |

| Starter Flow | Prompt to Agent | Active Skills | Expected Output |
|---|---|---|---|
| 1. Authentic Storytelling | `Share a lesson about [topic]. Use story-engine (Jasmin Alić framework) and humanizer to remove fluff.` | [`story-engine`](../.agents/skills/story-engine/SKILL.md), [`humanizer`](../.agents/skills/humanizer/SKILL.md) | High-retention post with hook, narrative tension, conversational cadence, and zero AI filler. |
| 2. Visual Infographic | `Create a 16:9 visual infographic summarizing [key findings] using infographic skill with modern style.` | [`infographic`](../.agents/skills/infographic/SKILL.md), [`beautiful-html-templates`](../.agents/skills/beautiful-html-templates/SKILL.md) | Responsive HTML/CSS layout with embedded charts and a 2x Retina PNG screenshot. |
| 3. Style DNA Analysis | `Analyze the writing style of [Creator Handle] using viral-analyzer. Save to plans/[creator-slug].md.` | [`viral-analyzer`](../.agents/skills/viral-analyzer/SKILL.md) | Structured dossier dissecting hook formulas, rhythm, vocabulary, and platform-specific habits. |

| Quest: Research & Story (250 pts) | Points | Action / Prompt | Verification Check |
|---|---:|---|---|
| Style DNA Extraction | 50 pts | `Analyze writing style of [creator] with viral-analyzer` | Dossier created in `plans/<creator>.md` with voice, hooks, and rhythm breakdown. |
| Audience Pain-Point Mining | 75 pts | `Research pain points on [topic] using reddit-research-mcp or glasser` | Identified target audience concerns, real quotes, and discussion themes. |
| Story Integrity Interrogation | 50 pts | `Run Phase 1 Story Integrity on [topic] with story-engine` | Evaluated honesty, stakes, and root conflict before drafting. |
| Fluff-Free Humanization | 75 pts | `Run humanizer on [sample draft] to eliminate corporate jargon` | Stripped stock phrases, passive constructions, and AI rhetorical patterns. |

| Quest: Visuals & Rich Media (250 pts) | Points | Action / Prompt | Verification Check |
|---|---:|---|---|
| Executive Infographic 16:9 | 75 pts | `Build 16:9 infographic with infographic skill using technical layout` | Self-contained HTML file generated with Playwright 2x Retina screenshot. |
| Interactive Slide Deck | 75 pts | `Create a 5-slide deck using beautiful-html-templates brutalist theme` | Interactive HTML slide presentation with keyboard navigation. |
| Video Overlay Compositing | 50 pts | `uv run python -m tools.video_edit --help` | Tested video composite CLI for face-tracking circular PiP and audio mixing. |
| Preview-First Web Design | 50 pts | `Draft responsive hero section spec and preview with web-design` | Browser-testable preview artifact with clean responsive CSS. |

| Quest: Strategy & Architecture (250 pts) | Points | Action / Prompt | Verification Check |
|---|---:|---|---|
| Brand OS Package Setup | 75 pts | `Initialize brand strategy package for [Product Name] using branding` | Structured `brand.yaml` manifest with positioning and voice guidelines created. |
| Diátaxis Documentation Guide | 50 pts | `Structure a how-to guide for [workflow] using documentation skill` | Four-quadrant Diátaxis structure applied with clear step-by-step guidance. |
| Bidirectional Conversion | 50 pts | `Convert Markdown spec to PDF with Mermaid using file-conversion` | Clean PDF output generated with preserved diagrams and tables. |
| Ponytail Minimalist Refactor | 75 pts | `Review script using ponytail (lite/full) to eliminate unnecessary code` | Removed external dependencies in favor of Python standard library primitives. |

| Quest: Publishing & Intelligence (250 pts) | Points | Action / Prompt | Verification Check |
|---|---:|---|---|
| Unified Post Schema Validation | 50 pts | Inspect canonical schema in `tools/common/samples/post.json` | Validated platform-agnostic post format across LinkedIn, X, and Facebook. |
| Publishing Diagnostics Dry-Run | 75 pts | `uv run python -m tools.linkedin_agent.doctor` | Verified browser CDP connection, auth profile, and DOM readiness safely. |
| High-Signal Twitter Angle | 50 pts | `Evaluate target tweet and draft 3 angles using twitter-reply-strategy` | Scored engagement potential while avoiding algorithm deboost triggers. |
| TypeSafe Jev Router Demo | 75 pts | `uv run --project . python scripts/skill-selector-demo/server.py` | Ran local web demo visualizing Jev two-stage confidence scores. |

| Milestone Rank | Required Points | Unlocked Status & Privileges |
|---|---:|---|
| 🥉 Explorer Agent | 150 pts | Completed 3 starter flows; understands core Research -> Copy pipeline. |
| 🥈 Creator Agent | 400 pts | Generates high-impact visual assets, slide decks, and audience-researched copy. |
| 🥇 Publisher Agent | 750 pts | Operates Brand OS, executes Diátaxis docs, and tests safe publishing CLIs. |
| 🏆 Grandmaster Orchestrator | 1,000 pts | Mastered all 15 skills, automation tools, and TypeSafe semantic routing. |
