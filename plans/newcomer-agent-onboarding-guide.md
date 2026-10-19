---
name: newcomer-agent-onboarding-guide
summary: Onboarding guide for newcomer agents covering installation, conceptual pipeline, starter flows, and advanced capabilities.
---

# Newcomer Agent Onboarding Guide

```text
1. Research & Style  ──>  2. Story & Copy  ──>  3. Rich Visuals  ──>  4. Guarded Publish
 (style-analyzer,          (story-engine,        (infographic,        (linkedin, twitter,
  glasser, reddit)          humanizer)            html decks, video)   facebook agents)
```

| Step | Instruction | Details & Purpose |
| --- | --- | --- |
| 1. Install | `install https://github.com/nghuyenthevinh2000/social-content` | Equips the agent with specialized content skills, research tools, visual generators, and guarded publishing CLIs. |
| 2. Concept | 4-Stage Content Engine | Organizes creation into Research -> Story/Copy -> Visual Assets -> Guarded Distribution. |
| 3. Practice | Test 3 Starter Flows | Run basic copy-paste prompts below to build an immediate mental model before exploring advanced tools. |

| Starter Flow | Prompt to Agent | Active Skills | Expected Output |
| --- | --- | --- | --- |
| 1. Authentic Storytelling | `Share a lesson about [topic]. Use story-engine (Jasmin Alić framework) and humanizer to remove fluff.` | [`story-engine`](../.agents/skills/story-engine/SKILL.md), [`humanizer`](../.agents/skills/humanizer/SKILL.md) | High-retention post with hook, narrative tension, conversational cadence, and zero AI filler. |
| 2. Visual Infographic | `Create a 16:9 visual infographic summarizing [key findings] using infographic skill with modern style.` | [`infographic`](../.agents/skills/infographic/SKILL.md), [`beautiful-html-templates`](../.agents/skills/beautiful-html-templates/SKILL.md) | Responsive HTML/CSS layout with embedded charts and a 2x Retina PNG screenshot. |
| 3. Style DNA Analysis | `Analyze the writing style of [Creator Handle] using writing-style-analyzer. Save to plans/[creator-slug].md.` | [`writing-style-analyzer`](../.agents/skills/writing-style-analyzer/SKILL.md) | Structured dossier dissecting hook formulas, rhythm, vocabulary, and platform-specific habits. |

| Advanced Capability | What You Can Do | Key Resources |
| --- | --- | --- |
| Complete Brand OS | Build brand strategy, positioning, tone of voice, and manage persistent `brand.yaml` across 15 workflows. | [`branding`](../.agents/skills/branding/SKILL.md) |
| Supervised Publishing | Direct CLI posting to personal LinkedIn, Twitter/X, and Facebook with local checks and manual inspection fallback. | [`social-platform-orchestrator`](../.agents/skills/social-platform-orchestrator/SKILL.md), [`tools/`](../tools/) |
| Audience Research | Discover subreddits and mine real user discussions, pain points, and sentiment. | [`tools/reddit-research-mcp`](../tools/reddit-research-mcp/), [`glasser`](../.agents/skills/glasser/SKILL.md) |
| Video Compositing | Face-centered circular overlay video, background music mixing, and static watermark removal. | [`video-editing`](../.agents/skills/video-editing/SKILL.md), [`tools/video_edit`](../tools/video_edit/) |
| Twitter Reply Strategy | Select high-signal targets and draft replies optimized for engagement and deboost avoidance. | [`twitter-reply-strategy`](../.agents/skills/twitter-reply-strategy/SKILL.md) |
| Diátaxis Documentation | Author structured technical documentation (tutorials, how-to guides, reference docs, explanations). | [`documentation`](../.agents/skills/documentation/SKILL.md) |
| Lean Engineering | Execute minimal, dependency-light code changes following YAGNI and standard-library-first principles. | [`ponytail`](../.agents/skills/ponytail/SKILL.md) |
| Intelligent Skill Router | Automatic PreInvocation semantic ranking and injection of the right skill and template via TypeSafe Jev. | [`skill-selection-router-hook-guide.md`](./skill-selection-router-hook-guide.md) |

| Pipeline Stage | Focus Area | Recommended Skills & Tools |
| --- | --- | --- |
| 1. Research & Style | Audience pain points, creator voice reverse-engineering, external data lookup. | `writing-style-analyzer`, `reddit-research-mcp`, `glasser` |
| 2. Story & Copy | Narrative integrity, LinkedIn/X frameworks, fluff stripping, reply angles. | `story-engine`, `humanizer`, `twitter-reply-strategy` |
| 3. Rich Visuals | Responsive HTML/CSS charts, presentation decks, face-overlay video clips. | `infographic`, `beautiful-html-templates`, `video-editing` |
| 4. Publishing | Human-in-the-loop terminal submission, draft validation, diagnostic checks. | `linkedin_agent`, `twitter_agent`, `facebook_agent`, `social-platform-orchestrator` |
