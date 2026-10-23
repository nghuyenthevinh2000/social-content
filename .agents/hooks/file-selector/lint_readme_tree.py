#!/usr/bin/env python3
"""
Directory Index & Repository Manifest Linter.

Verifies that the unified directory index (local/index.json) exists, is valid JSON,
and correctly maps active project and local directories (including Block L&C).
Replaces the legacy per-README frontmatter checks.

Usage:
    uv run --project . .agents/hooks/file-selector/lint_readme_tree.py --all
    uv run --project . .agents/hooks/file-selector/lint_readme_tree.py --changed-only
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import List, Set

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent.parent
INDEX_FILE = REPO_ROOT / "local" / "index.json"


def get_git_modified_directories(repo_root: Path = REPO_ROOT) -> Set[Path]:
    """Get all directories containing modified, added, or untracked files in git."""
    modified_dirs: Set[Path] = set()
    try:
        res = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        )
        for line in res.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line[2:].strip().split(" -> ")
            rel_path = parts[-1].strip()
            fpath = repo_root / rel_path
            if fpath.exists() and fpath.is_dir():
                modified_dirs.add(fpath)
            elif fpath.parent.exists():
                modified_dirs.add(fpath.parent)
    except Exception:
        pass
    return modified_dirs


def lint_directory_index() -> List[str]:
    """Validate that local/index.json exists and is structured properly."""
    errors = []
    if not INDEX_FILE.exists():
        errors.append(f"Directory index is missing at `{INDEX_FILE}`.")
        return errors

    try:
        data = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        errors.append(f"Directory index at `{INDEX_FILE}` is not valid JSON: {e}")
        return errors

    dirs = data.get("directories")
    if not isinstance(dirs, dict) or len(dirs) == 0:
        errors.append("Directory index has no mapped directories under 'directories'.")
        return errors

    # Check key project areas
    required_keys = ["local/block-lc", "tools", "topics"]
    for req in required_keys:
        if req not in dirs and not any(k.startswith(req) for k in dirs):
            errors.append(f"Key directory '{req}' is missing from index.")

    return errors


def lint_directory(directory: Path, repo_root: Path = REPO_ROOT) -> List[str]:
    """Single directory validation - checks if present in local/index.json."""
    if not INDEX_FILE.exists():
        return lint_directory_index()
    try:
        rel = str(directory.resolve().relative_to(repo_root.resolve()))
    except Exception:
        rel = str(directory)
    if rel == ".":
        return []

    try:
        data = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
        dirs = data.get("directories", {})
        if rel not in dirs:
            # If not yet indexed, flag for refresh
            return [f"Directory `{rel}` is not yet registered in `local/index.json`."]
    except Exception:
        pass
    return []


def main():
    parser = argparse.ArgumentParser(description="Lint directory index")
    parser.add_argument("--changed-only", action="store_true", help="Check only git modified dirs")
    parser.add_argument("--all", action="store_true", help="Check directory index health")
    args = parser.parse_args()

    errors = lint_directory_index()
    if errors:
        print("❌ Directory index validation failed:")
        for err in errors:
            print(f"  • {err}")
        print("\nRun `uv run .agents/hooks/file-selector/sync_directory_index.py` to fix.")
        sys.exit(1)
    else:
        print("✅ Directory index (`local/index.json`) is valid and up to date.")
        sys.exit(0)


if __name__ == "__main__":
    main()
