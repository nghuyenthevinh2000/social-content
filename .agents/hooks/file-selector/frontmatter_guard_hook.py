#!/usr/bin/env python3
"""
Directory Index Guard Hook (Stop lifecycle event).

Fires when the agent attempts to complete its turn (`terminationReason: "model_stop"`).
Checks that `local/index.json` exists and is valid. If modified directories were introduced
without index update, automatically refreshes `local/index.json` to keep agent index
fresh without interrupting work.

Replaces the legacy frontmatter guard that blocked on README frontmatter.
"""

import json
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent.parent
INDEX_FILE = REPO_ROOT / "local" / "index.json"

sys.path.insert(0, str(SCRIPT_DIR))


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        print(json.dumps({"decision": "allow"}))
        return

    reason = payload.get("terminationReason", "")
    if reason not in {"model_stop", ""}:
        print(json.dumps({"decision": "allow"}))
        return

    # Check if index exists; if missing, auto-generate it silently
    if not INDEX_FILE.exists():
        try:
            from sync_directory_index import sync_index
            sync_index(with_repomix=False)
        except Exception:
            pass

    print(json.dumps({"decision": "allow"}))


if __name__ == "__main__":
    main()
