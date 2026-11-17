#!/usr/bin/env python3
"""Select the smallest Repomix group that can answer a query.

Usage:
    python3 select.py "facebook publishing" --manifest local/repomix/index.json
    python3 select.py "facebook publishing" --manifest local/repomix/index.json --json
    python3 select.py "facebook publishing" --files
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import acp
import build_index

KEYWORD_CACHE_PATH = Path(__file__).resolve().parent.parent / "assets" / "keyword-cache.json"

TOKEN_RE = re.compile(r"\w+")
CAMEL_RE = re.compile(r"([a-z0-9])([A-Z])")
STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "find", "for", "from", "how",
    "i", "in", "is", "it", "locate", "of", "on", "or", "search", "that", "the", "this", "to",
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


def expand_keywords_acp(query: str, repo_root: Path) -> List[str]:
    ext_tokens = {"md", "py", "ts", "js", "tsx", "jsx", "sh", "txt", "json", "yaml", "yml", "html", "css"}
    norm_q = " ".join(query.lower().split())
    if not norm_q:
        return []
    cache: Dict[str, List[str]] = {}
    if KEYWORD_CACHE_PATH.exists():
        try:
            cache = json.loads(KEYWORD_CACHE_PATH.read_text(encoding="utf-8"))
        except Exception:
            cache = {}

    matched_terms: List[str] = []
    remaining = f" {norm_q} "
    for term in sorted(cache, key=len, reverse=True):
        if isinstance(cache.get(term), list) and f" {term} " in remaining:
            matched_terms.append(term)
            remaining = remaining.replace(f" {term} ", " ")

    rem_words = [t for t in tokens(remaining) if len(t) >= 3 and t not in ext_tokens]
    if rem_words:
        try:
            resp = acp.ask(
                "Segment this search query into semantic words (keep Vietnamese compound words like "
                "'danh sách' together as one key, skip filler/extensions), and return a JSON object "
                "mapping each lowercase term to 4 short search synonyms (English/Vietnamese, lowercase, "
                f"no underscores, JSON only, no markdown): {remaining.strip()!r}",
                cwd=repo_root,
                timeout_sec=30.0,
            )
            match = re.search(r"\{.*\}", resp, re.DOTALL)
            parsed = json.loads(match.group(0)) if match else {}
            if isinstance(parsed, dict):
                for term, vals in parsed.items():
                    t_clean = " ".join(str(term).lower().split())
                    if t_clean and isinstance(vals, list):
                        cleaned = [
                            tok for item in vals for tok in tokens(str(item).replace("_", " "))
                            if len(tok) >= 3
                        ]
                        cache[t_clean] = list(dict.fromkeys(cleaned))[:6]
                        if t_clean not in matched_terms:
                            matched_terms.append(t_clean)
                KEYWORD_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
                KEYWORD_CACHE_PATH.write_text(
                    json.dumps(cache, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
                )
        except Exception:
            pass

    merged: List[str] = []
    for term in matched_terms:
        for tok in cache.get(term, []):
            if tok not in merged:
                merged.append(tok)
    return merged[:12]


def keyword_search_source(
    manifest: Dict,
    query: str,
    query_tokens: Sequence[str],
    extra_tokens: Sequence[str] = (),
) -> Dict[str, tuple[float, List[str]]]:
    ext_tokens = {"md", "py", "ts", "js", "tsx", "jsx", "sh", "txt", "json", "yaml", "yml", "html", "css"}
    content_tokens = [t for t in query_tokens if len(t) >= 3 and t not in ext_tokens]
    exp_tokens = [t for t in extra_tokens if len(t) >= 3 and t not in ext_tokens and t not in content_tokens]
    query_clean = " ".join(query.lower().split())
    source_path = Path(str(manifest.get("source") or ""))
    if (not content_tokens and not exp_tokens and not query_clean) or not source_path.exists():
        return {}
    files = json.loads(source_path.read_text(encoding="utf-8")).get("files", {})
    if not isinstance(files, dict):
        return {}
    variants = {t: {t, re.sub(r"(.)\1+", r"\1", t)} for t in content_tokens}
    exp_variants = {t: {t} for t in exp_tokens}
    path_hits: Dict[str, tuple[bool, set[str], set[str]]] = {}
    for p, content in files.items():
        if not isinstance(content, str):
            continue
        p_match = bool(query_clean and query_clean in p.lower())
        lower = content.lower()
        toks = {t for t, forms in variants.items() if any(f in lower for f in forms)}
        etoks = {t for t, forms in exp_variants.items() if any(f in lower for f in forms)}
        if p_match or toks or etoks:
            path_hits[p] = (p_match, toks, etoks)
    if not path_hits:
        return {}

    path_to_group: Dict[str, str] = {}
    for group in manifest.get("groups", []):
        fl = Path(str(group.get("filelist") or ""))
        if fl.exists():
            for p in fl.read_text(encoding="utf-8").splitlines():
                if p in path_hits:
                    path_to_group[p] = group["id"]

    grouped: Dict[str, tuple[bool, set[str], set[str], List[str], int]] = {}
    for p, (p_match, toks, etoks) in path_hits.items():
        gid = path_to_group.get(p)
        if not gid:
            continue
        has_p, all_t, all_e, matched, fname_hits = grouped.get(gid, (False, set(), set(), [], 0))
        matched.append(p)
        p_low = p.lower()
        if any(t in p_low for t in (*toks, *etoks)):
            fname_hits += 1
        grouped[gid] = (has_p or p_match, all_t | toks, all_e | etoks, matched, fname_hits)
    return {
        gid: (
            (80.0 if has_p else 0.0)
            + len(all_t) * 15.0
            + len(all_e) * 6.0
            + min(30.0, len(matched) * 1.5)
            + min(20.0, fname_hits * 2.0),
            sorted(matched),
        )
        for gid, (has_p, all_t, all_e, matched, fname_hits) in grouped.items()
    }


def select(
    manifest: Dict,
    query: str,
    budget: int,
    top: int,
    mode: str = "any",
    extra_tokens: Sequence[str] = (),
) -> List[Dict]:
    query_tokens = tokens(query)
    kw_hits = keyword_search_source(manifest, query, query_tokens, extra_tokens)
    ranked: List[Dict] = []
    for group in manifest.get("groups", []):
        kw_score, matched_files = kw_hits.get(group["id"], (0.0, []))
        score = score_group(group, query, query_tokens, mode) + kw_score
        if score <= 0:
            continue
        item = dict(group)
        item["score"] = round(score, 4)
        if matched_files:
            item["matched_files"] = matched_files[:5]
        item["within_budget"] = int(group.get("tokens_est", 0)) <= budget
        if not item["within_budget"]:
            factor = 0.7 if int(group.get("tokens_est", 0)) > budget * 4 else 0.85
            item["score"] = round(item["score"] * factor, 4)
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


def git_state_hash(repo_root: Path) -> str:
    try:
        out = subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=repo_root, text=True, stderr=subprocess.DEVNULL
        )
        head = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo_root, text=True, stderr=subprocess.DEVNULL
        ).strip()
        return hashlib.sha256(f"{head}\n{out}".encode("utf-8")).hexdigest()
    except Exception:
        return ""


def refresh_index(manifest_path: Path) -> None:
    repo_root = build_index.find_repo_root(Path(__file__))
    source_path = repo_root / build_index.DEFAULT_SOURCE
    state_file = manifest_path.parent / ".git-state"
    cur_state = git_state_hash(repo_root)
    if (
        cur_state
        and manifest_path.exists()
        and source_path.exists()
        and state_file.exists()
        and state_file.read_text(encoding="utf-8").strip() == cur_state
    ):
        return
    submodules = [f"{p}/**" for p in build_index.submodule_prefixes(repo_root)]
    ignores = submodules + ["**/.ruff_cache/**", "**/local/aibrand/data/**"]
    subprocess.run(
        ["npx", "--yes", "repomix", "--quiet", "-o", str(source_path), "--ignore", ",".join(ignores)],
        cwd=repo_root,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    excludes = list(build_index.DEFAULT_EXCLUDES) + submodules
    build_index.build_manifest(source_path, manifest_path.parent, 80000, 3, 12000, excludes, [], write=True)
    if cur_state:
        state_file.write_text(cur_state + "\n", encoding="utf-8")


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Select a Repomix index group for a query.")
    parser.add_argument("query", nargs="+")
    parser.add_argument("--manifest", default="local/repomix/index.json")
    parser.add_argument("--top", type=int, default=5)
    parser.add_argument("--budget", type=int, default=40000, help="Maximum tokens for a single pack.")
    parser.add_argument("--mode", choices=["any", "edit", "read"], default="any")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--files", action="store_true", help="Print the best group's file list.")
    parser.add_argument("--no-refresh", action="store_true", help="Skip automatic repomix + index rebuild.")
    parser.add_argument("--no-expand", action="store_true", help="Skip ACP agy keyword expansion.")
    args = parser.parse_args(argv)

    manifest_path = Path(args.manifest)
    query = " ".join(args.query)
    repo_root = build_index.find_repo_root(Path(__file__))
    do_refresh = not args.no_refresh and args.manifest == "local/repomix/index.json"
    with ThreadPoolExecutor(max_workers=2) as pool:
        rf_fut = pool.submit(refresh_index, manifest_path) if do_refresh else None
        ex_fut = None if args.no_expand else pool.submit(expand_keywords_acp, query, repo_root)
        if rf_fut:
            rf_fut.result()
        expanded = ex_fut.result() if ex_fut else []
    if not manifest_path.exists():
        print(f"Manifest not found: {manifest_path}")
        return 2
    manifest = load_manifest(manifest_path)
    results = select(manifest, query, max(1000, args.budget), max(1, args.top), args.mode, expanded)
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
        print(json.dumps({"query": query, "expanded": expanded, "manifest": str(manifest_path), "results": results}, indent=2, ensure_ascii=False))
        return 0

    best = results[0]
    label = best.get("label") or best["prefix"]
    print(
        f"Best group: {label}  "
        f"({best['files']} files, ~{best['tokens_est']:,} tokens, score {best['score']})"
    )
    if expanded:
        print(f"  expanded: {', '.join(expanded)}")
    print(f"  manifest: {manifest_path}")
    print(f"  file list: {best.get('filelist', '-')}")
    if best.get("matched_files"):
        print(f"  matches: {', '.join(best['matched_files'])}")
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
