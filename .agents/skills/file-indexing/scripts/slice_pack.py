#!/usr/bin/env python3
"""Slice one group out of an existing Repomix JSON pack.

This is the fastest way to stop loading a 40 MB pack: pick a group, write a
smaller Repomix-shaped JSON file, and let the agent read only that.

Usage:
    python3 slice_pack.py --group tools__facebook_agent --out local/repomix/packs/facebook.json
    python3 slice_pack.py --prefix tools/facebook_agent --max-chars 200000 --print
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List, Optional, Sequence

DEFAULT_SOURCE = "local/repomix/repomix-output.json"
DEFAULT_MANIFEST = "local/repomix/index.json"
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


def is_sensitive_path(path: str) -> bool:
    name = path.rsplit("/", 1)[-1]
    if name in SENSITIVE_NAMES:
        return True
    if name.startswith(".env.") and name not in SAFE_ENV_NAMES:
        return True
    return name.endswith(SENSITIVE_SUFFIXES)


def load_manifest(path: Path) -> Dict:
    return json.loads(path.read_text(encoding="utf-8"))


def find_group(manifest: Dict, group_id: Optional[str], prefix: Optional[str]) -> Dict:
    groups = manifest.get("groups", [])
    if group_id:
        for group in groups:
            if group.get("id") == group_id:
                return group
        raise KeyError(f"Group not found: {group_id}")
    if prefix:
        normalized = prefix.strip("/")
        for group in groups:
            if str(group.get("prefix", "")).strip("/") == normalized:
                return group
        raise KeyError(f"Prefix not found: {prefix}")
    raise ValueError("Provide --group or --prefix")


def read_paths(group: Dict) -> List[str]:
    filelist = group.get("filelist")
    if filelist and Path(filelist).exists():
        return [line.strip() for line in Path(filelist).read_text(encoding="utf-8").splitlines() if line.strip()]
    return list(group.get("paths", []))


def build_tree(paths: Sequence[str]) -> str:
    tree: Dict = {}
    for path in sorted(paths):
        node = tree
        parts = path.split("/")
        for part in parts[:-1]:
            node = node.setdefault(part + "/", {})
        node[parts[-1]] = None

    lines: List[str] = []

    def walk(node: Dict, depth: int) -> None:
        indent = "  " * depth
        for name in sorted(node):
            value = node[name]
            if value is None:
                lines.append(f"{indent}{name}")
            else:
                lines.append(f"{indent}{name}")
                walk(value, depth + 1)

    walk(tree, 0)
    return "\n".join(lines)


def render_markdown(paths: Sequence[str], files: Dict[str, str], title: str) -> str:
    lines = [f"# {title}", "", "## Repository structure", "", "```text", build_tree(paths), "```", ""]
    for path in paths:
        content = files.get(path, "")
        lines.extend(["## " + path, "", "~~~text", content, "~~~", ""])
    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Slice a group from a Repomix JSON pack.")
    parser.add_argument("--source", default=DEFAULT_SOURCE)
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST)
    parser.add_argument("--group", help="Group id from the manifest.")
    parser.add_argument("--prefix", help="Group prefix, e.g. tools/facebook_agent.")
    parser.add_argument("--out", default=None)
    parser.add_argument("--max-chars", type=int, default=0, help="Stop after N characters (0 = no limit).")
    parser.add_argument(
        "--include-secrets",
        action="store_true",
        help="Include .env and key material; off by default.",
    )
    parser.add_argument("--style", choices=["json", "markdown"], default="json")
    parser.add_argument("--print", action="store_true", help="Write to stdout instead of a file.")
    args = parser.parse_args(argv)

    source_path = Path(args.source)
    manifest_path = Path(args.manifest)
    if not source_path.exists():
        print(f"Source not found: {source_path}")
        return 2
    if not manifest_path.exists():
        print(f"Manifest not found: {manifest_path}")
        return 2

    manifest = load_manifest(manifest_path)
    try:
        group = find_group(manifest, args.group, args.prefix)
    except (KeyError, ValueError) as exc:
        print(str(exc))
        return 2

    source = json.loads(source_path.read_text(encoding="utf-8"))
    all_files = source.get("files", {})
    paths = [path for path in read_paths(group) if path in all_files]

    selected: Dict[str, str] = {}
    total_chars = 0
    omitted: List[str] = []
    sensitive_omitted: List[str] = []
    for path in paths:
        if not args.include_secrets and is_sensitive_path(path):
            sensitive_omitted.append(path)
            continue
        content = all_files[path]
        size = len(content)
        if args.max_chars and total_chars + size > args.max_chars and selected:
            omitted.append(path)
            continue
        selected[path] = content
        total_chars += size

    title = f"Repomix slice: {group.get('prefix', group.get('id'))}"
    if args.style == "markdown":
        payload = render_markdown(list(selected), selected, title)
    else:
        payload = json.dumps(
            {
                "fileSummary": source.get("fileSummary", {}),
                "directoryStructure": build_tree(list(selected)),
                "files": selected,
                "repomixIndex": {
                    "group": group.get("id"),
                    "prefix": group.get("prefix"),
                    "source": str(source_path),
                    "files": len(selected),
                    "chars": total_chars,
                    "omitted": omitted,
                    "sensitive_omitted": sensitive_omitted,
                },
            },
            indent=2,
            ensure_ascii=False,
        )

    if args.print:
        print(payload)
        return 0
    if not args.out:
        print("Provide --out or --print.")
        return 2
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(payload + "\n", encoding="utf-8")
    print(
        f"Sliced {len(selected)} files ({total_chars:,} chars) from "
        f"{group.get('prefix', group.get('id'))} -> {out}"
    )
    if omitted:
        print(f"Omitted {len(omitted)} files over --max-chars; rerun with a larger limit if needed.")
    if sensitive_omitted:
        print(f"Skipped {len(sensitive_omitted)} sensitive files; use --include-secrets to override.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
