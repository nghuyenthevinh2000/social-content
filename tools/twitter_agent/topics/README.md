---
name: topics
summary: JSON topic configurations and a full-field reusable template for bounded X engagement reports. Includes audience metadata, watch presets, default discovery themes, and focused Vietnam blockchain legal searches.
tags: [twitter, x, topics, report, configuration]
submodules:
  template.json: Full-field single-topic configuration with audience metadata, category, date, and watch presets.
  topics.json: Default broad discovery themes for technical builders and founders.
  topics_vietnam_blockchain_legal.json: Focused discovery configuration for Vietnam blockchain legal and regulatory discussions.
---

# How to create a topic configuration and run a report

Use this workflow for agents researching a subject on X. Run commands from the
repository root. You need `uv`, synced dependencies (`uv sync`), and Chrome
running with CDP on port 9222 and a manually authenticated X account.

## 1. Create a JSON configuration

Copy [`template.json`](./template.json) to a descriptive filename such as
`tools/twitter_agent/topics/ai_agents.json`. Edit the copy to match the user's
subject, language, and desired scope. Leave the original template and unrelated
configs unchanged.

The template includes the same fields as `topics_vietnam_blockchain_legal.json`.
Update `name`, `version`, `updated_at` (YYYY-MM-DD), `description`, and
`target_audience` for the new research scope. For each topic, adapt `id`, `name`,
`category`, `summary`, `search_keywords`, and `watch_query`; update the named
`quick_presets` to match those terms.

`report` requires only `topics` and each topic's `id`, `name`, and
`search_keywords`. The other fields provide reusable context: `watch_query` and
`quick_presets` are comma-separated term strings for manually passing to
`watch --topics`, not report search expressions or automatically loaded filters.
Keep them consistent with the keywords. The following is a **minimal valid
example**; copy the full template when creating a reusable config.

```json
{
  "topics": [
    {
      "id": "ai-agent-tooling",
      "name": "AI Agent Tooling",
      "search_keywords": ["AI agents", "agent orchestration", "#AIAgents"]
    }
  ]
}
```

Use a few focused terms per topic. Terms are joined with **OR**, so adding a
generic keyword broadens the search rather than narrowing it. Multi-word terms
are quoted automatically. Separate distinct research questions into separate
topic objects. See the [configuration reference](../README.md#topic-configuration)
for field requirements and keyword restrictions.

## 2. Validate before browsing

```bash
uv run python - tools/twitter_agent/topics/ai_agents.json <<'PY'
from pathlib import Path
import sys
from tools.twitter_agent.topic_config import load_topics

topics = load_topics(Path(sys.argv[1]))
print(f"Valid configuration: {len(topics)} topic(s)")
PY
```

If validation fails, correct the JSON or keywords before continuing.

Update this folder's README frontmatter for the new file:

```bash
uv run --project . .agents/hooks/file-selector/sync_readme_tree.py tools/twitter_agent/topics
uv run --project . .agents/hooks/file-selector/lint_readme_tree.py --changed-only
```

## 3. Check browser readiness

```bash
uv run python -m tools.twitter_agent doctor
```

If Chrome is unavailable, ask the human to run
`uv run python -m tools.social_agent start-browser` and log into X. Stop for human action
if the doctor reports authentication problems, a challenge, or an account block.

## 4. Run the report CLI

```bash
uv run python -m tools.twitter_agent report \
  --topics-file tools/twitter_agent/topics/ai_agents.json \
  --window-hours 24 \
  --per-topic 5 \
  --candidate-limit 100
```

Replace `ai_agents.json` with your config filename. Set `--window-hours` to the
requested lookback. `--per-topic` must be between 1 and `--candidate-limit`;
`--candidate-limit` must be between 2 and 100 and is split across Top and Latest.
The CLI applies browsing delays automatically. No replies or posts are published.

Without `--topics-file`, the report uses this folder's `topics.json`. For the
existing focused configuration:

```bash
uv run python -m tools.twitter_agent report \
  --topics-file tools/twitter_agent/topics/topics_vietnam_blockchain_legal.json \
  --window-hours 24 --per-topic 5 --candidate-limit 100
```

## 5. Inspect evidence and report limitations

The CLI prints JSON with artifact paths, summary, coverage, partial status, and
the UTC window. Open `data.artifacts.evidence_json`; by default this is under
`.twitter-agent/reports/report-<timestamp>/evidence.json`.

- Exit **0**: collection completed without recorded degradation.
- Exit **4**: partial/degraded collection; inspect per-topic errors and disclose gaps.
- Other nonzero codes: check the [exit-code reference](../README.md#exit-codes)
  and resolve the reported problem instead of inventing results.

Summarize only what the evidence supports and cite post URLs and timestamps.
Even a successful report is a bounded sample, not an exhaustive search. Keep
generated evidence out of this folder; it stores reusable configs only.
