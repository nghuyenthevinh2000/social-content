# Hook Validation Loop: Product Research Plan

**Product thesis:** Generate hook + video variants → distribute → pull platform metrics → AI diagnoses *why* variants won or lost → feed learnings into the next generation round. Generation tools are commoditizing; the closed learning loop is the candidate moat.

**Research goals (in order):**

1. Map the existing market and where each player stops in the loop.
2. Articulate our added value versus Higgsfield Marketing Studio and similar tools.
3. Discover a defensible moat.
4. Decide the target user (still open).

---

## Phase 1: Competitor Matrix (start here, ~3–4 days)

### 1.1 Loop-stage coverage (the core view)

Score each tool per stage: ❌ none, 🟡 partial/manual, ✅ native. *Initial entries are hypotheses from a first web pass, so verify each one with a hands-on trial or the vendor docs.*

| Tool | Hook ideation | Video generation | Auto-distribution (organic posting) | Metrics ingestion | AI diagnosis of *why* | Auto-feeds next generation |
| --- | --- | --- | --- | --- | --- | --- |
| **Higgsfield Marketing Studio** | ✅ hook generator, templates | ✅ avatars, UGC templates, URL/ref-ad input | ❌ export to ad managers | ❌ | ❌ | ❌ |
| **Creatify (AdMax)** | ✅ | ✅ URL-to-video, batch | 🟡 ad-platform tie-in | 🟡 ROAS dashboards (verify) | 🟡 (verify) | 🟡 (verify) |
| **Arcads** | 🟡 scripts | ✅ realistic actors | ❌ | ❌ | ❌ | ❌ |
| **MakeUGC** | 🟡 | ✅ | ❌ | ❌ | ❌ | ❌ |
| **Syllaby** | ✅ trends/scripts | 🟡 avatars | 🟡 scheduling | ❓ | ❓ | ❌ |
| **Icon / Poppy AI** | ❓ | ❓ | ❓ | ❓ | ❓ | ❓ |
| **Adjacent: Motion, Triple Whale, Foreplay, Atria** (creative analytics / swipe files) | 🟡 | ❌ | ❌ | ✅ | ✅ | ❌ |
| **Adjacent: Buffer, Metricool, Hootsuite** (schedulers) | ❌ | ❌ | ✅ | ✅ shallow | ❌ | ❌ |
| **DIY: ChatGPT + CapCut + native analytics** | 🟡 | 🟡 | manual | manual | 🟡 | manual |
| **Hook Validation Loop (us)** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |

**Insight to test:** Generators sit on the left, analytics tools on the right, and almost nobody owns the full chain. The gap is the "diagnose → regenerate" handoff.

### 1.2 Per-competitor deep dive template

For each of 8–12 tools, fill in:

- **Positioning and ICP:** who they say they serve.
- **Pricing and unit economics:** cost per video, per seat, per credit.
- **Generation quality:** run the same test brief through every tool (see 1.3).
- **Hook tooling:** how hooks are made, whether they are data-informed or generic.
- **Analytics depth:** which metrics (3s hook rate, hold rate, shares, saves, CPA), which platforms, API vs manual.
- **Feedback mechanism:** does any output change the next generation automatically?
- **Public sentiment:** G2, Reddit, X, Trustpilot complaints. These show unmet needs.
- **Lock-in and integrations:** Meta/TikTok APIs, Shopify, etc.

### 1.3 Hands-on benchmark (same brief everywhere)

- One product/topic, 5 hook angles each, 9:16, ~20s.
- Measure: time to first usable video, cost, edit effort, hook quality (blind-rated by 3–5 people), and platform-readiness.

---

## Phase 2: Added-Value Hypotheses vs. Higgsfield

**Core added value: automate the validation loop**, saving users the time and cost of repeating the same manual steps every cycle.

Today, users running a loop with a generator do this by hand: generate → download/export → upload and post per platform → wait → open each platform's analytics → copy numbers into a sheet → interpret → write the next brief → re-enter it into the generator. We replace all of that with one automated cycle.

| Manual step per loop | Higgsfield-style workflow | Hook Validation Loop |
| --- | --- | --- |
| Generate hook/video variants | In tool | Automated |
| Export and post to each platform | Manual | Automated |
| Collect metrics per platform | Manual, copy-paste | Automated |
| Compare variants and diagnose | Manual or ad hoc ChatGPT | Automated (AI) |
| Brief the next round | Manual | Automated |
| Human involvement | Every step | Approval/oversight only |

**Quantify the value (research task):**

- **Time saved:** measure minutes per loop iteration done manually vs. automated. Time 5–10 real users or run it ourselves with the DIY stack as the baseline.
- **Cost saved:** compare the combined cost of tools, credits and labour (or freelancer/agency rates) with our price per loop.
- **Waste avoided:** credits spent on variants that were never validated, and posts that were never analysed.
- **Speed:** loop cycle time (days → hours) and iterations per month.

**Claims to validate with users (not assume):**

1. Users repeat this loop manually today and find it tedious (frequency, hours per week).
2. They would pay to remove that work, and they would trust AI to decide what to try next, with an approval step.
3. Platform APIs allow automated posting and metric pulls (check feasibility and ToS per platform).
4. Time and cost savings are large enough to beat "good enough" DIY (ChatGPT + CapCut + a sheet).

> [!NOTE]
> Automation is easy to copy, so the moat work in Phase 3 matters. Test whether accumulated loop data and integrations make leaving costly. Test this in addition to the time-saving pitch.

---

## Phase 3: Moat Discovery

Candidate moats, with the evidence needed for each:

| Candidate moat | What makes it defensible | Research to test it |
| --- | --- | --- |
| **Proprietary outcome dataset** (hook features → metrics, by niche/platform) | Generators don't see outcomes; the data compounds | How much usable signal exists at small scale? Run a pilot and check statistical power |
| **Per-account learned playbook** | Switching cost: leaving means losing history | Do users' winners repeat across weeks? |
| **Attribution and diagnosis quality** (separating hook from body, audience, timing) | Hard causal inference; experiment design is the skill | Test whether AI diagnoses match controlled A/B results |
| **Platform integrations** (posting and analytics APIs) | Friction and API access | Audit API limits, ToS, and approval needs for TikTok/IG/YT/X/LinkedIn |
| **Workflow and model neutrality** | Works with any generator, so it isn't threatened by Higgsfield or others | Check whether competitors would integrate or copy |

**Threat to check:** Higgsfield, Creatify or Meta/TikTok could add analytics feedback. Estimate how fast and how deep, and decide whether our moat is *data and learning* rather than *features*.

---

## Phase 4: Target-User Discovery (parallel)

Because the ICP is open, run 10–15 short interviews across three segments: solo creators, indie founders / small SaaS, and DTC brands/agencies.

Ask about:

- Their current hook-testing process.
- Tools and spend today.
- How they judge "what worked".
- Their pain with Higgsfield/Arcads-type tools.
- Willingness to pay.

Pick the segment with the sharpest pain, the highest budget and an accessible metrics API.

---

## Phase 5: Loop Feasibility Experiment (after the matrix)

- Pick 1 niche, 2 platforms, 10 hook variants with the same body.
- Run 2 loop iterations; compare iteration 2 with iteration 1 on 3s view rate and retention.
- **Key risk:** organic metrics are noisy, with small samples and algorithm variance. Define minimum sample size and the decision rule up front.

---

## Timeline

| Days | Work |
| --- | --- |
| 1–2 | Build the matrix skeleton; collect public info for 10+ tools |
| 3–4 | Hands-on benchmark; verify ❓ cells; sentiment mining |
| 5 | Synthesize: positioning map and moat shortlist |
| 5–10 | User interviews (parallel) |
| 10–14 | Loop feasibility pilot |

## Deliverables

- `competitor-matrix.md` (filled version of §1.1/1.2)
- `benchmark-results.md`
- `positioning-and-moat.md`
- `interview-notes/`
- `pilot-results.md`

## Open questions

- Is the product a standalone app or a layer on top of existing generators?
- Organic only, or paid-ad testing too? This affects metric quality and the competitor set.
