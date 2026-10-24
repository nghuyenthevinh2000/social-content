# Viral research brief: `<run-id>`

| Field | Value |
|---|---|
| Run ID | `<run-id>` |
| Brief version | `<v1>` |
| Campaign | `local/<campaign-slug>` |
| Objective | `<buyer_research \| audience_growth \| creative_inspiration>` |
| Hypothesis | `null` (not required for research) |
| Market | `<country or region>` |
| Language | `<language>` |
| Industry | `<industry>` |
| Buyer | `<catalog-supported role, or unknown>` |
| Context files | `product-marketing.json` (`marketing_goal`, `product.catalog`) |
| Past analyses | `<included sources/viral/ analysis paths, or none; historical feedback only>` |
| Query families | `<local-language problem, role, application, location, synonym>` |
| Seeds | `<user-confirmed creator, community or business>` |
| Publication window | `<start> to <end>`, or `null` when unknown |
| Collection limits | `<max results>, <max pages>` |
| Spend ceiling | `<currency> <decimal amount>` and approval reference |
| Stopping rule | `<stop at N candidates, N empty query families, or a spend limit>` |

| Rule | Requirement |
|---|---|
| Mirrors the manifest | Keep `manifest.json` `brief` fields identical to this file; regenerate `brief_sha256` after edits. |
| No viewer-age targeting | Record age only as an explicit business constraint outside targeting; viewer-age keys are never recorded. |
| Permitted gaps | Unknown publication dates stay `null`; missing campaign context blocks collection, not validation. |
| Placeholders | Replace every `<...>` before collection; this template is an example, not evidence. |
| Paid sources | Set `sources[].type` to `paid_api` and add `provider.run_url`, `provider.status` and `provider.charge`; free sources keep `provider: null`. |
| Hash | Store the SHA-256 of the exact `brief.md` bytes, e.g. `shasum -a 256 brief.md`, and regenerate it after every edit. Hashes are integrity checks, not approvals. |
