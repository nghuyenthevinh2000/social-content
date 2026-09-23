#!/usr/bin/env python3
"""
Folder and File Relevance Selector, backed by TypeSafe Jev (System One).

Two-stage hierarchical selection:
1. Stage 1 (Folder-level): Identifies candidate directories (e.g. topics/*, projects/*, scripts/, src/).
2. Stage 2 (File-level drilldown): For top candidate folders, discovers files (recursively,
   respecting ignores like node_modules) and uses Jev to select the exact lead file
   and relevant files to inspect.

Prevents the AI from reading broadly or wandering around the repository.

Usage:
    uv run --project . .agents/hooks/file-selector/file_selector.py "how to start a company"
    uv run --project . .agents/hooks/file-selector/file_selector.py "pop up city and digital nomads"
"""

import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent.parent

RECOMMEND_THRESHOLD = 0.30
MAX_FOLDER_DRILLDOWNS = 2
MAX_FILES_PER_FOLDER = 40
MAX_WALK_DEPTH = 6

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
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "scratch",
    ".cache",
    "coverage",
}


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

GROUPED_PARENT_DIRS = {"topics", "projects", "local"}
STANDALONE_TOP_DIRS = {"scripts", "src", "reflections"}

# Synthetic key representing the repository root itself, so loose top-level
# files (AGENTS.md, FRONTMATTER.md, README.md, pyproject.toml, etc.) and any
# top-level folder not in the two sets above are still reachable, instead of
# being silently invisible to the selector.
ROOT_FOLDER_KEY = "."


FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def read_frontmatter(md_path: Path) -> Optional[dict]:
    """
    Parse the enforced YAML frontmatter (name/summary/tags/submodules) from a
    README.md, per the Frontmatter & Documentation Integrity Rule in AGENTS.md.
    Returns None if the file is missing, has no frontmatter block, or fails to parse.
    """
    if not md_path.exists():
        return None
    try:
        text = md_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None

    m = FRONTMATTER_RE.match(text)
    if not m:
        return None

    try:
        data = yaml.safe_load(m.group(1))
    except Exception:
        return None

    if not isinstance(data, dict):
        return None
    return data


def frontmatter_folder_summary(fm: dict, rel_path: str) -> str:
    """Build a rich folder summary directly from enforced README frontmatter."""
    parts: List[str] = []

    summary = fm.get("summary")
    if isinstance(summary, str) and summary.strip():
        parts.append(" ".join(summary.split()))

    tags = fm.get("tags")
    if isinstance(tags, list) and tags:
        clean_tags = [str(t).strip() for t in tags if str(t).strip()]
        if clean_tags:
            parts.append(f"Tags: {', '.join(clean_tags[:10])}")

    submodules = fm.get("submodules")
    if isinstance(submodules, dict) and submodules:
        entries = []
        for name, desc in list(submodules.items())[:10]:
            desc_str = " ".join(str(desc).split()) if desc else ""
            entries.append(f"{name}: {desc_str}" if desc_str else str(name))
        parts.append("Sub-modules: " + " | ".join(entries))

    if not parts:
        return f"Directory {rel_path}"

    return " || ".join(parts)


def extract_folder_summary(folder_path: Path, rel_path: str) -> str:
    """Extract a rich, concise summary of what a folder contains and covers.

    Prefers the enforced README.md frontmatter (summary/tags/submodules) since
    it is authoritative and kept in sync via the repo's frontmatter guard hook.
    Falls back to heuristic content-scraping only when frontmatter is missing
    or invalid.
    """
    fm = read_frontmatter(folder_path / "README.md")
    if fm is not None:
        return frontmatter_folder_summary(fm, rel_path)

    summary_parts: List[str] = []

    best_md = folder_path / "README.md"
    if not best_md.exists():
        md_files = sorted(folder_path.glob("*.md"))
        if md_files:
            best_md = md_files[0]

    if best_md.exists():
        try:
            content = best_md.read_text(encoding="utf-8", errors="ignore")
            content = re.sub(r"^---\s*\n.*?\n---\s*\n", "", content, flags=re.DOTALL)
            content = re.sub(r"!\[.*?\]\(.*?\)", "", content)
            content = re.sub(r"```mermaid.*?```", "", content, flags=re.DOTALL)
            content = re.sub(r"<[^>]+>", "", content)

            lines = [line.strip() for line in content.splitlines() if line.strip()]

            for line in lines[:5]:
                if line.startswith("#"):
                    clean_title = line.lstrip("#").strip()
                    if clean_title:
                        summary_parts.append(clean_title)
                        break

            body_snippets: List[str] = []
            char_count = 0
            for line in lines[:60]:
                if line.startswith("## ") or line.startswith("### "):
                    h = line.lstrip("#").strip()
                    body_snippets.append(f"[{h}]")
                    char_count += len(h)
                elif line.startswith("- **") or line.startswith("• **") or line.startswith("> **"):
                    clean = " ".join(line.split())
                    clean = clean.replace(">", "").strip()
                    body_snippets.append(clean)
                    char_count += len(clean)
                elif not line.startswith("#") and not line.startswith("|") and len(line) > 25:
                    clean = " ".join(line.split())
                    body_snippets.append(clean)
                    char_count += len(clean)

                if char_count >= 350:
                    break

            if body_snippets:
                summary_parts.append(" ".join(body_snippets)[:400])
        except Exception:
            pass

    if not summary_parts and (folder_path / "index.html").exists():
        try:
            html = (folder_path / "index.html").read_text(encoding="utf-8", errors="ignore")
            title_m = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE)
            if title_m:
                summary_parts.append(title_m.group(1).strip())
        except Exception:
            pass

    try:
        subdirs: List[str] = []
        for child in sorted(folder_path.iterdir()):
            if child.is_dir() and not child.name.startswith(".") and child.name not in IGNORE_DIRS:
                nested = [
                    gc.name for gc in sorted(child.iterdir())
                    if gc.is_dir() and not gc.name.startswith(".") and gc.name not in IGNORE_DIRS
                ][:4]
                if nested:
                    subdirs.append(f"{child.name}/({', '.join(nested)})")
                else:
                    subdirs.append(child.name)
        if subdirs:
            summary_parts.append(f"Sub-modules: {', '.join(subdirs[:6])}")
    except Exception:
        pass

    if not summary_parts:
        summary_parts.append(f"Directory {rel_path}")

    return " | ".join(summary_parts)


def extract_root_summary(root_resolved: Path) -> str:
    """Build a summary for the repository root itself.

    Prefers FRONTMATTER.md (the enforced root manifest, per AGENTS.md), same
    as `extract_folder_summary` prefers a folder's README.md. Falls back to a
    generic description if FRONTMATTER.md is missing or invalid.
    """
    fm = read_frontmatter(root_resolved / "FRONTMATTER.md")
    if fm is not None:
        return frontmatter_folder_summary(fm, ROOT_FOLDER_KEY)

    return (
        f"Repository root ({root_resolved.name}). Contains top-level configuration, "
        "policy, and documentation files not scoped to any single subdirectory "
        "(e.g. AGENTS.md, README.md, pyproject.toml)."
    )


def extract_file_summary(
    file_path: Path,
    rel_path: str,
    submodule_desc: Optional[str] = None,
) -> str:
    """Extract a concise summary of what a file contains, including title and goal/summary.

    If the parent folder's README frontmatter already describes this exact
    file/dir entry in its `submodules` map, that authoritative description is
    used verbatim (it's kept accurate by the repo's frontmatter guard hook)
    instead of re-deriving a summary by scraping file content.
    """
    if submodule_desc:
        return submodule_desc

    ext = file_path.suffix.lower()
    summary_parts: List[str] = []

    # For a folder's own README.md, prefer its frontmatter `summary` field
    # over scraping the rendered markdown body.
    if file_path.name == "README.md":
        fm = read_frontmatter(file_path)
        if fm is not None:
            fm_summary = fm.get("summary")
            if isinstance(fm_summary, str) and fm_summary.strip():
                return " ".join(fm_summary.split())

    try:
        raw_text = file_path.read_text(encoding="utf-8", errors="ignore")[:4000]
    except Exception:
        return f"File {rel_path}"

    if ext in {".md", ".markdown"}:
        fm_m = re.match(r"^---\s*\n(.*?)\n---\s*\n", raw_text, re.DOTALL)
        if fm_m:
            for line in fm_m.group(1).splitlines():
                if line.startswith("title:") or line.startswith("description:"):
                    val = line.split(":", 1)[1].strip().strip('"\'')
                    if val:
                        summary_parts.append(val)
            raw_text = raw_text[fm_m.end():]

        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        for line in lines[:10]:
            if line.startswith("#") and not summary_parts:
                summary_parts.append(line.lstrip("#").strip())
                break

        body_snippets: List[str] = []
        for line in lines[:35]:
            if line.startswith("- **Goal:**") or line.startswith("> **") or line.startswith("## "):
                clean = " ".join(line.replace(">", "").replace("#", "").split()).strip()
                body_snippets.append(clean)
            elif not line.startswith("#") and not line.startswith("|") and len(line) > 20:
                body_snippets.append(" ".join(line.split()))
            if len(" ".join(body_snippets)) >= 220:
                break

        if body_snippets:
            summary_parts.append(" ".join(body_snippets)[:250])

    elif ext in {".py", ".sh", ".bash"}:
        doc_m = re.search(r'^(?:#[^\n]*\n)*\s*(?:"""|\'\'\')(.*?)(?:"""|\'\'\')', raw_text, re.DOTALL)
        if doc_m:
            doc = " ".join(doc_m.group(1).split())
            summary_parts.append(doc[:220])
        else:
            comments = [
                line.lstrip("#").strip()
                for line in raw_text.splitlines()[:15]
                if line.startswith("#") and len(line.strip()) > 3
            ]
            if comments:
                summary_parts.append(" ".join(comments)[:220])

    elif ext in {".html", ".htm"}:
        title_m = re.search(r"<title>(.*?)</title>", raw_text, re.IGNORECASE)
        if title_m:
            summary_parts.append(title_m.group(1).strip())
        h1_m = re.search(r"<h1[^>]*>(.*?)</h1>", raw_text, re.IGNORECASE)
        if h1_m:
            summary_parts.append(re.sub(r"<[^>]+>", "", h1_m.group(1)).strip())

    elif ext in {".json", ".yaml", ".yml", ".toml"}:
        summary_parts.append(f"Config/Data file ({ext})")

    if not summary_parts:
        summary_parts.append(f"{file_path.name}")

    return " | ".join(summary_parts)


def discover_candidate_folders(root_dir: Path = REPO_ROOT) -> Dict[str, str]:
    """Discover logical candidate folders across the repository and their summaries."""
    candidates = {}
    root_resolved = root_dir.resolve()

    if not root_resolved.exists():
        return candidates

    for group_name in GROUPED_PARENT_DIRS:
        group_path = root_resolved / group_name
        if group_path.is_dir():
            for child in sorted(group_path.iterdir()):
                if child.is_dir() and not child.name.startswith(".") and child.name not in IGNORE_DIRS:
                    rel = f"{group_name}/{child.name}"
                    candidates[rel] = extract_folder_summary(child, rel)

    for top_name in STANDALONE_TOP_DIRS:
        top_path = root_resolved / top_name
        if top_path.is_dir():
            candidates[top_name] = extract_folder_summary(top_path, top_name)

    # Repository root itself: covers loose top-level files (AGENTS.md,
    # FRONTMATTER.md, README.md, pyproject.toml, etc.) and any top-level
    # folder not already covered by the two named sets above.
    candidates[ROOT_FOLDER_KEY] = extract_root_summary(root_resolved)

    return candidates


def discover_folder_files(
    folder_path: Path,
    root_dir: Path = REPO_ROOT,
    max_depth: int = MAX_WALK_DEPTH,
    max_files: int = MAX_FILES_PER_FOLDER,
) -> Dict[str, str]:
    """Discover candidate files within a directory and extract summaries.

    Whenever a file/subdir is already described in its parent folder's
    README frontmatter `submodules` map, that authoritative, human/AI-curated
    description is used instead of re-deriving a summary from raw content.
    This depends on the frontmatter guard hook keeping submodules accurate.
    """
    files: Dict[str, str] = {}
    folder_res = folder_path.resolve()
    root_res = root_dir.resolve()

    if not folder_res.exists() or not folder_res.is_dir():
        return files

    # Cache of {dir_path: submodules dict} to avoid re-parsing README frontmatter.
    submodules_cache: Dict[Path, Dict[str, str]] = {}

    def get_submodules(dir_path: Path) -> Dict[str, str]:
        if dir_path in submodules_cache:
            return submodules_cache[dir_path]
        fm = read_frontmatter(dir_path / "README.md")
        submodules = {}
        if fm is not None:
            raw_submodules = fm.get("submodules")
            if isinstance(raw_submodules, dict):
                submodules = {
                    str(k).rstrip("/"): " ".join(str(v).split())
                    for k, v in raw_submodules.items()
                }
        submodules_cache[dir_path] = submodules
        return submodules

    candidate_paths: List[Path] = []
    for root, dirs, filenames in os.walk(folder_res):
        # Exclude ignored directories anywhere in the walk tree
        dirs[:] = [
            d for d in dirs
            if not is_ignored_path((Path(root) / d).resolve().relative_to(root_res))
        ]

        depth = len(Path(root).relative_to(folder_res).parts)
        if depth >= max_depth:
            dirs.clear()

        for filename in filenames:
            if filename.startswith(".") or filename in IGNORE_FILENAMES:
                continue
            fpath = Path(root) / filename
            if fpath.suffix.lower() in IGNORE_EXTENSIONS:
                continue
            candidate_paths.append(fpath)

    # Prioritize files explicitly described in a parent's submodules map
    # (authoritative signal), then markdown files, then guides/docs.
    def file_priority(p: Path) -> Tuple[int, int, int, str]:
        parent_submodules = get_submodules(p.parent)
        has_submodule_desc = 0 if parent_submodules.get(p.name) else 1
        is_md = 0 if p.suffix == ".md" else 1
        is_guide_or_stage = 0 if any(part in {"guides", "stages", "structures"} for part in p.parts) else 1
        return (has_submodule_desc, is_md, is_guide_or_stage, p.name)

    candidate_paths.sort(key=file_priority)
    candidate_paths = candidate_paths[:max_files]

    for fpath in candidate_paths:
        try:
            rel = str(fpath.resolve().relative_to(root_res))
            parent_submodules = get_submodules(fpath.parent)
            submodule_desc = parent_submodules.get(fpath.name)
            files[rel] = extract_file_summary(fpath, rel, submodule_desc=submodule_desc)
        except Exception:
            pass

    return files


def discover_root_files(
    root_dir: Path = REPO_ROOT,
    max_files: int = MAX_FILES_PER_FOLDER,
) -> Dict[str, str]:
    """Discover loose top-level files directly in the repository root.

    Intentionally shallow (non-recursive): subdirectories are already covered
    as their own candidates via `discover_candidate_folders`, so recursing
    here would just re-walk the entire repository tree.
    """
    files: Dict[str, str] = {}
    root_res = root_dir.resolve()

    if not root_res.exists() or not root_res.is_dir():
        return files

    fm = read_frontmatter(root_res / "FRONTMATTER.md")
    submodules: Dict[str, str] = {}
    if fm is not None:
        raw_submodules = fm.get("submodules")
        if isinstance(raw_submodules, dict):
            submodules = {
                str(k).rstrip("/"): " ".join(str(v).split())
                for k, v in raw_submodules.items()
            }

    candidate_paths: List[Path] = []
    for child in sorted(root_res.iterdir()):
        if not child.is_file():
            continue
        if child.name.startswith(".") or child.name in IGNORE_FILENAMES:
            continue
        if child.suffix.lower() in IGNORE_EXTENSIONS:
            continue
        candidate_paths.append(child)

    def file_priority(p: Path) -> Tuple[int, int, str]:
        has_submodule_desc = 0 if submodules.get(p.name) else 1
        is_md = 0 if p.suffix == ".md" else 1
        return (has_submodule_desc, is_md, p.name)

    candidate_paths.sort(key=file_priority)
    candidate_paths = candidate_paths[:max_files]

    for fpath in candidate_paths:
        try:
            rel = str(fpath.resolve().relative_to(root_res))
            files[rel] = extract_file_summary(fpath, rel, submodule_desc=submodules.get(fpath.name))
        except Exception:
            pass

    return files


def select_folders(
    request_text: str,
    folders: Optional[Dict[str, str]] = None,
    threshold: float = RECOMMEND_THRESHOLD,
) -> dict:
    """Evaluate candidate folders against user request using Jev."""
    if folders is None:
        folders = discover_candidate_folders()

    if not folders:
        return {
            "primary": None,
            "primary_confidence": 0.0,
            "recommended": [],
            "all_scores": {},
        }

    from typesafe_sdk import Choice, Noul, TypeSafeClient

    questions = {}
    for folder_path, summary in folders.items():
        questions[f"rel::{folder_path}"] = Noul(
            instructions=(
                f"Could the user's request find relevant guides, notes, frameworks, code, or knowledge in '{folder_path}'? "
                f"Description: {summary}"
            )
        )

    choice_criteria = dict(folders)
    choice_criteria["none"] = "No single folder is the primary focus, or the task is repo-wide / generic."
    questions["primary_folder"] = Choice(
        instructions=(
            "Which single folder is the primary focus of this request? "
            "Choose 'none' if no single folder dominates or if multiple folders share equal weight."
        ),
        criteria=choice_criteria,
    )

    with TypeSafeClient() as client:
        response = client.system_one(
            state={"user_request": request_text, "workspace": REPO_ROOT.name},
            questions=questions,
        )

    all_scores = {}
    for folder_path in folders:
        answer = response.answers[f"rel::{folder_path}"]
        all_scores[folder_path] = round(answer.noul, 4)

    recommended = sorted(
        (
            {"folder": folder_path, "probability": prob}
            for folder_path, prob in all_scores.items()
            if prob >= threshold
        ),
        key=lambda item: -item["probability"],
    )

    primary_answer = response.answers["primary_folder"]
    primary_choice = primary_answer.choice if primary_answer.choice != "none" else None

    return {
        "primary": primary_choice,
        "primary_confidence": round(primary_answer.confidence, 4),
        "recommended": recommended,
        "all_scores": all_scores,
    }


def select_files(
    request_text: str,
    files: Dict[str, str],
    threshold: float = RECOMMEND_THRESHOLD,
) -> dict:
    """Evaluate candidate files within a folder against user request using Jev."""
    if not files:
        return {
            "primary": None,
            "primary_confidence": 0.0,
            "recommended": [],
            "all_scores": {},
        }

    if len(files) == 1:
        only_file = next(iter(files.keys()))
        return {
            "primary": only_file,
            "primary_confidence": 1.0,
            "recommended": [{"file": only_file, "probability": 1.0}],
            "all_scores": {only_file: 1.0},
        }

    from typesafe_sdk import Choice, Noul, TypeSafeClient

    questions = {}
    for file_path, summary in files.items():
        questions[f"file::{file_path}"] = Noul(
            instructions=(
                f"Could the user's request find relevant knowledge, methodology, guides, or answers in '{file_path}'? "
                f"Description: {summary}"
            )
        )

    choice_criteria = dict(files)
    choice_criteria["none"] = "No single file is the clear lead file for this request."
    questions["lead_file"] = Choice(
        instructions=(
            "Which single file is the best starting point or lead file to inspect/edit for this request? "
            "Pick 'none' if no single file clearly leads."
        ),
        criteria=choice_criteria,
    )

    with TypeSafeClient() as client:
        response = client.system_one(
            state={"user_request": request_text},
            questions=questions,
        )

    all_scores = {}
    for file_path in files:
        answer = response.answers[f"file::{file_path}"]
        all_scores[file_path] = round(answer.noul, 4)

    recommended = sorted(
        (
            {"file": file_path, "probability": prob}
            for file_path, prob in all_scores.items()
            if prob >= threshold
        ),
        key=lambda item: -item["probability"],
    )

    primary_answer = response.answers["lead_file"]
    primary_choice = primary_answer.choice if primary_answer.choice != "none" else None

    return {
        "primary": primary_choice,
        "primary_confidence": round(primary_answer.confidence, 4),
        "recommended": recommended,
        "all_scores": all_scores,
    }


def select_hierarchical(
    request_text: str,
    root_dir: Path = REPO_ROOT,
    max_folder_drilldowns: int = MAX_FOLDER_DRILLDOWNS,
) -> dict:
    """Two-stage selection: evaluate folders first, then drill down into files."""
    root_res = root_dir.resolve()
    folders = discover_candidate_folders(root_res)
    folder_result = select_folders(request_text, folders=folders)

    candidate_folders: List[str] = []
    if folder_result.get("primary"):
        candidate_folders.append(folder_result["primary"])
    for r in folder_result.get("recommended", []):
        if r["folder"] not in candidate_folders:
            candidate_folders.append(r["folder"])

    # Fallback: if no folder cleared the threshold, don't abort early.
    # Take the top 2 candidate folders that score meaningfully above the noise floor (>= 0.12)
    if not candidate_folders and folder_result.get("all_scores"):
        sorted_folders = sorted(
            folder_result["all_scores"].items(),
            key=lambda item: -item[1],
        )
        for folder_name, score in sorted_folders[:max_folder_drilldowns]:
            if score >= 0.12:
                candidate_folders.append(folder_name)

    candidate_folders = candidate_folders[:max_folder_drilldowns]

    files_by_folder = {}
    top_lead_file = None
    top_lead_confidence = 0.0
    all_recommended_files = []

    best_folder = folder_result.get("primary")
    for folder_name in candidate_folders:
        if folder_name == ROOT_FOLDER_KEY:
            files = discover_root_files(root_dir=root_res)
        else:
            folder_path = root_res / folder_name
            files = discover_folder_files(folder_path, root_dir=root_res)
        if not files:
            continue
        f_res = select_files(request_text, files)
        files_by_folder[folder_name] = f_res

        # If this folder produced higher-confidence lead file or primary had no files
        if f_res.get("primary"):
            if not top_lead_file or f_res.get("primary_confidence", 0.0) > top_lead_confidence or (folder_result.get("primary") and not files_by_folder.get(folder_result.get("primary", ""), {}).get("recommended")):
                top_lead_file = f_res["primary"]
                top_lead_confidence = f_res["primary_confidence"]
                best_folder = folder_name

        all_recommended_files.extend(f_res.get("recommended", []))

    if best_folder:
        folder_result["primary"] = best_folder

    all_recommended_files.sort(key=lambda item: -item["probability"])

    return {
        "folder": folder_result,
        "files": {
            "lead_file": top_lead_file,
            "lead_confidence": top_lead_confidence,
            "recommended": all_recommended_files,
            "by_folder": files_by_folder,
        },
    }


def main():
    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / ".env")

    if len(sys.argv) > 1:
        request_text = " ".join(sys.argv[1:])
    else:
        request_text = sys.stdin.read().strip()

    if not request_text:
        print(json.dumps({"error": "No request text provided"}, indent=2))
        sys.exit(1)

    result = select_hierarchical(request_text, root_dir=REPO_ROOT)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
