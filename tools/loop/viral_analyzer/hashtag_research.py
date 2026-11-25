"""Cross-platform TikTok and Instagram hashtag research engine."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import re
import sys
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union
import unicodedata

from tools.app.backend.errors import ErrorAggregator, handle_glasser_error
from tools.loop.viral_analyzer import glasser, normalize, runtime

HASHTAG_PLATFORMS = ("tiktok", "instagram")

_ENDPOINT_SPECS: Dict[str, Tuple[str, str, int, Callable[[str, int], Dict[str, Any]]]] = {
    "tiktok": (
        "tikhub",
        "/api/v1/tiktok/app/v3/fetch_hashtag_search_result",
        5,
        lambda q, count: {"keyword": q, "count": count},
    ),
    "instagram": (
        "tikhub",
        "/api/v1/instagram/v2/search_hashtags",
        5,
        lambda q, _count: {"keyword": q},
    ),
}


def strip_accents(text: str) -> str:
    """Convert Vietnamese/Unicode text to ASCII-folded text (preserving d/D for đ/Đ)."""
    replaced = (text or "").replace("đ", "d").replace("Đ", "D")
    return "".join(
        ch for ch in unicodedata.normalize("NFD", replaced)
        if unicodedata.category(ch) != "Mn"
    )


def normalize_tag(tag: str) -> str:
    """Normalize a hashtag or phrase into lowercase alphanumeric ASCII."""
    folded = strip_accents((tag or "").lstrip("#")).lower()
    return re.sub(r"[^a-z0-9]", "", folded)


def parse_keywords(keywords: Union[str, Sequence[str]], limit: int = 3) -> List[str]:
    """Parse comma-separated string or sequence into deduplicated keywords."""
    raw_items = keywords.split(",") if isinstance(keywords, str) else list(keywords or [])
    out: List[str] = []
    seen = set()
    for item in raw_items:
        cleaned = re.sub(r"\s+", " ", str(item or "")).strip()
        if not cleaned:
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(cleaned)
        if limit > 0 and len(out) >= limit:
            break
    return out


def derive_platform_queries(
    keywords: Sequence[str],
    platform: str,
    include_ascii_stems: bool = True,
    extra_stems: Optional[Sequence[str]] = None,
    max_queries: int = 6,
) -> List[str]:
    """Derive bounded search queries for TikTok or Instagram from seed keywords."""
    # ponytail: simple stem derivation; pass extra_stems for custom short stems.
    candidates: List[str] = []
    if platform == "tiktok":
        for kw in keywords:
            candidates.append(kw)
            if include_ascii_stems:
                stem = normalize_tag(kw)
                if stem and stem != kw.lower():
                    candidates.append(stem)
    elif platform == "instagram":
        for kw in keywords:
            stem = normalize_tag(kw)
            if stem:
                candidates.append(stem)
    for stem in extra_stems or ():
        cleaned = normalize_tag(stem)
        if cleaned:
            candidates.append(cleaned)

    out: List[str] = []
    seen = set()
    for q in candidates:
        key = q.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(q)
        if max_queries > 0 and len(out) >= max_queries:
            break
    return out


def normalize_tiktok_hashtags(data: Any, query: str) -> List[Dict[str, Any]]:
    """Normalize TikHub TikTok hashtag search response."""
    if not isinstance(data, dict):
        return []
    inner = data.get("data") if isinstance(data.get("data"), dict) else {}
    items = inner.get("challenge_list") or []
    out: List[Dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        info = item.get("challenge_info") if isinstance(item.get("challenge_info"), dict) else item
        tag = str(info.get("cha_name") or "").strip().lstrip("#")
        norm = normalize_tag(tag)
        if not tag or not norm:
            continue
        out.append({
            "tag": tag,
            "hashtag": f"#{tag}",
            "normalized": norm,
            "platform": "tiktok",
            "views": normalize.parse_int(info.get("view_count")),
            "videos": normalize.parse_int(info.get("user_count")),
            "posts": 0,
            "matched_query": query,
        })
    return out


def normalize_instagram_hashtags(data: Any, query: str) -> List[Dict[str, Any]]:
    """Normalize TikHub Instagram hashtag search response."""
    if not isinstance(data, dict):
        return []
    outer = data.get("data")
    if isinstance(outer, dict):
        items = outer.get("items") or outer.get("results") or []
    else:
        items = data.get("items") or data.get("results") or []
    out: List[Dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        tag = str(item.get("name") or "").strip().lstrip("#")
        norm = normalize_tag(tag)
        if not tag or not norm:
            continue
        out.append({
            "tag": tag,
            "hashtag": f"#{tag}",
            "normalized": norm,
            "platform": "instagram",
            "views": 0,
            "videos": 0,
            "posts": normalize.parse_int(item.get("media_count")),
            "matched_query": query,
        })
    return out


_NORMALIZERS: Dict[str, Callable[[Any, str], List[Dict[str, Any]]]] = {
    "tiktok": normalize_tiktok_hashtags,
    "instagram": normalize_instagram_hashtags,
}


def score_hashtag_relevance(tag: str, keywords: Sequence[str]) -> int:
    """Score how relevant a hashtag is to seed keywords; 0 filters unrelated noise."""
    norm = normalize_tag(tag)
    if not norm:
        return 0

    seed_tokens: List[str] = []
    seed_bigrams: List[str] = []
    single_word_stems: List[str] = []
    seen_tokens = set()

    for kw in keywords:
        words = [w for w in re.split(r"[^a-z0-9]+", strip_accents(kw).lower()) if len(w) >= 2]
        if len(words) == 1:
            single_word_stems.append(words[0])
        for w in words:
            if w not in seen_tokens:
                seen_tokens.add(w)
                seed_tokens.append(w)
        for idx in range(len(words) - 1):
            bg = words[idx] + words[idx + 1]
            if bg not in seed_bigrams:
                seed_bigrams.append(bg)

    matched_tokens = [tok for tok in seed_tokens if tok in norm]
    matched_bigrams = [bg for bg in seed_bigrams if bg in norm]
    matched_single = any(norm == stem or stem in norm for stem in single_word_stems)
    has_acronym = any(len(tok) == 3 and tok in norm for tok in seed_tokens)

    if not (matched_single or matched_bigrams or (has_acronym and len(matched_tokens) >= 1 and len(norm) <= 24)):
        return 0
    return len(matched_tokens) + len(matched_bigrams)


def search_platform_hashtags(
    platform: str,
    query: str,
    *,
    count: int = 20,
    cache_dir: Optional[Path] = None,
    log: Optional[Callable[[str], None]] = None,
    task_id: Optional[str] = None,
    aggregator: Optional[ErrorAggregator] = None,
    glasser_fn: Optional[Callable[..., Any]] = None,
    ctx: Optional[runtime.EngineContext] = None,
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """Search hashtags on one supported platform (tiktok or instagram)."""
    spec = _ENDPOINT_SPECS.get(platform)
    normalizer = _NORMALIZERS.get(platform)
    if spec is None or normalizer is None:
        return [], None

    provider, endpoint, version, payload_fn = spec
    payload = payload_fn(query, count)
    if glasser_fn is not None:
        data, src, err = glasser_fn(provider, endpoint, version, payload, cache_dir, task_id=task_id)
    else:
        data, src, err = glasser.run_glasser_json(
            provider,
            endpoint,
            version,
            payload,
            cache_dir,
            task_id=task_id,
            sub_action="hashtag_search",
            cache_sub_action="hashtag_cache",
            ctx=ctx,
        )

    items = normalizer(data, query) if data is not None else []
    if err is not None and not items:
        if aggregator is not None:
            aggregator.add(handle_glasser_error(err, log=log))
        elif log:
            log(f"[{platform}] {err}")
    return items, src


def _prefer_display_tag(existing: str, candidate: str, existing_vol: int, candidate_vol: int) -> str:
    """Keep the higher-volume tag; break ties in favor of ASCII/clean tags."""
    if candidate_vol > existing_vol:
        return candidate
    if candidate_vol == existing_vol and candidate.isascii() and not existing.isascii():
        return candidate
    return existing


def run_hashtag_research(
    keywords: Union[str, Sequence[str]],
    run_dir: Optional[Path] = None,
    *,
    platforms: Sequence[str] = HASHTAG_PLATFORMS,
    extra_stems: Optional[Sequence[str]] = None,
    count: int = 20,
    min_relevance: int = 1,
    limit: int = 30,
    options: Optional[Dict[str, Any]] = None,
    log: Optional[Callable[[str], None]] = None,
    job_id: str = "",
    aggregator: Optional[ErrorAggregator] = None,
    glasser_fn: Optional[Callable[..., Any]] = None,
    ctx: Optional[runtime.EngineContext] = None,
) -> Dict[str, Any]:
    """Run TikTok + Instagram hashtag research for seed keywords and rank results."""
    opts = options or {}
    parsed_keywords = parse_keywords(keywords, limit=int(opts.get("max_keywords", 3)))
    if not parsed_keywords:
        return {
            "keywords": [],
            "queries": {},
            "hashtags": [],
            "hashtag_list": [],
            "by_platform": {},
            "source_breakdown": {},
            "error": "Từ khoá hashtag trống.",
            "errors": [],
        }

    eng_ctx = ctx or runtime.default_context()
    _log = log or (lambda _msg: None)
    agg = aggregator or ErrorAggregator(job_id=job_id)
    cache_dir = (Path(run_dir) / "cache") if run_dir is not None else None
    if cache_dir is not None:
        cache_dir.mkdir(parents=True, exist_ok=True)

    target_platforms = tuple(p.strip().lower() for p in platforms if p.strip().lower() in _ENDPOINT_SPECS)
    task_id = opts.get("glasser_task") or os.environ.get("GLASSER_TASK_ID") or None
    queries_by_platform = {
        plat: derive_platform_queries(parsed_keywords, plat, extra_stems=extra_stems)
        for plat in target_platforms
    }
    tasks = [(plat, q) for plat, qs in queries_by_platform.items() for q in qs]

    source_breakdown: Dict[str, List[str]] = {"glasser_api": [], "cache": [], "empty": []}
    raw_items: List[Dict[str, Any]] = []

    with ThreadPoolExecutor(max_workers=min(eng_ctx.max_workers, len(tasks) or 1)) as pool:
        futures = [
            (
                plat,
                q,
                eng_ctx.submit_fn(
                    pool,
                    search_platform_hashtags,
                    plat,
                    q,
                    count=count,
                    cache_dir=cache_dir,
                    log=_log,
                    task_id=task_id,
                    aggregator=agg,
                    glasser_fn=glasser_fn,
                    ctx=eng_ctx,
                ),
            )
            for plat, q in tasks
        ]
        for plat, q, fut in futures:
            items, src = fut.result()
            tag = f"{plat}:{q}"
            if src == "cache":
                source_breakdown["cache"].append(tag)
            elif src == "glasser_api":
                source_breakdown["glasser_api"].append(tag)
            else:
                source_breakdown["empty"].append(tag)
            raw_items.extend(items)

    merged: Dict[str, Dict[str, Any]] = {}
    by_platform: Dict[str, Dict[str, Dict[str, Any]]] = {p: {} for p in target_platforms}

    for item in raw_items:
        rel = score_hashtag_relevance(item["tag"], parsed_keywords)
        if rel < min_relevance:
            continue
        norm = item["normalized"]
        plat = item["platform"]
        vol = item["views"] if plat == "tiktok" else item["posts"]

        plat_bucket = by_platform.setdefault(plat, {})
        existing_plat = plat_bucket.get(norm)
        if existing_plat is None or vol > (existing_plat["views"] if plat == "tiktok" else existing_plat["posts"]):
            plat_bucket[norm] = {**item, "relevance_score": rel}

        entry = merged.get(norm)
        if entry is None:
            merged[norm] = {
                "hashtag": item["hashtag"],
                "tag": item["tag"],
                "normalized": norm,
                "platforms": [plat],
                "relevance_score": rel,
                "tiktok_views": item["views"],
                "tiktok_videos": item["videos"],
                "instagram_posts": item["posts"],
                "matched_queries": [item["matched_query"]],
                "_best_vol": vol,
            }
        else:
            if plat not in entry["platforms"]:
                entry["platforms"].append(plat)
            entry["relevance_score"] = max(entry["relevance_score"], rel)
            entry["tiktok_views"] = max(entry["tiktok_views"], item["views"])
            entry["tiktok_videos"] = max(entry["tiktok_videos"], item["videos"])
            entry["instagram_posts"] = max(entry["instagram_posts"], item["posts"])
            if item["matched_query"] not in entry["matched_queries"]:
                entry["matched_queries"].append(item["matched_query"])
            entry["hashtag"] = _prefer_display_tag(
                entry["hashtag"], item["hashtag"], entry["_best_vol"], vol
            )
            entry["tag"] = entry["hashtag"].lstrip("#")
            entry["_best_vol"] = max(entry["_best_vol"], vol)

    ranked = sorted(
        merged.values(),
        key=lambda x: (len(x["platforms"]) > 1, x["relevance_score"], x["tiktok_views"], x["instagram_posts"]),
        reverse=True,
    )[: max(1, limit)]
    for entry in ranked:
        entry.pop("_best_vol", None)

    by_platform_sorted = {
        plat: sorted(
            items.values(),
            key=lambda x: (x["relevance_score"], x["views"], x["posts"]),
            reverse=True,
        )[: max(1, limit)]
        for plat, items in by_platform.items()
    }
    errors = [e.to_dict() for e in agg.all_errors()]

    return {
        "keywords": parsed_keywords,
        "queries": queries_by_platform,
        "hashtags": ranked,
        "hashtag_list": [entry["hashtag"] for entry in ranked],
        "by_platform": by_platform_sorted,
        "source_breakdown": source_breakdown,
        "error": errors[0]["message"] if (errors and not ranked) else None,
        "errors": errors,
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python3 -m tools.loop.viral_analyzer.hashtag_research",
        description="Research and rank #hashtags across TikTok and Instagram.",
    )
    parser.add_argument("--keywords", required=True, help="Comma-separated seed keywords (max 3)")
    parser.add_argument("--platforms", default="tiktok,instagram", help="Comma-separated platforms")
    parser.add_argument("--extra-stems", help="Optional comma-separated extra stems (e.g. batdongsan)")
    parser.add_argument("--run-dir", default="local/hashtag-research", help="Cache directory")
    parser.add_argument("--count", type=int, default=20, help="TikTok hashtags per query")
    parser.add_argument("--limit", type=int, default=30, help="Max ranked hashtags to return")
    parser.add_argument("--output", help="Optional JSON output file")
    args = parser.parse_args(argv)

    result = run_hashtag_research(
        keywords=args.keywords,
        run_dir=Path(args.run_dir),
        platforms=[p.strip() for p in args.platforms.split(",") if p.strip()],
        extra_stems=[s.strip() for s in (args.extra_stems or "").split(",") if s.strip()] or None,
        count=args.count,
        limit=args.limit,
    )
    payload = {"ok": not result.get("error"), **result}
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(rendered, encoding="utf-8")
    print(rendered)
    return 0 if payload["ok"] else 2


if __name__ == "__main__":
    sys.exit(main())
