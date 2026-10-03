# Marketing Skills Comparison: marketingskills vs. This Repository

Compared on: 2026-10-03

Source: [coreyhaines31/marketingskills](https://github.com/coreyhaines31/marketingskills), compared with this repository's `.agents/skills/`, including nested web-design layout skills.

## Summary

**Their repo is a marketing-growth toolkit. Ours is a content, brand, design, and publishing toolkit.** They are complementary, but installing everything would create overlap.

“Missing” below means **no dedicated equivalent**, not that an agent cannot perform the task. This is a comparison of documented workflows, not a benchmark of output quality. The upstream repository may change after this comparison.

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
| **Story integrity and reflective writing** | `story-engine` | Explicit honesty, stakes, emotional-conflict, and approval gates before drafting |
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
