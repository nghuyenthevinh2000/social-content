#!/usr/bin/env python3
"""Search a Repomix pack without putting the whole pack in context.

Repomix JSON stores each file as one JSON string, so plain grep sees escaped
newlines. This script decodes the ``files`` map and reports real file paths and
line numbers. It also works on XML, Markdown, and plain packs.

Usage:
    python3 search_pack.py local/repomix/packs/facebook.json "publish"
    python3 search_pack.py local/repomix/packs/facebook.json "publish" --context 2
    python3 search_pack.py pack.json "TODO" --files-only
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Sequence, Tuple


def load_json_files(path: Path) -> Optional[Dict[str, str]]:
    if path.suffix.lower() != ".json":
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    files = data.get("files") if isinstance(data, dict) else None
    if not isinstance(files, dict):
        return None
    return {str(key): value for key, value in files.items() if isinstance(value, str)}


def iter_text(
    path: Path,
    files: Optional[Dict[str, str]],
) -> Iterator[Tuple[str, List[str]]]:
    if files is not None:
        for file_path, content in files.items():
            yield file_path, content.splitlines()
        return
    text = path.read_text(encoding="utf-8", errors="replace")
    yield str(path), text.splitlines()


def compile_pattern(pattern: str, fixed: bool, ignore_case: bool) -> re.Pattern[str]:
    if fixed:
        pattern = re.escape(pattern)
    flags = re.IGNORECASE if ignore_case else 0
    return re.compile(pattern, flags)


def clip(text: str, limit: int) -> str:
    text = text.rstrip("\n")
    if limit and len(text) > limit:
        return text[: limit - 1] + "…"
    return text


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Search a Repomix JSON, XML, or Markdown pack.")
    parser.add_argument("pack")
    parser.add_argument("pattern")
    parser.add_argument("--context", type=int, default=0, help="Lines before and after a hit.")
    parser.add_argument("--max-hits", type=int, default=20)
    parser.add_argument("--max-line-chars", type=int, default=240)
    parser.add_argument("--fixed", action="store_true", help="Treat the pattern as literal text.")
    parser.add_argument("--ignore-case", action="store_true")
    parser.add_argument("--files-only", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    pack = Path(args.pack)
    if not pack.exists():
        print(f"Pack not found: {pack}", file=sys.stderr)
        return 2
    try:
        regex = compile_pattern(args.pattern, args.fixed, args.ignore_case)
    except re.error as exc:
        print(f"Invalid pattern: {exc}", file=sys.stderr)
        return 2

    files = load_json_files(pack)
    hits = 0
    seen_files: List[str] = []
    json_hits: List[Dict] = []

    for file_path, lines in iter_text(pack, files):
        file_hit = False
        for index, line in enumerate(lines):
            if not regex.search(line):
                continue
            file_hit = True
            hits += 1
            if file_path not in seen_files:
                seen_files.append(file_path)
            if args.json:
                start = max(0, index - max(0, args.context))
                end = min(len(lines), index + max(0, args.context) + 1)
                json_hits.append(
                    {
                        "path": file_path,
                        "line": index + 1,
                        "text": clip(line, args.max_line_chars),
                        "context": [
                            {"line": number + 1, "text": clip(lines[number], args.max_line_chars)}
                            for number in range(start, end)
                        ],
                    }
                )
            elif not args.files_only:
                if args.context:
                    start = max(0, index - args.context)
                    end = min(len(lines), index + args.context + 1)
                    for number in range(start, end):
                        marker = ">" if number == index else " "
                        print(
                            f"{file_path}:{number + 1}:{marker} "
                            f"{clip(lines[number], args.max_line_chars)}"
                        )
                else:
                    print(f"{file_path}:{index + 1}: {clip(line, args.max_line_chars)}")
            if hits >= max(1, args.max_hits):
                break
        if file_hit and args.files_only:
            print(file_path)
        if hits >= max(1, args.max_hits):
            break

    if args.json:
        print(json.dumps({"pack": str(pack), "hits": json_hits, "files": seen_files}, indent=2, ensure_ascii=False))
    if hits == 0:
        print(f"No matches for {args.pattern!r} in {pack}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
