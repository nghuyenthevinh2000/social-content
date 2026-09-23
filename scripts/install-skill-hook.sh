#!/usr/bin/env bash
#
# install-skill-hook.sh — one-click installer for the TypeSafe/Jev-backed
# skill-selection router hook (.agents/hooks/skill-selector/skill_selector.py +
# .agents/hooks/skill-selector/skill_injector_hook.py) into any workspace.
#
# What it does:
#   1. Copies skill_selector.py + skill_injector_hook.py into
#      <target>/.agents/hooks/skill-selector/.
#   2. Ensures <target> is a uv project (uv init --bare if it isn't one
#      yet) and runs `uv add` there to fetch python-dotenv, pyyaml, and
#      typesafe-sdk into that project's own lockfile/venv.
#   3. Merges the "skill-selection-router" PreInvocation hook entry into
#      <target>/.agents/hooks.json without clobbering any other hooks
#      already registered there.
#   4. Creates <target>/.agents/skills/ (where the hook discovers skills)
#      if it doesn't exist yet, and a <target>/.env with a
#      TYPESAFE_API_KEY placeholder if one isn't already present.
#
# Usage:
#   ./scripts/install-skill-hook.sh /path/to/other/workspace
#   ./scripts/install-skill-hook.sh .                # install into cwd
#
# Safe to re-run: copies are overwritten (you're expected to own these
# two files as vendored router code, not to hand-edit them in place),
# but hooks.json, .env, and .agents/skills/ are merged/preserved.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_REPO="$(cd "$SCRIPT_DIR/.." && pwd)"

usage() {
  echo "Usage: $0 <target-workspace-dir>" >&2
  exit 1
}

[ $# -eq 1 ] || usage
TARGET_DIR="$(cd "$1" 2>/dev/null && pwd)" || {
  echo "error: target directory '$1' does not exist" >&2
  exit 1
}

if [ "$TARGET_DIR" = "$SOURCE_REPO" ]; then
  echo "error: target is the same as the source repo ($SOURCE_REPO) — nothing to install" >&2
  exit 1
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "error: uv is not installed. Install it first: https://docs.astral.sh/uv/getting-started/installation/" >&2
  exit 1
fi

echo "Installing skill-selection router into: $TARGET_DIR"
echo

# --- 1. Vendor the router scripts -------------------------------------------
mkdir -p "$TARGET_DIR/.agents/hooks/skill-selector"
cp "$SOURCE_REPO/.agents/hooks/skill-selector/skill_selector.py" "$TARGET_DIR/.agents/hooks/skill-selector/skill_selector.py"
cp "$SOURCE_REPO/.agents/hooks/skill-selector/skill_injector_hook.py" "$TARGET_DIR/.agents/hooks/skill-selector/skill_injector_hook.py"
echo "✓ copied .agents/hooks/skill-selector/skill_selector.py + skill_injector_hook.py"

# --- 2. Ensure a uv project + fetch dependencies ----------------------------
if [ ! -f "$TARGET_DIR/pyproject.toml" ]; then
  echo "  no pyproject.toml found — running 'uv init --bare'"
  uv init --bare --name "$(basename "$TARGET_DIR")" "$TARGET_DIR" >/dev/null
fi

echo "  fetching python-dotenv, pyyaml, typesafe-sdk via uv…"
uv add --project "$TARGET_DIR" python-dotenv pyyaml typesafe-sdk
echo "✓ dependencies resolved into $TARGET_DIR/uv.lock"

# --- 3. Merge the hook registration into .agents/hooks.json -----------------
mkdir -p "$TARGET_DIR/.agents"
HOOKS_FILE="$TARGET_DIR/.agents/hooks.json"

python3 - "$HOOKS_FILE" <<'PYEOF'
import json
import sys
from pathlib import Path

hooks_file = Path(sys.argv[1])

try:
    existing = json.loads(hooks_file.read_text()) if hooks_file.exists() else {}
except json.JSONDecodeError:
    print(f"  warning: {hooks_file} has invalid JSON, refusing to overwrite it", file=sys.stderr)
    sys.exit(1)

existing["skill-selection-router"] = {
    "enabled": True,
    "PreInvocation": [
        {
            "type": "command",
            "command": "uv run --project .. hooks/skill-selector/skill_injector_hook.py",
            "timeout": 15,
        }
    ],
}

hooks_file.write_text(json.dumps(existing, indent=2) + "\n")
PYEOF
echo "✓ registered hook in .agents/hooks.json"

# --- 4. Scaffolding: skills dir + .env placeholder --------------------------
mkdir -p "$TARGET_DIR/.agents/skills"
echo "✓ ensured .agents/skills/ exists (add skill folders with SKILL.md here)"

ENV_FILE="$TARGET_DIR/.env"
if [ ! -f "$ENV_FILE" ] || ! grep -q "^TYPESAFE_API_KEY=" "$ENV_FILE" 2>/dev/null; then
  printf '%sTYPESAFE_API_KEY=\n' "$( [ -f "$ENV_FILE" ] && cat "$ENV_FILE" && echo )" > "$ENV_FILE"
  echo "✓ added a TYPESAFE_API_KEY= placeholder to .env — fill in your key"
else
  echo "✓ .env already has TYPESAFE_API_KEY — left untouched"
fi

echo
echo "Done. Next steps:"
echo "  1. Set TYPESAFE_API_KEY in $ENV_FILE"
echo "  2. Add skill folders (each with a SKILL.md) under $TARGET_DIR/.agents/skills/"
echo "  3. Test it: echo '{\"userMessage\": \"...\"}' | uv run --project \"$TARGET_DIR\" python .agents/hooks/skill-selector/skill_injector_hook.py"
