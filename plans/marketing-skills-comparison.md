# Marketing Skills Comparison: marketingskills vs. This Repository

Compared on: 2026-10-03

Source: [coreyhaines31/marketingskills](https://github.com/coreyhaines31/marketingskills), compared with this repository's `.agents/skills/`, including nested web-design layout skills.

## Summary

**Their repo is a marketing-growth toolkit. Ours is a content, brand, design, and publishing toolkit.** They are complementary, but installing everything would create overlap.

“Missing” below means **no dedicated equivalent**, not that an agent cannot perform the task. This is a comparison of documented workflows, not a benchmark of output quality. The upstream repository may change after this comparison.

## Different starting points: professional workflows vs. learning by doing

My own starting point matters here: this repository grew from being a beginner learning to do marketing. I added support for the problems I encountered: finding a story worth telling, learning how to write it, making visuals, researching conversations, and publishing safely.

I read `marketingskills` as a toolkit organized around an established marketing discipline. It is easier to navigate when you already recognize the work you need: attribution, conversion-rate optimization (CRO), lifecycle email, pricing research, or revenue operations (RevOps). That is my interpretation of its structure, not a claim that beginners cannot use it.

| Viewpoint | Their repository | This repository |
|---|---|---|
| Starting question | Which marketing workflow do I need to execute? | What do I need to learn or build to do this task? |
| Organization | Broad coverage across marketing functions and the customer journey | Detailed support for tasks encountered while creating and distributing content |
| Guidance | Marketing frameworks, specialist references, and service integrations | Interviews, previews, explicit review, and local execution workflows |
| Likely blind spot | A beginner may not know which capability to look for | Problems I have not encountered may have no dedicated workflow yet |

This explains why their repository contains capabilities I did not initially know to look for. My collection reflects the marketing problems I already recognize. Their collection gives me a map of areas I have yet to explore.

The practical response is to choose a current goal, learn which marketing function supports it, and adopt the relevant workflow. Installing every skill would expand the collection without necessarily improving my understanding of when to use it.

### What the follow-up inspection changed

The initial comparison relied heavily on the skill list and selected files. It should remain a preliminary capability map. Their repository also has deeper reference documents, integration guides, and executable CLIs; comparing skill names alone misses some of that coverage.

In particular, their `social` skill already covers X research and reply drafting:

- [`listening.md`](https://github.com/coreyhaines31/marketingskills/blob/main/skills/social/references/listening.md) describes authenticated browser searches, profiles, and lists, followed by post extraction, opportunity scoring, and comment drafting. The user reviews and posts manually.
- [`reverse-engineering.md`](https://github.com/coreyhaines31/marketingskills/blob/main/skills/social/references/reverse-engineering.md) describes creator discovery, post and engagement-data collection, and analysis of hooks, topics, and formats.
- [`x-algorithm.md`](https://github.com/coreyhaines31/marketingskills/blob/main/skills/social/references/x-algorithm.md) provides algorithm research and posting guidance with sourcing caveats.

They also ship a [Buffer CLI](https://github.com/coreyhaines31/marketingskills/blob/main/tools/clis/buffer.js) for outbound publishing and scheduled queue management. It does not provide X research or reply operations. Their [Buffer integration guide](https://github.com/coreyhaines31/marketingskills/blob/main/tools/integrations/buffer.md) notes that the CLI's legacy API is unavailable to new developer-app registrations, so the documented workflow is not automatically usable by a new account.

Our X distinction is the dedicated executable CLI, persistent drafts and review, pacing controls, and approved reply submission. Research, opportunity scoring, and drafting are areas of overlap. A documented browser workflow or service integration also needs its external tools and authentication configured; installing the skill alone does not supply those.

## What They Have That We Lack

| Capability | Their skills | Our coverage |
|---|---|---|
| **SEO and search discovery** | `seo-audit`, `ai-seo`, `programmatic-seo`, `schema`, `site-architecture`, `aso` | Basic SEO/AEO guidance in landing/pricing pages, but no dedicated system |
| **Measurement and experiments** | `analytics`, `attribution`, `ab-testing` | No dedicated equivalent |
| **Full-funnel conversion** | `cro`, `signup`, `onboarding`, `popups`, `paywalls` | Landing-page conversion covered; signup, activation, and upgrade flows largely missing |
| **Email and messaging** | `cold-email`, `emails`, `sms` | No dedicated equivalent |
| **Paid acquisition** | `ads`, `ad-creative` | No dedicated equivalent |
| **Retention** | `churn-prevention` | No dedicated equivalent |
| **Sales operations** | `prospecting`, `revops`, `sales-enablement` | We can make decks, but lack dedicated prospecting, pipeline, and sales-handoff workflows |
| **Growth channels** | `referrals`, `co-marketing`, `community-marketing`, `influencer-marketing`, `events`, `public-relations`, `directory-submissions` | Social posting and replies covered; broader distribution channels mostly missing |
| **Marketing planning** | `marketing-plan`, `launch`, `marketing-ideas`, `marketing-loops`, `marketing-council` | Brand strategy exists; campaign planning and recurring growth workflows are less explicit |
| **Commercial strategy** | `pricing`, `offers`, `free-tools`, `lead-magnets` | Pricing-page presentation covered, but pricing research, offer construction, and acquisition assets less deeply |
| **Editorial strategy** | `content-strategy`, `social` | Strong individual-post craft; less explicit calendar, repurposing, and performance-review guidance |
| **AI media production** | `image`, `video` | Strong HTML graphics and footage editing; less dedicated AI image/video generation guidance |

**Biggest gap:** we have extensive support for producing and publishing content, but much less dedicated support for **measuring its business impact and improving the acquisition funnel**.

## What We Have That They Lack—or Cover Less Specifically

| Our capability | Our skills | Difference |
|---|---|---|
| **Complete brand identity system** | `branding` | Naming and availability checks, visual identity, brand architecture, audits, rebranding, and persistent brand packages—not just product positioning |
| **Story integrity** | `story-engine` | Explicit honesty, stakes, emotional-conflict, and approval gates before drafting |
| **Detailed creator-style analysis** | `writing-style-analyzer` | Dedicated, evidence-backed “Style DNA” reports; theirs has related viral-content analysis, so this is partial overlap |
| **Specialized X reply execution** | `twitter-reply-strategy` | Opportunity scoring, discovery commands, draft review, and pacing tied to our local tools |
| **Repo-native social publishing** | `social-platform-orchestrator` | Concrete browser/CLI workflows for X, Facebook, and LinkedIn; theirs delegates publishing to connected scheduling tools/APIs |
| **Web/UI design and implementation** | `web-design` + layout skills | Preview-first workflow, browser approval, responsive implementation, and a substantial visual-layout library |
| **Deterministic visual deliverables** | `infographic`, `beautiful-html-templates` | HTML infographics, screenshot output, and reusable presentation templates—not merely general image or sales-deck guidance |
| **Technical footage editing** | `video-editing` | Specific ffmpeg, synchronization, portrait/HDR, and face-overlay workflows; their video skill emphasizes generation and production |
| **Non-marketing technical work** | `documentation`, `file-conversion`, `ponytail`, `typesafe-ai` | Technical docs, conversions, minimal-code discipline, and typed AI decisions are outside their main scope |

Our `humanizer` is **not entirely unique**: their copywriting/social guidance also rejects AI-sounding patterns. Ours makes that a dedicated, reusable editing workflow.

## Overlap Worth Avoiding

- **`product-marketing` ↔ `branding`:** audience, positioning, voice, differentiation, and persistent context.
- **`copywriting` / `copy-editing` ↔ our page skills + `humanizer`:** useful additions, but overlapping instructions.
- **`social` ↔ `story-engine` + orchestrator + reply strategy:** theirs adds planning and optimization; ours adds craft and local execution.
- **`pricing` ↔ `pricing-page`:** theirs decides **what to charge**; ours focuses on **how to present it**.
- **`image` / `video` ↔ our visual skills:** different production approaches, not complete duplicates.

One integration issue: their skills expect `.agents/product-marketing.md`; our branding system uses `brand.yaml` and companion Markdown files. **Those contexts will not automatically stay synchronized.**

## What to Add First

For this social-content repository:

1. **`content-strategy`** — connects individual posts into a coherent plan.
2. **`social`** — adds calendars, repurposing, listening, and performance reviews; retain our existing craft/publishing workflows.
3. **`analytics` + `attribution`** — connects attention to conversions and revenue.
4. **`emails` + `lead-magnets`** — creates a path from social followers to an owned audience.
5. **`launch`** — coordinates content around an actual product release.

If the priority becomes selling a SaaS, add **`cro`, `ab-testing`, `pricing`, and `seo-audit`** next.

**Bottom line: keep our production system; borrow their strategy, measurement, and funnel skills.**
