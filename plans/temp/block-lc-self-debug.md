# Block L&C Content Pipeline Self-Debug

```text
Historical failure: Hypothesis -> skipped evidence -> multi-channel copy -> generic visual
Implemented: Project policy -> evidence -> human research review -> Facebook copy -> SVG/PNG checks -> human approval -> guarded publish -> register
```

| Dimension | Finding | Impact | Severity |
|---|---|---|---|
| Platform scope | Historical redundant LinkedIn drafting. Current hypotheses already specify Facebook; explicit `allowed_channels` now removes ambiguity. | Old drafts are not a source of channel policy. | Medium |
| Visual identity | Historical dark/neon styling. Current SVG has an Alabaster canvas but still contains non-token red/green paints, generic fonts and unsupported filters. | A background fix alone does not establish brand compliance. | High |
| Research gating | Current dossier lists legal texts without primary-source URLs, checked/effective dates or a documented empirical case. | Claims remain unverified; the new gate correctly blocks progression. | Critical |

| Failure ID | Observed Defect | Root Cause | Immediate Remediation |
|---|---|---|---|
| DEF-01 | Unrequested channel variants | Skill defaulted to cross-platform broadcasting; project safeguards lived under sibling `loop/`, not project root. | Keyword-based skill discovery, repository routing, project-root rules, explicit allowed channels and active-post artifact checks. |
| DEF-02 | Off-brand assets | Prose brand rules were not connected to execution. | Brand token JSON, constrained SVG canvas/paint/font checks, rendered PNG dimensions and hash-bound human visual inspection. |
| DEF-03 | Unsupported legal claims | Presence of a dossier was mistaken for evidence quality; no executable gate. | Structured source/provision/date/claim records plus explicit research review before drafting. Scripts do not verify legal truth. |
| DEF-04 | Stale or bypassed approval | Review-proposal approval differs from publication approval; direct posting previously had no project content gate. | Dedicated content approval binds copy/media/policy/destinations. Shared guard runs before browser connection and immediately before submission, including direct calls. |

| Stage | Required Artifact | Quality Gate & Acceptance Criteria | Enforcement Mechanism |
|---|---|---|---|
| 1. Research | `research.md`, `research.json`, `research-review.json` | Two official primary statutes, one documented case, mapped claims, jurisdiction/effective/checked dates, applicability review. | `preflight --stage research`; explicit `review-research`; downstream stages require current research receipt. Instructions govern drafting; scripts cannot prohibit arbitrary file writes. |
| 2. Copywriting | `content.json`, exact copy file | Facebook Page only; confirmed voice references and phone/email CTA. No internal authoring notes in publication text. | `preflight --stage draft`; selected active post checked for unauthorized channel artifacts. Historical drafts are preserved. |
| 3. Visual | SVG source, 2× PNG | Harvey tokens; paper canvas; configured primary fonts; source-to-render correspondence and legibility. | `preflight --stage visual`; actual rendered PNG must also receive explicit human inspection. Static checks intentionally reject CSS, filters, embedded media and gradients. |
| 4. Publication | `content-approval.json` | Explicit approval of exact content/media/destinations; correct active Page. | `approve-content`, then `preflight --stage publish`; shared Facebook guard rechecks hashes and exact submitted arguments before clicking. |
| 5. Registration | `loop/publications.json` | Confirmed canonical URL/time; registration-time validation audit. | `register` records publication facts even if current artifacts fail. `cycle` measures afterward; neither command is a pre-publication gate. |

| Action Item | Target File | Status | Owner |
|---|---|---|---|
| Routing and policy | Root `AGENTS.md`, social-campaign skill, project root rules and config | Implemented; fresh-session model routing still needs a manual smoke test | Agent |
| Shared validator and approvals | `tools/loop/preflight.py`, loop CLI, Facebook CLI/publisher | Implemented with offline regression coverage | Agent |
| New-project prevention | `tools/loop/project_init.py` | Creates root instructions, explicit Page policy and content manifest without overwriting existing files | Agent |
| Post 2 channel cleanup | `local/block-lc/posts/2/` | No LinkedIn file present at implementation time; nothing deleted | Existing state |
| Post 2 research repair | `research.md`, missing `research.json` | Blocked: obtain real sources, verify current law/case facts, map claims, request human research approval | Researcher + human reviewer |
| Post 2 copy and visual repair | `facebook-ad.md`, `visual-rwa-spv.svg`, missing PNG | Pending research review; preserve existing drafts, then remove internal notes, correct unsupported assertions and produce compliant assets | Agent + human reviewer |
| Local privacy | `local/block-lc/` | Project policy/tokens remain gitignored; generic tooling, templates and routing are repository files | Project owner |

| Verification | Result |
|---|---|
| Loop regression suite | `python3 -m unittest discover -s tools/loop/tests`: 119 passed. |
| Facebook regression suite | `uv run python -m unittest discover -s tools/facebook_agent/tests`: 149 passed, including intercepted offline browser fixtures. No live Facebook actions. |
| Current Post 2 preflight | Exit 2: missing `research.json`. No source evidence, research review, rendered PNG or content approval was fabricated. |
| Routing coverage | Keyword-description and root-routing contract tested; fresh-session model invocation remains a manual smoke test. |
| Changed-file integrity | `git diff --check` passed. Existing post drafts and source SVG were preserved. |
