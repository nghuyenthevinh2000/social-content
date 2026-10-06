# Solo-founder market research: lessons from Reddit posts and replies

Research date: 2026-10-06.

## Bottom line

Research should help you choose a customer, understand a buying situation, and decide what to test next. A convincing market report, a large response count, or enthusiastic feedback cannot do those jobs alone.

The replies strengthen the original post-only analysis, but also add important qualifications: pricing cannot be separated from audience selection; directional B2B research can be useful without population-level precision; recruitment requires trust; and some apparently inconsistent findings measure different things.

## Scope and evidence limits

- Starting dataset: `local/market-research/marketresearch_posts.json`, containing 150 posts dated April 15–October 6, 2026. All stored reply arrays are empty. Those zeros are not evidence that the original discussions had no comments.
- Selected 19 threads relevant to the earlier lessons and adjacent founder questions. This is a purposive selection, not a representative sample of the subreddit or founders.
- Retrieved 152 distinct comment bodies through TikHub via Glasser, plus an RSS view of the unfamiliar-market thread. Comments include original-poster follow-ups, brief reactions, and substantive advice; 152 is not the number of independent experts or validated observations.
- Direct Reddit JSON access returned HTTP 403; the RSS route initially worked, then returned HTTP 429. Used the paid API with permission: 25 completed calls at $0.001 each, total **$0.025**. The provider returned HTTP 200 and usable comment data for all 25 calls.
- Coverage is incomplete. Some trees still expose pagination; others return fewer bodies than Reddit's reported count even when `hasNextPage` is false. Removed content, collapsed branches, and provider behavior cannot be disentangled from these responses. Do not describe this as a complete comment export.
- Reddit identities, professional credentials, firsthand experiences, vendor claims, and reported outcomes were not independently verified. Votes indicate local reception, not truth or market prevalence.
- Vendor-branded accounts and people offering services contribute to several discussions. Their advice can be useful, but product recommendations are not independent comparative evidence.

Each finding below separates retrieved advice from the recommended founder action. Comment links are the public citations; the appendix links the provider records used to retrieve them.

## 1. Start with a decision and the cost of being wrong

**What the replies add:** In the business-decisions thread, CaptCriollo asks what decision the research should support before designing it: who to target, where to find them, or which offer to choose. CuriousMindLab adds the need to connect a finding to money. The B2B-validity discussion argues that the importance and economics of a segment should determine how much rigor to buy.

**Founder action:** Write a short research brief:

1. Decision: what am I choosing?
2. Assumption: what must be true for that choice to work?
3. Evidence: what observation would change my mind?
4. Stakes: what does a wrong decision cost?
5. Budget: how much time or money is worth spending to reduce that risk?

For a reversible landing-page experiment, directional evidence may suffice. For regulated product development, inventory commitments, or an expensive enterprise integration, more verification is justified. Do not demand the same confidence for every decision.

Sources: [decision-first research — CaptCriollo](https://www.reddit.com/r/Marketresearch/comments/1ttytmd/what_makes_research_actually_useful_for_business/op60h27/); [research rigor versus segment economics — xkmasada](https://www.reddit.com/r/Marketresearch/comments/1txgk8a/question_about_b2b_market_research_validity/opvtrnr/).

## 2. Use market reports for context; identify buyers at company level

**What the replies add:** ParticularOddDan recommends starting with active firms and observable activity: importing, hiring, tendering, trade-press mentions, and customs records. Another commenter cautions against abandoning reports and statistics entirely. These are complementary approaches, not a reason to reject all desk research.

The fertility-benchmarking replies add another distinction: a clinic is not necessarily an independent purchasing unit. One commenter suggests investigating ownership groups and centralized research buying. That ownership claim is a lead to verify, not an established fact about the whole fertility market.

**Founder action:** Maintain a prospect table with company, relevant activity, existing workaround, likely user, budget owner, parent organization, and contact route. Build a bottom-up estimate from plausible purchasing accounts, not merely locations or individual users.

For B2B, a rough revenue scenario is: reachable qualified accounts × plausible conversion × annual contract value. Show several scenarios and label conversion assumptions; do not present them as measured forecasts. For consumer businesses, distinguish initial purchases from repeat demand.

Sources: [company-level demand signals](https://www.reddit.com/r/Marketresearch/comments/1vod5sy/ever_get_a_market_report_that_looks_great_then/p4d666w/); [possible centralized clinic purchasing](https://www.reddit.com/r/Marketresearch/comments/1wxc9ep/what_would_a_private_healthcare_company_pay_for_a/pdvl1un/).

## 3. Discover workflows, not abstract lists of problems

**What the replies add:** The SurveyMonkey-branded account suggests asking people to walk through an existing task, including manual steps and workarounds, rather than asking them to name problems. The unfamiliar-market thread recommends combining a landscape map, competitors, public sources, and real-world feedback. Its original poster also reports that paid AI produced generic answers rather than reliable detail about UK business workflows.

**Founder action:** Use desk research to learn enough vocabulary to conduct a useful conversation, then investigate concrete recent examples:

- What triggered the task last time?
- Walk me through what happened, including handoffs.
- Where did you repeat work, wait, or make an exception?
- What have you already tried, and why did you keep or abandon it?
- Who experiences the problem, who benefits from fixing it, and who approves spending?

Ask to see a redacted artifact or demonstration with permission. One family's workflow is a hypothesis about a segment, not validation of it. Interview people outside your immediate network, including people whose current process works well.

Sources: [workflow walkthroughs](https://www.reddit.com/r/Marketresearch/comments/1wh7805/how_to_find_real_problems/pa6sqeg/); [outside-in industry research](https://www.reddit.com/r/Marketresearch/comments/1uczfl6/how_do_you_research_a_market_youve_never_worked_in/ot9fng3/); [original poster on generic AI output](https://www.reddit.com/r/Marketresearch/comments/1uczfl6/how_do_you_research_a_market_youve_never_worked_in/ot7x92k/).

## 4. Recruitment is a trust problem as well as a channel problem

**What the replies add:** Recruitment suggestions include panels, specialist communities, LinkedIn groups with leader permission, usability platforms, and paid Reddit advertising leading to a screener. One person reports using paid Reddit recruitment for a niche audience; no acquisition cost or conversion benchmark is supplied.

A separate thread delivers a sharper lesson: commenters explicitly object to AI-written language and perceive the research request as disguised product development. The poster acknowledges using AI to save typing time. Whatever the technical merits of the question, the presentation reduces willingness to help.

**Founder action:** Write a short, specific request yourself. Disclose that you are exploring a business idea, explain why this person is relevant, state the time commitment, and distinguish research from a sales pitch. Follow community rules and get permission where required. Do not conceal your affiliation to evade anti-promotion rules.

Track contacted people, qualified replies, scheduled conversations, completed conversations, and reasons for refusal. Offer reasonable compensation for time when appropriate, not for positive feedback. A low reply rate might reflect the channel, message, audience, or credibility; it does not isolate demand.

Sources: [group permission and incentives](https://www.reddit.com/r/Marketresearch/comments/1sz2tct/market_research_where_to_find_users/oj6ihhy/); [reported paid Reddit recruitment](https://www.reddit.com/r/Marketresearch/comments/1sz2tct/market_research_where_to_find_users/oj18msq/); [pushback on AI-written outreach](https://www.reddit.com/r/Marketresearch/comments/1w41r3w/whats_the_last_project_that_went_sideways_and_how/p74v2nh/).

## 5. Define the buyer before trying to discover a price ceiling

**What the replies add:** In the premium watch-strap discussion, Saffa1986 distinguishes motorsport fans from wealthy watch enthusiasts: one group may care about the story but lack purchasing fit; another may have money but prefer factory straps. The original poster narrows the hypothesis to people interested in both watches and motorsport, while acknowledging the size and supported price are unknown.

The commenter discusses two methods: Van Westendorp's open-ended price perceptions, which depend on category knowledge and framing, and Gabor–Granger purchase-intent questions at specified prices. They warn that generic panels and clicks can misrepresent a niche luxury audience. Their proposed 0.5% and 5% conversion scenarios are sensitivity checks, not observed conversion rates.

The healthcare-report replies do not validate the proposed £3k–£5k price. Instead, they question buyer relevance, data access, competitive alternatives, and why customers would pay rather than assemble public information themselves.

**Founder action:** First establish who buys the category, what else competes for that budget, and why your difference matters. Use stated-price exercises to refine a hypothesis, then make a real offer: a paid manual pilot, a scoped proposal to the budget holder, or a clearly explained preorder with delivery and refund terms.

Treat acceptance, refusal, timing, procurement constraints, and objections as evidence. A survey answer about buying is still not a purchase. A pilot payment establishes some willingness to pay, not retention or scalable acquisition.

Sources: [pricing methods and audience mismatch](https://www.reddit.com/r/Marketresearch/comments/1u2c2g2/how_do_you_find_the_price_ceiling_for_a_product/oqweml9/); [narrower audience hypothesis](https://www.reddit.com/r/Marketresearch/comments/1u2c2g2/how_do_you_find_the_price_ceiling_for_a_product/oqxkpx2/); [benchmarking product objections](https://www.reddit.com/r/Marketresearch/comments/1wxc9ep/what_would_a_private_healthcare_company_pay_for_a/pdt42t8/).

## 6. Match sampling precision to the question—not a magic response count

**What the replies add:** The B2B-validity discussion separates total-market estimates from individual segment estimates. Commenters recommend concentrating on meaningful target segments, accepting directional insights in hard-to-reach populations, or oversampling important segments rather than demanding equal precision everywhere.

**Founder action:** Choose among three different research jobs:

| Job | Useful early approach | What it does not establish |
|---|---|---|
| Understand a workflow | Purposeful interviews with relevant people | Percentage of the market with that workflow |
| Estimate prevalence | Appropriate sampling and a well-designed survey | Purchase behavior merely from stated intent |
| Test an offer | Real proposals or purchase experiments | Population demand from a few early customers |

The thread's suggestions of roughly 30 respondents per segment or 50–100 niche completes are practitioner heuristics, not general validity thresholds. Likewise, 384 responses does not automatically imply representativeness or a ±5% margin of error: sampling design, assumptions, nonresponse, and the statistic being estimated matter. For a niche B2B product, go deep on the actual buyers before surveying the entire surrounding industry.

Sources: [directional niche B2B findings](https://www.reddit.com/r/Marketresearch/comments/1txgk8a/question_about_b2b_market_research_validity/opwuole/); [focus on the segment that matters](https://www.reddit.com/r/Marketresearch/comments/1txgk8a/question_about_b2b_market_research_validity/opy8xk6/).

## 7. Preference, usefulness, and buying intent are separate measurements

**What the replies add:** The inconsistent-results poster describes changing “which would you prefer” to “which better fits your needs” as a slight wording change. Commenters disagree: a Ferrari can be preferred while a minivan meets someone's needs. Other replies recommend checking sample composition, prior questions, stimuli, mobile rendering, answer coding, and recruitment before assigning a cause.

**Founder action:** Decide what you need to measure before writing the question. Someone liking an idea does not mean it fits their workflow, displaces their current solution, or warrants spending.

When comparing experiments, record the exact wording, audience, stimulus, recruitment source, question order, and response coding. Change one thing at a time where feasible. The thread identifies plausible explanations for the reported discrepancy; it does not prove which caused it.

Sources: [preference versus needs](https://www.reddit.com/r/Marketresearch/comments/1tquq57/inconsistent_results/ooj2vn0/); [sampling, context, and stimulus checks](https://www.reddit.com/r/Marketresearch/comments/1tquq57/inconsistent_results/ooj5bo6/).

## 8. Cheap responses can create expensive false confidence

**What the replies add:** Quality discussions recommend multiple checks rather than trusting verified identity or readable prose. One researcher reports answers that passed conventional checks but had concerning device or behavioral indicators. Another commenter points out that long surveys and poor compensation can themselves encourage low-effort participation.

**Founder action:** Keep research short and relevant, screen for actual experience, ask specific questions, review inconsistencies, and inspect a small initial batch before scaling collection. For purchased panels, ask how participants are recruited and screened, how quality is assessed, and what replacement policy applies.

Do not automatically reject someone for a VPN, fast completion, repeated scale values, or text that “sounds AI-written.” These are possible signals, not proof of fraud. Set exclusion rules beforehand where possible, review ambiguous cases, and report what was removed and why. Collect only the personal or device data genuinely needed and permitted.

Sources: [limits of content-only review](https://www.reddit.com/r/Marketresearch/comments/1wm4o1k/participant_verification_is_not_the_same_as/pc0k65t/); [layered quality checks](https://www.reddit.com/r/Marketresearch/comments/1sx06y8/anyone_else_annoyed_with_data_quality_issuesai/oik85at/); [incentive and effort concern](https://www.reddit.com/r/Marketresearch/comments/1sx06y8/anyone_else_annoyed_with_data_quality_issuesai/oiurt4p/).

## 9. Use AI to assist research, not manufacture customer evidence

**What the replies add:** The synthetic-panel thread is strongly critical, but a later exchange makes a useful distinction: simulated respondents can pressure-test an interview guide without becoming a measurement of customer demand. The original poster accepts that narrower use while warning about pressure to replace research.

The real-data thread recommends AI-assisted deterministic analysis and checking both scripts and output. The AI-workflow thread includes a concrete account of theme-tagging NPS comments, alongside warnings about conversational drift and excessive agreement. These are reported workflows, not model-performance benchmarks.

The AI-moderation discussion is also mixed. Several commenters raise concerns about senior B2B respondents, domain shorthand, probing, and engagement. One reports success with a tool in B2C but explicitly has not tested B2B. Some participants have commercial interests in human research. The evidence does not justify saying AI moderation never works.

**Founder action:** Use AI to prepare questions, organize source-backed notes, suggest competing explanations, draft analysis code, and identify passages to revisit. Verify quotations and calculations against originals. Respect consent, confidentiality, and the data provider's terms before uploading material.

Personally conduct the first important buyer conversations when feasible: learning the vocabulary and noticing unexpected answers are part of founder discovery. If testing AI moderation, compare depth and participant experience against human interviews before expanding it. Keep generated hypotheses explicitly separate from observed evidence.

Sources: [synthetic as rehearsal, not measurement](https://www.reddit.com/r/Marketresearch/comments/1w2yszo/synthetic_panel_n_is_not_the_same_as_human/p7e1ba7/); [original poster acknowledges the distinction](https://www.reddit.com/r/Marketresearch/comments/1w2yszo/synthetic_panel_n_is_not_the_same_as_human/p7ixnv6/); [deterministic analysis and confidentiality](https://www.reddit.com/r/Marketresearch/comments/1wczp3t/tips_on_using_ai_with_real_collected_market/p92m50l/); [reported NPS tagging workflow](https://www.reddit.com/r/Marketresearch/comments/1sn3yw7/for_researchers_what_are_the_real_use_cases_for/ognifqm/); [B2B domain shorthand](https://www.reddit.com/r/Marketresearch/comments/1wtqcjm/anyone_tested_ai_moderated_interviews_for_b2b/pcwhukh/); [B2C-only positive experience](https://www.reddit.com/r/Marketresearch/comments/1wtqcjm/anyone_tested_ai_moderated_interviews_for_b2b/pdawmf8/).

## 10. Keep an evidence log and refresh the affected finding

**What the replies add:** Research-refresh commenters suggest reviewing individual findings rather than expiring an entire study. Pricing changes may invalidate value-for-money conclusions without invalidating onboarding observations. Other triggers include new competitors, buyer-role changes, and sales win/loss reasons that contradict earlier research. A commenter proposes five refresher interviews as a cheap check—not a guaranteed sufficient sample.

The statistics-validation thread recommends checking the primary source, method, bias, calculation, and independent corroboration, then preserving a short audit trail. The data-handoff thread adds record-count reconciliation around important exports and joins.

**Founder action:** Use one simple table:

| Claim | Source and date | Segment and context | Confidence and limitation | Decision | Recheck trigger |
|---|---|---|---|---|---|
| Buyers manually reconcile invoices | Interview and observed redacted sheet | Small agencies | Workflow observed; prevalence unknown | Test a manual service | Different segment or workflow |
| Buyers will pay $100/month | Interview reaction only | Same segment | Unconfirmed stated intent | Offer a paid pilot | Actual acceptance or refusal |

Put interview dates beside reused quotes. Preserve original data separately from summaries. When moving between files or tools, check record counts, unique identifiers, and the denominators behind numbers that inform decisions. Investigate unexplained differences rather than assuming they are rounding.

Sources: [refresh finding by finding](https://www.reddit.com/r/Marketresearch/comments/1wq0gie/how_do_you_decide_when_customer_research_needs/pc000a1/); [win/loss and buyer-role triggers](https://www.reddit.com/r/Marketresearch/comments/1wq0gie/how_do_you_decide_when_customer_research_needs/pcue6t3/); [source audit trail](https://www.reddit.com/r/Marketresearch/comments/1sww4ms/whats_your_process_for_validating_a_stat_before/oiir1kw/); [reconcile important handoffs](https://www.reddit.com/r/Marketresearch/comments/1w41r3w/whats_the_last_project_that_went_sideways_and_how/p81ssjj/).

## A small founder research cycle

This is a recommended operating plan, not a process tested by these threads. The numbers are starting points, not statistical thresholds.

1. **Choose:** one segment, one buying situation, one risky assumption, and a decision deadline.
2. **Orient:** spend a limited desk-research block learning alternatives, terminology, buying roles, and constraints.
3. **Recruit:** identify roughly 30 relevant prospects and send honest, personalized requests through permitted channels.
4. **Investigate:** aim for 8–12 conversations, including people with good existing solutions. Record recent behavior, consequences, alternatives, and decision authority.
5. **Offer:** where appropriate, make a scoped paid-pilot offer to 3–5 qualified buyers. Do not force a buying test before feasibility or safety questions are resolved.
6. **Review:** separate observed facts, stated intentions, and your interpretations. Investigate contradictory examples.
7. **Decide:** continue, narrow the segment, change the offer, or stop. A recurring costly workaround and credible commitments justify a next experiment; they do not yet prove product-market fit.

Set the stop or revision conditions before you start. Examples: the supposed buyers have no authority to buy; the pain rarely occurs; existing solutions are good enough; delivery costs exceed realistic prices; or interviews reveal a different problem consistently worth solving.

## What the deeper reading changed

- **Stronger:** decision-first research, company-level demand investigation, and workflow walkthroughs now have direct reply support.
- **More specific:** pricing is primarily an audience-and-alternative question before it is a price-method question.
- **New:** personally written, transparent recruitment matters; AI-looking outreach can lose respondents before any research begins.
- **Corrected:** inconsistent survey results are not necessarily evidence that research failed; two questions may measure different constructs.
- **Qualified:** small B2B samples can guide decisions, but cannot automatically support precise market percentages. Synthetic responses can rehearse research, but do not establish demand. AI moderation should be evaluated by audience and task, not dismissed or adopted wholesale.
- **Still unproven:** the healthcare report's proposed prices, a scalable acquisition channel, actual pilot conversion, and any particular product opportunity. No retrieved thread establishes those outcomes.

## Retrieval appendix

“Bodies” counts distinct API-returned comments with readable content across the retrieved pages. “Reported” is the provider's Reddit comment count. A last-page value of “no” does not explain or resolve count discrepancies. RSS supplied additional context for thread 10 but is not included in these API counts.

| # | Thread | Bodies / reported | Last page has more? | Provider record |
|---|---|---|---|---|
| 1 | Fertility benchmarking pricing | 4 / 4 | No | [Run](https://app.glasser.ai/runs/c0f1a0fb-5023-45a6-b694-69628af77b50) |
| 2 | AI-moderated B2B interviews | 16 / 26 | Yes | [Page 1](https://app.glasser.ai/runs/c883aae1-baa6-4c20-b3fa-087840fa6d22), [page 2](https://app.glasser.ai/runs/fd467882-744c-4d0e-8029-7c6b07c843d4) |
| 3 | Updating customer research | 11 / 15 | No | [Page 1](https://app.glasser.ai/runs/38b44f7a-1fa6-46d6-9b65-9fa4d9c253a8), [page 2](https://app.glasser.ai/runs/683d6a05-09fb-4c90-8820-40cc7e422696) |
| 4 | Participant verification versus response quality | 2 / 6 | No | [Run](https://app.glasser.ai/runs/35c0c96b-3dc9-4ad0-83c4-0cf9d7f16f46) |
| 5 | Finding real problems | 6 / 7 | No | [Run](https://app.glasser.ai/runs/e8e113a8-12d6-4a61-8e68-e688985c1122) |
| 6 | AI with collected survey data | 8 / 16 | No | [Run](https://app.glasser.ai/runs/45ffe1dc-b18c-4bb0-94bb-98d44a219592) |
| 7 | Projects going sideways and handoff errors | 7 / 7 | No | [Run](https://app.glasser.ai/runs/1f94b771-a2a3-4e10-befd-f2b5068e30dc) |
| 8 | Synthetic panels and sample size | 16 / 29 | Yes | [Page 1](https://app.glasser.ai/runs/416065c6-c535-40a9-bad5-1502f298efc1), [page 2](https://app.glasser.ai/runs/078af365-7f22-4f75-818d-8734edf90e22) |
| 9 | Attractive reports versus actual selling | 2 / 5 | No | [Run](https://app.glasser.ai/runs/03e9642d-4073-4e72-bb41-bae3aea85ea0) |
| 10 | Researching an unfamiliar market | 8 / 25 | Yes | [Run](https://app.glasser.ai/runs/ec0f1a8c-e707-40a6-950b-0634171aa69f) |
| 11 | Premium watch-strap pricing | 3 / 3 | No | [Run](https://app.glasser.ai/runs/28e53154-59eb-4024-b573-0193e4134892) |
| 12 | B2B sample validity | 8 / 9 | No | [Run](https://app.glasser.ai/runs/46d9699d-fcd7-489b-bb1d-8c3e1674d936) |
| 13 | Research useful for business decisions | 5 / 15 | No | [Run](https://app.glasser.ai/runs/a28e3c3a-37a4-4fc0-8b74-703d7d69f31c) |
| 14 | Inconsistent survey results | 13 / 14 | No | [Page 1](https://app.glasser.ai/runs/7e9dbc6a-a700-404b-a49d-a49f9207ce8e), [page 2](https://app.glasser.ai/runs/a92d266c-cb20-4884-ab28-064f00e542f1) |
| 15 | Sharing a research survey | 3 / 8 | No | [Run](https://app.glasser.ai/runs/8780c4cf-3317-4ca9-a177-d225c85a401f) |
| 16 | Finding research participants | 14 / 22 | No | [Page 1](https://app.glasser.ai/runs/5fdf6109-53da-41c4-98c7-bda1ef6fcee6), [page 2](https://app.glasser.ai/runs/87ab3acc-1c2e-445d-9ca9-7a9dab94363f) |
| 17 | Data-quality issues and AI | 8 / 27 | Yes | [Run](https://app.glasser.ai/runs/361ba8b6-080f-45b4-9250-409e5c91ca4f) |
| 18 | Validating statistics | 2 / 4 | No | [Run](https://app.glasser.ai/runs/fd05e59b-b838-451e-98f3-9f7dc16c1015) |
| 19 | Actual AI research workflows | 16 / 48 | Yes | [Page 1](https://app.glasser.ai/runs/13325cf2-c765-4854-b013-aa3ff7666b2f), [page 2](https://app.glasser.ai/runs/a8d139db-b2ba-41b2-896c-cf69227df7fd) |

All runs completed and returned comment data. The six second-page calls brought spending to the approved cap; remaining branches were not fetched. Provider records are private to the Glasser workspace; the Reddit comment links above are public.
