# Viral Research and Creator Style

```text
Existing campaign → Brief → Validated brief → Sources → Promotion gate
                        ↓                                  ↓
                  blocked if missing            Relevance + qualification
                                                        ↓
                                        run validated → reuse gate → worksheet
```

## Campaign binding

| Rule | Requirement |
|---|---|
| Resolve first | Map the request to an existing `local/<slug>/`. Read only `product-marketing.json` for campaign facts: `marketing_goal` and `product.catalog`. Do not require brand files, customer profiles, hypotheses, loop configuration or scaffolds for research. |
| Blocked states | Missing or ambiguous campaign stops work. For a resolved campaign, missing required context blocks searching/collection, but offline candidate proposals may proceed from available facts with gaps disclosed. Never initialize a campaign, default to the paper-product project or adopt another campaign's brief. |
| Objective | Record `buyer_research`, `audience_growth` or `creative_inspiration`. An unnamed objective blocks collection. |
| Isolation | Seeds, observations, shortlists and reports never cross campaigns. |
| Sources vs channels | Research sources are separate from `allowed_channels`; researching a platform never authorizes publishing there. |
| Platform scope | Bind research to the platforms explicitly requested in the brief; if absent, ask. Multiple requested platforms get separate hashtag runs and evidence; do not wander into other platforms or feeds. |
| Approval | Research output is a recommendation. Content approval and publishing gates remain separate and human. |

## Hashtag validation

| Item | Requirement |
|---|---|
| Reference | Follow [hashtag validation](hashtag-validation.md) for the full command sequence, provider boundary, labels, decisions, history contract and limits. |
| Tools | `python3 -m tools.loop.viral_analyzer.hashtag_generate`, `…hashtag_verify` and `…viral_scrape`; templates in [assets/hashtag-generation](../assets/hashtag-generation/). |
| Boundary | Generation is offline; collection spends only with `--execute --ceiling` plus approval. Labels are agent judgments over inspected samples; history is campaign-local. |

## Per-run sub-agent contract

```text
Parent: bind campaign, platform runs, scope and approved budget
       ├── Worker A → viral/run-A/ → TikTok: all relevant tags → Report/artifacts
       └── Worker B → viral/run-B/ → Instagram: all relevant tags → Report/artifacts
Parent: check each handoff → Compare evidence and limitations → Return all run links
```

| Responsibility | Requirement |
|---|---|
| Delegation unit | Each `sources/viral/run-*/` directory is one run and gets exactly one dedicated sub-agent, even for a single-run request. One run targets one platform and queries its full relevant hashtag/keyword set within the agreed scope/budget. Hashtags are candidates/calls inside that run, not separate runs or workers. |
| End-to-end ownership | The same worker handles the run's candidate generation/import, verification planning/collection/review, approved expansion, analysis and report. Do not create workers per hashtag, query, product or workflow stage. Separate platform run directories get separate workers; the parent coordinates and checks handoffs, never substitutes its own research for a missing worker. No nested delegation. |
| Worker brief | Pass exact campaign/run/output paths, requested platform, objective, application, market/language, product goal/catalog, optional past analyses, relevant skill/reference/template paths, stopping limits and the current spend-approval state. Missing brand/customer/hypothesis files are not new prerequisites. |
| Ownership and isolation | Write only the assigned run's `brief.md`, `report.md` and `artifacts/`. Other run reports are read-only historical/comparison context, never fresh evidence. Do not modify sibling artifacts or copy successful results into a failed run. Record the worker identity/session reference in the run manifest; worker identity is not human approval. |
| Safe scheduling | Offline work may run in parallel. Allocate bounded per-run provider budgets within the explicitly approved total before any paid dispatch; no worker independently reuses the full shared ceiling. Without a clear allocation/approval, workers stop at preview. Serialize shared campaign-history writes and browser work through parent-coordinated turns. No publication authority is delegated. |
| Same completion checklist | Every worker delivers a populated brief and report plus `artifacts/manifest.json` and `artifacts/relevance.json`, with valid paths/hashes. Supporting prompts, plans, receipts and reviews exist only for stages actually reached. No-video runs may have `records: []`; insufficient leads retain unknown qualification. Explain absent stages instead of fabricating receipts, results or reviews. |
| Reporting depth parity | Use the full report template for every outcome: scope/product mapping; per-query coverage and receipts; attempted/empty/error/returned/deduplicated/qualified counts; linked videos or explicit zero; evidence/access limits; qualification/baseline; costs/approval provenance; observed timing; recommendation, stopping reason and revisit conditions. Unknown/not-applicable entries need reasons, not omitted sections. Equal completeness does not mean equal word counts or video counts. |
| Failed/low-yield runs | Investigate saved evidence enough to distinguish provider failure, empty retrieval and weak semantic evidence. Include query-level diagnostics, available leads with direct links, spend and a scoped platform/market recommendation. A short generic failure summary or automatic collection starter is not a finished worker report. No new calls beyond the approved scope/budget to pad it. |
| Worker handoff | Return run ID, owner reference, outcome, brief/report/manifest/relevance paths, actual cost or unknown, qualified/lead counts and unresolved limitations. Report blocked/interrupted/cancelled work too. Resume with the same owner when possible; handoffs to a replacement keep only one active writer and preserve saved evidence. |
| Parent acceptance | Check each worker's artifacts against the same checklist, source links, counts and hashes before comparison. Return omissions to that run's worker for completion, including zero-result runs; do not accept the richer run while silently dropping the poorer one. Surface missing/incomplete handoffs explicitly. Agent acceptance checks do not replace human research/content approval. |
| No sub-agent capability | Report the execution limitation and ask how to proceed. Do not silently fall back to parent-run execution or claim a worker ran when none did. |

## Topic-discovery routing

```text
Resolved campaign + requested platforms → Offline candidates → Import
                                                               ↓
                                       Context complete? → Verification plan/preview
                                              no ↓                  ↓
                                         Report gaps         Spend approval → Collect/review → Expand
```

| Situation | Required next action |
|---|---|
| Topic/hashtag discovery | Run `hashtag_generate build-prompt` before external searches; read its prompt, save the agent JSON and run `import-response`. Supplied-video and explicitly requested feed/creator analysis retain their own routes. |
| No hashtag history | Treat absent `sources/viral/hashtag-performance.json`, or no matching platform history, as a cold start. Propose a small set from application, process and workshop-role vocabulary, marked `generated_unverified`. Do not manufacture win/lose evidence. |
| Past analyses | Include available campaign-local `sources/viral/` analyses as optional historical feedback: useful hooks, failed branches, relevance judgments and limitations. Never borrow another campaign's results or treat prose as structured hashtag win/lose history. |
| Analysis bounds | `build-prompt` includes up to five newest readable Markdown/JSON analysis/report/review/relevance/evaluation/creator-style files, each at most 20,000 bytes. Skipped/limited context produces warnings. Raw/calls/expansion folders, prompts and the current run are excluded. Paths/hashes are recorded; missing analyses never block. |
| Search budget | Default to no preliminary web probes. If optional seed evidence is needed, declare a finite query budget before searching, record each query, and stop on repeated login walls/tag aggregations; no paraphrased retries or platform switching to avoid a gate. Web snippets alone do not validate hashtag usage. |
| Context gaps | Only missing/invalid product goal/catalog blocks research collection. Report the exact product input to repair; do not request brand/safeguard/customer/hypothesis files. After repair, rebuild the prompt and regenerate/import candidates. |
| No spend approval | With complete context, inspect a supported provider schema/current price, save the verification plan and preview; request the exact ceiling. Stop before paid execution, not before candidate generation. |

## Artifact contract

Every run lives in `local/<slug>/sources/viral/<run-id>/` and is instantiated from the templates below. `schema_version: 1` applies to new runs only; historical runs are not rewritten or validated.

```text
<run-id>/
├── brief.md
├── report.md
└── artifacts/
    ├── manifest.json, relevance.json, context.json, candidates.json, plan.json
    ├── prompt.md, response.json, response.raw.json, schema.json, reviews
    └── raw/, calls/, expansion/, creator-style analyses
```

| Artifact | Content | Template |
|---|---|---|
| `brief.md` | Human-readable brief; exact bytes are hashed into the manifest. | [brief](../assets/viral-research/brief.md) |
| `artifacts/manifest.json` | Run identity, mode, structured brief mirror, sources, files with hashes, budget, timing. All embedded file paths remain relative to the run root, not this file's parent. | [manifest](../assets/viral-research/manifest.json) |
| `artifacts/relevance.json` | Per-observation evidence, promotion decision, relevance outcome, qualification; paths relative to the run root. | [relevance](../assets/viral-research/relevance.json) |
| `report.md` | Required for every outcome/platform: coverage, shortlist or no-result finding, costs, failures and marketing recommendation. | [report](../assets/viral-research/report.md) |
| `artifacts/creator-style-<slug>.md` | Style DNA analysis when creator mode runs; root report links it. | Free-form |
| Supporting files | Save all agent JSON responses, schemas, prompts, raw/call receipts, reviews and expansion outputs inside `artifacts/`; only brief/report are root files. | Public CLIs return their exact output paths. |
| Legacy runs | Flat context/plan/manifest/call/expansion data resumes in place; never manually move receipts, change hashes or break provenance. Mixed flat/nested artifact layouts are rejected. Campaign-wide `hashtag-performance.json` remains outside individual runs. | No automatic migration. |

| Field group | Required content |
|---|---|
| Identity | `schema_version`, `run_id` equal to the folder name, `campaign` equal to the resolved slug, `mode` (`discovery` or `creator`). |
| Brief link | `brief_version`, `brief_sha256` of the exact `brief.md` bytes; regenerate after every edit. Hashes are integrity checks, not approvals. |
| Brief fields | Objective, product context file, market, language, industry/application, query families or seeds, publication window, limits, stopping rule. Buyer roles unsupported by the catalog stay unknown; no hypothesis file is required. |
| Sources | Stable ID, type, URL/query/seed, requested versus supported filters, collection time, raw path; paid calls also record provider run URL, status and charge. |
| Files | Every raw and derived artifact listed with its SHA-256; source and original-record paths must resolve inside the run folder. |
| Budget | Currency, decimal-string approved ceiling, actual charge, approval reference when paid sources are used. |
| Timing | Collection and review start/end, or null. Measured elapsed time is not active work. |

## Brief

| Field | Required decision |
|---|---|
| Market and language | Target country/region recorded separately from language. Clarify whether “nationality” means market location, language community or citizenship; never infer citizenship. |
| Industry and buyer | Ground applications in the product catalog; unsupported buyer roles/problems stay unknown rather than triggering customer-profile research. Fit means audience relevance, not a matching hashtag. |
| Age | Do not target or score viewer age. An age-band business constraint belongs in the campaign's own policy, never in research targeting; viewer-age keys are never recorded. |
| Hypothesis | Not required for research. A legacy manifest field may be null or `pending`; never load past posts to fill it. |
| Context | `product-marketing.json` only: goal/catalog. Missing brand, customer, loop or hypothesis files never block collection. |
| Window and limits | Publication window, max results, max pages, spend ceiling and stopping rule agreed before collection. Unknown dates stay null. |

## Sources

| Strategy | Access | Control |
|---|---|---|
| Free search | `websearch`, `webfetch`, public creator pages | Record query, source, rank and collection time; no provider receipts. |
| Supplied links | User-provided URLs and seeds | Confirm why each seed serves the brief; a creator's name is not demographic evidence. |
| Paid enrichment | `glasser` endpoints only after inspecting the schema and current price per call | Record approval reference, provider run URL, status and charge; stay under the ceiling. |
| Feed exploration | `uv run python -m tools.facebook_agent --cdp <ENDPOINT> reels --page-id <PAGE_ID> --limit <1-50> --output <NEW_JSON>` | Label as personalized exploration, not a national ranking; no query, region, language or date filters and no view counts. |
| Capability gaps | Requested versus supported filters are recorded per source | Disclose unsupported targeting or choose another approved source; never invent parameters. |
| Coverage | Spread the bounded budget across families and seeds | Report candidates and useful results per source; deduplicate before measuring yield. |

## Promotion gate

[Reels selection](reels-selection.md) owns promotion `allow`/`exclude`. Default allowance is preserved: only explicit promotion of an unrelated offer excludes an observation. Eligibility is not a recommendation.

## Review

| Layer | Record | Rule |
|---|---|---|
| Promotion | Decision, offer, evidence, reason | Policy only; unclear promotion stays allowed. |
| Relevance | Observed language/provenance, industry/buyer link, outcome `audience_shortlist` / `inspiration_only` / `not_shortlisted` | Explain the link. Entertainment may stay allowed without qualifying for the shortlist. Never pad the list with weak fits. |
| Qualification | Criterion source, named metric, operator, threshold, observed value, result, baseline | Only named metrics and allowlisted comparisons. Missing inputs yield `unknown`, never a pass. |
| Evidence medium | `caption`, `transcript`, `audio`, `video` or `mixed` | Captions support caption analysis; transcripts support speech; only inspected video supports visual sequence. |
| Unknowns | Missing metrics, audio, dates, demographics | Persist nulls; never substitute zero or infer views from likes. |

## Verifiable video handoff

```text
Observed video permalink + saved source evidence
                    ↓
         Relevance + metric qualification
                    ↓
      Linked report rows → Linked chat results
                    ↓ missing links/evidence
             Partial / unverified, not complete
```

| Requirement | Rule |
|---|---|
| Link-first results | In both `report.md` and the final chat response, return one row per video with a clickable direct platform video permalink, record ID, platform/creator, observed engagement metrics and observation time, relevance/qualification, and access/evidence limitations. A link to the report may supplement, never replace, the actual video links. |
| Link provenance | Copy the exact permalink observed in saved source evidence into `relevance.json` `records[].url` and the report/chat row. Never guess a URL from a concept, fabricate an ID/handle or present a hashtag/search/profile page as an individual video. Deduplicate by video identity. |
| Inspectability | State what was inspected: video, caption, transcript or search snippet. Distinguish an observed URL from a successfully opened video. Login walls/deleted/inaccessible videos remain explicitly limited leads, not inspected/verified videos; a working link alone does not prove engagement or audience fit. |
| Source trace | Each report row references the saved source path and record index/order, with collection time. Keep actual raw search/provider results separate from derived `relevance.json`; the analysis cannot cite itself as raw evidence. Missing raw evidence is disclosed, not reconstructed from an invented search receipt. |
| Qualification | Show the observed metric/value, criterion and result; missing metrics/thresholds yield `unknown`, never `qualified`. Do not claim viral status from a trend label or concept. Preserve nulls and distinguish popularity from a baseline-supported viral outlier. |
| No concept substitution | Invented shot concepts, adaptation ideas and plausible hooks belong in an explicitly labeled ideas section, never the observed-video list. Product-specific demonstrations/materials/performance claims require inspected source evidence; catalog fit does not establish what a video showed. |
| Partial outcome | If fewer than the requested number have traceable links and the required qualification, return the actual count and links, list missing evidence separately, and state `partial`/`blocked`/`unverified`. Zero verifiable results means say so; never turn ten concepts into ten found videos. Stop at existing source/spend limits and request approval before further paid collection. |
| Prior analyses | Historical claims without video links, source traces or metrics remain unverified ideas. Do not promote them into observed seeds, verified counts or product facts merely because they appear in past `sources/viral/` reports. |
| Final self-check | Before claiming completion, compare each delivered URL/ID with its source and `relevance.json`, confirm report/chat contain the links, recount deduplicated qualified results, and disclose unknowns. This is an agent obligation, not a mechanically enforced tool gate. |

## Zero-result and failed-platform reports

| Requirement | Rule |
|---|---|
| Always close | Create/update root `report.md` before handoff on success, partial, no-results, blocked, failed, cancelled or interrupted work. Every requested platform/run gets its own report; another platform's success never erases a failed attempt. If no query ran, state that explicitly. |
| Automatic fallback | `build-prompt` creates brief/report starters; executed `collect` updates its automatic report from receipts. `hashtag_verify report --project <PROJECT> --run <RUN>` regenerates missing/automatic reports from saved context/plan/receipts without network. Authored reports are preserved. The agent must finalize the report; preview commands remain read-only, and an exception/interrupt may leave a pending starter until reconciled. |
| Evidence | List platform, intended Vietnam market and language, exact queries, provider/endpoint/filters, observed collection dates, attempted/empty/error/usable counts, receipt links, actual reported charges versus approved budget, and unknowns. No returned videos means no video links; link the query receipts instead. |
| Separate failure types | Distinguish empty successful responses from authentication/login walls, unsupported filters/endpoints, timeouts, provider errors, budget stops and semantically irrelevant videos. Technical collection failure is not evidence that Vietnamese buyers are absent. |
| Useful decision | State a practical campaign recommendation such as “deprioritize Instagram hashtag discovery for this Vietnam paper/printing campaign with the tested provider/queries; no usable videos found.” Record the next evidence that would justify revisiting it. No automatic repeated probes, extra spend or switch of platform. |
| Market limits | A bounded query/provider sample cannot establish that Instagram is a dead market or that marketing cannot work across Vietnam. Do not turn retrieval yield into platform-wide audience size, demand, buyer-conversion or sales conclusions. Preserve the negative result for future runs with its scope and uncertainty. |

## Qualification and baselines

| Concept | Rule |
|---|---|
| Reuse criterion | Campaign policy governs reuse eligibility. A record is reusable only when its criterion passes and it is audience-shortlisted. |
| Popularity | Single-snapshot totals are observed popularity. Storing them needs no baseline. |
| Viral outlier | A `viral_outlier` claim requires an available baseline with method, cohort, window and sample size. |
| Baselines | Never invent a cohort. Unknown baselines still permit storage, not outlier claims. |
| Comparisons | Compare same platform, format, publication-age range and topic when observations allow; show cohort size. |
| Growth | Resample only when permitted; compute change over the actual observation interval. |

## Adaptation worksheet

| Field | Entry |
|---|---|
| Source mechanism | Observed hook, pacing, reveal, payoff or CTA |
| Observed evidence | Caption quote, transcript timestamp or inspected video range |
| Campaign problem | Buyer problem from the brief |
| Factual substitution | Product fact being substituted, with claims the campaign can support |
| Original shot concept | New treatment; inspiration is not permission to reuse footage |
| Rights check | Origin, permission or licensing decision |
| Primary test variable | One variable and the metric that will judge it |

## Creator style

| Requirement | Rule |
|---|---|
| Campaign reason | State why studying this creator serves the resolved objective; refuse otherwise. |
| Research | Minimum four targeted searches for real samples, each with query, platform and source. |
| Synthesis | Eight dimensions: voice/persona, rhythm and length, hook and opening, vocabulary, structure, emotional register, platform habits, distinctive fingerprint. |
| Evidence | Verbatim quotes only, at least one per dimension and 3–5 in a sample bank. Never invent quotes. |
| Qualification | Creator mode does not require video-engagement qualification, but provenance, identity and file checks still apply. Reuse of a creator-mode record as a viral reference is blocked. |
| Output | Translate findings into campaign-specific tests consistent with brand voice; do not search unrelated platforms by default. |

## Pilot reporting

| Metric | Requirement |
|---|---|
| Unique useful yield | Deduplicated shortlisted observations, not raw captures. |
| Coverage | Candidates and useful results per source and query family. |
| Cost | Actual charge against the approved ceiling, with receipts. |
| Timing | Measured elapsed collection and review, plus active work if tracked separately. |
| Unknown rate | Share of records with missing metrics, audio or dates; never treat unknowns as zero. |
| Confounding | Same-source strategies compare cleanly; different sources are a confounded workflow comparison. |
| Review status | Name the human reviewer and date; agents cannot self-approve. |

## Boundaries

| Constraint | Rule |
|---|---|
| Read-only collection | Public CLIs only. No inline Python/subprocess wrappers, private-helper probes, raw CDP/JS or feed engagement controls. |
| Enforcement limits | Artifact checks cannot prove audience fit, human approval, media inspection or that a threshold came from the owner. Raw platform commands remain callable; instructions are not guards. |
| Preservation | Keep raw files unchanged; analyses reference them by path and order. |
| Claims | Personalized recommendations are not a national ranking; likes are not views; one snapshot is not a trend. |
| Capability gaps | Missing targeting or filters require disclosure, an approved alternative source, or a requested tool change with tests — never silent substitution. |

## Routing checks

| Request | Required behavior |
|---|---|
| No campaign named | Ask which existing `local/<slug>/`; run nothing. |
| Ambiguous or multiple campaigns | Ask; do not merge briefs or reuse seeds. |
| Resolved campaign | Read its product goal/catalog before collection; artifacts land only in that campaign. |
| Campaign missing research context | Ask only for missing product goal/catalog or request-level platform/market decisions; do not invent them or demand brand setup. |
| Creator style with no campaign reason | Refuse until the reason is supplied. |
