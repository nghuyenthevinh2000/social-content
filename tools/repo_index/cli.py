"""Command line interface for the repository index."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from .indexer import (
    DEFAULT_INDEX_REL,
    SCHEMA_VERSION,
    build_index,
    check_index,
    ensure_fresh,
)
from .query import query_index


def find_root(start: Path) -> Path:
    current = start.resolve()
    for candidate in [current, *current.parents]:
        if (candidate / ".git").exists() or (candidate / ".repo-indexignore").exists():
            return candidate
    return current


def _index_path(root: Path, value: Optional[str]) -> Path:
    if not value:
        return (root / DEFAULT_INDEX_REL).resolve()
    path = Path(value)
    return path if path.is_absolute() else (root / path).resolve()


def _print_report(report: Dict[str, Any]) -> None:
    if report.get("ok"):
        print(f"✅ Index is fresh: {report.get('path')}")
        return
    print(f"❌ Index drift detected: {report.get('path')}")
    if report.get("reason"):
        print(f"  reason: {report['reason']}")
    for key, label in (
        ("added", "added files"),
        ("removed", "removed files"),
        ("changed", "changed files"),
        ("directories_added", "added directories"),
        ("directories_removed", "removed directories"),
        ("hash_mismatches", "hash mismatches"),
        ("private_paths", "private paths in public index"),
    ):
        values = report.get(key) or []
        if values:
            print(f"  {label} ({len(values)}):")
            for value in values[:20]:
                print(f"    - {value}")
            if len(values) > 20:
                print(f"    ... and {len(values) - 20} more")


def cmd_build(args: argparse.Namespace) -> int:
    root = find_root(Path(args.root))
    out = _index_path(root, args.out)
    data = build_index(
        root,
        out,
        public=args.public,
        include_submodules=args.include_submodules,
        write=True,
        quiet=args.quiet,
    )
    if args.json:
        print(json.dumps({"index": str(out), "stats": data.get("stats", {})}, indent=2))
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    root = find_root(Path(args.root))
    path = _index_path(root, args.index)
    report = check_index(
        root,
        path,
        public=args.public,
        include_submodules=args.include_submodules,
        deep=args.deep,
    )
    if not report.get("ok") and args.fix:
        print("Index drift detected; rebuilding...")
        build_index(
            root,
            path,
            public=args.public,
            include_submodules=args.include_submodules,
            write=True,
            quiet=args.quiet,
        )
        report = check_index(
            root,
            path,
            public=args.public,
            include_submodules=args.include_submodules,
            deep=args.deep,
        )
    _print_report(report)
    if args.json:
        print(json.dumps(report, indent=2))
    return 0 if report.get("ok") else 1


def cmd_query(args: argparse.Namespace) -> int:
    root = find_root(Path(args.root))
    result = query_index(
        " ".join(args.text),
        root,
        _index_path(root, args.index),
        top=args.top,
        mode=args.mode,
        semantic=args.semantic,
        refresh=not args.no_refresh,
    )
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    primary = result.get("primary")
    if not primary:
        print("No matching file found.")
        return 0
    print(
        f"Primary: {primary['path']}  "
        f"(score {primary['score']}, confidence {primary['confidence']:.2f})"
    )
    if primary.get("summary"):
        print(f"  {primary['summary']}")
    if args.explain and primary.get("why"):
        print(f"  why: {', '.join(primary['why'])}")
    if primary.get("change_when"):
        print(f"  change when: {primary['change_when']}")
    if primary.get("tests"):
        print(f"  tests: {', '.join(primary['tests'])}")
    if primary.get("dependents"):
        print(f"  dependents: {', '.join(primary['dependents'])}")
    print("\nOther candidates:")
    for item in result["results"][1:]:
        print(f"  {item['score']:>7.2f}  {item['path']}")
        if args.explain and item.get("why"):
            print(f"           why: {', '.join(item['why'])}")
    if result.get("semantic_error"):
        print(f"\nSemantic rerank skipped: {result['semantic_error']}")
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    root = find_root(Path(args.root))
    path = _index_path(root, args.index)
    from .query import load_index

    data = load_index(root, path, refresh=not args.no_refresh)
    print(json.dumps(data.get("stats", {}), indent=2))
    return 0


def cmd_ensure(args: argparse.Namespace) -> int:
    root = find_root(Path(args.root))
    path = _index_path(root, args.index)
    rebuilt = ensure_fresh(
        root,
        path,
        public=args.public,
        include_submodules=args.include_submodules,
        quiet=args.quiet,
    )
    if not args.quiet:
        print("Index rebuilt." if rebuilt else "Index already fresh.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="repo_index",
        description="Build, check, and query the repository's edit-oriented index.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {SCHEMA_VERSION}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build", help="Build the canonical index.")
    build.add_argument("--root", default=".", help="Repository root (default: auto-detect).")
    build.add_argument("--out", default=None, help=f"Output path (default: {DEFAULT_INDEX_REL}).")
    build.add_argument("--public", action="store_true", help="Exclude local/ and private paths.")
    build.add_argument("--include-submodules", action="store_true", help="Walk into git submodules.")
    build.add_argument("--quiet", action="store_true")
    build.add_argument("--json", action="store_true")
    build.set_defaults(func=cmd_build)

    check = subparsers.add_parser("check", help="Detect stale or dangling index entries.")
    check.add_argument("--root", default=".")
    check.add_argument("--index", default=None)
    check.add_argument("--public", action="store_true")
    check.add_argument("--include-submodules", action="store_true")
    check.add_argument("--deep", action="store_true", help="Compare content hashes, not just size/mtime.")
    check.add_argument("--fix", action="store_true", help="Rebuild when drift is found.")
    check.add_argument("--quiet", action="store_true")
    check.add_argument("--json", action="store_true")
    check.set_defaults(func=cmd_check)

    query = subparsers.add_parser("query", help="Find the file to read or edit.")
    query.add_argument("text", nargs="+")
    query.add_argument("--root", default=".")
    query.add_argument("--index", default=None)
    query.add_argument("--top", type=int, default=8)
    query.add_argument("--mode", choices=["any", "edit", "read"], default="any")
    query.add_argument("--semantic", action="store_true", help="Rerank top candidates with TypeSafe Jev.")
    query.add_argument("--no-refresh", action="store_true", help="Do not rebuild a stale index first.")
    query.add_argument("--explain", action="store_true")
    query.add_argument("--json", action="store_true")
    query.set_defaults(func=cmd_query)

    stats = subparsers.add_parser("stats", help="Print index statistics.")
    stats.add_argument("--root", default=".")
    stats.add_argument("--index", default=None)
    stats.add_argument("--no-refresh", action="store_true")
    stats.set_defaults(func=cmd_stats)

    ensure = subparsers.add_parser("ensure", help="Rebuild only if the index is stale.")
    ensure.add_argument("--root", default=".")
    ensure.add_argument("--index", default=None)
    ensure.add_argument("--public", action="store_true")
    ensure.add_argument("--include-submodules", action="store_true")
    ensure.add_argument("--quiet", action="store_true")
    ensure.set_defaults(func=cmd_ensure)

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
