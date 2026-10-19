# Facebook target-audience research: implementation and capability test

**Date:** 2026-10-16  
**Status:** Proposed; catalog inspected and initial web discovery completed. No paid provider runs or Facebook browser collection performed.  
**Implementation home:** `tools/facebook_agent/`

## 1. Objective and real test case

The user sells **colored paper and ink** to wedding-invitation businesses. The research task is to discover and understand these B2B buyers, not couples purchasing finished invitations.

**Seed keywords:** `thiệp cưới`, `xưởng in thiệp cưới`.

**Desired outcome:** A verifiable table of relevant businesses/discussions, evidence of their role in invitation production, expressed material needs, and provisional audience segments. Keyword matches alone do not establish customer fit or buying intent.

Pipeline: **keyword → community/business discovery → posts/comments → evidenced author role → material/purchasing needs → provisional segment → owner validation**.

## 2. Existing tool and implementation boundary

`tools/facebook_agent/cli.py` currently exposes `doctor` and `post`; it has no search or research command. `browser.py` wraps the shared `CDPBrowser`, and `dom.py` centralizes locators. Existing publishing is personal-profile-only and must remain unchanged.

Add read-only research within this package, not a separate crawler project. Start with manual seed URLs plus bounded provider collection; automate Facebook keyword discovery only after a feasibility check establishes that the accessible UI can support it reliably and permissibly. Do not build a generalized provider framework, database, scheduler, or lead-outreach system.

X/Twitter and other platforms can later corroborate findings through their own tools. They are outside this Facebook implementation.

## 3. Acquisition method

| Stage | Concrete technique for this business | Data to retain | Audience decision |
|---|---|---|---|
| Keyword expansion | Search seed phrases separately, then `in thiệp cưới`, `phôi thiệp cưới`, `giấy mỹ thuật`, `giấy màu in thiệp`, `mực in thiệp cưới`; add machine/material terms only when actually observed | Exact query, purpose, language, discovery date | Distinguish invitation shoppers from manufacturers, print shops, designers, resellers, and material suppliers |
| Community discovery | Facebook group search/manual review; supplementary indexed-web queries such as `site:facebook.com/groups/ "xưởng in thiệp cưới"` | Group URL/name, relevance evidence, access/rules, seller density | Identify trade communities rather than wedding consumer communities; names alone are insufficient |
| Business discovery | Inspect relevant pages/accounts advertising invitation production, wholesale blanks, printing, or finishing | Page URL and short evidence quote, production versus resale role, unknowns | Shortlist potential paper/ink buyers without assuming every invitation retailer operates equipment |
| Post collection | Bounded recent group/page posts from approved known URLs; compare recent and popular views where supported | Post ID/permalink, source/query provenance, text, date, collection method, pagination state | Locate explicit production work, supply requests, equipment context, recurring needs, and commercial promotions |
| Keyword filtering | Preserve original Vietnamese text; match accented and accent-normalized variants locally; inspect context and expand vocabulary | Matched term, relevant excerpt, exclusion reason, review status | Remove unrelated wedding chatter; do not treat a failed literal match as proof of irrelevance |
| Thread collection | Collect selected relevant post comments and, where supported, bounded replies | Parent/post references, quote, date, author research ID, missing-thread notices | Discover questions about stock, color consistency, ink compatibility, delivery, or supplier choice **only if expressed** |
| Author-role review | Review the post and minimal relevant business context; tag mixed/unknown roles | Evidence-backed manufacturer/printer, designer/reseller, supplier, end customer, unknown | A supplier's promotion maps competition; it is not evidence of a buyer's unmet need |
| Segment formation | Group independent evidence by operation, input purchased, purchasing trigger, and required proof | Supporting IDs, distinct-author counts, counterexamples, uncertainty | Candidate production-shop and reseller segments; no guessed company size, budget, equipment, or purchasing volume |
| Validation | Ask the user to review fit against existing customers; later use opt-in interviews and authorized sales data | Confirmed/rejected fits and reasons, consented interview findings | Determine who actually purchases colored paper or compatible ink rather than who merely mentions invitations |

Paper and ink require separate qualification: a workshop may use pre-colored stock but outsource printing, or print on supplied blanks. Record each input's fit independently. Ask the user for paper specifications, ink technology/compatibility, geographic coverage, and minimum order before ranking commercial fit.

## 4. Glasser feasibility findings

Catalog checked via authenticated CLI search/inspect on 2026-10-16. Task reference: `tsk_c6c3772d3d5082ab`. Prices are snapshots, not guarantees; inspect again before a paid run. No data run was executed.

| Capability | Inspected provider / endpoint | Contract and current price | Implication |
|---|---|---|---|
| Group metadata | ScrapeCreators `/v1/facebook/group`, v2 | Requires `url`; optional `group_id`; $0.00188/call | Can attempt enrichment of a known group, not group keyword discovery |
| Group posts | ScrapeCreators `/v1/facebook/group/posts`, v2 | Requires `url`; optional `cursor`, `group_id`, `sort_by`; $0.00188/call | URL-first collection with pagination; no keyword or date filter in the inspected input schema |
| Post details | ScrapeCreators `/v1/facebook/post`, v2 | Requires `url`; $0.00188/call | Useful for checking an indexed-web seed against actual retrieved content |
| Comments | ScrapeCreators `/v1/facebook/post/comments`, v2 | Requires `url`; optional `cursor`, `feedback_id`; $0.00188/call | Thread context; actual field completeness and public/group coverage need a live test |
| Profile/page posts | ScrapeCreators `/v1/facebook/profile/posts`, v2 | Requires `url`; optional `cursor`, `pageId`; $0.00188/call | Candidate business context; bounded business inspection, not unrestricted personal-history crawling |
| Public group alternative | Apify `/apify/facebook-groups-scraper`, v1 | One HTTPS group URL in `startUrls`; up to 10 recent posts; async; $0.006/result, cap $0.075; NO_RESULT $0.002 | Small public-group alternative if primary collection fails; separately approve costs |
| Endpoint named “Facebook search” | ScrapeCreators `/v1/facebook/adLibrary/search/ads`, v2 | Requires `query`; $0.00188/call; ad-library filters | **Ad search, not organic audience discussion search.** Keep advertiser intelligence separate |
| Organic keyword/group discovery | Not confirmed by inspected contracts | Catalog searches returned many mixed candidates; search was not exhaustive | Use manual/DOM/web discovery initially; do not claim catalog-wide absence or fabricate support |

For the inspected ScrapeCreators endpoints, NO_RESULT is charged $0.00188; PROVIDER_ERROR, TIMED_OUT, and INTERNAL are listed as $0.00. A completed run can still contain no useful content. Report both provider outcome and actual charge.

Provider output schemas are unspecified/raw. Normalization must wait for an approved pilot payload; do not assume author IDs, dates, or cursor fields exist. A provider listing is not a guarantee of lawful access, completeness, private-group coverage, or live reliability.

References: [group posts](https://docs.scrapecreators.com/v1/facebook/group/posts), [group info](https://docs.scrapecreators.com/v1/facebook/group), [post details](https://docs.scrapecreators.com/v1/facebook/post), [comments](https://docs.scrapecreators.com/v1/facebook/post/comments), [profile posts](https://docs.scrapecreators.com/v1/facebook/profile/posts), [ad search](https://docs.scrapecreators.com/v1/facebook/adLibrary/search/ads), [Apify group posts](https://apify.com/apify/facebook-groups-scraper/api). Glasser inspect contracts, not vendor documentation alone, govern broker inputs and billing.

## 5. Actual capability test the user can verify

### Initial discovery already performed

Public web search returned these candidate Facebook URLs. They are **unverified search-result leads**, not confirmed buyers or successfully collected Facebook records. Search ranking and snippets are incomplete and may be stale.

| Discovery query | Candidate | Verifiable URL | What still needs checking |
|---|---|---|---|
| `site:facebook.com/groups/ "xưởng in thiệp cưới"` | HỘI IN THIỆP CƯỚI — Wedding invitation | https://www.facebook.com/groups/inthiepcuoidep/posts/9722049874508650/ | Group access, actual post relevance, trade versus consumer content |
| `site:facebook.com "thiệp cưới" "giấy màu" "mực"` | Thiệp Cưới Giá Tốt — Cần Thơ; result titled “Các mẫu thiệp thiết kế năm 2025” | https://www.facebook.com/thiepcuoigiatotcantho/posts/1155869239873702/ | Whether the page performs printing or resells; any actual paper/ink demand |
| Same query | In Thiệp Cưới / Thiệp Laser / Thiệp 3D / Thiệp Popup | https://www.facebook.com/thiepcuoigift/ | Actual operator role and product/material fit |
| Same query | Máy In Thiệp Cưới / Thiệp Mời / Phong Bì / Decal | https://www.facebook.com/mayinthiep/ | Likely equipment-related discovery source; distinguish supplier from target buyer |

An initial query may return irrelevant countries and generic wedding posts. Log those exclusions; do not cherry-pick them into a successful audience claim.

### Proposed bounded paid pilot — requires approval

**Maximum: five ScrapeCreators calls at $0.00188 each = $0.00940**, at inspected pricing. Re-inspect before admission. No pagination, retries, alternative provider calls, or automatic fallback beyond this approval. Empty results may still cost money.

| Call | Action | What it verifies |
|---|---|---|
| 1 | Known group metadata | Whether the discovered group URL resolves and yields usable metadata |
| 2 | One group-post page, chronological where supported | Whether actual group content, source links, and usable text are returned; locally check the seed terms |
| 3 | One known business-page post | Whether indexed discovery can be resolved into verifiable content |
| 4 | One relevant post's comments, if a usable post was found | Whether discussion context and author references are accessible; skip if no relevant thread exists |
| 5 | One candidate business page's posts | Whether business role can be evidenced; not a full profile crawl |

Capture provider run URLs, statuses, exact charges, limited-access raw artifacts, normalized records, and short human-reviewable excerpts. Never substitute “COMPLETED” for evidence that the desired content was actually retrieved.

### Pass/fail and user verification

| Test dimension | Pass evidence | Failure / limitation reporting |
|---|---|---|
| Retrieval | Returned post text with a source URL the user can open | Empty, inaccessible, removed, or unsupported; retain actual provider response |
| Keyword relevance | Context genuinely concerns invitation production; quote shows relevance | Mere keyword occurrence or wedding-consumer content is not a pass |
| Author role | Explicit printing/workshop/business evidence with source | Unknown or resale-only; no inferred manufacturing claim |
| Paper fit | Explicit material use/need consistent with the user's supplied specifications | Not established; invitation production alone is insufficient |
| Ink fit | Explicit printing technology or compatibility consistent with the user's ink | Not established; no assumption that every printer uses the same ink |
| Audience learning | At least one supported business-role/need observation with clear limits | Do not claim a validated segment or lead-generation coverage from five calls |
| Reproducibility | Input, retrieval timestamp, endpoint/version, run URL, outcome, charge | Missing provenance blocks use as verified evidence |

The pilot tests **URL-based retrieval and qualification**, not automated organic keyword discovery. The keyword-to-seed stage is web/manual discovery until the DOM search experiment passes. Report each stage separately.

## 6. Minimal implementation sequence

| Phase | Changes in `tools/facebook_agent/` | Acceptance gate |
|---|---|---|
| 0. Real capability spike | Execute the approved pilot using existing Glasser CLI; inspect payloads before writing collectors | User-verifiable sources and honest coverage report; stop if data is unusable |
| 1. Seeded collection MVP | Add `research.py`; extend `cli.py` with proposed `research collect`; reuse `AgentError`, stdlib JSON/CSV and subprocess, existing Glasser CLI | Explicit seed URLs, endpoint allowlist, call/spend limits, no browser needed for provider collection; validate arguments before execution |
| 2. Evidence export | Export normalized records and a blank/manual-review coding table; keep authored interpretation separate | Each observation links to evidence; unknowns preserved; local keyword matching documented |
| 3. Native discovery feasibility | Inspect Facebook group/search UI using existing `Browser` and shared CDP; add feature locators in `dom.py` only if supported | Read-only bounded searches work against observed UI; otherwise retain manual seed workflow |
| 4. Bounded native discovery | Proposed `research discover` with keyword matrix, result/scroll/time caps and query provenance | No endless scrolling, no joining groups, no ambiguous selector guessing; serialized browser operations |
| 5. Audience report | Agent/manual synthesis from reviewed evidence, not an additional model integration | Claims cite IDs; buyers separated from suppliers/consumers; owner reviews commercial fit |

Proposed CLI names are **not implemented commands**. Keep initial inputs simple: keywords plus explicit URLs and limits. Do not add an automatic bulk research loop or paid fallback. Preserve `doctor`/`post` behavior and existing exit codes; optional provider setup must not become a dependency of publishing.

## 7. Output contract

Store a run directory under an explicit operator-selected output path; use a new directory or refuse overwrite. Keep customer research artifacts out of version control by default.

| Artifact | Required fields/content |
|---|---|
| `manifest.json` | Research purpose, original keywords, seed URLs, approved budget/calls, timestamps, provider task/run references, pagination/coverage limits, actual charges, stop reason |
| `evidence.jsonl` | Evidence ID, source URL, parent/source ID if available, group/page context, exact relevant text, published date or null, retrieval date, query/seed provenance, collection method, author research ID or null, missing fields |
| `coding.csv` | Evidence ID, relevance, evidenced role, production/resale/unknown, paper fit, ink fit, explicit need, buying stage, reviewer, interpretation and uncertainty |
| `audience-report.md` | Search coverage/exclusions, candidates with evidence links, situation-based segments, distinct-author counts within sample, counterexamples, unknowns and next validation questions |

Use stable research-local pseudonyms only when a source author identifier is available; do not merge different people by display name or match identities across platforms. Keep personal contact details out of normalized output. Private raw data needs restricted access and a retention decision, not automatic indefinite storage.

Audience table: **Business/operation → source/query → evidenced role → paper requirement → ink technology/requirement → procurement trigger → evidence IDs → uncertainty → owner fit decision**. Missing requirements remain unknown.

## 8. Guardrails and tests

- Read-only research: no posting, reactions, joining groups, DMs, contact harvesting, or outreach. No bypassing login/challenges/private access or provider restrictions.
- Public providers cannot be assumed to inherit the browser's private-group permissions. Do not send private-group data to a third party without separate authorization.
- Shared-browser commands execute sequentially. Reuse existing CDP lifecycle; preserve user tabs and never close the browser/context. Stop for manual login/challenges.
- Enforce call and decimal-string budget caps before each paid request. Persist run identifiers and idempotency keys before retries; reconcile ambiguous outcomes rather than making new paid requests blindly.
- Stop pagination on repeated cursor/no progress, time/result/call limit, or unavailable cursor. Date coverage is observed, not guaranteed by a local 90-day filter.
- Offline tests: CLI validation before browser/network use; Vietnamese matching with originals preserved; deduplication without display-name merging; raw-provider normalization with missing fields; budget/empty-result accounting; pagination limits; partial/error output; no publishing calls from research.
- Browser fixtures only if DOM discovery is built: group results, post expansion, ambiguous controls, challenge/access denial, and tool-owned tab cleanup. Regression run: `uv run python -m unittest discover -s tools/facebook_agent/tests -v`.
- Update `tools/facebook_agent/README.md` only when commands are implemented, clearly separating supported research from publishing and documenting coverage limits. No live publishing in research tests.

## 9. Next decision

Approve or reject the bounded **five-call / $0.00940** pilot. Then inspect its actual data before deciding whether provider collection is sufficient or native keyword discovery is worth implementing. The user should supply paper specifications, ink compatibility, service geography, and whether resellers also count as targets before any commercial ranking.
