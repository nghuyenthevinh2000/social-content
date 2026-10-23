# Content Gates

```text
Evidence → research review → draft → rendered visual → content approval → guarded publish → register
```

| Contract | Location and meaning |
|---|---|
| Project policy | `loop/config.json`: `allowed_channels` plus `content_policy` with `schema_version: 1`. Preserve existing settings. |
| Root instructions | Project `AGENTS.md` governs all posts; `loop/AGENTS.md` retains measurement-specific safeguards. Explicitly read both. |
| Research requirements | Optional `content_policy.research`: `min_primary_statutes`, `min_case_studies`, `primary_hosts`. When present, require `research.md`, structured `research.json`, and a current human research review. |
| Brand | Optional `guidelines_file`, `tokens_file` reference project-relative files. Tokens contain `colors` (including `canvas`), approved primary `fonts`, and `render_scale` (default 2). Guidelines remain the authority; update tokens together with approved brand changes. |
| Copy | `required_cta` lists exact required strings. `forbidden_artifacts` lists disallowed filename globs, checked only in the selected active post. `require_visual` requires source plus rendered PNG. |
| Content selection | `posts/<id>/content.json`: `schema_version: 1`, `channel`, `copy`, optional `visual: {source, image}` and `groups`. Paths are post-relative and cannot escape the post folder. Copy file contains exact publication text, without authoring notes. Terminal file newlines are excluded from submitted text; other whitespace stays exact. Approval hashes the whole file. |
| Evidence selection | `posts/<id>/research.json`: `schema_version: 1`, `sources`, `claims`. Templates: [research](../assets/research.json), [content](../assets/content.json). Templates intentionally fail until completed; never manufacture evidence to pass. |
| Source record | `id`, `type` (`primary_statute` or `case_study`), `title`, HTTPS `url`, `jurisdiction`, `checked_at` (ISO date), substantive `analysis`. Statutes also require `provisions` and `effective_date`; not-yet-effective laws cannot support current-law claims. |
| Claim record | `claim`, nonempty `source_ids`, `limitations`. Explain applicability and distinguish enacted law, interpretation, proposals and foreign analogies. Source minimums are not proof of legal correctness. |
| Review | Human research reviewer checks actual sources, current legal effect, case facts and mapped claims. Human content approver checks final copy and rendered PNG, including legibility, typography and source correspondence. |
| Approval integrity | Receipts bind decisions to artifact/config/brand/instruction/hypothesis hashes. Edits invalidate approval. CLI flags record human attestations; they cannot authenticate a human or verify legal truth. Agents must never invent reviewers or self-approve. |

| Step | Command from repository root | Gate |
|---|---|---|
| Evidence | `python -m tools.loop --project <PROJECT> preflight --post <ID> --stage research` | Validate artifacts and source metadata offline. Does not fetch or legally verify sources. |
| Research decision | `python -m tools.loop --project <PROJECT> review-research --post <ID> --reviewer <HUMAN> --approved` | Run only after explicit human research approval; writes `research-review.json`. |
| Draft | `python -m tools.loop --project <PROJECT> preflight --post <ID> --stage draft` | Requires current research review when configured, allowed channel and exact CTA. Run research gate before drafting, then draft gate afterward. |
| Visual | `python -m tools.loop --project <PROJECT> preflight --post <ID> --stage visual` | Adds constrained SVG paint/font/canvas checks and PNG dimensions. |
| Content decision | `python -m tools.loop --project <PROJECT> approve-content --post <ID> --reviewer <HUMAN> --approved --visual-reviewed` | Only after human inspection and explicit approval; writes `content-approval.json`. Omit visual attestation only for text-only content. |
| Publish readiness | `python -m tools.loop --project <PROJECT> preflight --post <ID> --stage publish` | Adds current content approval. Nonzero exit and structured errors mean blocked. |
| Facebook Page | `uv run python -m tools.facebook_agent --cdp <ENDPOINT> post --project <PROJECT> --post <ID> --page-id <PAGE_ID> --text-file <COPY_FILE> --image <PNG>` | Reads UTF-8 copy directly, excluding terminal newlines; no shell/Python wrapper. Checks approval before browser connection and submission, including exact text, image, Page and groups. |
| Registration | `python -m tools.loop --project <PROJECT> register --post <ID> --url <CONFIRMED_URL> --published-at <TIMESTAMP>` | Records facts after publication; policy-managed projects attach a registration-time preflight audit. It does not retroactively block publication. |

| Limit / recovery | Required response |
|---|---|
| Unsupported visual syntax | Static validator accepts explicit SVG attributes, approved hex paints/fonts and paper canvas; rejects CSS/classes, filters, gradients and embedded resources. Convert to the supported subset; never silently relax policy. Human inspection remains mandatory. |
| Raster verification | PNG header dimensions are checked, not full image decoding or pixel-level brand compliance. The human attestation binds the actual rendered file and SVG hashes. |
| Instruction bypass | Markdown instructions cannot prevent arbitrary file writes. Guards enforce this Facebook publisher's path, not arbitrary external tools. Other platform publishers still need explicit channel selection and human approval. |
| Managed Page without scope | Publishing to a policy-managed Page without `--project`/`--post` fails, including direct Python and name-only calls once identity is observed. Personal-profile and unmanaged Page workflows retain existing behavior. |
| Failed or uncertain submission | Preserve the tab; never retry automatically. Inspect manually before any subsequent publish request. |
| Confirmed without permalink | `status: confirmed` is not a URL receipt. `permalink` is populated only from an unambiguous supported link in fresh success confirmations; feed links and old toasts are ignored. Missing/ambiguous extraction retains success and reports `registration_status: needs_permalink`, never a request to repost. |
| Read-only URL recovery | `uv run python -m tools.facebook_agent --cdp <ENDPOINT> content-library --page-id <PAGE_ID> --output <NEW_JSON>`. Inspect saved placements; verify exact copy, author, original placement and publish time. A latest row, Insights URL or group-copy URL is not proof of the original permalink. If not uniquely verifiable, ask for manual inspection. |
| Operational capability decision | Use public CLI → inspect `--help`/reference → reuse supported read-only recovery → stop/report if still missing. Never substitute inline subprocess wrappers, private `preflight._svg` probes, raw JS/CDP, or ad-hoc browser scripts. Use `preflight --stage visual`; a blocked prerequisite must be fixed, not bypassed for an isolated check. This does not prohibit implementation/tests while developing repository tools. |
| Existing legacy project | Do not silently migrate or invent policy. Add explicit allowed channels/project instructions and policy with user authorization; existing unrelated metrics operations remain compatible. |
| Fresh-session routing smoke test | In a new session, request a social project post without naming the skill. Verify `social-campaign` loads, project rules precede drafting, only configured channels are selected, and missing evidence blocks progression. Keyword/static tests cannot prove model routing. |
