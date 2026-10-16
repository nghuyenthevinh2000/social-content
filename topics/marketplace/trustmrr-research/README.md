---
name: trustmrr-research
summary: TrustMRR product and customer research. Purpose and documentation for topics/marketplace/trustmrr-research.
tags:
- trustmrr-research
submodules:
  local/: TrustMRR top-100 research — October 7, 2026. Purpose and documentation for
    topics/marketplace/trustmrr-research/local.
  build_report.py: Render reviewed notes and dated source evidence into private research
    artifacts.
  collect.py: Private TrustMRR snapshot and bounded official-site research; no paid
    services.
  pilot-2026-10-07.csv: File pilot-2026-10-07.csv
  pilot-2026-10-07.md: TrustMRR five-company research pilot
---

# TrustMRR product and customer research

The five-company pilot is in `pilot-2026-10-07.md` and its companion CSV.
Bulk source data and research outputs are private, under the git-ignored
`local/` subdirectory here. Do not publish API-derived datasets
without the permission required by TrustMRR's acceptable-use policy.

The completed October 7 deliverables are [local/README.md](local/README.md),
[market-summary.md](local/market-summary.md), [top-100-dossiers.md](local/top-100-dossiers.md),
[top-100.csv](local/top-100.csv), and [summary.json](local/summary.json).
All 100 selected entries have reviewed evidence/limits; 42 are anonymous.
Purchase/renewal reasons are hypotheses, not verified customer interviews.
Use a fresh output directory for future snapshots: the collector resumes
from dated cache files and must not silently relabel them as current data.

## Collection

Configure `TRUSTMRR_API_KEY` in the root `.env`. Never commit or print the key.
The script uses the repository's existing `python-dotenv` dependency.

```sh
python3 topics/marketplace/trustmrr-research/collect.py check
python3 topics/marketplace/trustmrr-research/collect.py snapshot
python3 topics/marketplace/trustmrr-research/collect.py research
```

The snapshot exhausts a minimum-MRR filter, lowers the threshold if needed,
and selects 100 by descending MRR with a slug tie-break. It does not confuse
the API's revenue sort or `rank` field with an MRR ranking. The live API on
October 7 returned monetary amounts and applied filters in USD, despite
documentation describing cents; confirm units before future runs.

API calls are paced for standard keys and resume from cached pages. Source
collection uses bounded downloads, respects official-site robots rules,
records failures, and reads public TrustMRR Markdown profiles. It fetches at
most a homepage plus four linked pricing/customer/product pages per public
business. Collection is not a substitute for reviewing the resulting text.

## Research standards

- Distinguish the user, purchaser, budget owner, and end beneficiary.
- Separate provider-backed aggregate metrics from founder-edited descriptions.
- Record verification freshness; an expired feed is not current performance.
- Label named paid tiers as vendor-reported unless transactions are verified.
- Logos, testimonials, free users, and subscription counts do not prove a
  named paying customer or unique customer count.
- Preserve anonymous/stealth entries; do not infer undisclosed identities.
- Price comparisons and purchase/retention explanations require sources or
  explicit hypothesis labels.
- Record inaccessible pages and evidence gaps rather than manufacturing an answer.
- No bulk outreach, paid enrichment, publication, or product cloning is part
  of this research task.
