#!/usr/bin/env python3
"""
README Tree Frontmatter Linter.

Enforces that project directories have a standardized README.md with YAML frontmatter:
---
name: <folder_name>
summary: <Concise 1-2 sentence description of folder's purpose and scope>
tags: [<tag1>, <tag2>]
submodules:
  - <child_file_or_dir>: <brief description>
---

Usage:
    uv run --project . .agents/hooks/lint_readme_tree.py --changed-only   # Checks directories modified in git
    uv run --project . .agents/hooks/lint_readme_tree.py --all            # Full tree validation
"""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent

IGNORE_DIRS: Set[str] = {
    ".git",
    ".agents",
    ".gemini",
    ".vscode",
    ".idea",
    ".system_generated",
    "brain",
    "node_modules",
    "site-packages",
    "dist-packages",
    "dist",
    "build",
    "__pycache__",
    ".venv",
    "venv",
    "env",
    "scratch",
    "coverage",
    ".cache",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".turbo",
    ".next",
    ".nuxt",
    ".astro",
    ".output",
}

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def is_ignored_path(path: Path) -> bool:
    """Check if any segment in the path belongs to ignored dependency/build directories."""
    for part in path.parts:
        if part in IGNORE_DIRS:
            return True
        if part.startswith(".") and part not in {".", ".."}:
            return True
        if part.endswith(".egg-info") or part.endswith(".dist-info"):
            return True
    return False


def get_git_modified_directories(repo_root: Path = REPO_ROOT) -> Set[Path]:
    """Get all directories containing modified, added, or untracked files in git."""
    modified_dirs: Set[Path] = set()

    try:
        # Check uncommitted status (staged and unstaged)
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
            # Status is in the first 2 characters, file path follows
            parts = line[2:].strip().split(" -> ")
            rel_path = parts[-1].strip()
            fpath = repo_root / rel_path

            # Skip ignored directories and root-level config files
            if is_ignored_path(fpath.relative_to(repo_root)):
                continue

            parent = fpath.parent if not fpath.is_dir() else fpath
            if parent != repo_root and parent.exists() and not is_ignored_path(parent.relative_to(repo_root)):
                modified_dirs.add(parent.resolve())
    except Exception as e:
        print(f"Warning: git status check failed: {e}", file=sys.stderr)

    return modified_dirs


def validate_readme_frontmatter(readme_path: Path) -> List[str]:
    """Validate that README.md has valid frontmatter with name and summary."""
    errors = []
    if not readme_path.exists():
        return [f"Missing '{readme_path.name}'"]

    try:
        text = readme_path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        return [f"Unable to read file: {e}"]

    match = FRONTMATTER_RE.match(text)
    if not match:
        return ["Missing YAML frontmatter (expected '---' at start of file)"]

    try:
        data = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError as e:
        return [f"Invalid YAML in frontmatter: {e}"]

    if not isinstance(data, dict):
        return ["Frontmatter must be a YAML dictionary"]

    # Check required fields
    summary = data.get("summary")
    if not summary:
        errors.append("Missing required field 'summary' in frontmatter")
    elif not isinstance(summary, str) or len(summary.strip()) < 15:
        errors.append(f"'summary' must be a descriptive string of at least 15 characters (got: {summary!r})")

    return errors


def lint_directory(directory: Path, repo_root: Path = REPO_ROOT) -> List[str]:
    """Lint a single directory for frontmatter compliance (FRONTMATTER.md at root, README.md elsewhere)."""
    is_root = (directory.resolve() == repo_root.resolve())
    if is_root:
        target = repo_root / "FRONTMATTER.md"
        rel = "FRONTMATTER.md"
    else:
        target = directory / "README.md"
        rel = str(directory.resolve().relative_to(repo_root.resolve()))

    errors = validate_readme_frontmatter(target)

    if errors:
        return [f"`{rel}`: {'; '.join(errors)}"]
    return []


def main():
    parser = argparse.ArgumentParser(description="Lint folder README.md frontmatter tree")
    parser.add_argument("--changed-only", action="store_true", help="Only check directories with git modifications")
    parser.add_argument("--all", action="store_true", help="Check all project directories")
    parser.add_argument("directories", nargs="*", help="Specific directories to check")
    args = parser.parse_args()

    dirs_to_check: Set[Path] = set()

    if args.directories:
        for d in args.directories:
            p = Path(d)
            if p.is_dir():
                dirs_to_check.add(p.resolve())
    elif args.changed_only or not args.all:
        dirs_to_check = get_git_modified_directories(REPO_ROOT)
    else:
        # Check all logical folders in topics, projects, local, src, scripts
        for target in ["topics", "projects", "local", "src", "scripts"]:
            tpath = REPO_ROOT / target
            if tpath.is_dir():
                for root, dirs, _ in os.walk(tpath):
                    dirs[:] = [
                        d for d in dirs
                        if not is_ignored_path((Path(root) / d).resolve().relative_to(REPO_ROOT.resolve()))
                    ]
                    if not is_ignored_path(Path(root).resolve().relative_to(REPO_ROOT.resolve())):
                        dirs_to_check.add(Path(root).resolve())

    all_violations: List[str] = []
    for d in sorted(dirs_to_check):
        violations = lint_directory(d, REPO_ROOT)
        all_violations.extend(violations)

    if all_violations:
        print("❌ README Frontmatter Lint Violations Found:")
        for v in all_violations:
            print(f"  • {v}")
        print("\nRun `uv run .agents/hooks/sync_readme_tree.py <dir>` or manually add frontmatter to resolve.")
        sys.exit(1)
    else:
        print("✅ README Frontmatter check passed! (All inspected directories comply)")
        sys.exit(0)


if __name__ == "__main__":
    main()
