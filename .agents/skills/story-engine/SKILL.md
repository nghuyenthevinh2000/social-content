---
name: story-engine
description: "Storytelling router and workflow skill. Routes requests to story-flows/ and shapes drafts with story-formats/."
---

# Story Engine

| Step | Action | Rule |
|---|---|---|
| 1. Route | Match request to one flow below | Never skip interrogation regardless of language or prompt detail |
| 2. Gate 1 | Run flow's interrogation + research | Wait for user confirmation of conflict/law/tension |
| 3. Format | Select guide in `story-formats/` | Confirm platform (`longform/`, `linkedin/`, `x/`, `instagram/`, `other/`) |
| 4. Gate 2 | Present Story/World Brief | Wait for user approval before drafting |
| 5. Humanize | Run `humanizer` skill on draft | Strip AI patterns ("not X, it's Y", filler, moralizing tags) while keeping facts and voice |

| Story Signal | Flow | Core Engine | File |
|---|---|---|---|
| Lived experience, memoir, setback | Personal & Reflective | Fact/feeling separation + loss | [`personal-reflective.md`](story-flows/personal-reflective.md) |
| Symbolic world, parable, allegory | World & Allegory | Governing law + 8 symbols | [`world-allegory.md`](story-flows/world-allegory.md) |
| Contrarian take, paradox, POV post | Thesis & Perspective | Hidden fear + proof + shift | [`thesis-perspective.md`](story-flows/thesis-perspective.md) |
| Third-person story, case study | Narrative & Character | Character cost + responsibility | [`narrative-conflict.md`](story-flows/narrative-conflict.md) |

```text
Request -> Classify -> Gate 1 (Conflict) -> Format -> Gate 2 (Brief) -> Draft -> Humanize
```

| Failure | Fix |
|---|---|
| Wrong flow | Route POV posts to `thesis-perspective.md` |
| Parable, not story | Name what the character gives up |
| Writing to impress | Aim for reader recognition |
| Explained ending | Let final line earn silence |
