# Reels selection policy

## Understand the campaign offer first

| Source, relative to the resolved campaign | What to establish |
|---|---|
| `product-marketing.json` | Only required factual context: `marketing_goal` and `product.catalog`. No brand, customer-profile, hypothesis or loop-file prerequisite. |
| Research request | Requested platforms, application, market/language and collection limits; never import another campaign's scope. |
| Explicit Facebook feed request only | The public feed CLI needs the exact Page ID as an operational argument; ask if unavailable. This is not a general analyzer context requirement. |

| Understanding | Grounded context; reread sources each session |
|---|---|
| Offer | Whatever the resolved campaign states. Do not import another project's catalog, and do not invent measurement units. |
| Goal | `marketing_goal` from the product brief. |
| Buyers | Use only roles supported by catalog applications; otherwise keep unknown. Never infer confirmed buyers. |
| Differentiation | Catalog-stated facts only; plant origin or similar labels do not prove safety or certification. |
| Creative research | Entertainment can supply hooks, pacing, reveals, movement and emotion without being about the campaign's product or proving buyer intent. |
| Unknowns | Missing campaign context is a blocker to collection, not a gap to fill by assumption. |

## Apply a default-allow gate

```text
Observed Reel + resolved campaign context
                  ↓
Explicit product/service promotion supported by evidence?
       no / unclear → ALLOW
       yes → Is the promoted offer unrelated to the campaign offer?
                         no / unclear → ALLOW
                         yes → EXCLUDE
```

| Decision | Rule |
|---|---|
| `allow` | Default, including unclear intent, missing captions, unavailable audio and incomplete observation. State evidence limits without moving the Reel to a review-only bucket. |
| `exclude` | Both explicit selling/promotion and an unrelated offer are supported by observed evidence. Identify the offer and quote the promotional evidence. |
| Explicit evidence | Enrollment invitation, course/app promotion, purchase link, affiliate offer, product-specific booking/order CTA, price/discount tied to an offer, or a clear spoken/on-screen sales pitch. A Sponsored label alone does not identify what is sold. |
| Not sufficient | Language, a lesson, school/company name, logo alone, branded account, generic Follow control, music attribution, hashtags, attractive people, or a product incidentally appearing. |
| Unknown | Record uncertainty and allow. Do not invent a hidden funnel, landing-page purpose or sales pitch. |
| Evidence coverage | Caption-only collection cannot establish audiovisual content. Use video/audio evidence only when actually inspected; do not claim unseen dancing, demonstrations or speech. |
| Separate ranking | Apply this gate before ranking eligible inspiration. Low relevance or low engagement is not an unrelated-promotion exclusion. |
| Local allowance | Allow-list means inclusion in the research output only. Never click Facebook favorites, follows, likes, hides or recommendation controls. |

| Agent review | Contract |
|---|---|
| Collection | `uv run python -m tools.facebook_agent --cdp <ENDPOINT> reels --page-id <PAGE_ID> --limit <1-50> --output local/<slug>/sources/viral/<run-id>/reels.json` |
| Page identity | `PAGE_ID` comes from the resolved campaign's `loop/config.json`; the browser must already be switched into that Page. |
| Selection | The agent reads the campaign context and captured evidence directly. Do not invoke a separate Jev/TypeSafe decision layer or replace it with a keyword blacklist. |
| Audience evidence | Cite observed language content or actually inspected speech/context. No numeric audience gate. A name that looks like the target market does not establish audience fit. |
| Evidence | Save selected URLs, source order/timestamps, caption evidence, allow/exclude reasons and limitations separately from raw observations. Unclear promotion remains allowed. |
| Timing | Prefix collection with `/usr/bin/time -p`; record review start/end timestamps in `manifest.json` and report measured elapsed collection and review separately. Never present collection-only time as total discovery time. |
| Relevance handoff | Promotion output is eligibility only. Relevance outcomes and qualification are recorded in `relevance.json` under the [artifact contract](viral-analyzer.md#artifact-contract); an allowed record is not automatically shortlisted. |
| Historical runs | Preserve prior decisions and timing reports as historical evidence; they are not the current selection workflow. |

## Examples

| Observation | Decision | Reason |
|---|---|---|
| Person dancing; ordinary-life clip; travel scenery | Allow | No explicit unrelated offer; direct product relevance is unnecessary. |
| Joke or vocabulary lesson, even from a school account | Allow | Topic and account name do not establish explicit promotion. |
| “Đăng ký khóa IELTS, giảm 30%, inbox nhận tư vấn” | Exclude | Explicit enrollment/discount for an unrelated course. |
| “Download our app and get a personalized learning plan” | Exclude | Explicit promotion of an unrelated product. |
| Dancing clip with “Buy this skincare set through my affiliate link” | Exclude | Entertainment does not override explicit unrelated product promotion. |
| “Follow for more”; unclear caption; no observed sales pitch | Allow | Generic audience growth or uncertainty is not an unrelated offer. |
| Demonstration of the campaign's own category | Allow | Relevant context; track competitor/source identity separately without claiming buyer intent. |

## Preserve decisions

| Field per observation | Required content |
|---|---|
| `url`, `observed_at`, source file/order | Link to the actual feed observation; retain encounter order separately from ranking. |
| `decision` | `allow` or `exclude`; do not introduce `review` as an exclusion fallback. |
| `promoted_offer` | Identified product/service, or `unknown` / `none observed`. |
| `promotion_evidence` | Exact observed quote or specific audiovisual observation, with source and medium. Empty if no explicit evidence. |
| `reason` | Why the evidence establishes an unrelated promotion, or why the default allowance applies. |
| `limitations` | Missing audio/video, truncated caption, unverified publication date or other evidence gaps. |

| Reporting | Requirement |
|---|---|
| Storage | Keep raw observations unchanged. Save decisions separately next to the collection, naming the campaign-context paths used, and record them in `relevance.json` with `schema_version: 1`. |
| Evidence coverage | Report what the medium can support: caption text alone cannot establish speech, dancing or pacing; state the audio/video inspection gap per record. |
| Retrospective correction | Do not exclude prior recommendations solely by creator or topic. Reassess individual Reels for explicit promotional evidence. |
| Completion | Count allowed Reels, not observations. Continue bounded sampling if needed; disclose a shortfall instead of padding with excluded content. |
| Claims | Personalized recommendations are not a nationwide leaderboard. Displayed likes are not views; observing today does not prove recent publication. |
| Relevance | Selection output is eligibility only. Apply [viral research](viral-analyzer.md) relevance review before any shortlist or ranking. |
