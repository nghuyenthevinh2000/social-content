---
name: story-engine
description: >
  Unified storytelling skill. Run before writing any story, post, caption, or narrative.
  Covers two sequential phases: (1) Story Integrity — interrogates whether the story earns
  the right to be told; (2) Story Craft — shapes and writes the story using a platform-specific
  format file from story-formats/. LinkedIn formats include Jescil-Richard and Jasmin Alić frameworks.
---

# Story Engine

## What This Skill Does

Story Engine combines two previously separate skills into a single, sequenced workflow:

| Phase | Capability | Purpose |
|:------|:-----------|:--------|
| **1 — Before writing** | [Story Integrity Interrogation](brainstorming/integrity-interrogation.md) | Tests whether the story deserves to be told — honesty, stakes, earned transformation |
| **2 — During writing** | Platform format file in [`story-formats/<platform>/`](story-formats/) | Shapes and writes the story using the format conventions of the target platform |

Story formats for each platform live in `story-formats/`. Use them to understand the structural conventions of the platform before drafting.

---

## Capabilities

### [integrity-interrogation](brainstorming/integrity-interrogation.md)
Interrogates the story before any writing begins. Tests honesty, recognition, stakes, transformation, craft integrity, and responsibility. Produces a **Story Readiness Assessment** before handoff to crafting.

Run this **always** before writing. A technically excellent draft on an unearned story feels hollow.

### Independent method: [world-interrogation](brainstorming/world-interrogation.md)
Use directly when the user requests world-based brainstorming or a world-consistency diagnosis. It has its own topic and emotion interview, world selection, eight-symbol gap loop, approval gate, and consistency audit. It does not require the integrity method and is not a mandatory step in the workflow below. A request to run this independent method follows its own completion gate rather than the full Story Engine pre-draft gate.

### Story Craft — via `story-formats/<platform>/`
After the integrity phase, select the appropriate format file for your platform. Format files guide structure and writing practices; some also provide platform-specific interviews and brief templates. The long-form [personal essay guide](story-formats/longform/personal-essay.md) focuses on craft and uses the approved Story Brief.

**LinkedIn format files:**
- [`story-formats/linkedin/jescil-richard-formats.md`](story-formats/linkedin/jescil-richard-formats.md) — 10-principle Jescil-Richard framework: parameter interview, story brief, bang opening, show/don't tell, punch ending
- [`story-formats/linkedin/jasmin-alic-formats.md`](story-formats/linkedin/jasmin-alic-formats.md) — Hook + Rehook anatomy, 5 named post formats (list, contrarian, scene→insight, insider, proof point)

---

## Story Format Reference

Platform-specific format files live in `story-formats/`. Each subfolder represents one platform. Add story format files to the platform folder that fits your usecase.

| Platform | Folder |
|:---------|:-------|
| LinkedIn | [`story-formats/linkedin/`](story-formats/linkedin/) |
| X (Twitter) | [`story-formats/x/`](story-formats/x/) |
| Instagram | [`story-formats/instagram/`](story-formats/instagram/) |
| Long-form / Blog | [`story-formats/longform/`](story-formats/longform/) |
| Other | [`story-formats/other/`](story-formats/other/) |

---

## Full Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│  PHASE 1 — STORY INTEGRITY                                      │
│  [brainstorming/integrity-interrogation.md]                      │
│                                                                 │
│  1. Run interrogation questions (honesty, recognition,          │
│     stakes, transformation, craft, responsibility)              │
│  2. Emotional recognition research — search similar stories     │
│  3. Produce Story Readiness Assessment                          │
│  4. Loop until user confirms root conflict — not surface        │
│                                                                 │
│  ✅ Verdict: Ready → proceed to Phase 2                         │
│  ❌ Verdict: Not ready → resolve the flagged gap first          │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  PHASE 2 — STYLE SELECTION                                      │
│                                                                 │
│  Ask the user:                                                  │
│                                                                 │
│  "What platform and craft style do you want to use?"           │
│                                                                 │
│  Present the available format files as options:                 │
│                                                                 │
│  LinkedIn:                                                      │
│    A. Jescil-Richard — 10 principles: bang opening,            │
│       emotion over facts, write to one person, punch ending     │
│    B. Jasmin Alić — Hook + Rehook, 5 post formats:             │
│       list, contrarian, scene→insight, insider, proof point     │
│                                                                 │
│  Other platforms: ask which platform, then check               │
│  story-formats/<platform>/ for available format files           │
│                                                                 │
│  Wait for the user's answer before proceeding.                  │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  PHASE 3 — STORY CRAFT                                          │
│  [story-formats/<platform>/<chosen-format-file>.md]             │
│                                                                 │
│  1. Read and follow the chosen format file                      │
│  2. Parameter interview — questions defined in format file      │
│  3. Produce Story Brief — openings, core scene, arc, ending     │
│  4. User approves brief                                         │
│  5. Draft — apply principles from the chosen format file        │
└─────────────────────────────────────────────────────────────────┘
```

> **Rule**: Do NOT skip Phase 1. Do NOT draft during the interview. Do NOT write a draft before the Story Brief is approved.

### Enforcement — applies to all requests, all languages

**For the full story-writing workflow, no input bypasses the workflow.** A topic, an outline, a 4-part structure, a personal story, a platform name — none of these substitute for Phase 1. They are raw material, not permission to draft. A standalone world-interrogation request uses that method's own interview and approval gate; completing it does not automatically start this workflow.

**No language bypasses the workflow.** Requests in Vietnamese, English, or any other language follow the identical 3-phase sequence.

**The fuller the input, the stricter the gate.** A detailed brief describes what the user thinks they want to say. Phase 1 finds what the story actually needs to say. More detail upfront means higher risk of skipping — not lower need for interrogation.

**Pre-draft gate — all boxes must be checked before any draft is produced:**
```
[ ] Emotional recognition research completed
[ ] Story Readiness Assessment produced and presented
[ ] User confirmed root conflict
[ ] Platform and format file confirmed
[ ] Story Brief approved by user
```

### Pipeline registration and terminal approvals

Run these commands from the repository root. Before requesting any terminal approval, the agent must register the intended output path:

```sh
python3 .agents/skills/story-engine/hooks/story_pipeline.py init --target-file "topics/<category>/<story-slug>.md"
```

The target Markdown file does **not** need to exist yet: `--target-file` identifies the future draft, and `init` stores its path in the pipeline registry without creating the file. Do not create a placeholder draft to enable approval. Use the same path throughout the workflow. Check `status` before registering an existing topic; do not re-run `init` on an in-progress topic, since it resets its approvals.

After presenting the root conflict, ask the **user** to run:

```sh
python3 .agents/skills/story-engine/hooks/story_pipeline.py confirm-conflict --target-file "topics/<category>/<story-slug>.md"
```

After presenting the Story Brief, ask the **user** to run:

```sh
python3 .agents/skills/story-engine/hooks/story_pipeline.py approve-brief --target-file "topics/<category>/<story-slug>.md"
```

Replace the placeholders with the registered path and keep each command on one line. The agent must not execute either approval command. A "not found in registry" error means registration is missing or the supplied path differs—not that the Markdown file must be created. Use `python3 .agents/skills/story-engine/hooks/story_pipeline.py status` to inspect registration before requesting approval.

---

## Common Failure Modes (Quick Reference)

| Failure | Signal | Fix |
|:--------|:-------|:----|
| Parable, not story | Protagonist gains insight without losing anything | What does the character give up? |
| Too-fast reward | Universe immediately validates right action | Does the story hold ambiguity after? |
| Performative vulnerability | Shares personal detail, avoids dangerous truth | Which detail am I most afraid to include? |
| Writing to impress | Clever language, reader can't find themselves | Am I helping them recognize, or making them admire? |
| Explained ending | Final lines state the lesson the story proved | Does the last line earn silence, or break it? |
| Collateral exposure | Honest about teller, careless about others | Who else appears here — are they protected? |
| Behavioral title | Title describes what character does, not what it costs | Does this title name a wound, paradox, or climax? |
| Opening with context | Post starts with background, not conflict | Open with conflict, surprise, or tension |
| Writing to everyone | "You all" energy | Pick one reader, write to them specifically |
| Passive constructions | "Was [verb]ed" everywhere | Find every passive and flip it |
