#!/usr/bin/env python3
"""
Repository Directory Index & Repomix Generator.

Crawls all repository directories and files (ignoring build, venv, and cache artifacts)
and outputs a comprehensive, unified JSON directory index saved to:
    local/index.json (with symlink local/directory_index.json)
And updates Repomix pack output:
    local/repomix-output.json

Provides AI agents and hooks (e.g. file_selector) with a complete, single-lookup
view of all folders, nested subdirectories, tags, and files without requiring
piecemeal frontmatter headers inside README.md files.

Usage:
    uv run --project . .agents/hooks/file-selector/sync_directory_index.py
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent.parent
LOCAL_DIR = REPO_ROOT / "local"
OUTPUT_JSON = LOCAL_DIR / "index.json"
SYMLINK_JSON = LOCAL_DIR / "directory_index.json"

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
    ".obsidian",
    ".copilot",
    ".opencode",
}

IGNORE_EXTENSIONS: Set[str] = {
    ".pyc",
    ".pyo",
    ".lock",
    ".map",
}

IGNORE_FILENAMES: Set[str] = {
    ".DS_Store",
    "package-lock.json",
    "uv.lock",
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
    """Extract a quick 1-line description of a file for listing."""
    ext = file_path.suffix.lower()
    if ext in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico"}:
        return f"Image asset ({file_path.name})"
    if ext in {".pdf"}:
        return f"PDF document ({file_path.name})"
    if ext in {".mp4", ".mov", ".mkv", ".webm"}:
        return f"Video asset ({file_path.name})"
    if ext in {".csv"}:
        return f"CSV dataset ({file_path.name})"

    try:
        text = file_path.read_text(encoding="utf-8", errors="ignore")[:3000]
    except Exception:
        return f"File {file_path.name}"

    if ext in {".md", ".markdown"}:
        fm_m = FRONTMATTER_RE.match(text)
        if fm_m:
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

    elif ext == ".json":
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                desc = data.get("description") or data.get("summary") or data.get("name")
                if desc:
                    return str(desc)[:120]
        except Exception:
            pass
        return f"JSON configuration ({file_path.name})"

    return f"File {file_path.name}"


KNOWN_SUMMARIES = {
    "local/block-lc": "Unified operations hub for Block L&C (Crypto & Web3 Legal & Consulting), consolidating brand identity package, visual assets, competitor research, event assets, executive one-pagers, and the social campaign metrics loop.",
    "local/block-lc/brand": "Structured brand package containing visual identity guidelines, brand.yaml, context.md, naming strategy, competitor audits, and design benchmarks.",
    "local/block-lc/brand/assets": "Official brand graphics, logo marks, and visual creative assets for Block L&C.",
    "local/block-lc/brand/one-pager": "Executive legal tech one-pager, value proposition breakdown, and layout design content.",
    "local/block-lc/brand/preview": "Live brand system switcher preview (Harvey, Ironclad, Legora, Fenwick) and web showcase.",
    "local/block-lc/brand/references": "Brand style DNA benchmarks, writing analysis (Phoebe Duong), and visual references.",
    "local/block-lc/customer": "Target client personas (founders, DAOs, funds) and qualified inbound lead pipelines.",
    "local/block-lc/event": "Crypto & Web3 legal workshops, event skeletons, and content execution plans.",
    "local/block-lc/loop": "Project-scoped metrics loop, publications registry, and checkpoint engine for ongoing publishing iterations.",
    "local/block-lc/loop/runs": "Run artifacts, verification logs, and checkpoint executions.",
    "local/block-lc/posts": "Staged social campaign posts, copy variations, and hypothesis matrices.",
    "local/block-lc/posts/1": "First staged social campaign post batch: LinkedIn post, Facebook ad, and DAO liability visual asset.",
    "local/block-lc/sources": "Performance receipts, raw post metrics exports, and DOM captures.",
    "local/paper-ink-product": "E-commerce and marketing operation for Thế Vinh Eco Paper & Ink, featuring product marketing profiles, video blends, and social loops.",
    "local/paper-ink-product/posts": "Staged social posts and video campaigns for Thế Vinh Eco Paper & Ink.",
    "local/paper-ink-product/brand-assets": "Official logos, product photo assets, and packaging labels for Thế Vinh Eco Paper & Ink.",
    "local/charity-platform": "Transparency Fun charity platform research, executive one-pagers, and Chùa Việt initiative documents.",
    "local/market-research": "Fanpage agency service proposal, Web3 legal marketing research, and small business community scans.",
    "local/chinese-story": "Chinese story translation and narrative content workspace.",
    "local/interviews": "Transcripts and notes from expert interviews (Effective Altruism, Myrias).",
}


def extract_folder_summary(dir_path: Path, rel_path: str) -> str:
    """Determine a rich, concise summary for the folder."""
    if rel_path in KNOWN_SUMMARIES:
        return KNOWN_SUMMARIES[rel_path]

    # Check README.md
    readme = dir_path / "README.md"
    if readme.exists():
        try:
            txt = readme.read_text(encoding="utf-8", errors="ignore")
            lines = [l.strip() for l in txt.splitlines() if l.strip()]
            for l in lines:
                if l.startswith("# "):
                    return l.lstrip("#").strip() + f". Documentation for {rel_path}."
        except Exception:
            pass

    # Check index.html
    index_html = dir_path / "index.html"
    if index_html.exists():
        try:
            txt = index_html.read_text(encoding="utf-8", errors="ignore")
            title_m = re.search(r"<title>(.*?)</title>", txt, re.IGNORECASE)
            if title_m:
                return f"{title_m.group(1).strip()} ({rel_path})"
        except Exception:
            pass

    return f"Workspace directory for {rel_path}."


def generate_directory_index(repo_root: Path = REPO_ROOT) -> Dict[str, Any]:
    """Crawl entire repository and build the directory index mapping."""
    directories: Dict[str, Any] = {}

    for root, dir_names, filenames in os.walk(repo_root):
        dir_path = Path(root)
        try:
            rel = dir_path.relative_to(repo_root)
        except Exception:
            continue

        if rel != Path(".") and is_ignored_path(rel):
            continue

        rel_str = str(rel) if str(rel) != "." else "."

        # Filter valid immediate subdirectories
        valid_subdirs = []
        for d in sorted(dir_names):
            sub_p = rel / d if rel != Path(".") else Path(d)
            if not is_ignored_path(sub_p):
                valid_subdirs.append(str(sub_p))

        # Filter and summarize valid immediate files
        files_map: Dict[str, str] = {}
        for f in sorted(filenames):
            if f in IGNORE_FILENAMES or f.startswith("."):
                continue
            ext = Path(f).suffix.lower()
            if ext in IGNORE_EXTENSIONS:
                continue
            file_path = dir_path / f
            files_map[f] = extract_file_title_or_snippet(file_path)

        tags = [p for p in rel.parts if p not in {".", ".."}]
        if not tags:
            tags = ["root"]

        entry = {
            "path": rel_str,
            "name": dir_path.name if rel_str != "." else repo_root.name,
            "summary": extract_folder_summary(dir_path, rel_str),
            "tags": tags,
            "subdirectories": valid_subdirs,
            "files": files_map,
        }
        directories[rel_str] = entry

    data = {
        "version": "1.0",
        "description": "Comprehensive unified repository directory index for TypeSafe Jev, Repomix, and AI agents.",
        "directories": directories,
    }
    return data


def run_repomix():
    """Run Repomix CLI using repomix.config.json if npx is available."""
    npx_bin = shutil.which("npx")
    if not npx_bin:
        print("ℹ️  npx not found, skipping repomix pack.")
        return
    try:
        res = subprocess.run(
            [npx_bin, "-y", "repomix"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if res.returncode == 0:
            print("✅ Repomix pack refreshed at `local/repomix-output.json`")
        else:
            print(f"⚠️  Repomix finished with code {res.returncode}: {res.stderr[:200]}")
    except Exception as e:
        print(f"⚠️  Could not run repomix: {e}")


def sync_index(with_repomix: bool = True):
    LOCAL_DIR.mkdir(parents=True, exist_ok=True)
    index_data = generate_directory_index(REPO_ROOT)
    
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(index_data, f, indent=2, ensure_ascii=False)
    print(f"✅ Generated directory index with {len(index_data['directories'])} directories at `{OUTPUT_JSON}`")

    try:
        if SYMLINK_JSON.is_symlink() or SYMLINK_JSON.exists():
            SYMLINK_JSON.unlink()
        SYMLINK_JSON.symlink_to("index.json")
        print(f"✅ Created symlink `{SYMLINK_JSON}` -> index.json")
    except Exception:
        with open(SYMLINK_JSON, "w", encoding="utf-8") as f:
            json.dump(index_data, f, indent=2, ensure_ascii=False)

    if with_repomix:
        run_repomix()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Synchronize directory index & Repomix pack")
    parser.add_argument("--no-repomix", action="store_true", help="Skip running repomix packing")
    args = parser.parse_args()
    sync_index(with_repomix=not args.no_repomix)
