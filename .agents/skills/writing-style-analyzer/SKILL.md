---
name: writing-style-analyzer
description: >
  Analyze the writing style of any content creator by name. The agent runs web searches
  to gather real writing samples, then synthesizes a structured "Style DNA" report covering
  voice, tone, sentence rhythm, hook patterns, vocabulary, structural conventions, and
  platform-specific habits. Use when a user wants to study, emulate, or contrast a creator's style.
---

# Writing Style Analyzer

## What This Skill Does

Given a content creator's name, this skill:

1. **Researches** — runs targeted web searches to find writing samples (posts, essays, threads, newsletters, captions)
2. **Extracts** — pulls verbatim quotes that best demonstrate the creator's style fingerprint
3. **Synthesizes** — produces a structured **Style DNA** report
4. **Operationalizes** — translates findings into actionable rules you can follow when writing in their style

---

## Input

The user provides:

| Field | Required | Notes |
|:------|:---------|:------|
| **Creator name** | ✅ | Full name or handle (e.g. "Paul Graham", "@naval", "Alex Hormozi") |
| **Platform focus** | Optional | LinkedIn / X / newsletter / blog — narrows which samples to fetch |
| **Angle focus** | Optional | e.g. "only their storytelling posts", "their thread style" |

If no platform is specified, search broadly across all public channels and note which platform each sample came from.

---

## Step 1 — Research

Run **at minimum 4 targeted web searches** across these dimensions. Do not proceed to Step 2 until you have gathered enough raw material.

### Search Query Templates

```
"{creator name}" writing style breakdown
"{creator name}" best posts site:linkedin.com OR site:twitter.com OR site:substack.com
"{creator name}" examples posts threads essays
"{creator name}" hook opening technique
"{creator name}" newsletter writing style
how does "{creator name}" write
"{creator name}" signature phrases vocabulary
```

Adapt queries based on what you know about the creator's primary platform. For a LinkedIn creator, prioritize LinkedIn URLs. For a newsletter writer, prioritize Substack or their personal domain.

### What to collect

For each search result, extract:
- **Verbatim quotes** (minimum 3–5 real excerpts) — actual sentences or paragraphs from the creator
- **Post/article title or context** — where and when it appeared
- **Platform** — LinkedIn, X/Twitter, Substack, blog, etc.

> **Rule**: Never invent quotes. If a search returns no usable verbatim content, run additional searches with different queries before proceeding.

---

## Step 2 — Style DNA Analysis

Analyze the collected samples across these **8 dimensions**. For each dimension, provide:
- A **1–2 sentence observation**
- **1–3 verbatim example quotes** from Step 1 to back it up

### The 8 Dimensions

#### 1. Voice & Persona
- What role does the writer play? (teacher, contrarian, confessor, strategist, provocateur)
- Is the voice authoritative, vulnerable, peer-to-peer, or hierarchical?
- First person or third person? How often do they name themselves?

#### 2. Sentence Rhythm & Length
- Short punchy sentences? Long flowing paragraphs? Mixed?
- Do they use fragments deliberately?
- Average line length — scannable (short) or dense (long)?
- Do they use the "one word. period." technique?

#### 3. Hook & Opening Strategy
- How do they open posts or essays? (Question / Bold claim / Personal story / Counter-intuitive stat / List tease)
- What is the characteristic hook pattern? Name it.
- Do they use a re-hook mid-post?

#### 4. Vocabulary & Diction
- Everyday language vs. industry jargon?
- Any signature words, phrases, or coinages they repeat?
- What level of formality? (casual, professional, academic)
- Active vs. passive voice tendency?

#### 5. Structural Conventions
- Do they use numbered lists, headers, bullet points — or flowing prose?
- Is there a repeating template? (e.g. Problem → Story → Lesson → CTA)
- How do they end posts? (Call-to-action / Rhetorical question / Punchy mic-drop / Soft landing?)

#### 6. Emotional Register & Tone
- Primary emotional tone: inspiring, provocative, educational, empathetic, humorous, skeptical?
- Do they use vulnerability? If so, how much and how?
- Do they moralize, or let the story speak?

#### 7. Platform-Specific Habits
- Formatting quirks: line breaks, emojis, white space, hashtags?
- Do they thread? If so, how do they sequence?
- Any consistent CTA pattern (e.g. "Follow for more", "Reply below", "Share this")?

#### 8. What Makes Them Distinctive
- The 1–2 things no other creator does the same way
- The "if you removed the name, could you still tell it was them?" test — what gives it away?

---

## Step 3 — Style DNA Report

Produce the final report in this structure:

```
# Style DNA: [Creator Name]

## Quick Summary (3 sentences)
[Who they write for, how they sound, what makes them unmistakable]

## Platform(s) Analyzed
[LinkedIn / X / Substack / etc. — with note on sample quality]

---

## 1. Voice & Persona
[Observation]
> "[Verbatim quote]" — [source/context]

## 2. Sentence Rhythm & Length
[Observation]
> "[Verbatim quote]"

## 3. Hook & Opening Strategy
[Observation — name the hook pattern]
> "[Verbatim quote of an opening]"

## 4. Vocabulary & Diction
[Observation]
Signature phrases: [list]
> "[Verbatim quote showing diction]"

## 5. Structural Conventions
[Observation — name the template if there is one]
> "[Verbatim quote showing structure]"

## 6. Emotional Register & Tone
[Observation]
> "[Verbatim quote]"

## 7. Platform-Specific Habits
[Observation]
> "[Verbatim quote or description of formatting]"

## 8. What Makes Them Distinctive
[2–3 bullet points — the fingerprint]

---

## Style Emulation Rules
(Use these rules when writing in this creator's style)

1. [Rule 1 — voice/persona]
2. [Rule 2 — sentence rhythm]
3. [Rule 3 — hook pattern]
4. [Rule 4 — vocabulary/diction]
5. [Rule 5 — structure]
6. [Rule 6 — tone]
7. [Rule 7 — platform habits]
8. [Rule 8 — the distinctive fingerprint]

---

## Verbatim Sample Bank
(3–5 real excerpts for reference and future study)

### Sample 1: [Title / Context]
> [Full quote]
Source: [URL or platform + date if known]

### Sample 2: [Title / Context]
> [Full quote]
Source: [URL or platform + date if known]

### Sample 3: [Title / Context]
> [Full quote]
Source: [URL or platform + date if known]
```

---

## Step 4 — Save to Reflections

After producing the Style DNA report, **always** save it as a markdown file under the repo's `reflections/` directory.

### File naming convention

```
reflections/<creator-slug>.md
```

- **`creator-slug`** — kebab-case of the creator's name or handle (e.g. `paul-graham`, `alex-hormozi`, `naval-ravikant`)
- If the file already exists, **append** a new dated section at the bottom rather than overwriting

### How to resolve the path

```bash
REPO_ROOT=$(git rev-parse --show-toplevel)
mkdir -p "$REPO_ROOT/reflections"
```

Write the full Style DNA report (verbatim, exactly as produced in Step 3) to:

```
$REPO_ROOT/reflections/<creator-slug>.md
```

### File header format

Prepend this header block at the top of a new file (skip if appending to existing):

```
---
creator: [Full name]
platforms: [LinkedIn / X / Substack / etc.]
analyzed: [YYYY-MM-DD]
---
```

If appending to an existing file, add a horizontal rule `---` and a `## Re-analysis: [YYYY-MM-DD]` heading before the new content.

### Verify

```bash
ls -lh "$REPO_ROOT/reflections/<creator-slug>.md"
```

Confirm the file exists with non-zero size, then tell the user the file path.

---

## Quality Rules

| Rule | Detail |
|:-----|:-------|
| **No fabricated quotes** | Every quote in the report must come from a real search result |
| **Source every claim** | Each observation must be backed by at least one verbatim example |
| **Minimum 4 searches** | Do not produce a report from a single search pass |
| **Name the patterns** | Don't just describe — give each pattern a label (e.g. "The Confessional Re-entry", "The Single-Line Gut Punch") |
| **Be specific** | Avoid generic adjectives like "engaging" or "authentic" — describe the mechanics |
| **Flag gaps** | If a dimension can't be analyzed from available samples, say so explicitly |

---

## Failure Modes to Avoid

| Failure | Fix |
|:--------|:----|
| Generic observations ("he writes clearly") | Name the specific technique or structure |
| No verbatim quotes | Always include real excerpts — they anchor every claim |
| Treating all platforms as identical | Note where style shifts across platforms |
| Skipping the emulation rules | The rules are the most actionable output — always include them |
| Making up a persona from reputation alone | Analyze actual writing, not what people say about the writer |

---

## Quick Reference

| Task | Action |
|:-----|:-------|
| Minimum searches | 4 (more if early results are thin) |
| Minimum verbatim quotes | 3 in sample bank, at least 1 per dimension |
| Report format | Style DNA Report template above |
| Resolve repo root | `REPO_ROOT=$(git rev-parse --show-toplevel)` |
| Save report | `write_to_file → $REPO_ROOT/reflections/<creator-slug>.md` |
| Verify saved file | `ls -lh "$REPO_ROOT/reflections/<creator-slug>.md"` |
| When samples are thin | Run more searches; note the gap in the report |
| Optional extension | Ask user: "Want me to write a sample post in this style?" |
