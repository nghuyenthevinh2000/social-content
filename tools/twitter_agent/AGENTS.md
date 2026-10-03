# X Topic Report Workflow for Agents

For topic-based X research, create or reuse a JSON configuration in
`tools/twitter_agent/topics/`, then run the `report` CLI. Do not replace this
workflow with ad hoc browser scraping or `watch --topics`: watch does not load
JSON configs and is intended for reply opportunity discovery.

1. Read [`topics/README.md`](./topics/README.md). Copy `topics/template.json` to a
   descriptive `<subject>.json` filename and adapt the topics to the user's
   research scope. Reuse an existing config only if its scope matches. Do not
   overwrite unrelated configs or change the broad default for a one-off report.
2. Use a nonempty `topics` array. Each topic needs a unique `id`, a `name`, and
   nonempty `search_keywords`. Use literal terms, hashtags, or phrases, not X
   query operators. The CLI builds the OR expression and time window.
3. Validate with `load_topics` as shown in the guide before connecting to X.
4. Run from the repository root, using an explicit config and a lookback window
   matching the request:

   ```bash
   uv run python -m tools.twitter_agent report \
     --topics-file tools/twitter_agent/topics/<subject>.json \
     --window-hours 24 \
     --per-topic 5 \
     --candidate-limit 100
   ```

5. Read the CLI JSON output and the file at `data.artifacts.evidence_json`.
   Check `partial`, coverage, and per-topic errors before drawing conclusions.
   Exit code 4 means a degraded report, not complete success; disclose missing
   coverage. Results are a bounded sample, not all X posts or proof of a trend.
   Cite post URLs and timestamps from the evidence. Never fabricate findings
   when Chrome, authentication, or collection is unavailable.
6. Keep generated evidence in the default `.twitter-agent/reports/` state area,
   not the topic config folder. Creating a config does not authorize publishing
   replies or posts. Respect existing pacing and stop for human action when X
   presents a block or challenge; do not automatically retry around it.
7. Update `topics/README.md` frontmatter for any added or changed config and
   comply with the repository's README-tree validation rule.

Chrome must already be launched with CDP and logged into X manually. If needed,
ask the human to run `uv run python -m tools.social_agent start-browser` and log in;
`uv run python -m tools.twitter_agent doctor` verifies the connection.
