#!/usr/bin/env python3
"""
README Tree Frontmatter Synchronizer.

Auto-generates or refreshes YAML frontmatter for folder README.md files,
listing sub-modules / files and rolling up child summaries to parent folders.
Strictly ignores dependency, environment, and build directories like
node_modules, site-packages, .venv, etc.

Usage:
    uv run --project . scripts/sync_readme_tree.py topics/blockchain
    uv run --project . scripts/sync_readme_tree.py --all
    uv run --project . scripts/sync_readme_tree.py projects/innovation-research --recursive
"""

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent

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

IGNORE_EXTENSIONS: Set[str] = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".svg",
    ".ico",
    ".pdf",
    ".mp4",
    ".mov",
    ".mkv",
    ".webm",
    ".mp3",
    ".wav",
    ".m4a",
    ".aac",
    ".flac",
    ".ogg",
    ".zip",
    ".tar",
    ".gz",
    ".pyc",
    ".pyo",
    ".lock",
    ".map",
}

IGNORE_FILENAMES: Set[str] = {
    "package.json",
    "package-lock.json",
    "tsconfig.json",
    "LICENSE",
    "LICENSE.md",
    "LICENSE.txt",
    ".DS_Store",
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


def extract_file_title_or_snippet(file_path: Path) -> str:
    """Extract a quick 1-line description of a file for submodule listing."""
    ext = file_path.suffix.lower()
    try:
        text = file_path.read_text(encoding="utf-8", errors="ignore")[:1000]
    except Exception:
        return f"{file_path.name}"

    if ext in {".md", ".markdown"}:
        fm_m = FRONTMATTER_RE.match(text)
        if fm_m:
            try:
                data = yaml.safe_load(fm_m.group(1)) or {}
                if data.get("summary"):
                    return data["summary"]
                if data.get("title"):
                    return data["title"]
            except Exception:
                pass
            text = text[fm_m.end():]

        for line in text.splitlines():
            line = line.strip()
            if line.startswith("#"):
                return line.lstrip("#").strip()
            if not line.startswith("|") and len(line) > 20:
                return " ".join(line.split())[:120]

    return f"File {file_path.name}"


def sync_directory_readme(directory: Path, repo_root: Path = REPO_ROOT) -> bool:
    """Sync frontmatter for a single directory's README.md."""
    if not directory.is_dir():
        return False

    try:
        rel_path = directory.resolve().relative_to(repo_root.resolve())
    except Exception:
        rel_path = directory

    # Strictly skip if inside node_modules, site-packages, etc.
    if is_ignored_path(rel_path):
        return False

    readme_path = directory / "README.md"
    existing_text = ""
    existing_meta = {}

    if readme_path.exists():
        existing_text = readme_path.read_text(encoding="utf-8", errors="ignore")
        match = FRONTMATTER_RE.match(existing_text)
        if match:
            try:
                existing_meta = yaml.safe_load(match.group(1)) or {}
            except Exception:
                pass
            existing_text = existing_text[match.end():]

    folder_name = directory.name

    # Collect submodules (immediate subdirectories with summaries, or key files)
    submodules: Dict[str, str] = {}

    # 1. Child directories (skipping node_modules, site-packages, etc.)
    for child in sorted(directory.iterdir()):
        if child.is_dir():
            try:
                child_rel = child.resolve().relative_to(repo_root.resolve())
            except Exception:
                child_rel = child

            if is_ignored_path(child_rel):
                continue

            child_readme = child / "README.md"
            child_desc = ""
            if child_readme.exists():
                try:
                    c_text = child_readme.read_text(encoding="utf-8", errors="ignore")
                    c_match = FRONTMATTER_RE.match(c_text)
                    if c_match:
                        c_meta = yaml.safe_load(c_match.group(1)) or {}
                        child_desc = c_meta.get("summary", "")
                except Exception:
                    pass
            if not child_desc:
                child_desc = f"Subdirectory containing {child.name} modules"
            submodules[f"{child.name}/"] = child_desc

    # 2. Key files in current directory (excluding README.md, lockfiles, package noise)
    for child in sorted(directory.iterdir()):
        if child.is_file() and child.name != "README.md" and not child.name.startswith("."):
            if child.name in IGNORE_FILENAMES or child.suffix.lower() in IGNORE_EXTENSIONS:
                continue
            submodules[child.name] = extract_file_title_or_snippet(child)

    # Build metadata
    name = existing_meta.get("name") or folder_name
    summary = existing_meta.get("summary")
    if not summary:
        first_h1 = None
        for line in existing_text.splitlines():
            if line.startswith("# "):
                first_h1 = line.lstrip("#").strip()
                break
        if first_h1:
            summary = f"{first_h1}. Purpose and documentation for {rel_path}."
        else:
            summary = f"Documentation and resources for {rel_path}."

    tags = existing_meta.get("tags") or [folder_name]

    frontmatter_dict = {
        "name": name,
        "summary": summary,
        "tags": tags,
    }
    if submodules:
        frontmatter_dict["submodules"] = submodules

    fm_yaml = yaml.dump(frontmatter_dict, sort_keys=False, allow_unicode=True).strip()
    new_content = f"---\n{fm_yaml}\n---\n\n{existing_text.strip()}\n"

    readme_path.write_text(new_content, encoding="utf-8")
    print(f"✅ Synced frontmatter for `{rel_path}/README.md`")
    return True


def sync_path_recursive(directory: Path, repo_root: Path = REPO_ROOT) -> None:
    """Sync a directory and its valid subdirectories bottom-up, skipping node_modules and site-packages."""
    if not directory.is_dir():
        return

    try:
        rel = directory.resolve().relative_to(repo_root.resolve())
    except Exception:
        rel = directory

    if is_ignored_path(rel):
        return

    for root, dirs, _ in os.walk(directory.resolve(), topdown=False):
        # Prune ignored directories in place
        dirs[:] = [
            d for d in dirs
            if not is_ignored_path((Path(root) / d).resolve().relative_to(repo_root.resolve()))
        ]
        sync_directory_readme(Path(root), repo_root)


def main():
    parser = argparse.ArgumentParser(description="Synchronize README.md frontmatter tree")
    parser.add_argument("--all", action="store_true", help="Sync all project directories")
    parser.add_argument("-r", "--recursive", action="store_true", help="Sync recursively for specified paths")
    parser.add_argument("paths", nargs="*", help="Specific folder paths to sync")
    args = parser.parse_args()

    if args.paths:
        for p in args.paths:
            path = Path(p).resolve()
            if path.is_dir():
                if args.recursive:
                    sync_path_recursive(path, REPO_ROOT)
                else:
                    sync_directory_readme(path, REPO_ROOT)
    elif args.all:
        for target in ["topics", "projects", "local", "src", "scripts"]:
            tpath = REPO_ROOT / target
            if tpath.is_dir():
                sync_path_recursive(tpath, REPO_ROOT)
    else:
        print("Please provide directory paths or use --all.")
        sys.exit(1)


if __name__ == "__main__":
    main()
