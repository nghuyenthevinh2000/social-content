# Viral research report: `<run-id>`

```text
Brief → sources → promotion gate → relevance review → qualification → shortlist/report
```

| Coverage | Recorded value |
|---|---|
| Campaign, brief version | `<local/slug>`, `<v1>` |
| Outcome / requested count | `<complete / partial / blocked / unverified>` / `<requested number>`; complete only with traceable links and required qualification |
| Sources attempted / useful | `<n>` / `<n>`, with per-source yield |
| Unique useful yield | `<n>` deduplicated observations |
| Unknown-demographic or unknown-date rate | `<n>/<n>` |
| Spend | `<currency> <actual> of <approved>` |
| Collection timing | `<elapsed>` measured with `/usr/bin/time -p` |
| Review timing | `<elapsed>` and `<active work>` if measured separately |
| Human review status | `<not reviewed \| reviewed by NAME on DATE>` |

## Inspectable video results

| Video link / record ID | Platform / creator | Observed metrics / observation time | Relevance / qualification | Evidence / access limits | Saved source |
|---|---|---|---|---|---|
| `<clickable Markdown link using the exact observed direct video permalink>` / `<r-id>` | `<platform>` / `<observed creator or unknown>` | `<named metric=value or unknown>` / `<observed timestamp or unknown>` | `<audience_shortlist / inspiration_only>`; `<criterion and pass/fail/unknown>` | `<video/caption/transcript/snippet inspected; opened or login-blocked; missing evidence>` | `<raw source path, record index/order>` |

| Unverified leads / exclusions | Reason / missing evidence |
|---|---|
| `<record ID, observed permalink if available, or none>` | `<missing URL, raw source, metrics, inaccessible video or relevance failure; not counted as verified>` |

| Cohort limitation | Note |
|---|---|
| Comparable cohort | `<platform, format, publication-age range, topic/market>`; sample size `<n>` |
| Baseline | `<method, window, sample size>` or `unknown` |
| Viral-outlier claim | `<allowed only with an available baseline>` |
| Confounders | `<different sources, feed personalization, missing metrics>` |

## Adaptation worksheet

| Field | Entry |
|---|---|
| Source mechanism | `<observed hook, pacing, reveal, payoff or CTA>` |
| Observed evidence | `<caption quote, transcript timestamp, or inspected video range>` |
| Campaign problem | `<buyer problem from the brief>` |
| Factual substitution | `<product fact being substituted; no unsupported claims>` |
| Original shot concept | `<new treatment; no reused footage>` |
| Rights check | `<origin, permission, or licensing decision>` |
| Primary test variable | `<one variable and the metric that will judge it>` |

| Boundary | Rule |
|---|---|
| User handoff | Repeat the actual video links, metrics, relevance and limitations in the final chat response. Local file links and record IDs alone do not let the user verify the videos. |
| No links / insufficient evidence | State the actual qualified count and a partial/blocked/unverified outcome. Never invent URLs, treat a concept as a found video, claim unknown metrics passed, or cite this analysis as raw source evidence. |
| Evidence scope | Captions support caption analysis; transcripts support speech; only inspected video supports visual claims. |
| Approval | This report is a recommendation. Content approval and publishing gates remain separate. |
| Reuse | Cite a record only when its criterion passes and it is audience-shortlisted. |
