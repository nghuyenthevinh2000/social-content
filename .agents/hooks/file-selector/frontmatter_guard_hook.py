#!/usr/bin/env python3
"""
Frontmatter Guard Hook (Stop lifecycle event).

Fires when the agent attempts to complete its turn (`terminationReason: "model_stop"`).
Checks `git status` for modified, added, or untracked files across project folders.
If any touched directory has a missing or invalid README.md frontmatter, or if files
were modified without updating the directory's frontmatter, it BLOCKS the stop by
returning `{"decision": "continue", "reason": "..."}`.

This strictly forces the agent to update folder frontmatter before finishing.

Expected stdin (Antigravity Stop contract):
    {
      "executionNum": 1,
      "terminationReason": "model_stop",
      "error": "",
      "fullyIdle": true,
      "workspacePaths": [...]
    }

Expected stdout:
    {"decision": "allow"}
    or
    {"decision": "continue", "reason": "..."}
"""

import json
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent.parent

sys.path.insert(0, str(SCRIPT_DIR))


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        print(json.dumps({"decision": "allow"}))
        return

    # Only guard normal model completion
    reason = payload.get("terminationReason", "")
    if reason not in {"model_stop", ""}:
        print(json.dumps({"decision": "allow"}))
        return

    workspace_paths = payload.get("workspacePaths") or []
    workspace = Path(workspace_paths[0]) if workspace_paths else REPO_ROOT

    from lint_readme_tree import get_git_modified_directories, lint_directory

    modified_dirs = get_git_modified_directories(workspace)
    if not modified_dirs:
        print(json.dumps({"decision": "allow"}))
        return

    violations = []
    for d in sorted(modified_dirs):
        errors = lint_directory(d, workspace)
        violations.extend(errors)

    if violations:
        reason_msg = (
            "STOP BLOCKED (Frontmatter Integrity Rule):\n"
            "You modified or created files in project directories, but the corresponding README.md "
            "frontmatter is missing or invalid:\n\n"
            + "\n".join(f"  • {v}" for v in violations)
            + "\n\nREQUIRED ACTION:\n"
            "Update the YAML frontmatter (with 'name', 'summary', and 'submodules') in each touched directory's "
            "README.md before finishing your turn. You can also run:\n"
            "  `uv run --project . .agents/hooks/file-selector/sync_readme_tree.py <dir>`"
        )
        print(json.dumps({
            "decision": "continue",
            "reason": reason_msg,
        }))
    else:
        print(json.dumps({"decision": "allow"}))


if __name__ == "__main__":
    main()
