"""Deterministic repository index builder.

The index is an edit-oriented catalog, not a documentation dump. For every file
it records what the file owns (symbols, imports, dependents, tests, entrypoint),
plus a short summary and optional ``change_when`` guidance.

The canonical output lives at ``local/index.json`` by default. ``local/`` is
gitignored in this repository, so the index can safely mention machine-local
paths without publishing them. ``--public`` builds a sanitized index that
excludes ``local/`` for CI or sharing.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

import yaml

from .ignore import IgnoreRules, load_rules

SCHEMA_VERSION = 2
GENERATOR = "tools.repo_index"
DEFAULT_INDEX_REL = "local/index.json"
OVERRIDES_REL = "local/index.overrides.json"
TEXT_LIMIT = 64 * 1024
HASH_LIMIT = 8 * 1024 * 1024

FRONTMATTER_RE = re.compile(r"^---\s*\r?\n(.*?)\r?\n---\s*\r?\n", re.DOTALL)
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)

TEXT_EXTENSIONS: Set[str] = {
    ".md",
    ".markdown",
    ".mdx",
    ".py",
    ".js",
    ".jsx",
    ".mjs",
    ".cjs",
    ".ts",
    ".tsx",
    ".html",
    ".htm",
    ".css",
    ".scss",
    ".sass",
    ".less",
    ".json",
    ".jsonc",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".conf",
    ".sh",
    ".bash",
    ".zsh",
    ".fish",
    ".sql",
    ".go",
    ".rs",
    ".java",
    ".kt",
    ".kts",
    ".c",
    ".h",
    ".cc",
    ".cpp",
    ".hpp",
    ".rb",
    ".php",
    ".swift",
    ".xml",
    ".txt",
    ".rst",
    ".csv",
    ".tsv",
}

LANGUAGE_BY_EXT: Dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".html": "html",
    ".htm": "html",
    ".css": "css",
    ".scss": "scss",
    ".md": "markdown",
    ".markdown": "markdown",
    ".mdx": "markdown",
    ".json": "json",
    ".jsonc": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".sh": "shell",
    ".bash": "shell",
    ".zsh": "shell",
    ".sql": "sql",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".kt": "kotlin",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".rb": "ruby",
    ".php": "php",
    ".swift": "swift",
    ".xml": "xml",
}

TEST_PATH_RE = re.compile(r"(^|/)(tests?|__tests__)/|(^|/)test_[^/]+\.py$|_test\.py$|\.test\.[jt]sx?$|\.spec\.[jt]sx?$")

MEDIA_SUMMARIES: Dict[str, str] = {
    ".png": "Image asset",
    ".jpg": "Image asset",
    ".jpeg": "Image asset",
    ".gif": "Image asset",
    ".webp": "Image asset",
    ".svg": "SVG image asset",
    ".ico": "Icon asset",
    ".pdf": "PDF document",
    ".mp4": "Video asset",
    ".mov": "Video asset",
    ".mp3": "Audio asset",
    ".wav": "Audio asset",
    ".csv": "CSV dataset",
    ".tsv": "TSV dataset",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def posix_rel(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def read_text(path: Path, limit: int = TEXT_LIMIT) -> Optional[str]:
    """Read a text file, returning None for binary/oversized content."""
    suffix = path.suffix.lower()
    if suffix not in TEXT_EXTENSIONS:
        return None
    try:
        if path.stat().st_size > 2 * 1024 * 1024:
            return None
        data = path.read_bytes()[:limit]
        if b"\x00" in data:
            return None
        return data.decode("utf-8", errors="ignore")
    except OSError:
        return None


def parse_frontmatter(text: Optional[str]) -> Dict[str, Any]:
    if not text:
        return {}
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}
    try:
        data = yaml.safe_load(match.group(1))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def normalize_submodules(raw: Any) -> Dict[str, str]:
    if not isinstance(raw, dict):
        return {}
    result: Dict[str, str] = {}
    for key, value in raw.items():
        name = str(key).strip().rstrip("/")
        desc = " ".join(str(value).split()) if value is not None else ""
        if name:
            result[name] = desc
    return result


def summarize_text(value: Any) -> str:
    if isinstance(value, (list, tuple)):
        return " ".join(str(v).strip() for v in value if str(v).strip())
    return " ".join(str(value).split()) if value is not None else ""


def first_heading(text: str) -> str:
    match = HEADING_RE.search(text)
    return match.group(2).strip() if match else ""


def first_paragraph(text: str) -> str:
    for block in re.split(r"\n\s*\n", text):
        lines = []
        for line in block.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith(("#", "|", "```", "---", ">")):
                continue
            lines.append(stripped)
        if lines:
            candidate = " ".join(" ".join(lines).split())
            if len(candidate) >= 15:
                return candidate[:240]
    return ""


def humanize_name(name: str) -> str:
    stem = Path(name).stem
    stem = re.sub(r"[_-]+", " ", stem)
    stem = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", stem)
    return stem.strip().capitalize() or name


def language_for(path: Path) -> str:
    return LANGUAGE_BY_EXT.get(path.suffix.lower(), "other")


def kind_for(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".md", ".markdown", ".mdx"}:
        return "doc"
    if suffix == ".py":
        return "python"
    if suffix in {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx"}:
        return "code"
    if suffix in {".html", ".htm"}:
        return "web"
    if suffix in {".json", ".jsonc", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf"}:
        return "config"
    if suffix in {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico"}:
        return "image"
    if suffix in MEDIA_SUMMARIES:
        return "media"
    if suffix in {".sh", ".bash", ".zsh", ".fish"}:
        return "script"
    return "file"


def _line_of(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def _signature(node: ast.AST) -> str:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        args = [a.arg for a in node.args.posonlyargs + node.args.args]
        if node.args.vararg:
            args.append("*" + node.args.vararg.arg)
        if node.args.kwarg:
            args.append("**" + node.args.kwarg.arg)
        return f"{node.name}({', '.join(args)})"
    if isinstance(node, ast.ClassDef):
        bases = []
        for base in node.bases:
            try:
                bases.append(ast.unparse(base))
            except Exception:
                pass
        return f"class {node.name}" + (f"({', '.join(bases)})" if bases else "")
    return getattr(node, "name", "")


def python_analysis(text: str) -> Tuple[List[Dict[str, Any]], List[str], str]:
    symbols: List[Dict[str, Any]] = []
    imports: List[str] = []
    docstring = ""

    try:
        tree = ast.parse(text)
    except SyntaxError:
        return symbols, imports, docstring

    if tree.body and isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, ast.Constant):
        value = tree.body[0].value.value
        if isinstance(value, str):
            docstring = " ".join(value.split())[:300]

    def visit(node: ast.AST, prefix: str = "") -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                qual = f"{prefix}{child.name}"
                symbols.append(
                    {
                        "name": qual,
                        "kind": "method" if prefix else "function",
                        "line": getattr(child, "lineno", 0),
                        "signature": _signature(child),
                    }
                )
                visit(child, prefix=f"{qual}.")
            elif isinstance(child, ast.ClassDef):
                qual = f"{prefix}{child.name}"
                symbols.append(
                    {
                        "name": qual,
                        "kind": "class",
                        "line": getattr(child, "lineno", 0),
                        "signature": _signature(child),
                    }
                )
                visit(child, prefix=f"{qual}.")
            else:
                visit(child, prefix=prefix)

    visit(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            prefix = "." * (node.level or 0)
            imports.append(prefix + module)
    return symbols, imports, docstring


def javascript_analysis(text: str) -> Tuple[List[Dict[str, Any]], List[str], str]:
    symbols: List[Dict[str, Any]] = []
    imports: List[str] = []
    patterns = [
        (r"(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)", "function"),
        (r"(?:export\s+)?class\s+([A-Za-z_$][\w$]*)", "class"),
        (r"(?:export\s+)?interface\s+([A-Za-z_$][\w$]*)", "interface"),
        (r"(?:export\s+)?type\s+([A-Za-z_$][\w$]*)\s*=", "type"),
        (r"(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\(", "function"),
        (r"(?:export\s+)?(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?[A-Za-z_$][\w$]*\s*=>", "function"),
    ]
    for pattern, kind in patterns:
        for match in re.finditer(pattern, text):
            name = match.group(1)
            if any(s["name"] == name for s in symbols):
                continue
            symbols.append(
                {
                    "name": name,
                    "kind": kind,
                    "line": _line_of(text, match.start()),
                    "signature": test_name(name),
                }
            )
    for match in re.finditer(r"(?:from\s+|require\s*\(\s*)['\"]([^'\"]+)['\"]", text):
        imports.append(match.group(1))
    comment = re.search(r"/\*\*(.*?)\*/", text, re.DOTALL)
    docstring = " ".join(comment.group(1).replace("*", " ").split())[:300] if comment else ""
    if not docstring:
        lines = [line.strip() for line in text.splitlines()[:15]]
        docstring = " ".join(line.lstrip("/# ").strip() for line in lines if line.startswith("//"))[:300]
    return symbols, imports, docstring


def test_name(name: str) -> str:
    return f"{name}()"


def shell_analysis(text: str) -> Tuple[List[Dict[str, Any]], List[str], str]:
    symbols: List[Dict[str, Any]] = []
    for match in re.finditer(r"^\s*(?:function\s+)?([A-Za-z_][\w-]*)\s*\(\)\s*\{", text, re.MULTILINE):
        symbols.append(
            {
                "name": match.group(1),
                "kind": "function",
                "line": _line_of(text, match.start()),
                "signature": f"{match.group(1)}()",
            }
        )
    lines = []
    for line in text.splitlines()[:20]:
        stripped = line.strip()
        if stripped.startswith("#") and not stripped.startswith("#!"):
            lines.append(stripped.lstrip("#").strip())
        elif stripped and not stripped.startswith("#!"):
            break
    return symbols, [], " ".join(lines)[:300]


def markdown_analysis(text: str) -> Tuple[List[Dict[str, Any]], List[str], str]:
    symbols: List[Dict[str, Any]] = []
    for match in HEADING_RE.finditer(text):
        symbols.append(
            {
                "name": match.group(2).strip(),
                "kind": f"h{len(match.group(1))}",
                "line": _line_of(text, match.start()),
                "signature": match.group(2).strip(),
            }
        )
    return symbols, [], ""


def structured_analysis(path: Path, text: str) -> Tuple[List[Dict[str, Any]], List[str], str]:
    symbols: List[Dict[str, Any]] = []
    suffix = path.suffix.lower()
    try:
        if suffix in {".json", ".jsonc"}:
            data = json.loads(re.sub(r"^\s*//.*$", "", text, flags=re.MULTILINE))
            if isinstance(data, dict):
                symbols = [{"name": str(k), "kind": "key", "line": 0, "signature": str(k)} for k in list(data)[:40]]
        elif suffix in {".yaml", ".yml"}:
            data = yaml.safe_load(text)
            if isinstance(data, dict):
                symbols = [{"name": str(k), "kind": "key", "line": 0, "signature": str(k)} for k in list(data)[:40]]
        elif suffix == ".toml":
            import tomllib

            data = tomllib.loads(text)
            if isinstance(data, dict):
                symbols = [{"name": str(k), "kind": "key", "line": 0, "signature": str(k)} for k in list(data)[:40]]
    except Exception:
        pass
    return symbols, [], ""


def analyze_file(path: Path, text: Optional[str]) -> Tuple[List[Dict[str, Any]], List[str], str]:
    if text is None:
        return [], [], ""
    suffix = path.suffix.lower()
    if suffix == ".py":
        return python_analysis(text)
    if suffix in {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx"}:
        return javascript_analysis(text)
    if suffix in {".sh", ".bash", ".zsh", ".fish"}:
        return shell_analysis(text)
    if suffix in {".md", ".markdown", ".mdx"}:
        return markdown_analysis(text)
    if suffix in {".json", ".jsonc", ".yaml", ".yml", ".toml"}:
        return structured_analysis(path, text)
    return [], [], ""


def detect_generated(text: Optional[str]) -> bool:
    if not text:
        return False
    head = text[:2000].lower()
    markers = ("auto-generated", "automatically generated", "generated by", "do not edit", "@generated")
    return any(marker in head for marker in markers)


def detect_entrypoint(rel: str, text: Optional[str]) -> bool:
    path = PurePosixPath(rel)
    name = path.name
    if name == "__main__.py":
        return True
    if text and re.search(r"if\s+__name__\s*==\s*['\"]__main__['\"]", text):
        return True
    if text:
        first_line = text.splitlines()[0] if text.splitlines() else ""
        if first_line.startswith("#!") and any(token in first_line for token in ("python", "node", "bash", "sh")):
            return True
    if any(part in {"scripts", "bin"} for part in path.parts) and path.suffix.lower() in {".py", ".sh", ".js", ".ts"}:
        return True
    if name == "package.json" and text:
        try:
            data = json.loads(text)
            if isinstance(data, dict) and data.get("bin"):
                return True
        except Exception:
            pass
    return False


def hash_file(path: Path) -> Tuple[Optional[str], str]:
    try:
        size = path.stat().st_size
        if size > HASH_LIMIT:
            return None, "size+mtime"
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest(), "sha256"
    except OSError:
        return None, "unavailable"


def parse_gitmodules(root: Path) -> Set[str]:
    path = root / ".gitmodules"
    if not path.exists():
        return set()
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return set()
    paths: Set[str] = set()
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("path") and "=" in stripped:
            value = stripped.split("=", 1)[1].strip().strip('"')
            if value:
                paths.add(value.strip("/"))
    return paths


def load_overrides(root: Path) -> Dict[str, Any]:
    path = root / OVERRIDES_REL
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def git_metadata(root: Path) -> Tuple[Optional[str], bool]:
    rev: Optional[str] = None
    dirty = False
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        if result.returncode == 0:
            rev = result.stdout.strip()
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        if status.returncode == 0:
            dirty = bool(status.stdout.strip())
    except Exception:
        pass
    return rev, dirty


def walk_tree(
    root: Path,
    rules: IgnoreRules,
    submodules: Set[str],
    include_submodules: bool = False,
) -> Tuple[Dict[str, List[str]], Dict[str, List[str]], Set[str]]:
    """Walk the tree once, returning per-directory files, subdirs, opaque submodules."""
    root = root.resolve()
    dir_files: Dict[str, List[str]] = {}
    dir_subdirs: Dict[str, List[str]] = {}
    opaque: Set[str] = set()

    for dirpath, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
        current = Path(dirpath)
        rel_dir = "." if current == root else current.relative_to(root).as_posix()
        dir_files.setdefault(rel_dir, [])
        dir_subdirs.setdefault(rel_dir, [])

        kept: List[str] = []
        for dirname in sorted(dirnames):
            child = current / dirname
            child_rel = child.relative_to(root).as_posix()
            if child.is_symlink():
                continue
            if rules.is_ignored(child_rel, is_dir=True):
                continue
            dir_subdirs[rel_dir].append(child_rel)
            if child_rel in submodules and not include_submodules:
                opaque.add(child_rel)
                continue
            kept.append(dirname)
        dirnames[:] = kept

        for filename in sorted(filenames):
            child = current / filename
            child_rel = child.relative_to(root).as_posix()
            if rules.is_ignored(child_rel, is_dir=False):
                continue
            dir_files[rel_dir].append(filename)

    return dir_files, dir_subdirs, opaque


def _summary_from_frontmatter(fm: Dict[str, Any]) -> str:
    for key in ("summary", "description", "title"):
        value = summarize_text(fm.get(key))
        if value:
            return value
    return ""


def _file_summary(
    path: Path,
    rel: str,
    text: Optional[str],
    fm: Dict[str, Any],
    docstring: str,
    parent_submodule: str,
    overrides: Dict[str, Any],
) -> str:
    override = overrides.get("files", {}).get(rel, {}) if isinstance(overrides.get("files"), dict) else {}
    for candidate in (
        summarize_text(override.get("summary")) if isinstance(override, dict) else "",
        parent_submodule,
        _summary_from_frontmatter(fm),
        docstring,
    ):
        if candidate:
            return candidate[:300]

    suffix = path.suffix.lower()
    if suffix in {".md", ".markdown", ".mdx"} and text:
        heading = first_heading(text)
        if heading:
            return heading[:300]
        paragraph = first_paragraph(text)
        if paragraph:
            return paragraph
    if text:
        paragraph = first_paragraph(text)
        if paragraph:
            return paragraph[:300]
    if suffix in MEDIA_SUMMARIES:
        return f"{MEDIA_SUMMARIES[suffix]} ({path.name})"
    return f"{humanize_name(path.name)} ({path.name})"


def _tags(
    path: Path,
    rel: str,
    fm: Dict[str, Any],
    parent_tags: Sequence[str],
    overrides: Dict[str, Any],
) -> List[str]:
    tags: List[str] = []
    override = overrides.get("files", {}).get(rel, {}) if isinstance(overrides.get("files"), dict) else {}
    for source in (
        override.get("tags") if isinstance(override, dict) else None,
        fm.get("tags"),
        parent_tags,
        [language_for(path)],
    ):
        if isinstance(source, str):
            source = [source]
        if isinstance(source, (list, tuple)):
            for tag in source:
                clean = str(tag).strip().lower()
                if clean and clean not in tags:
                    tags.append(clean)
    return tags[:10]


def _change_when(fm: Dict[str, Any], override: Dict[str, Any]) -> str:
    for source in (override, fm):
        if not isinstance(source, dict):
            continue
        value = source.get("change_when") or source.get("change-when")
        if value:
            return summarize_text(value)[:300]
    return ""


def build_index(
    root: Path,
    out_path: Optional[Path] = None,
    *,
    public: bool = False,
    include_submodules: bool = False,
    write: bool = True,
    quiet: bool = False,
) -> Dict[str, Any]:
    root = root.resolve()
    out_path = (out_path or (root / DEFAULT_INDEX_REL)).resolve()
    submodules = parse_gitmodules(root)
    overrides = load_overrides(root)
    overrides_files = overrides.get("files", {}) if isinstance(overrides.get("files"), dict) else {}
    overrides_dirs = overrides.get("directories", {}) if isinstance(overrides.get("directories"), dict) else {}

    extra_patterns: List[str] = []
    if public:
        extra_patterns.append("local/")
    try:
        out_rel = out_path.relative_to(root).as_posix()
        extra_patterns.append(out_rel)
    except ValueError:
        pass

    rules = load_rules(root, extra_patterns=extra_patterns)
    dir_files, dir_subdirs, opaque = walk_tree(root, rules, submodules, include_submodules=include_submodules)

    previous: Dict[str, Any] = {}
    if out_path.exists():
        try:
            previous = json.loads(out_path.read_text(encoding="utf-8"))
        except Exception:
            previous = {}
    previous_files = previous.get("files", {}) if isinstance(previous.get("files"), dict) else {}

    fm_cache: Dict[Path, Dict[str, Any]] = {}

    def frontmatter(path: Path) -> Dict[str, Any]:
        if path not in fm_cache:
            fm_cache[path] = parse_frontmatter(read_text(path))
        return fm_cache[path]

    files: Dict[str, Any] = {}
    symbol_index: Dict[str, List[str]] = {}

    for rel_dir, filenames in dir_files.items():
        directory = root if rel_dir == "." else root / rel_dir
        parent_fm = frontmatter(directory / "README.md")
        parent_submodules = normalize_submodules(parent_fm.get("submodules"))
        parent_tags = parent_fm.get("tags") if isinstance(parent_fm.get("tags"), list) else []

        for filename in filenames:
            path = directory / filename
            rel = filename if rel_dir == "." else f"{rel_dir}/{filename}"
            try:
                stat = path.stat()
            except OSError:
                continue

            text = read_text(path)
            fm = frontmatter(path) if path.suffix.lower() in {".md", ".markdown", ".mdx"} else {}
            symbols, imports, docstring = analyze_file(path, text)
            override = overrides_files.get(rel, {}) if isinstance(overrides_files.get(rel), dict) else {}
            parent_submodule = parent_submodules.get(filename, "")

            prev = previous_files.get(rel, {}) if isinstance(previous_files.get(rel), dict) else {}
            if prev.get("size") == stat.st_size and prev.get("mtime_ns") == stat.st_mtime_ns and prev.get("sha256"):
                sha256, hash_mode = prev["sha256"], prev.get("hash_mode", "sha256")
            else:
                sha256, hash_mode = hash_file(path)

            entry: Dict[str, Any] = {
                "path": rel,
                "name": filename,
                "directory": rel_dir,
                "kind": kind_for(path),
                "language": language_for(path),
                "size": stat.st_size,
                "mtime_ns": stat.st_mtime_ns,
                "mtime": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                "sha256": sha256,
                "hash_mode": hash_mode,
                "summary": _file_summary(path, rel, text, fm, docstring, parent_submodule, overrides),
                "tags": _tags(path, rel, fm, parent_tags, overrides),
                "symbols": symbols,
                "imports": sorted(set(imports)),
                "dependencies": [],
                "dependents": [],
                "tests": [],
                "tests_for": [],
                "entrypoint": detect_entrypoint(rel, text),
                "generated": detect_generated(text),
                "change_when": _change_when(fm, override),
                "lines": text.count("\n") + 1 if text else 0,
            }
            if isinstance(override, dict):
                if "entrypoint" in override:
                    entry["entrypoint"] = bool(override["entrypoint"])
                if "generated" in override:
                    entry["generated"] = bool(override["generated"])
                if override.get("owner"):
                    entry["owner"] = str(override["owner"])
            files[rel] = entry

            for symbol in symbols:
                name = str(symbol.get("name", ""))
                if name and symbol.get("kind") not in {"h1", "h2", "h3", "h4", "h5", "h6", "key"}:
                    symbol_index.setdefault(name, []).append(rel)

    # Resolve imports to repository files.
    module_map: Dict[str, str] = {}
    basename_map: Dict[str, List[str]] = {}
    for rel in files:
        if not rel.endswith(".py"):
            continue
        pure = PurePosixPath(rel)
        if pure.name == "__init__.py":
            module = ".".join(pure.parent.parts)
        else:
            module = ".".join(pure.with_suffix("").parts)
        module_map[module] = rel
        basename_map.setdefault(pure.stem, []).append(rel)

    def resolve_python(module: str, importer: str) -> Optional[str]:
        if not module:
            return None
        if module.startswith("."):
            level = len(module) - len(module.lstrip("."))
            remainder = module.lstrip(".").replace(".", "/")
            base = PurePosixPath(importer).parent
            for _ in range(max(0, level - 1)):
                base = base.parent
            candidate = (base / remainder).as_posix()
            for suffix in (".py", "/__init__.py"):
                if candidate + suffix in files:
                    return candidate + suffix
            return None
        if module in module_map:
            return module_map[module]
        parent = module.rsplit(".", 1)[0] if "." in module else module
        if parent in module_map:
            return module_map[parent]
        basename = module.rsplit(".", 1)[-1]
        matches = basename_map.get(basename, [])
        return matches[0] if len(matches) == 1 else None

    def resolve_js(spec: str, importer: str) -> Optional[str]:
        if not spec.startswith("."):
            return None
        base = PurePosixPath(importer).parent
        target = (base / spec).as_posix()
        candidates = [target]
        for suffix in (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".json"):
            candidates.append(target + suffix)
        for suffix in (".ts", ".tsx", ".js", ".jsx"):
            candidates.append(f"{target}/index{suffix}")
        for candidate in candidates:
            normalized = os.path.normpath(candidate).replace("\\", "/")
            if normalized in files:
                return normalized
        return None

    for rel, entry in files.items():
        dependencies: Set[str] = set()
        suffix = Path(rel).suffix.lower()
        for imported in entry.get("imports", []):
            resolved = resolve_python(imported, rel) if suffix == ".py" else resolve_js(imported, rel)
            if resolved and resolved != rel:
                dependencies.add(resolved)
        entry["dependencies"] = sorted(dependencies)

    for rel, entry in files.items():
        for dependency in entry.get("dependencies", []):
            if dependency in files:
                files[dependency]["dependents"].append(rel)
    for entry in files.values():
        entry["dependents"] = sorted(set(entry["dependents"]))

    # Map tests to source files by convention and by imports.
    tests_by_source: Dict[str, Set[str]] = {}

    def add_test(source: str, test: str) -> None:
        if source != test and source in files and test in files:
            tests_by_source.setdefault(source, set()).add(test)

    for rel, entry in files.items():
        if not TEST_PATH_RE.search(rel):
            continue
        for dependency in entry.get("dependencies", []):
            add_test(dependency, rel)
        stem = PurePosixPath(rel).stem
        if stem.startswith("test_"):
            stem = stem[5:]
        elif stem.endswith("_test"):
            stem = stem[:-5]
        for source in basename_map.get(stem, []):
            add_test(source, rel)

    for rel in files:
        pure = PurePosixPath(rel)
        stem = pure.stem
        candidates = [
            pure.parent / "tests" / f"test_{stem}.py",
            pure.parent / f"test_{stem}.py",
            pure.parent / f"{stem}_test.py",
            PurePosixPath("tests") / f"test_{stem}.py",
            PurePosixPath("tools/repo_index/tests") / f"test_{stem}.py",
        ]
        for candidate in candidates:
            candidate_rel = candidate.as_posix()
            if candidate_rel in files:
                add_test(rel, candidate_rel)

    for source, tests in tests_by_source.items():
        files[source]["tests"] = sorted(tests)
    for rel, entry in files.items():
        if TEST_PATH_RE.search(rel):
            entry["tests_for"] = sorted(
                source
                for source, tests in tests_by_source.items()
                if rel in tests
            )

    # Build directory entries.
    directories: Dict[str, Any] = {}
    for rel_dir, filenames in dir_files.items():
        directory = root if rel_dir == "." else root / rel_dir
        if rel_dir == ".":
            fm = frontmatter(root / "FRONTMATTER.md")
            if not fm:
                fm = frontmatter(root / "README.md")
        else:
            fm = frontmatter(directory / "README.md")
        override = overrides_dirs.get(rel_dir, {}) if isinstance(overrides_dirs.get(rel_dir), dict) else {}
        summary = ""
        if isinstance(override, dict):
            summary = summarize_text(override.get("summary"))
        if not summary:
            summary = _summary_from_frontmatter(fm)
        if not summary:
            children = [name.rstrip("/") for name in dir_subdirs.get(rel_dir, []) if name]
            if rel_dir == ".":
                summary = f"Repository root ({root.name})."
            elif children:
                summary = f"Directory containing {', '.join(children[:6])}."
            else:
                summary = f"Directory {rel_dir}."
        tags: List[str] = []
        for source in (
            override.get("tags") if isinstance(override, dict) else None,
            fm.get("tags"),
            [part for part in PurePosixPath(rel_dir).parts if part not in {".", ""}] if rel_dir != "." else ["root"],
        ):
            if isinstance(source, str):
                source = [source]
            if isinstance(source, (list, tuple)):
                for tag in source:
                    clean = str(tag).strip().lower()
                    if clean and clean not in tags:
                        tags.append(clean)
        file_map = {
            name: files[f"{rel_dir}/{name}" if rel_dir != "." else name]["summary"]
            for name in filenames
            if (f"{rel_dir}/{name}" if rel_dir != "." else name) in files
        }
        entrypoints = sorted(
            f"{rel_dir}/{name}" if rel_dir != "." else name
            for name in filenames
            if (f"{rel_dir}/{name}" if rel_dir != "." else name) in files
            and files[f"{rel_dir}/{name}" if rel_dir != "." else name]["entrypoint"]
        )
        directories[rel_dir] = {
            "path": rel_dir,
            "name": root.name if rel_dir == "." else directory.name,
            "summary": summary[:400],
            "tags": tags[:10],
            "subdirectories": sorted(dir_subdirs.get(rel_dir, [])),
            "files": file_map,
            "file_count": len(file_map),
            "entrypoints": entrypoints,
            "submodule": False,
        }

    for rel_submodule in sorted(opaque):
        directory = root / rel_submodule
        fm = frontmatter(directory / "README.md")
        summary = _summary_from_frontmatter(fm) or f"Git submodule at {rel_submodule}."
        directories[rel_submodule] = {
            "path": rel_submodule,
            "name": directory.name,
            "summary": summary[:400],
            "tags": ["submodule"] + [part for part in PurePosixPath(rel_submodule).parts],
            "subdirectories": [],
            "files": {},
            "file_count": 0,
            "entrypoints": [],
            "submodule": True,
        }

    languages: Dict[str, int] = {}
    for entry in files.values():
        language = entry.get("language", "other")
        languages[language] = languages.get(language, 0) + 1

    rev, dirty = git_metadata(root)
    data: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "generator": GENERATOR,
        "generated_at": utc_now(),
        "source_rev": rev,
        "git_dirty": dirty,
        "root": root.name,
        "public": public,
        "include_submodules": include_submodules,
        "stats": {
            "directories": len(directories),
            "files": len(files),
            "symbols": len(symbol_index),
            "languages": dict(sorted(languages.items(), key=lambda item: (-item[1], item[0]))),
        },
        "directories": directories,
        "files": files,
        "symbol_index": {name: sorted(set(paths)) for name, paths in sorted(symbol_index.items())},
    }

    if write:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=out_path.name + ".", suffix=".tmp", dir=str(out_path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(data, handle, indent=2, ensure_ascii=False)
                handle.write("\n")
            os.replace(temp_name, out_path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
        if not quiet:
            print(
                f"Indexed {len(files)} files in {len(directories)} directories "
                f"({len(symbol_index)} symbols) -> {out_path}"
            )

    return data


def quick_check(
    root: Path,
    index_path: Optional[Path] = None,
    *,
    public: bool = False,
    include_submodules: bool = False,
) -> Dict[str, Any]:
    """Cheap staleness check: compare path sets and size/mtime, not summaries."""
    root = root.resolve()
    index_path = (index_path or (root / DEFAULT_INDEX_REL)).resolve()
    if not index_path.exists():
        return {"ok": False, "reason": "missing", "path": str(index_path)}

    try:
        data = json.loads(index_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"ok": False, "reason": "unreadable", "error": str(exc), "path": str(index_path)}

    if data.get("schema_version") != SCHEMA_VERSION:
        return {"ok": False, "reason": "schema", "path": str(index_path)}

    extra_patterns = ["local/"] if public else []
    try:
        extra_patterns.append(index_path.relative_to(root).as_posix())
    except ValueError:
        pass
    rules = load_rules(root, extra_patterns=extra_patterns)
    submodules = parse_gitmodules(root)
    dir_files, dir_subdirs, opaque = walk_tree(root, rules, submodules, include_submodules=include_submodules)

    expected_files: Dict[str, Tuple[int, int]] = {}
    for rel_dir, filenames in dir_files.items():
        for filename in filenames:
            rel = filename if rel_dir == "." else f"{rel_dir}/{filename}"
            path = root / rel
            try:
                stat = path.stat()
            except OSError:
                continue
            expected_files[rel] = (stat.st_size, stat.st_mtime_ns)

    expected_dirs = set(dir_files) | set(dir_subdirs) | opaque
    actual_files = data.get("files", {}) if isinstance(data.get("files"), dict) else {}
    actual_dirs = set(data.get("directories", {})) if isinstance(data.get("directories"), dict) else set()

    added = sorted(set(expected_files) - set(actual_files))
    removed = sorted(set(actual_files) - set(expected_files))
    changed = sorted(
        rel
        for rel in set(expected_files) & set(actual_files)
        if isinstance(actual_files[rel], dict)
        and (
            actual_files[rel].get("size") != expected_files[rel][0]
            or actual_files[rel].get("mtime_ns") != expected_files[rel][1]
        )
    )
    dirs_added = sorted(expected_dirs - actual_dirs)
    dirs_removed = sorted(actual_dirs - expected_dirs)

    private = []
    if public:
        private = sorted(
            path
            for path in list(actual_files) + list(actual_dirs)
            if path == "local" or path.startswith("local/")
        )

    ok = not (added or removed or changed or dirs_added or dirs_removed or private)
    return {
        "ok": ok,
        "path": str(index_path),
        "added": added,
        "removed": removed,
        "changed": changed,
        "directories_added": dirs_added,
        "directories_removed": dirs_removed,
        "private_paths": private,
        "counts": {
            "files": len(expected_files),
            "directories": len(expected_dirs),
        },
    }


def check_index(
    root: Path,
    index_path: Optional[Path] = None,
    *,
    public: bool = False,
    include_submodules: bool = False,
    deep: bool = False,
) -> Dict[str, Any]:
    report = quick_check(root, index_path, public=public, include_submodules=include_submodules)
    if not report.get("ok") or not deep or report.get("reason"):
        return report

    index_path = Path(report["path"])
    try:
        data = json.loads(index_path.read_text(encoding="utf-8"))
    except Exception:
        return report
    root = root.resolve()
    rules = load_rules(root, extra_patterns=["local/"] if public else [])
    submodules = parse_gitmodules(root)
    dir_files, _, _ = walk_tree(root, rules, submodules, include_submodules=include_submodules)
    mismatches: List[str] = []
    for rel_dir, filenames in dir_files.items():
        for filename in filenames:
            rel = filename if rel_dir == "." else f"{rel_dir}/{filename}"
            entry = data.get("files", {}).get(rel, {})
            if not isinstance(entry, dict):
                continue
            digest, mode = hash_file(root / rel)
            if mode == "sha256" and digest != entry.get("sha256"):
                mismatches.append(rel)
    report["hash_mismatches"] = sorted(mismatches)
    report["ok"] = not mismatches
    return report


def ensure_fresh(
    root: Path,
    index_path: Optional[Path] = None,
    *,
    public: bool = False,
    include_submodules: bool = False,
    quiet: bool = True,
) -> bool:
    """Rebuild the index only when path or mtime drift is detected."""
    report = quick_check(root, index_path, public=public, include_submodules=include_submodules)
    if report.get("ok"):
        return False
    build_index(
        root,
        index_path,
        public=public,
        include_submodules=include_submodules,
        write=True,
        quiet=quiet,
    )
    return True
