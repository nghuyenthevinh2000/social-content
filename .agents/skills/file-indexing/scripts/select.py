#!/usr/bin/env python3
"""Select the smallest Repomix group that can answer a query.

Usage:
    python3 select.py "facebook publishing" --manifest local/repomix/index.json
    python3 select.py "facebook publishing" --manifest local/repomix/index.json --json
    python3 select.py "facebook publishing" --files
"""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Dict, List, Optional, Sequence

TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")
CAMEL_RE = re.compile(r"([a-z0-9])([A-Z])")
STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "how",
    "i", "in", "is", "it", "of", "on", "or", "that", "the", "this", "to",
    "was", "what", "when", "where", "which", "who", "why", "with", "you", "your",
    "do", "does", "get", "make", "use", "using",
}


def stem(token: str) -> str:
    token = token.lower()
    if len(token) <= 3:
        return token
    if token.endswith("ies") and len(token) > 4:
        return token[:-3] + "y"
    for suffix in ("ing", "ed", "es", "s"):
        if token.endswith(suffix) and len(token) - len(suffix) >= 3:
            base = token[: -len(suffix)]
            if suffix == "s" and base.endswith("s"):
                continue
            return base
    return token


def tokens(text: str) -> List[str]:
    expanded = CAMEL_RE.sub(r"\1 \2", text or "")
    result: List[str] = []
    for raw in TOKEN_RE.findall(expanded):
        lowered = raw.lower()
        if len(lowered) <= 1 or lowered in STOPWORDS:
            continue
        cleaned = stem(lowered)
        if cleaned and cleaned not in STOPWORDS:
            result.append(cleaned)
    return result


def load_manifest(path: Path) -> Dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1:
        raise ValueError(f"Unsupported manifest schema: {data.get('schema_version')}")
    return data


def score_group(group: Dict, query: str, query_tokens: Sequence[str], mode: str) -> float:
    prefix = str(group.get("prefix", "")).lower()
    tags = {str(tag).lower() for tag in group.get("tags", [])}
    top_paths = " ".join(str(item.get("path", "")) for item in group.get("top_files", [])).lower()
    languages = group.get("languages", {})
    language_text = " ".join(str(key) for key in languages).lower()
    haystack = f"{prefix} {top_paths} {language_text}"
    query_clean = " ".join(query.lower().split())

    score = 0.0
    if query_clean and query_clean in prefix:
        score += 30.0
    for token in query_tokens:
        if token in prefix:
            score += 8.0
        if token in tags:
            score += 6.0
        if token in top_paths:
            score += 4.0
        if token in language_text:
            score += 2.0
        if token in haystack:
            score += 1.0
    if query_tokens:
        matched = sum(1 for token in query_tokens if token in haystack)
        score += 8.0 * (matched / len(query_tokens))

    code_exts = {".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".sh"}
    code_files = sum(count for ext, count in languages.items() if ext.lower() in code_exts)
    total_files = max(1, int(group.get("files", 0)))
    code_ratio = code_files / total_files
    if mode == "edit":
        score += 6.0 * code_ratio
        if prefix.startswith("local/") and code_ratio == 0:
            score -= 3.0
    elif mode == "read":
        score += 3.0 * (1.0 - code_ratio)
    return round(score, 4)


def select(
    manifest: Dict,
    query: str,
    budget: int,
    top: int,
    mode: str = "any",
) -> List[Dict]:
    query_tokens = tokens(query)
    ranked: List[Dict] = []
    for group in manifest.get("groups", []):
        score = score_group(group, query, query_tokens, mode)
        if score <= 0:
            continue
        item = dict(group)
        item["score"] = score
        item["within_budget"] = int(group.get("tokens_est", 0)) <= budget
        if not item["within_budget"]:
            item["score"] = round(item["score"] * 0.5, 4)
        ranked.append(item)
    ranked.sort(key=lambda item: (-item["score"], item["tokens_est"], item["id"]))
    return ranked[:top]


def command_for(group: Dict) -> str:
    filelist = group.get("filelist") or ""
    if filelist:
        return (
            f"cat {filelist} | npx repomix@latest --stdin --compress "
            f"--style xml --token-budget 40000 -o {group.get('pack', 'pack.xml')}"
        )
    return f"npx repomix@latest --include '{group.get('prefix')}/**' --compress --style xml"


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Select a Repomix index group for a query.")
    parser.add_argument("query", nargs="+")
    parser.add_argument("--manifest", default="local/repomix/index.json")
    parser.add_argument("--top", type=int, default=5)
    parser.add_argument("--budget", type=int, default=40000, help="Maximum tokens for a single pack.")
    parser.add_argument("--mode", choices=["any", "edit", "read"], default="any")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--files", action="store_true", help="Print the best group's file list.")
    args = parser.parse_args(argv)

    manifest_path = Path(args.manifest)
    if not manifest_path.exists():
        print(f"Manifest not found: {manifest_path}")
        return 2
    manifest = load_manifest(manifest_path)
    query = " ".join(args.query)
    results = select(manifest, query, max(1000, args.budget), max(1, args.top), args.mode)
    if not results:
        print("No matching group.")
        return 0

    if args.files:
        best = results[0]
        filelist = Path(best.get("filelist", ""))
        if filelist.exists():
            print(filelist.read_text(encoding="utf-8"))
            return 0
        print(f"File list missing: {filelist}")
        return 1

    if args.json:
        print(json.dumps({"query": query, "manifest": str(manifest_path), "results": results}, indent=2, ensure_ascii=False))
        return 0

    best = results[0]
    label = best.get("label") or best["prefix"]
    print(
        f"Best group: {label}  "
        f"({best['files']} files, ~{best['tokens_est']:,} tokens, score {best['score']})"
    )
    print(f"  manifest: {manifest_path}")
    print(f"  file list: {best.get('filelist', '-')}")
    print(f"  pack: {best.get('pack', '-')}")
    print(
        f"  next: python3 .agents/skills/file-indexing/scripts/search_pack.py "
        f"{best.get('pack', '<pack>')} \"<pattern>\""
    )
    print(f"  refresh: {command_for(best)}")
    if len(results) > 1:
        print("\nOther candidates:")
        for item in results[1:]:
            print(f"  {item['score']:>6.1f}  {item.get('label') or item['prefix']}  (~{item['tokens_est']:,} tokens)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
