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

### Story Craft — via `story-formats/<platform>/`
After the integrity phase, select the appropriate format file for your platform. Each format file contains the parameter interview, story brief template, platform conventions, and post structures to apply.

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
