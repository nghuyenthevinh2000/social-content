#!/usr/bin/env python3
"""
README Tree Frontmatter Synchronizer.

Auto-generates or refreshes YAML frontmatter for folder README.md files,
listing sub-modules / files and rolling up child summaries to parent folders.
Strictly ignores dependency, environment, and build directories like
node_modules, site-packages, .venv, etc.

For the repository root, synchronizes directly to `FRONTMATTER.md` at the project
root, serving as the master tree root for semantic routing.

Usage:
    uv run --project . .agents/hooks/file-selector/sync_readme_tree.py topics/blockchain
    uv run --project . .agents/hooks/file-selector/sync_readme_tree.py .                 # Syncs root FRONTMATTER.md
    uv run --project . .agents/hooks/file-selector/sync_readme_tree.py --all            # Syncs entire tree including root FRONTMATTER.md
    uv run --project . .agents/hooks/file-selector/sync_readme_tree.py projects/innovation-research --recursive
"""

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent.parent
ROOT_FRONTMATTER_FILE = "FRONTMATTER.md"

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


def get_target_manifest_path(directory: Path, repo_root: Path = REPO_ROOT) -> Path:
    """Return FRONTMATTER.md for repository root, and README.md for subdirectories."""
    if directory.resolve() == repo_root.resolve():
        return repo_root / ROOT_FRONTMATTER_FILE
    return directory / "README.md"


def extract_file_title_or_snippet(file_path: Path) -> str:
    """Extract a quick 1-line description of a file for submodule listing."""
    ext = file_path.suffix.lower()
    try:
        text = file_path.read_text(encoding="utf-8", errors="ignore")[:3000]
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
                # VitePress-style hero frontmatter (layout: home): use
                # hero.name + hero.text/tagline instead of falling through
                # to a random body line.
                hero = data.get("hero")
                if isinstance(hero, dict):
                    hero_name = hero.get("name")
                    hero_desc = hero.get("tagline") or hero.get("text")
                    if hero_name and hero_desc:
                        return f"{hero_name}: {hero_desc}"[:150]
                    if hero_name:
                        return str(hero_name)[:150]
            except Exception:
                pass
            text = text[fm_m.end():]

        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("<") or line.startswith("|") or line.startswith(":::"):
                continue
            if line.startswith("#"):
                return line.lstrip("#").strip()
            if len(line) > 20:
                return " ".join(line.split())[:120]

    elif ext in {".py", ".sh", ".bash"}:
        doc_open_m = re.match(r'^(?:#[^\n]*\n)*\s*(?:"""|\'\'\')', text)
        if doc_open_m:
            after_open = text[doc_open_m.end():]
            close_m = re.search(r'"""|\'\'\'', after_open)
            doc_body = after_open[:close_m.start()] if close_m else after_open
            doc = " ".join(doc_body.split())
            if doc:
                return doc[:150]
        comments = [
            line.lstrip("#").strip()
            for line in text.splitlines()[:15]
            if line.strip().startswith("#") and not line.strip().startswith("#!") and len(line.strip()) > 3
        ]
        if comments:
            return " ".join(comments)[:150]

    elif ext in {".html", ".htm"}:
        title_m = re.search(r"<title>(.*?)</title>", text, re.IGNORECASE | re.DOTALL)
        h1_m = re.search(r"<h1[^>]*>(.*?)</h1>", text, re.IGNORECASE | re.DOTALL)
        title = re.sub(r"<[^>]+>", "", title_m.group(1)).strip() if title_m else ""
        h1 = re.sub(r"<[^>]+>", "", h1_m.group(1)).strip() if h1_m else ""
        if title and h1 and title.lower() != h1.lower():
            return f"{title} — {h1}"[:150]
        if title:
            return title[:150]
        if h1:
            return h1[:150]

    return f"File {file_path.name}"


def sync_directory_readme(directory: Path, repo_root: Path = REPO_ROOT) -> bool:
    """Sync frontmatter for a single directory (FRONTMATTER.md at root, README.md elsewhere)."""
    if not directory.is_dir():
        return False

    is_root = (directory.resolve() == repo_root.resolve())
    try:
        rel_path = directory.resolve().relative_to(repo_root.resolve())
    except Exception:
        rel_path = directory

    # Strictly skip if inside node_modules, site-packages, etc.
    if not is_root and is_ignored_path(rel_path):
        return False

    manifest_path = get_target_manifest_path(directory, repo_root)
    existing_text = ""
    existing_meta = {}

    if manifest_path.exists():
        existing_text = manifest_path.read_text(encoding="utf-8", errors="ignore")
        match = FRONTMATTER_RE.match(existing_text)
        if match:
            try:
                existing_meta = yaml.safe_load(match.group(1)) or {}
            except Exception:
                pass
            existing_text = existing_text[match.end():]

    folder_name = repo_root.name if is_root else directory.name

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

    # 2. Key files in current directory (excluding README.md / FRONTMATTER.md, lockfiles, package noise)
    if not is_root:
        for child in sorted(directory.iterdir()):
            if child.is_file() and child.name not in {"README.md", "FRONTMATTER.md"} and not child.name.startswith("."):
                if child.name in IGNORE_FILENAMES or child.suffix.lower() in IGNORE_EXTENSIONS:
                    continue
                submodules[child.name] = extract_file_title_or_snippet(child)

    # Build metadata
    name = existing_meta.get("name") or folder_name
    summary = existing_meta.get("summary")
    if not summary:
        if is_root:
            summary = (
                "Central repository root and semantic tree orchestrator for social content, "
                "AI agent orchestration, innovation research, topic deep-dives, and creative publishing workflows."
            )
        else:
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

    if is_root and not existing_text.strip():
        existing_text = (
            "# Repository Semantic Routing Tree Root\n\n"
            "This file serves as the root manifest for TypeSafe Jev semantic directory navigation across the repository.\n"
        )

    new_content = f"---\n{fm_yaml}\n---\n\n{existing_text.strip()}\n"

    manifest_path.write_text(new_content, encoding="utf-8")
    rel_display = "FRONTMATTER.md" if is_root else f"{rel_path}/README.md"
    print(f"✅ Synced frontmatter for `{rel_display}`")
    return True


def sync_path_recursive(directory: Path, repo_root: Path = REPO_ROOT) -> None:
    """Sync a directory and its valid subdirectories bottom-up, skipping node_modules and site-packages."""
    if not directory.is_dir():
        return

    try:
        rel = directory.resolve().relative_to(repo_root.resolve())
    except Exception:
        rel = directory

    if directory.resolve() != repo_root.resolve() and is_ignored_path(rel):
        return

    for root, dirs, _ in os.walk(directory.resolve(), topdown=False):
        dirs[:] = [
            d for d in dirs
            if not is_ignored_path((Path(root) / d).resolve().relative_to(repo_root.resolve()))
        ]
        sync_directory_readme(Path(root), repo_root)


def main():
    parser = argparse.ArgumentParser(description="Synchronize README.md frontmatter tree")
    parser.add_argument("--all", action="store_true", help="Sync all project directories including root FRONTMATTER.md")
    parser.add_argument("-r", "--recursive", action="store_true", help="Sync recursively for specified paths")
    parser.add_argument("paths", nargs="*", help="Specific folder paths to sync")
    args = parser.parse_args()

    if args.paths:
        for p in args.paths:
            path = Path(p).resolve()
            if path == REPO_ROOT.resolve() or p in {".", "FRONTMATTER.md"}:
                sync_directory_readme(REPO_ROOT, REPO_ROOT)
            elif path.is_dir():
                if args.recursive:
                    sync_path_recursive(path, REPO_ROOT)
                else:
                    sync_directory_readme(path, REPO_ROOT)
    elif args.all:
        for target in ["topics", "projects", "local", "src", "scripts", "reflections"]:
            tpath = REPO_ROOT / target
            if tpath.is_dir():
                sync_path_recursive(tpath, REPO_ROOT)
        # Always sync root FRONTMATTER.md at the end so child summaries roll up
        sync_directory_readme(REPO_ROOT, REPO_ROOT)
    else:
        print("Please provide directory paths or use --all.")
        sys.exit(1)


if __name__ == "__main__":
    main()
