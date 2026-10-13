# Growth Indicators Research Plan: Competitor Platforms

**Purpose:** Judge how fast each competitor in [competitor-research-report.md](competitor-research-report.md) is growing, how healthy that growth is, and what it means for our entry timing, pricing and moat.

**Core questions**

1. Is the market growing, and which segment (UGC ads, avatars, creative analytics, schedulers) is growing fastest?
2. Which competitors are accelerating, flat, or declining?
3. Is anyone moving toward our loop (generate → post → measure → regenerate)? Growth plus a roadmap shift is the biggest threat signal.
4. Is demand price-sensitive enough to support a $49–$99/mo entry against Creatify AdMax ($299/mo)?

---

## 1. Scope: Platforms to Track

| Tier | Platforms | Why |
| --- | --- | --- |
| **Primary** | Higgsfield, Creatify, Arcads, MakeUGC | Direct generation competitors |
| **Adjacent (loop stages)** | Syllaby, Motion, Foreplay, Triple Whale, Ayrshare, Buffer, Metricool | Own a stage of our loop |
| **Potential entrants** | Meta/TikTok native AI tools, CapCut/Canva, HeyGen, Icon, Poppy AI | Could absorb the loop |
| **Benchmark** | DIY stack (ChatGPT + CapCut + Sheets) | The "do nothing new" alternative |

---

## 2. Indicator Framework

Indicators are grouped by how reliable they are. **Private-company revenue and user numbers are rarely public**, so we triangulate from several weak signals and score our confidence in each.

### A. Demand and Attention (public, free, quick)

| Indicator | Source | What it shows |
| --- | --- | --- |
| Search interest trend (12–24 mo) | Google Trends | Brand awareness trajectory |
| Monthly web visits and trend | Similarweb, Semrush, Ahrefs (free tiers) | Traffic scale and growth rate |
| Keyword volume for "[brand] alternative / pricing / review" | Ahrefs, Google Keyword Planner | Purchase intent |
| App store ranking/reviews (if any) | App Store, Play Store | Consumer-side traction |
| Social following growth | X, LinkedIn, YouTube, TikTok, IG (manual snapshots) | Marketing momentum |
| Community size and activity | Reddit, Discord, Facebook groups | Engaged users |

### B. Revenue and Funding (public when disclosed)

| Indicator | Source | What it shows |
| --- | --- | --- |
| Funding rounds, valuation, investors | Crunchbase, PitchBook, press releases | Capital and market confidence |
| Disclosed ARR/MRR, user counts | Founder posts on X/LinkedIn, interviews, podcasts | Scale (often self-reported) |
| Headcount and hiring trend | LinkedIn, job boards | Investment direction (which roles are hiring) |
| Pricing changes over time | Wayback Machine | Pricing power, monetization shifts |

### C. Product Velocity (public, high signal for threat assessment)

| Indicator | Source | What it shows |
| --- | --- | --- |
| Changelog and release cadence | Product blogs, X, Product Hunt | Shipping speed |
| Roadmap direction (analytics? auto-posting? agents?) | Changelog, job postings, founder talks | Convergence toward our loop |
| Integration additions (Meta, TikTok, Shopify APIs) | Docs, integration pages | Distribution/metrics capability |
| Model/partner announcements | Press, X | Technology dependencies |

### D. Customer Health (public but noisy)

| Indicator | Source | What it shows |
| --- | --- | --- |
| Review volume and rating trend | G2, Trustpilot, Capterra, Product Hunt | Satisfaction and adoption |
| Complaint themes over time | Reddit, X, Trustpilot | Churn drivers and unmet needs |
| Case studies and logo wall growth | Websites, Wayback | Enterprise traction |
| Affiliate/creator program size | Websites, YouTube sponsorship volume | Growth marketing spend |

### E. Paid Marketing Activity

| Indicator | Source | What it shows |
| --- | --- | --- |
| Active ads, ad count and longevity | Meta Ad Library, TikTok Creative Center | Spend intensity, which angles work |
| YouTube sponsorships/influencer volume | YouTube search, Social Blade | Acquisition channels |

### F. Market-Level Indicators

| Indicator | Source | What it shows |
| --- | --- | --- |
| Category size and CAGR (AI video, UGC ads, creator economy) | Analyst reports, Statista, Grand View | Tailwind or saturation |
| Short-form ad spend trend | Meta/TikTok earnings, eMarketer | Budget available to customers |
| New entrant count | Product Hunt, Crunchbase, Reddit | Competition density |

---

## 3. Per-Competitor Scorecard (template)

| Metric | Higgsfield | Creatify | Arcads | MakeUGC | Syllaby | Motion |
| --- | --- | --- | --- | --- | --- | --- |
| Monthly visits (now / 6 mo ago / % change) | | | | | | |
| Google Trends slope | | | | | | |
| Total funding / last round date | | | | | | |
| Disclosed ARR/users (source, date) | | | | | | |
| Headcount (now / 6 mo ago) | | | | | | |
| Release cadence (shipped features/month) | | | | | | |
| Movement toward our loop (0–3) | | | | | | |
| G2/Trustpilot reviews and rating | | | | | | |
| Active Meta ads count | | | | | | |
| **Growth stage** (accelerating / steady / flat / declining) | | | | | | |
| **Confidence** (high / med / low) | | | | | | |

Each cell stores: value, source link, retrieval date, and a confidence tag. Never mix estimated and reported figures without labelling.

---

## 4. Method

| Step | Task | Tools | Effort |
| --- | --- | --- | --- |
| 1 | Set up scorecard and source log | Sheet or markdown | 1 hr |
| 2 | Pull A-indicators (traffic, trends, keywords) | Similarweb, Google Trends, Ahrefs | 2–3 hrs |
| 3 | Pull B-indicators (funding, hiring, pricing history) | Crunchbase, LinkedIn, Wayback | 2–3 hrs |
| 4 | Pull C-indicators (changelogs, roadmap signals) | Product blogs, X, job posts | 3 hrs |
| 5 | Pull D/E-indicators (reviews, ads) | G2, Trustpilot, Ad Library | 2–3 hrs |
| 6 | Market-level sizing | Reports, earnings calls | 2 hrs |
| 7 | Synthesize: growth stage, threat level, opportunity | Report | 2 hrs |

Total: roughly 2–3 days. Searches can be delegated to research subagents for steps 2–5, while the synthesis stays with you.

### Triangulation rules

- Need at least **2 independent sources** for any claim you rely on.
- Traffic estimates from Similarweb/Semrush can be off by 2–3x for smaller sites. Use them for **trend direction**, not absolute numbers.
- Founder-reported ARR is a marketing claim. Tag as "self-reported."
- A flat signal in one category is not decline. Check at least 3 indicator groups before labelling a stage.

---

## 5. Interpretation Guide

| Pattern | Reading | Implication for us |
| --- | --- | --- |
| Traffic up, hiring up, shipping analytics features | Accelerating and converging | **High threat.** Move fast; sharpen the moat |
| Traffic up, only generation features | Growing in a different lane | Possible partner or integration, not a threat |
| Traffic flat, heavy discounting/pricing churn | Saturation or pricing pressure | Price-sensitivity room for a cheaper loop |
| Reviews cite credit waste or no analytics | Unmet need | Message and feature priority |
| Many new entrants, falling prices | Commoditizing generation | Reinforces the "don't compete on render quality" strategy |
| Creatify AdMax adoption signals (case studies, reviews) | Demand for loop features exists | Validates the category and a price gap |

**Decision outputs this research should produce**

1. Which 2–3 competitors to watch monthly (and which signals).
2. A "convergence risk" rating for each.
3. Evidence for or against the $49–$99/mo price point.
4. Timing call: is the window to build the loop open for 6 months, 12 months, or closing?

---

## 6. Deliverables

- `growth-indicators-scorecard.md` (filled table plus source log)
- `growth-indicators-report.md` (findings, charts, interpretation)
- `watchlist.md` (monthly tracking checklist for the chosen competitors)

## 7. Risks and Limits

- Private-company data is sparse, so conclusions will carry error bars. Report them.
- Traffic tools undercount API-first and in-app usage.
- Hype cycles (Higgsfield's rapid model launches) can inflate attention without retention. Pair attention indicators with review and churn signals.

## 8. Open Decisions

1. **Budget for tools:** free tiers only, or is a short paid Similarweb/Ahrefs trial acceptable? This changes data quality noticeably.
2. **Competitor list:** keep the 6 above, or add potential entrants (HeyGen, CapCut, Meta native tools) to the first pass?
3. **Cadence:** one-off snapshot, or set up a monthly refresh to track trend?
