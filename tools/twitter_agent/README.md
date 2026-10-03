---
name: twitter_agent
summary: Terminal-operated X DOM CLI with direct reply submission and explicitly approved standalone image posting, exact content checks,
  attempt quotas, randomized browsing delays, single-click submissions, and JSON-configured topic reporting with an agent workflow.
tags:
- x
- twitter
- playwright
- cdp
- terminal
- human-in-the-loop
submodules:
  topics/: Reusable report topic JSON configurations, a copyable template, and an agent how-to guide.
  tests/: Unit, pacing, DOM fixture, direct submission, topic configuration, and subprocess
    CLI tests for the terminal-operated X agent.
  __init__.py: Persistent state and shared models for the terminal-operated X CLI.
  __main__.py: Entry point for python -m tools.twitter_agent.
  AGENTS.md: Agent instructions for creating topic JSON configurations and running evidence-backed reports.
  browser.py: Playwright CDP browser lifecycle management and paced doctor connectivity
    checks.
  cli.py: CLI parser, JSON output formatting, and command dispatch with a topics-folder report default.
  launch_browser.sh: launch-browser.sh Detects whether Chrome is running with remote
    debugging (CDP) enabled. If not detected, launches Chrome with a dedicated user
    profil
  models.py: Shared values, stable errors, and exact-content approval binding.
  pacing.py: Shared randomized browsing delays and periodic action-budget breaks.
  posts.py: Paced post extraction and bounded read operations for timeline, search, and
    thread.
  publish.py: Standalone approved image-post command with account checks, shared quotas, and single-click confirmation.
  replies.py: Paced target preparation, inspection, and submission interactions for replies.
  report.py: Candidate selection, report orchestration, and artifact generation.
  selectors.py: Centralized DOM selectors and block/challenge detection for X.
  store.py: Transactional draft queue, attempt quotas, audit trail, and submission
    lock.
  submission.py: One-shot caller-selected reply submission with exact-content checks and no automatic retries.
  topic_config.py: Topic JSON validation and explicit query construction.
---

# Terminal-operated X DOM CLI

An agent-facing CLI with visible browser operations and direct submission from the caller's terminal. No separate supervisor process or interactive approval prompt is required.

## Standalone image posts

The separate image-post command saves the CDP publishing workflow used for the
Ha Noi post. It does not publish on import.
Launch Chrome with `./tools/twitter_agent/launch_browser.sh` and log into X first.

```bash
uv run python -m tools.twitter_agent.publish \
  --account TheVinhNguyen4 \
  --text 'Your exact approved text' \
  --image /absolute/path/to/image.jpg \
  --approved
```

Use `--approved` only after the human explicitly approves the exact text and image.
The command checks the signed-in account, binds the uploaded image bytes by SHA-256,
honors the existing pause, submission quotas, and submission lock, and clicks Post
at most once. Confirmation verifies the returned text and one photo, accounting
for X's appended media shortlink. Exit code 4 means uncertain submission: inspect
X manually and **do not automatically retry**. Each invocation is a new attempt;
there is no cross-run duplicate protection. Approval and attempt events use the
existing `.twitter-agent` state directory. The approval flag records approval already obtained through the caller's terminal; it does not launch a second review UI.

## Overview & Architecture

- **Agent Commands:** Emit structured JSON to stdout and progress to stderr. Agents can read the timeline, search posts, inspect threads, and enqueue draft replies.
- **Direct Submission:** `reply submit DRAFT_ID` sends exactly the selected pending draft. Review the AI's work in your existing terminal before invoking it; no separate supervisor or FIFO submission loop runs.
- **Exact Content Checks:** SHA-256 digests bind the canonical target ID and exact reply text. A changed composer blocks submission.
- **One-Click Submission:** Exactly one click is dispatched per approved attempt. If DOM confirmation cannot be verified within a bounded window, the draft transitions to `uncertain` and requires manual review. No automatic retries occur.
- **Operational Quotas & Burst Guard:** Enforces 6 submission attempts per rolling hour, 20 per rolling 24 hours, at least 120 seconds between attempts, and a maximum of 3 submissions within any 30-minute burst window.
- **Strategy & Watchlist Discovery:** Maintains target accounts in SQLite and computes opportunity scores based on recency and competition. AI reply generation strategy is governed by `.agents/skills/twitter-reply-strategy/SKILL.md`.

> [!NOTE]
> Direct submission is a publishing action, not a dry run. DOM automation does not guarantee immunity from platform restrictions or rate limits.

## Browsing Delays

Browsing is paced automatically before each live action:

- Account discovery (`from:handle` searches): **3–7 seconds**.
- Feed scrolling: **2–5 seconds**, plus the existing 500 ms rendering wait.
- Hashtag and other topic searches (including report Top/Latest searches): **5–10 seconds**.
- Home/thread navigation and reply target opening: **3–7 seconds**.
- After a randomly selected **50–100 actions**, an additional **30–60 second**
  break occurs before the next action; a new action budget is then selected.

Each navigation or scroll counts as one action, not each extracted post or DOM
inspection. The agent currently discovers accounts through search rather than
opening profile pages. Delays and action counts are shared across pages, report
topics, and polling cycles **within one CLI process**; separate CLI invocations
start fresh and concurrent processes are not coordinated. Intentional scroll
pauses do not consume the 30-second active collection budget. Local DOM fixtures
skip randomized pacing. Submission quotas remain enforced.

These delays reduce request bursts; they do not guarantee avoidance of platform
restrictions. Detected blocks and challenges still stop browser operations.

## Single-Terminal Workflow

### Step 1: Launch Chrome with Remote Debugging

Launch Chrome with a dedicated profile outside the repository using the provided helper script:

```bash
./tools/twitter_agent/launch_browser.sh
```

Or manually:

```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --remote-debugging-port=9222 \
  --user-data-dir="$HOME/chrome-twitter-profile"
```

Log into your X account manually in this browser profile window.

### Step 2: Verify Setup

From `projects/social-content`:

```bash
uv sync
uv run python -m tools.twitter_agent doctor
```

### Step 3: Read, prepare, and submit from your terminal

Run read and preparation commands in the same terminal where you review the AI's work:

```bash
# Manage target watchlist
uv run python -m tools.twitter_agent watchlist add @sama --notes "OpenAI founder"
uv run python -m tools.twitter_agent watchlist list
uv run python -m tools.twitter_agent watchlist remove sama

# Discover scored opportunities across watchlist
uv run python -m tools.twitter_agent watch --limit 10

# Discover opportunities across topics with lookback window and score filtering
uv run python -m tools.twitter_agent watch --topics --window-minutes 60 --min-score 80 --limit 20
uv run python -m tools.twitter_agent watch --topics "AI, LLM, claude" --window-minutes 30 --min-score 75

# Read recent home timeline posts (scored by opportunity)
uv run python -m tools.twitter_agent timeline --limit 10

# Search recent posts with automatic since_time window and score filter
uv run python -m tools.twitter_agent search "(AI OR LLM) min_faves:5 lang:en -filter:links" --window-minutes 60 --min-score 80 --limit 50

# Inspect a thread (replace 123 with actual target post ID or URL)
uv run python -m tools.twitter_agent thread 123

# Prepare a draft reply (123 is a placeholder ID)
uv run python -m tools.twitter_agent reply prepare 123 --text "Your reply text here"

# After reviewing the returned draft, submit its exact ID (publishes immediately)
uv run python -m tools.twitter_agent reply submit DRAFT_ID

# Check queue and submission status
uv run python -m tools.twitter_agent status

# Pause or resume submissions
uv run python -m tools.twitter_agent pause
uv run python -m tools.twitter_agent resume

# Cancel a pending draft
uv run python -m tools.twitter_agent cancel DRAFT_ID

# Generate high-engagement topic report across configured topics
uv run python -m tools.twitter_agent report --window-hours 24 --per-topic 5
```

## Topic Engagement Report

The `report` command gathers high-engagement posts found within a rolling lookback window across topics defined in a JSON topics file.

**Agent workflow:** create or reuse a config in [`topics/`](./topics/), validate it,
then run `report --topics-file tools/twitter_agent/topics/<subject>.json`.
Follow the [step-by-step guide](./topics/README.md) and [agent instructions](./AGENTS.md).
Generated evidence belongs in `.twitter-agent/reports/`, not the config folder.

```bash
uv run python -m tools.twitter_agent report \
  [--topics-file PATH] \
  [--window-hours 24] \
  [--per-topic 5] \
  [--candidate-limit 100] \
  [--output-dir DIR]
```

### Options

- `--topics-file PATH`: Path to topics JSON configuration (default: bundled `topics/topics.json`).
- `--window-hours INT`: Lookback window in hours from current UTC time (default: `24`, must be > 0).
- `--per-topic INT`: Target number of top posts selected per topic (default: `5`, 1 <= N <= candidate-limit).
- `--candidate-limit INT`: Candidate collection budget per topic split evenly between `Top` and `Latest` tabs (default: `100`, 2 <= N <= 100).
- `--output-dir DIR`: Directory for output run artifacts (default: `<state-dir>/reports`).

### Semantics & Ranking

- **Bounded Collection:** Divides `candidate-limit` across `Top` (50%) and `Latest` (50%) search tabs using explicit boolean queries (`since_time` / `until_time`).
- **Deduplication:** Posts seen in both tabs are merged, keeping the post record with highest total engagement.
- **Filtering & Ranking:** Posts are strictly filtered to the UTC window `[start, end]`. Surviving candidates are ranked deterministically by: `likes DESC`, `retweets DESC`, `replies DESC`, `id DESC`.
- **Fault Tolerance:** Search failures or timeouts on individual topics degrade that topic to `partial` or `failed` without halting the entire run. Browser-fatal errors record remaining topics as `skipped`.
- **Atomic Artifacts:** Writes `evidence.json` atomically into a unique run directory `<output-dir>/report-<datetime>/` (formatted as `report-YYYYMMDD-HHMMSS`).

### Exit Codes

- `0`: Complete success (all topics completed cleanly).
- `1`: Report writing or unhandled fatal runtime error.
- `2`: Invalid CLI arguments or malformed topics file.
- `3`: Browser connection failure or CDP session failure.
- `4`: Partial / degraded run (one or more topics experienced timeouts, search errors, or unparseable timestamps).

## Topic Configuration

[`topics/topics.json`](./topics/topics.json) contains ten broad themes for technical builders, founders, and
tech-curious professionals: AI and machine learning; agents and automation;
software and developer tools; cybersecurity and privacy; startups and products;
blockchain and digital finance; science and emerging technology; work, careers,
and education; technology and society; and digital life and wellbeing.

These themes guide discovery rather than encode personal projects or prescribed
opinions. Careers and education also cover builder grants, hackathons,
fellowships, remote jobs, and free education. Add or remove topics as the audience
changes; report coverage follows the configured list rather than a fixed count.

- `id`, `name`, and `search_keywords` are required by the topic loader.
- The JSON root must be an object with a nonempty `topics` array. Each `id` must
  be unique within the file; `id` and `name` must be nonempty strings and
  `search_keywords` a nonempty array of nonempty strings.
- `category` and `summary` describe the scope in neutral terms.
- `search_keywords` are literal terms or quoted phrases; the report builds an
  explicit OR query from them.
- Hashtags are accepted. Unquoted X operators (`from:`, `lang:`, `min_faves:`),
  parentheses, standalone `AND`/`OR`/`NOT`, malformed quotes, and control
  characters are rejected. Multi-word terms are quoted automatically. Keep
  query operators out of keyword phrases; the CLI adds the time filters.
- `watch_query` and `quick_presets` are comma-separated terms for passing to
  `watch --topics`, not ready-made X search expressions. `watch` does not load
  the JSON file automatically.

Version 2 replaces the previous project-specific IDs and removes personal
`relevance`, `priority`, `recommended_archetypes`, and `reply_angles` fields.
Personal positioning and reply strategy belong outside the discovery list.

Topic configs now live under `tools/twitter_agent/topics/`. Update older explicit
paths from `tools/twitter_agent/topics.json` to
`tools/twitter_agent/topics/topics.json`, and from
`tools/twitter_agent/topics_vietnam_blockchain_legal.json` to
`tools/twitter_agent/topics/topics_vietnam_blockchain_legal.json`.

## Batch Queue Format

Drafts can be enqueued from a UTF-8 JSON Lines (JSONL) file:

```jsonl
{"target": "123", "text": "First reply text"}
{"target": "https://x.com/username/status/456", "text": "Second reply text"}
```

Import drafts atomically:

```bash
uv run python -m tools.twitter_agent queue path/to/drafts.jsonl
```

Review drafts in your existing terminal, then invoke `reply submit DRAFT_ID` for each selected draft. Queue import never publishes automatically. `123` and `456` are placeholder post IDs.

`supervise` has been removed. `status` now reports `submission` instead of
`supervisor`. Existing drafts and audit history are preserved. Interrupted possible
submissions become `uncertain` and cannot be submitted again. The legacy
`supervisor.lock` filename is retained solely to exclude older running clients;
it does not start or require a supervisor process.

## Global Options

Global options may be specified before subcommands:

- `--state-dir DIR`: Directory for database and artifacts (default: `.twitter-agent`).
- `--cdp URL`: Chrome DevTools Protocol endpoint (default: `http://127.0.0.1:9222`).
- `--timeout-ms MS`: Timeout in milliseconds for browser operations (default: `15000`).

Example:

```bash
uv run python -m tools.twitter_agent --state-dir /path/to/state --cdp http://127.0.0.1:9222 status
```

## State & Privacy

- Local artifacts (SQLite database, screenshots, audit logs) reside in the `.twitter-agent/` directory (ignored by git).
- State and artifact directories are created with permissions `0700`, and files with `0600`.
- Diagnostic screenshots (`{draft_id}_before.png` and `{draft_id}_after.png`) are stored in `.twitter-agent/artifacts/`.
- No credentials or cookies are logged.

## Tests & Verification

Run the full automated test suite from `projects/social-content`:

```bash
uv run python -m unittest discover -s tools/twitter_agent/tests -v
uv run python -m tools.twitter_agent --help
```
