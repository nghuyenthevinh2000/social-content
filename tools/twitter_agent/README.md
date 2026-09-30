---
name: twitter_agent
summary: Supervised X DOM CLI with visible browser review, exact approval binding,
  attempt quotas, single-click submissions, and audience-focused topic discovery.
tags:
- x
- twitter
- playwright
- cdp
- supervisor
- human-in-the-loop
submodules:
  tests/: Unit, DOM fixture, supervisor review, topic configuration, and subprocess
    CLI tests for the supervised X agent.
  __init__.py: Persistent state and shared models for the supervised X CLI.
  __main__.py: Entry point for python -m tools.twitter_agent.
  browser.py: Playwright CDP browser lifecycle management and doctor connectivity
    checks.
  cli.py: CLI parser, JSON output formatting, and command dispatch.
  launch_browser.sh: launch-browser.sh Detects whether Chrome is running with remote
    debugging (CDP) enabled. If not detected, launches Chrome with a dedicated user
    profil
  models.py: Shared values, stable errors, and exact-content approval binding.
  posts.py: Post extraction and bounded read operations for timeline, search, and
    thread.
  replies.py: Prepare, inspect, and submit browser interactions for replies.
  report.py: Candidate selection, report orchestration, and artifact generation.
  selectors.py: Centralized DOM selectors and block/challenge detection for X.
  store.py: Transactional draft queue, attempt quotas, audit trail, and supervisor
    lock.
  supervisor.py: Interactive supervisor review orchestration, approval binding, and
    submission loop.
  topic_config.py: Topic JSON validation and explicit query construction.
  topics.json: File topics.json
---

# Supervised X DOM CLI

An agent-facing CLI with visible browser operations and mandatory human approval for every reply.

## Overview & Architecture

- **Agent Commands:** Emit structured JSON to stdout and progress to stderr. Agents can read the timeline, search posts, inspect threads, and enqueue draft replies.
- **Human Supervision:** A separate interactive terminal (`supervise`) owns the dedicated visible X tab. No reply can be submitted without explicit human approval typed in the supervisor terminal.
- **Exact Approval Binding:** Approvals cryptographically bind the canonical target ID and exact reply text via SHA-256 digests. If composer text or target changes prior to submit, approval is invalidated and must be reviewed again.
- **One-Click Submission:** Exactly one click is dispatched per approved attempt. If DOM confirmation cannot be verified within a bounded window, the draft transitions to `uncertain` and requires manual review. No automatic retries occur.
- **Operational Quotas & Burst Guard:** Enforces 6 submission attempts per rolling hour, 20 per rolling 24 hours, at least 120 seconds between attempts, and a maximum of 3 submissions within any 30-minute burst window.
- **Strategy & Watchlist Discovery:** Maintains target accounts in SQLite, computes real-time opportunity scores based on recency and competition, and surfaces high-priority targets in the supervisor Strategy HUD. AI reply generation strategy is governed by `.agents/skills/twitter-reply-strategy/SKILL.md`.

> [!NOTE]
> Same-user process access is not an OS security isolation boundary. Keep the supervisor terminal reserved for human interaction. DOM automation also does not guarantee immunity from platform restrictions or rate limits.

## Two-Terminal Workflow

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

### Step 3: Human Supervisor Terminal

In the human's terminal, launch the supervisor:

```bash
uv run python -m tools.twitter_agent supervise
```

The supervisor claims drafts FIFO, opens the target in the visible tab, fills the composer dialog, captures a screenshot, and displays draft details. The human reviews the draft and approves or rejects it using:
- `approve DRAFT_ID`
- `reject DRAFT_ID`
- `defer`

### Step 4: Agent Terminal

In a separate terminal or subagent process, run read and preparation commands:

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

# Check queue and supervisor status
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

```bash
uv run python -m tools.twitter_agent report \
  [--topics-file PATH] \
  [--window-hours 24] \
  [--per-topic 5] \
  [--candidate-limit 100] \
  [--output-dir DIR]
```

### Options

- `--topics-file PATH`: Path to topics JSON configuration (default: bundled `topics.json`).
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

`topics.json` contains ten broad themes for technical builders, founders, and
tech-curious professionals: AI and machine learning; agents and automation;
software and developer tools; cybersecurity and privacy; startups and products;
blockchain and digital finance; science and emerging technology; work, careers,
and education; technology and society; and digital life and wellbeing.

These themes guide discovery rather than encode personal projects or prescribed
opinions. Careers and education also cover builder grants, hackathons,
fellowships, remote jobs, and free education. Add or remove topics as the audience
changes; report coverage follows the configured list rather than a fixed count.

- `id`, `name`, and `search_keywords` are required by the topic loader.
- `category` and `summary` describe the scope in neutral terms.
- `search_keywords` are literal terms or quoted phrases; the report builds an
  explicit OR query from them.
- `watch_query` and `quick_presets` are comma-separated terms for passing to
  `watch --topics`, not ready-made X search expressions. `watch` does not load
  the JSON file automatically.

Version 2 replaces the previous project-specific IDs and removes personal
`relevance`, `priority`, `recommended_archetypes`, and `reply_angles` fields.
Personal positioning and reply strategy belong outside the discovery list.

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

Each draft in the queue must still be individually reviewed and approved in the supervisor terminal. Note that `123` and `456` in examples above are placeholder IDs that users replace with real post IDs.

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
