# Product-aware Reels selection

## Understand the offer first

| Source, relative to repository root | What to establish |
| --- | --- |
| User-supplied product directory | Use the requested product; do not assume every project sells the same thing. |
| `local/paper-ink-product/product-marketing.json` | Current catalog, applications, differentiation, marketing goal, and factual limits. |
| `local/paper-ink-product/posts/hypothesis.json` | Current campaign offer and success criteria. It explicitly says colored paper, not standalone ink. |
| `local/paper-ink-product/customer/profile.json` | Buyer roles, prospect hypotheses, applications, and offer. Do not treat customer-research exclusions as exclusions of entertainment references. |

| Current project understanding | Grounded context; reread sources each session |
| --- | --- |
| Offer | Ivory 230 for bags/boxes; Ánh Kim 180 for invitations/certificates/envelopes; Nhung đỏ 120 for Tết fans, lucky-money envelopes, ritual covers, and calligraphy. Do not invent measurement units. |
| Goal | Find distribution partners and printing businesses willing to trial colored paper. |
| Buyers | Printing workshops and relevant distributors; invitation printers are a researched prospect segment, not universally confirmed buyers. |
| Differentiation | Modified cassava-starch binder helps color adhere to paper. Plant origin alone does not prove safety or environmental certification. |
| Creative research | Entertainment can supply hooks, pacing, reveals, movement, and emotion without being about printing or proving buyer intent. |

## Apply a default-allow gate

```text
Observed Reel + current product context
                  ↓
Explicit product/service promotion supported by evidence?
       no / unclear → ALLOW
       yes → Is the promoted offer unrelated to our product context?
                         no / unclear → ALLOW
                         yes → EXCLUDE
```

| Decision | Rule |
| --- | --- |
| `allow` | Default, including unclear intent, missing captions, unavailable audio, and incomplete observation. State evidence limits without moving the Reel to a review-only bucket. |
| `exclude` | Both explicit selling/promotion and an unrelated offer are supported by observed evidence. Identify the offer and quote the promotional evidence. |
| Explicit evidence | Enrollment invitation, course/app promotion, purchase link, affiliate offer, product-specific booking/order CTA, price/discount tied to an offer, or a clear spoken/on-screen sales pitch. A Sponsored label alone does not identify what is sold. |
| Not sufficient | English language, an English lesson, school/company name, logo alone, branded account, generic Follow control, music attribution, hashtags, attractive people, or a product incidentally appearing. |
| Unknown | Record uncertainty and allow. Do not invent a hidden funnel, landing-page purpose, or sales pitch. |
| Evidence coverage | Caption-only collection cannot establish audiovisual content. Use video/audio evidence only when actually inspected; do not claim unseen dancing, demonstrations, or speech. |
| Separate ranking | Apply this gate before ranking eligible inspiration. Low relevance or low engagement is not an unrelated-promotion exclusion. |
| Local allowance | Allow-list means inclusion in the research output only. Never click Facebook favorites, follows, likes, hides, or recommendation controls. |

| Jev integration | Contract |
| --- | --- |
| Command | `uv run python -m tools.facebook_agent judge-reels --input observations.json --product-dir local/paper-ink-product --output judgments.json --limit 10 --dry-run` |
| Live calls | Explicit `--approve-api`, without `--dry-run`; requires `TYPESAFE_API_KEY`. Sends observed text and reduced product context to TypeSafe, not leads or cookies. Paid requests are bounded by `--limit`, not by a dollar cap. |
| Model judgments | Independent Nouls for explicit promotion and unrelated offer; Choices select exact observed lines for promotional and offer evidence. Code requires all probabilities/selection confidences at least 0.90 and both selected source lines to exclude. |
| Evidence schema | Runtime stores `promoted_offer_evidence` as source text, not a generated product name, plus `promotion_evidence`, model, token usage, signals, and limitations. Do not present a source span as a normalized product label. |
| Validation | Threshold is provisional; offline tests do not establish semantic accuracy. Jev's documented English-heavy training makes Vietnamese validation especially important. |
| Errors | Persist completed judgments; fail visibly on API errors. No silent allowance of unprocessed records. Never equate a dry run with model classification. |

## Examples

| Observation | Decision | Reason |
| --- | --- | --- |
| Woman dancing; ordinary-life clip; travel scenery | Allow | No explicit unrelated offer; direct paper relevance is unnecessary. |
| English joke or vocabulary lesson, even from a school account | Allow | Topic and account name do not establish explicit promotion. |
| “Đăng ký khóa IELTS, giảm 30%, inbox nhận tư vấn” | Exclude | Explicit enrollment/discount for an unrelated English course. |
| “Download our English app and get a personalized learning plan” | Exclude | Explicit promotion of an unrelated language-learning app. |
| Dancing clip with “Buy this skincare set through my affiliate link” | Exclude | Entertainment does not override explicit unrelated product promotion. |
| “Follow for more”; unclear caption; no observed sales pitch | Allow | Generic audience growth or uncertainty is not an unrelated offer. |
| Paper, printing, or invitation demonstration | Allow | Relevant context; track competitor/source identity separately without claiming buyer intent. |

## Preserve decisions

| Field per observation | Required content |
| --- | --- |
| `url`, `observed_at`, source file/order | Link to the actual feed observation; retain encounter order separately from ranking. |
| `decision` | `allow` or `exclude`; do not introduce `review` as an exclusion fallback. |
| `promoted_offer` | Identified product/service, or `unknown` / `none observed`. |
| `promotion_evidence` | Exact observed quote or specific audiovisual observation; source and medium. Empty if no explicit evidence. |
| `reason` | Why the evidence establishes an unrelated promotion, or why the default allowance applies. |
| `limitations` | Missing audio/video, truncated caption, unverified publication date, or other evidence gaps. |

| Reporting | Requirement |
| --- | --- |
| Storage | Keep raw observations unchanged. Save decisions separately next to the collection, with the product-context paths used. |
| Retrospective correction | Do not exclude the previous English-school recommendations solely by creator/topic. Reassess individual Reels for explicit promotional evidence. |
| Completion | Count allowed Reels, not observations. Continue bounded sampling if needed; disclose a shortfall instead of padding with excluded content. |
| Claims | Personalized recommendations are not a nationwide leaderboard. Displayed likes are not views; observing today does not prove publication within seven days. |
