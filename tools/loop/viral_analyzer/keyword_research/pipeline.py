"""Pipeline orchestration for cross-platform keyword search and campaign research."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from tools.app.backend.errors import ErrorAggregator
from tools.loop.viral_analyzer import normalize, profiling, runtime
from tools.loop.viral_analyzer.keyword_research import collect, config
from tools.loop.viral_analyzer.keyword_research.campaign.generate import (
    build_prompt,
    import_response,
)
from tools.loop.viral_analyzer.keyword_research.campaign.scrape import scrape
from tools.loop.viral_analyzer.keyword_research.campaign.verify import (
    build_review_prompt,
    collect_probes,
    history_report,
    plan_probes,
    record_review,
    report_collection,
)

PLATFORMS = config.PLATFORMS
_FALLBACK_EXPANSIONS = config.FALLBACK_EXPANSIONS
_safe_int = normalize.parse_int
_parse_compact_count = normalize.parse_compact_count
_fetch_public_followers = collect._fetch_public_followers
_enrich_creator_followers = collect._enrich_creator_followers
_dedup_queries = config.dedup_queries
expand_keyword = collect.expand_keyword
_glasser_run_json = collect._glasser_run_json
_normalize_youtube = normalize.normalize_search_youtube
_normalize_serper_videos = normalize.normalize_search_serper
_normalize_fb_ads = normalize.normalize_search_fb_ads
_normalize_tiktok = normalize.normalize_search_tiktok
_normalize_instagram = normalize.normalize_search_instagram


def search_platform(
    platform: str,
    query: str,
    cache_dir: Optional[Path] = None,
    log: Optional[Callable[[str], None]] = None,
    task_id: Optional[str] = None,
    aggregator: Optional[ErrorAggregator] = None,
    glasser_fn: Optional[Callable[..., Any]] = None,
    ctx: Optional[runtime.EngineContext] = None,
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """Search one platform using this module's patchable Glasser runner."""
    return collect.search_platform(
        platform=platform,
        query=query,
        cache_dir=cache_dir,
        log=log,
        task_id=task_id,
        aggregator=aggregator,
        glasser_fn=glasser_fn or _glasser_run_json,
        ctx=ctx,
    )


def run_viral_video_search(
    keyword: str,
    run_dir: Path,
    options: Optional[Dict[str, Any]] = None,
    log: Optional[Callable[[str], None]] = None,
    job_id: str = "",
    aggregator: Optional[ErrorAggregator] = None,
    ctx: Optional[runtime.EngineContext] = None,
) -> Dict[str, Any]:
    """Expand keyword (<=3 terms) and search platforms, returning normalized videos + creators."""
    opts = options or {}
    eng_ctx = ctx or runtime.default_context()
    _log = log or (lambda _msg: None)
    agg = aggregator or ErrorAggregator(job_id=job_id)
    cache_dir = Path(run_dir) / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    expand_kwargs: Dict[str, Any] = {
        "agent_id": opts.get("agent"),
        "model": opts.get("model"),
        "cwd": Path(run_dir),
        "log": _log,
        "language": opts.get("language"),
    }
    if ctx is not None:
        expand_kwargs["ctx"] = eng_ctx
    with profiling.span("keyword", "expand"):
        queries = expand_keyword(keyword, **expand_kwargs)
    if not queries:
        return {
            "queries": [],
            "reels": [],
            "creators": [],
            "source_breakdown": {},
            "error": "Từ khoá tìm kiếm trống.",
            "notice": None,
            "errors": [],
        }

    _log(f"Mở rộng từ khoá '{keyword}' -> {[q['text'] for q in queries]}")

    target_platforms = tuple(opts.get("platforms") or PLATFORMS)
    task_id = opts.get("glasser_task") or os.environ.get("GLASSER_TASK_ID") or None
    all_videos: List[Dict[str, Any]] = []
    seen_urls = set()
    source_breakdown: Dict[str, List[str]] = {"glasser_api": [], "cache": [], "empty": []}

    tasks = [(q_obj["text"], platform) for q_obj in queries for platform in target_platforms]
    search_kwargs_extra: Dict[str, Any] = {"ctx": eng_ctx} if ctx is not None else {}
    with profiling.span("keyword", "search_fanout"):
        with ThreadPoolExecutor(max_workers=min(eng_ctx.max_workers, len(tasks) or 1)) as pool:
            futures = [
                (
                    q_text,
                    platform,
                    eng_ctx.submit_fn(
                        pool,
                        search_platform,
                        platform,
                        q_text,
                        cache_dir=cache_dir,
                        log=_log,
                        task_id=task_id,
                        aggregator=agg,
                        glasser_fn=_glasser_run_json,
                        **search_kwargs_extra,
                    ),
                )
                for q_text, platform in tasks
            ]
            for q_text, platform, fut in futures:
                vids, src = fut.result()
                tag = f"{platform}:{q_text}"
                if src == "cache":
                    source_breakdown["cache"].append(tag)
                elif src == "glasser_api":
                    source_breakdown["glasser_api"].append(tag)
                else:
                    source_breakdown["empty"].append(tag)

                for v in vids:
                    u = (v.get("url") or "").strip()
                    if not u or u in seen_urls:
                        continue
                    seen_urls.add(u)
                    all_videos.append(v)

    all_videos.sort(key=lambda x: x.get("views", 0), reverse=True)

    creators_map: Dict[str, Dict[str, Any]] = {}
    for v in all_videos:
        c_url = (v.get("author_url") or "").strip()
        c_handle = (v.get("author_handle") or v.get("author_name") or "").strip()
        c_key = c_url or (f"{v.get('platform')}:{c_handle}" if c_handle else "")
        if not c_key:
            continue
        existing = creators_map.get(c_key)
        if not existing:
            creators_map[c_key] = {
                "name": v.get("author_name") or c_handle,
                "handle": c_handle,
                "url": c_url,
                "platform": v.get("platform") or "web",
                "followers": _safe_int(v.get("author_followers")),
                "video_count": 1,
                "top_views": v.get("views", 0),
            }
        else:
            existing["video_count"] += 1
            existing["followers"] = max(existing["followers"], _safe_int(v.get("author_followers")))
            existing["top_views"] = max(existing["top_views"], v.get("views", 0))

    creators = sorted(creators_map.values(), key=lambda c: c["top_views"], reverse=True)
    with profiling.span("keyword", "enrich_followers"):
        _enrich_creator_followers(creators)

    creators = [
        c for c in creators
        if (c.get("url") or "").strip().startswith("http") and _safe_int(c.get("followers")) > 0
    ]
    followers_by_url = {c["url"]: c["followers"] for c in creators}
    filtered_reels: List[Dict[str, Any]] = []
    for r in all_videos:
        r_url = (r.get("url") or r.get("reel_url") or "").strip()
        a_url = (r.get("author_url") or "").strip()
        if r_url.startswith("http") and a_url in followers_by_url:
            r["author_followers"] = followers_by_url[a_url]
            filtered_reels.append(r)
    all_videos = filtered_reels

    with profiling.span("keyword", "analyze_relevance"):
        collect.analyze_creator_relevance(
            keyword=keyword,
            creators=creators,
            reels=all_videos,
            agent_id=opts.get("agent"),
            model=opts.get("agy_model") or opts.get("model"),
            cwd=Path(run_dir),
            log=_log,
            ctx=ctx,
            timeout_sec=float(opts.get("acp_timeout", 240)),
            language=opts.get("language"),
        )

    off_topic_urls = {
        c["url"] for c in creators if (c.get("relevance") or "").strip().lower() == "off_topic"
    }
    if off_topic_urls:
        creators = [c for c in creators if c["url"] not in off_topic_urls]
        all_videos = [r for r in all_videos if (r.get("author_url") or "").strip() not in off_topic_urls]

    errors = [e.to_dict() for e in agg.all_errors()]
    notice = None if all_videos else f"Không tìm thấy video nào cho từ khoá '{keyword}'."

    return {
        "queries": queries,
        "reels": all_videos,
        "creators": creators,
        "source_breakdown": source_breakdown,
        "error": errors[0]["message"] if (errors and not all_videos) else None,
        "notice": notice,
        "errors": errors,
    }


def _run_search_cli(args) -> Tuple[Dict[str, Any], Any]:
    platform_list = [p.strip() for p in (args.platforms or "").split(",") if p.strip()]
    result = run_viral_video_search(
        keyword=args.keyword,
        run_dir=Path(args.run_dir),
        options={
            "platforms": platform_list or None,
            "agent": args.agent,
            "model": args.model,
        },
        log=lambda msg: print(msg, flush=True),
    )
    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": not result.get("error"), "command": "search", **result}, None


def register_search_subparser(commands):
    """Register the `search` subcommand for open cross-platform keyword discovery."""
    search = commands.add_parser(
        "search",
        help="Search viral videos and creators across platforms for a keyword",
    )
    search.add_argument("--keyword", required=True, help="Seed keyword or medical/niche phrase")
    search.add_argument("--run-dir", default="local/keyword-search", help="Directory for cache artifacts")
    search.add_argument("--platforms", help="Comma-separated platforms (default: all 5)")
    search.add_argument("--agent", help="Optional ACP agent ID for keyword expansion")
    search.add_argument("--model", help="Optional ACP model ID")
    search.add_argument("--output", help="Optional JSON output path")
    search.set_defaults(command="search", command_func=_run_search_cli)
    return search
