#!/usr/bin/env python3
"""Build a lightweight index and file lists from a Repomix JSON pack.

The goal is to stop loading one huge pack. The manifest tells an agent which
small group to inspect, and each group gets a plain-text file list that can be
fed to ``repomix --stdin`` for a fresh, compressed pack.

Usage:
    python3 build_index.py --source local/repomix/repomix-output.json --out local/repomix
    python3 build_index.py --source local/repomix/repomix-output.json --out local/repomix --check
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

SCHEMA_VERSION = 1
GENERATOR = "file-indexing"
DEFAULT_SOURCE = "local/repomix/repomix-output.json"
DEFAULT_OUT = "local/repomix"
DEFAULT_EXCLUDES = [
    ".git/**",
    "node_modules/**",
    ".venv/**",
    "__pycache__/**",
    "local/repomix/**",
]
SENSITIVE_NAMES = {
    ".env",
    ".npmrc",
    ".pypirc",
    ".netrc",
    "credentials.json",
    "secrets.json",
    "id_rsa",
    "id_ed25519",
}
SENSITIVE_SUFFIXES = (".pem", ".key", ".p12", ".pfx")
SAFE_ENV_NAMES = {".env.example", ".env.sample", ".env.template"}


class Node:
    __slots__ = ("children", "files", "total")

    def __init__(self) -> None:
        self.children: Dict[str, "Node"] = {}
        self.files: List[str] = []
        self.total = 0


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def estimate_tokens(chars: int) -> int:
    # Deliberately conservative and provider-agnostic. Repomix reports exact
    # token counts when it builds a pack; this is only for routing.
    return max(1, round(chars / 4))


def matches(path: str, patterns: Sequence[str]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def is_sensitive_path(path: str) -> bool:
    name = path.rsplit("/", 1)[-1]
    if name in SENSITIVE_NAMES:
        return True
    if name.startswith(".env.") and name not in SAFE_ENV_NAMES:
        return True
    return name.endswith(SENSITIVE_SUFFIXES)


def find_repo_root(start: Path) -> Path:
    current = start.resolve()
    for candidate in [current, *current.parents]:
        if (candidate / ".git").exists() or (candidate / ".gitmodules").exists():
            return candidate
    return Path.cwd()


def submodule_prefixes(root: Path) -> List[str]:
    path = root / ".gitmodules"
    if not path.exists():
        return []
    prefixes: List[str] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        stripped = line.strip()
        if stripped.startswith("path") and "=" in stripped:
            value = stripped.split("=", 1)[1].strip().strip('"').strip("/")
            if value and value not in prefixes:
                prefixes.append(value)
    return prefixes


def sanitize_id(prefix: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9._-]+", "__", prefix.strip("/"))
    return clean or "root"


def build_tree(paths: Iterable[str]) -> Node:
    root = Node()
    for path in paths:
        parts = path.split("/")
        node = root
        for part in parts[:-1]:
            node = node.children.setdefault(part, Node())
        node.files.append(path)
    return root


def compute_totals(node: Node, chars: Dict[str, int]) -> int:
    total = sum(chars[path] for path in node.files)
    for child in node.children.values():
        total += compute_totals(child, chars)
    node.total = total
    return total


def collect_paths(node: Node) -> List[str]:
    paths = list(node.files)
    for child in node.children.values():
        paths.extend(collect_paths(child))
    return paths


def make_group(
    prefix: str,
    paths: Sequence[str],
    chars: Dict[str, int],
    target: int,
    *,
    group_id: Optional[str] = None,
    partial: bool = False,
) -> Dict:
    unique_paths = sorted(set(paths))
    total_chars = sum(chars[path] for path in unique_paths)
    tokens = estimate_tokens(total_chars)
    top = sorted(unique_paths, key=lambda path: (-chars[path], path))[:5]
    languages: Dict[str, int] = {}
    for path in unique_paths:
        suffix = Path(path).suffix.lower() or "(none)"
        languages[suffix] = languages.get(suffix, 0) + 1
    tags = [part for part in prefix.split("/") if part][:8] or ["root"]
    if partial:
        tags = tags + ["misc"]
    return {
        "id": group_id or sanitize_id(prefix),
        "prefix": prefix or ".",
        "files": len(unique_paths),
        "chars": total_chars,
        "tokens_est": tokens,
        "oversized": tokens > target,
        "partial": partial,
        "tags": tags,
        "languages": dict(sorted(languages.items(), key=lambda item: (-item[1], item[0]))[:8]),
        "top_files": [
            {"path": path, "tokens_est": estimate_tokens(chars[path])}
            for path in top
        ],
        "paths": unique_paths,
    }


def split_groups(
    node: Node,
    prefix: str,
    depth: int,
    chars: Dict[str, int],
    target: int,
    max_depth: int,
    min_group_tokens: int,
) -> List[Dict]:
    if node.total <= target or not node.children:
        return [make_group(prefix, collect_paths(node), chars, target)]
    # Depth is a soft limit: ordinary groups stop at max_depth, but an
    # oversized subtree keeps splitting until it fits or runs out of children.
    if depth >= max_depth and node.total <= target * 2:
        return [make_group(prefix, collect_paths(node), chars, target)]

    groups: List[Dict] = []
    if node.files:
        groups.append(make_group(prefix, node.files, chars, target))

    small_paths: List[str] = []
    for name, child in sorted(node.children.items()):
        child_prefix = f"{prefix}/{name}" if prefix else name
        if child.total < min_group_tokens:
            small_paths.extend(collect_paths(child))
        else:
            groups.extend(
                split_groups(
                    child,
                    child_prefix,
                    depth + 1,
                    chars,
                    target,
                    max_depth,
                    min_group_tokens,
                )
            )

    if small_paths:
        small_chars = sum(chars[path] for path in small_paths)
        small_tokens = estimate_tokens(small_chars)
        group_id = sanitize_id(prefix + "__misc" if prefix else "root__misc")
        if small_tokens <= target:
            groups.append(
                make_group(
                    prefix,
                    small_paths,
                    chars,
                    target,
                    group_id=group_id,
                    partial=True,
                )
            )
        else:
            # Rare: many small siblings still exceed the target. Split them by
            # their first path segment so one group does not dominate.
            buckets: Dict[str, List[str]] = {}
            for path in small_paths:
                relative = path[len(prefix) :].lstrip("/") if prefix else path
                key = relative.split("/")[0] if "/" in relative else ""
                buckets.setdefault(key, []).append(path)
            for key, bucket in sorted(buckets.items()):
                bucket_id = sanitize_id(f"{prefix}/{key}" if key else group_id)
                groups.append(
                    make_group(
                        prefix,
                        bucket,
                        chars,
                        target,
                        group_id=bucket_id,
                        partial=True,
                    )
                )
    return groups


def load_source(source: Path) -> Tuple[Dict[str, str], str, int]:
    raw = source.read_bytes()
    data = json.loads(raw.decode("utf-8"))
    files = data.get("files")
    if not isinstance(files, dict):
        raise ValueError("Source is not a Repomix JSON pack: missing top-level 'files' object")
    clean: Dict[str, str] = {}
    for path, content in files.items():
        if isinstance(content, str):
            clean[str(path)] = content
    return clean, hashlib.sha256(raw).hexdigest(), len(raw)


def render_tree(paths: Sequence[str]) -> str:
    root = build_tree(sorted(paths))
    lines: List[str] = []

    def walk(node: Node, depth: int) -> None:
        indent = "  " * depth
        for name in sorted(node.children):
            lines.append(f"{indent}{name}/")
            walk(node.children[name], depth + 1)
        for path in sorted(node.files):
            lines.append(f"{indent}{Path(path).name}")

    walk(root, 0)
    return "\n".join(lines)


def build_domains(groups: Sequence[Dict]) -> List[Dict]:
    buckets: Dict[str, List[Dict]] = {}
    for group in groups:
        domain = str(group.get("prefix", ".")).split("/")[0] or "root"
        buckets.setdefault(domain, []).append(group)
    domains: List[Dict] = []
    for domain, items in sorted(buckets.items()):
        tokens = sum(item["tokens_est"] for item in items)
        files = sum(item["files"] for item in items)
        top = sorted(items, key=lambda item: (-item["tokens_est"], item["id"]))[:4]
        domains.append(
            {
                "id": sanitize_id(domain),
                "prefix": domain,
                "groups": len(items),
                "files": files,
                "tokens_est": tokens,
                "top_groups": [
                    {"id": item["id"], "prefix": item["prefix"], "tokens_est": item["tokens_est"]}
                    for item in top
                ],
            }
        )
    domains.sort(key=lambda item: (-item["tokens_est"], item["id"]))
    return domains


def write_outputs(
    manifest: Dict,
    groups: Sequence[Dict],
    out_dir: Path,
    write: bool = True,
) -> None:
    if not write:
        return
    out_dir.mkdir(parents=True, exist_ok=True)
    filelists = out_dir / "filelists"
    packs = out_dir / "packs"
    filelists.mkdir(exist_ok=True)
    packs.mkdir(exist_ok=True)

    for group in groups:
        filelist = filelists / f"{group['id']}.txt"
        filelist.write_text("\n".join(group["paths"]) + "\n", encoding="utf-8")
        group["filelist"] = str(filelist)
        group["pack"] = str(packs / f"{group['id']}.json")
        group["label"] = group["prefix"] + (" (misc)" if group.get("partial") else "")
        group.pop("paths", None)

    manifest["domains"] = build_domains(groups)
    manifest["groups"] = groups
    (out_dir / "index.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    rows = [
        "# Repomix index",
        "",
        "| Domain | Groups | Files | Tokens (est.) | Largest groups |",
        "|---|---:|---:|---:|---|",
    ]
    for domain in manifest["domains"]:
        top = ", ".join(group["prefix"] for group in domain["top_groups"][:3])
        rows.append(
            f"| `{domain['prefix']}` | {domain['groups']} | {domain['files']} | "
            f"{domain['tokens_est']:,} | {top} |"
        )
    (out_dir / "index.md").write_text("\n".join(rows) + "\n", encoding="utf-8")


def build_manifest(
    source: Path,
    out_dir: Path,
    target_tokens: int,
    max_depth: int,
    min_group_tokens: int,
    excludes: Sequence[str],
    includes: Sequence[str],
    write: bool = True,
) -> Dict:
    files, digest, source_bytes = load_source(source)
    selected: Dict[str, int] = {}
    sensitive_excluded = 0
    for path, content in files.items():
        if matches(path, excludes):
            continue
        if includes and not matches(path, includes):
            continue
        if is_sensitive_path(path):
            sensitive_excluded += 1
            continue
        selected[path] = len(content)

    chars = selected
    root = build_tree(selected)
    compute_totals(root, chars)
    groups = split_groups(
        root,
        "",
        0,
        chars,
        target_tokens,
        max_depth,
        min_group_tokens,
    )

    # Guarantee unique ids after sanitisation.
    seen: Dict[str, int] = {}
    for group in groups:
        base = group["id"]
        count = seen.get(base, 0)
        seen[base] = count + 1
        if count:
            group["id"] = f"{base}__{count + 1}"

    total_chars = sum(chars.values())
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "generator": GENERATOR,
        "generated_at": utc_now(),
        "source": str(source),
        "source_sha256": digest,
        "source_bytes": source_bytes,
        "target_tokens": target_tokens,
        "max_depth": max_depth,
        "stats": {
            "files": len(selected),
            "chars": total_chars,
            "tokens_est": estimate_tokens(total_chars),
            "sensitive_excluded": sensitive_excluded,
        },
        "groups": groups,
    }
    write_outputs(manifest, groups, out_dir, write=write)
    return manifest


def check_manifest(expected: Dict, manifest_path: Path) -> int:
    if not manifest_path.exists():
        print(f"Missing manifest: {manifest_path}")
        return 1
    actual = json.loads(manifest_path.read_text(encoding="utf-8"))
    problems: List[str] = []
    if actual.get("source_sha256") != expected.get("source_sha256"):
        problems.append("source hash changed")
    for key in ("files", "chars", "tokens_est", "sensitive_excluded"):
        if actual.get("stats", {}).get(key) != expected.get("stats", {}).get(key):
            problems.append(f"stats.{key} changed")
    actual_groups = {group["id"]: group for group in actual.get("groups", [])}
    expected_groups = {group["id"]: group for group in expected.get("groups", [])}
    if set(actual_groups) != set(expected_groups):
        problems.append("group set changed")
    else:
        for group_id, group in expected_groups.items():
            old = actual_groups[group_id]
            if old.get("files") != group.get("files") or old.get("tokens_est") != group.get("tokens_est"):
                problems.append(f"group {group_id} changed")
                break
    if problems:
        print("Index drift: " + "; ".join(problems))
        return 1
    print(f"Index is fresh: {manifest_path}")
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build a Repomix pack index and file lists.")
    parser.add_argument("--source", default=DEFAULT_SOURCE, help="Repomix JSON pack.")
    parser.add_argument("--out", default=DEFAULT_OUT, help="Output directory.")
    parser.add_argument("--target-tokens", type=int, default=80000, help="Soft token ceiling per group.")
    parser.add_argument("--max-depth", type=int, default=3, help="Normal directory depth to split.")
    parser.add_argument(
        "--min-group-tokens",
        type=int,
        default=12000,
        help="Merge sibling subtrees below this size into a misc group.",
    )
    parser.add_argument("--include", action="append", default=[], help="Only include matching globs.")
    parser.add_argument("--exclude", action="append", default=[], help="Additional exclude globs.")
    parser.add_argument(
        "--include-submodules",
        action="store_true",
        help="Index git submodule contents instead of excluding them.",
    )
    parser.add_argument("--check", action="store_true", help="Fail if the manifest is stale.")
    parser.add_argument("--json", action="store_true", help="Print a JSON summary.")
    args = parser.parse_args(argv)

    source = Path(args.source)
    out_dir = Path(args.out)
    if not source.exists():
        print(f"Source not found: {source}")
        return 2

    excludes = list(DEFAULT_EXCLUDES) + list(args.exclude)
    if not args.include_submodules:
        repo_root = find_repo_root(source)
        excludes.extend(f"{prefix}/**" for prefix in submodule_prefixes(repo_root))

    manifest = build_manifest(
        source,
        out_dir,
        max(1000, args.target_tokens),
        max(1, args.max_depth),
        max(1000, args.min_group_tokens),
        excludes,
        args.include,
        write=not args.check,
    )

    if args.check:
        return check_manifest(manifest, out_dir / "index.json")

    if args.json:
        print(
            json.dumps(
                {
                    "manifest": str(out_dir / "index.json"),
                    "stats": manifest["stats"],
                    "groups": len(manifest["groups"]),
                    "sensitive_excluded": manifest["stats"]["sensitive_excluded"],
                },
                indent=2,
            )
        )
    else:
        print(
            f"Indexed {manifest['stats']['files']} files into {len(manifest['groups'])} groups "
            f"({manifest['stats']['tokens_est']:,} tokens est.) -> {out_dir / 'index.json'}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
