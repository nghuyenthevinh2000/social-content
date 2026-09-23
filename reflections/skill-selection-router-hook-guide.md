# Skill-Selection Router (Jev Hook) — Full Guide

Every skill in `.agents/skills/` is more than its `SKILL.md` — `branding`
alone has 15+ reference docs and a `naming/` sub-tree, `beautiful-html-templates`
has 34 templates, `infographic` has bare template folders. Picking the
right skill *and* the right resource inside it by hand doesn't scale.

This repo ships a **PreInvocation hook** that runs before the agent reasons
on a turn: it sends the user's message to [TypeSafe](https://typesafe.ai)'s
Jev model, which returns calibrated probabilities across two stages —

1. **Which skill(s) apply** (`scripts/skill_selector.py::select_skills`)
2. **Which specific resource inside the top skill applies**
   (`scripts/skill_selector.py::select_resources`, via
   `discover_skill_resources`, which understands three shapes: structured
   `index.json` template metadata, frontmattered markdown references, and
   bare HTML template folders)

The result is injected as an ephemeral notice so the agent considers the
right skill *and* the right file before picking a path on its own. It fails
open on any error (missing key, bad payload, no match) — never a hard
failure of the turn.

## Relevant files

| File | Purpose |
| --- | --- |
| [`scripts/skill_selector.py`](../scripts/skill_selector.py) | Discovers skills + their sub-resources and runs the two-stage Jev selection. |
| [`scripts/skill_injector_hook.py`](../scripts/skill_injector_hook.py) | The PreInvocation entry point; reads the hook payload, calls the selector, formats the injected notice. |
| [`.agents/hooks.json`](../.agents/hooks.json) | Registers the hook to run on every turn. |
| [`scripts/install-skill-hook.sh`](../scripts/install-skill-hook.sh) | One-click installer that vendors this router into *any other* workspace. |
| [`scripts/skill-selector-demo/`](../scripts/skill-selector-demo/) | Local-only visual demo — type a request, watch two bar charts (skill, then resource) light up with Jev's confidence. |

## Requirements

- [`uv`](https://docs.astral.sh/uv/getting-started/installation/) installed and on `PATH`
- A [TypeSafe](https://typesafe.ai) API key (`TYPESAFE_API_KEY`)

## Install into this repo

Already wired up — nothing to do. `.agents/hooks.json` registers the hook,
and `pyproject.toml` / `uv.lock` already list `python-dotenv`, `pyyaml`, and
`typesafe-sdk`. Just make sure `.env` at the repo root has:

```
TYPESAFE_API_KEY=your-key-here
```

## Install into another workspace

Run the installer, pointing it at the target project:

```bash
./scripts/install-skill-hook.sh /path/to/other/workspace
```

This will:

1. Copy `skill_selector.py` + `skill_injector_hook.py` into `<target>/scripts/`
2. Run `uv init --bare` in `<target>` if it isn't a uv project yet, then
   `uv add python-dotenv pyyaml typesafe-sdk` there — **downloading and
   locking the dependencies through `uv`**, isolated in that workspace's own
   `uv.lock` / `.venv`
3. Merge a `skill-selection-router` entry into `<target>/.agents/hooks.json`
   without touching any other hooks already defined there
4. Create `<target>/.agents/skills/` if it doesn't exist, and add a
   `TYPESAFE_API_KEY=` placeholder to `<target>/.env` (only if one isn't
   already present)

Safe to re-run: it's idempotent — existing API keys, other hooks, and skill
folders are left untouched; only the two vendored script files are
overwritten on each run.

After installing:

```bash
# 1. Set the key
echo "TYPESAFE_API_KEY=your-key-here" >> /path/to/other/workspace/.env

# 2. Add skill folders (each needs a SKILL.md with name + description frontmatter)
#    under /path/to/other/workspace/.agents/skills/

# 3. Test it directly
echo '{"userMessage": "help me name my new brand"}' \
  | uv run --project /path/to/other/workspace python scripts/skill_injector_hook.py
```

A working response looks like:

```json
{"injectSteps": [{"ephemeralMessage": "NOTICE: TypeSafe skill router suggests the following for this request:\n- Lead skill: 'branding' (confidence 1.00)\n  Within 'branding':\n  - Lead resource: 'references/10-naming.md' (confidence 0.87)\n..."}]}
```

An empty `{"injectSteps": []}` means it failed open — check that
`TYPESAFE_API_KEY` is set and that `.agents/skills/` has at least one skill
with a valid `SKILL.md` frontmatter.

## Visual demo (optional)

To see the router's confidence scores as an animated two-section bar chart
instead of raw JSON:

```bash
uv run --project . python scripts/skill-selector-demo/server.py
# open http://127.0.0.1:8765
```

This spins up a local-only stdlib server (no new dependencies): it serves
the static frontend and relays the Jev call server-side, since TypeSafe's
API rejects direct browser-origin CORS requests.
