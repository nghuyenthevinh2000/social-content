# Product-Marketing Overfit in Viral Analyzer & Campaign Core

| Summary | Detail |
|---|---|
| Core problem | `viral_analyzer`, `tools/loop`, `AGENTS.md`, and `social-campaign` hardcode `product-marketing.json` (`marketing_goal`, non-empty `product.catalog`, and B2B workshop/substrate wording) as mandatory core context |
| Impact on other archetypes | Personal branding, creator education, founder storytelling, and media accounts lack a physical `product.catalog` or factory/buyer role; the engine either sets `collection_blocked: true` or forces artificial catalog entries |
| Target direction | Replace required `product-marketing.json` coupling with a neutral campaign schema (`campaign.json`) and opt-in archetype adapters (`product`, `personal_brand`, `media`, `service`) |

```text
Current:
  core (viral_analyzer, loop) -> product-marketing.json -> required product.catalog + B2B workshop rubric

Target:
  core (viral_analyzer, loop) -> neutral campaign.json (archetype, mission, audience, themes)
                                       ├── archetype=product        -> product.catalog optional adapter
                                       ├── archetype=personal_brand -> persona, pillars, POV, authority cues
                                       └── archetype=media          -> editorial focus, recurring formats
```

## Exact Coupling Hotspots

| Layer | File & Lines | Hardcoded Product Assumption | Effect on Non-Product / Personal-Brand Runs |
|---|---|---|---|
| Keyword config | [`config.py:32`](file:///Users/thevinhnguyen/Documents/computer-science/projects/social-content/tools/loop/viral_analyzer/keyword_research/config.py#L32) | `REQUIRED_CONTEXT = ('product-marketing.json',)` | Every campaign hashtag/keyword run rejects missing `product-marketing.json` even when creator positioning already exists |
| Prompt generator | [`generate.py:29,65,73,104-118`](file:///Users/thevinhnguyen/Documents/computer-science/projects/social-content/tools/loop/viral_analyzer/keyword_research/campaign/generate.py#L104-L118) | Enforces nonempty `product.catalog[*].name`, prompt Rule 3 (`workshop-role vocabulary`), Rule 11 (`product-marketing.json` only), template `buyer or process connection` | Blocks collection (`collection_blocked=True`) for personal brands lacking SKUs; pushes B2B buyer/workshop framing into LLM candidate generation |
| Evidence review | [`verify.py:20-25,51-54`](file:///Users/thevinhnguyen/Documents/computer-science/projects/social-content/tools/loop/viral_analyzer/keyword_research/campaign/verify.py#L19-L57) | Fixed labels (`direct_application`, `adjacent_process`) and `observed` fields (`substrate/application`, `process`, `workshop/buyer role`) | Fits physical/manufacturing inputs; lacks labels for audience resonance, authority fit, narrative style, or lifestyle alignment |
| Campaign validator | [`structure.py:88-106`](file:///Users/thevinhnguyen/Documents/computer-science/projects/social-content/tools/loop/validate/structure.py#L88-L106) | `validate-campaign` fails any project without `product-marketing.json` containing non-empty `marketing_goal` and `product.catalog` | Fails validation on personal branding or media-only projects |
| Project scaffold | [`project_init.py:236,294`](file:///Users/thevinhnguyen/Documents/computer-science/projects/social-content/tools/loop/project_init.py#L236-L295), [`folder_structure.json:35`](file:///Users/thevinhnguyen/Documents/computer-science/projects/social-content/tools/loop/samples/folder_structure.json#L35) | Always scaffolds `product-marketing.json` with B2B `"distribution partners"`, `"product.catalog"`, and `"unique.origin"` | Forces personal-brand campaigns into a B2B SKU template on `init` |
| Repo rules & skills | [`AGENTS.md:9`](file:///Users/thevinhnguyen/Documents/computer-science/projects/social-content/AGENTS.md#L9), [`SKILL.md:17,78`](file:///Users/thevinhnguyen/Documents/computer-science/projects/social-content/.agents/skills/social-campaign/SKILL.md#L17) | Defines `product-marketing.json` (`marketing_goal`, `product.catalog`) as sole research factual context | Instructs agents never to rely on brand voice or creator positioning during viral discovery |

## Use-Case Gap Comparison

| Campaign Archetype | Primary Core Entities Needed | Fit with `product.catalog` + Workshop Rubric | What Breaks Without Decoupling |
|---|---|---|---|
| Physical / B2B Product *(current)* | SKUs, specs, applications, buyer/process roles | Native fit | None *(benchmark origin: `local/paper-ink-product/`)* |
| Personal Branding | Founder persona, worldview, content pillars, credibility proof, target followers | Mismatch — creator is the brand, not a SKU | Empty catalog triggers `collection_blocked`; prompts look for industrial applications |
| Educational / Creator Media | Series formats, audience pain/curiosity triggers, retention hooks | Mismatch — value is editorial attention, not physical unit sales | `adjacent_process` and `workshop/buyer` evidence fields become meaningless noise |
| Consulting / B2B Service | Service offers, ICP pains, case-study outcomes, trust signals | Partial — services are capabilities rather than physical substrates | Requires shoehorning intangible offers into SKU specs |

## Next To-Do

| Task | Scope & Approach | Priority | Status |
|---|---|---|---|
| Define neutral `campaign.json` schema | Require archetype-agnostic `campaign_goal`, `archetype` (`product\|personal_brand\|media\|service`), `positioning`, `pillars`; make `product.catalog` optional (`product` module) | High | Open |
| Extract archetype adapters out of `viral_analyzer` core | Keep core [`keyword_research/`](file:///Users/thevinhnguyen/Documents/computer-science/projects/social-content/tools/loop/viral_analyzer/keyword_research/__init__.py) domain-neutral; drive prompt rules (`generate.py`) and sample rubrics (`verify.py`) from selected archetype config | High | Open |
| Generalize `project_init` & `validate-campaign` | Accept `--archetype` in `project_init.py`; allow either `campaign.json` or legacy `product-marketing.json` in `validate/structure.py` during transition | Medium | Open |
| Plan `local/*` migration & doc updates | Rename `local/{paper-ink-product,block-lc}/product-marketing.json` only after adapter rollout; update `AGENTS.md`, `social-campaign`, `video-editing`, and `tools/loop/README.md` together | Medium | Open |
