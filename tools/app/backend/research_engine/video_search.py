"""Viral Video Search Engine across 5 platforms via Glasser CLI."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any, Callable, Dict, List, Optional, Tuple

from tools.app.backend.acp import ACPClient, ACPError
from tools.app.backend.errors import ErrorAggregator, handle_glasser_error
from tools.loop.viral_analyzer.glasser import (
    GlasserExecutionError,
    GlasserMissingKeyError,
    GlasserNotFoundError,
    check_glasser_key,
    ensure_glasser_env,
)

PLATFORMS = ("youtube", "google", "facebook", "tiktok", "instagram")

_FALLBACK_EXPANSIONS: Dict[str, Tuple[str, str]] = {
    "gyno conditions": ("gynecomastia", "nữ hóa tuyến vú"),
    "gyno": ("gynecomastia", "nữ hóa tuyến vú"),
    "acne": ("acne vulgaris", "mụn trứng cá"),
    "pcos": ("polycystic ovary syndrome", "hội chứng buồng trứng đa nang"),
    "hair loss": ("alopecia", "rụng tóc"),
}


def _safe_int(val: Any) -> int:
    if isinstance(val, (int, float)):
        return int(val)
    if isinstance(val, str):
        digits = re.sub(r"[^\d]", "", val)
        return int(digits) if digits else 0
    return 0


def _dedup_queries(items: List[Dict[str, str]], limit: int = 3) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    seen = set()
    for item in items:
        text = re.sub(r"\s+", " ", str(item.get("text") or "")).strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append({"kind": item.get("kind") or "original", "text": text})
        if len(out) >= limit:
            break
    return out


def expand_keyword(
    keyword: str,
    agent_id: Optional[str] = None,
    model: Optional[str] = None,
    cwd: Optional[Path] = None,
    log: Optional[Callable[[str], None]] = None,
) -> List[Dict[str, str]]:
    """Expand keyword into at most 3 queries: [original, abbreviation, vi]."""
    kw = re.sub(r"\s+", " ", (keyword or "")).strip()
    if not kw:
        return []
    _log = log or (lambda _msg: None)
    queries: List[Dict[str, str]] = [{"kind": "original", "text": kw}]

    # Deterministic dictionary lookup first for exact known terms
    known = _FALLBACK_EXPANSIONS.get(kw.lower())
    if known:
        abbr, vi = known
        return _dedup_queries([
            {"kind": "original", "text": kw},
            {"kind": "abbreviation", "text": abbr},
            {"kind": "vi", "text": vi},
        ])

    # Optional ACP expansion when agent_id is provided
    if agent_id:
        try:
            from tools.app.backend.research_engine.research import _harness_lock, resolve_agent

            prompt = (
                f'Expand the search keyword "{kw}" into JSON with two short search terms:\n'
                '{"abbreviation": "<medical/slang full form or acronym, or empty>", '
                '"vi": "<natural Vietnamese translation, or empty>"}\n'
                "Return ONLY valid JSON."
            )
            with _harness_lock(_log):
                preset = resolve_agent(agent_id, model=model)
                client = ACPClient(preset["command"], cwd=cwd or Path.cwd(), timeout_sec=30.0, log=_log)
                client.initialize()
                sid = client.new_session()
                raw = client.prompt(sid, prompt)
            match = re.search(r"\{[\s\S]*\}", raw or "")
            if match:
                parsed = json.loads(match.group(0))
                if parsed.get("abbreviation"):
                    queries.append({"kind": "abbreviation", "text": str(parsed["abbreviation"])})
                if parsed.get("vi"):
                    queries.append({"kind": "vi", "text": str(parsed["vi"])})
        except (ACPError, Exception) as exc:
            _log(f"Bỏ qua mở rộng từ khoá qua ACP ({exc}); dùng từ khoá gốc.")

    return _dedup_queries(queries, limit=3)


def _glasser_run_json(
    provider: str,
    endpoint: str,
    version: int,
    payload: Dict[str, Any],
    cache_dir: Optional[Path],
    task_id: Optional[str] = None,
    timeout: float = 45.0,
) -> Tuple[Optional[Any], Optional[str], Optional[Exception]]:
    """Run a single Glasser endpoint with disk cache."""
    cache_key = hashlib.sha256(
        json.dumps({"p": provider, "e": endpoint, "v": version, "i": payload}, sort_keys=True).encode("utf-8")
    ).hexdigest()[:20]
    cache_file = (cache_dir / f"{cache_key}.json") if cache_dir else None
    if cache_file and cache_file.exists():
        try:
            return json.loads(cache_file.read_text(encoding="utf-8")), "cache", None
        except Exception:
            pass

    ensure_glasser_env()
    glasser_bin = shutil.which("glasser")
    if not glasser_bin:
        return None, None, GlasserNotFoundError(handle=f"{provider}:{endpoint}")

    has_key, _ = check_glasser_key()
    out_file = cache_file or Path(f"/tmp/glasser-{cache_key}.json")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    idem = f"vvs-{cache_key}"

    cmd = [
        glasser_bin,
        "run",
        "-p", provider,
        "-e", endpoint,
        "-i", json.dumps(payload, ensure_ascii=False),
        "--endpoint-version", str(version),
        "--idempotency-key", idem,
        "-o", str(out_file),
    ]
    if task_id:
        cmd.extend(["--task", task_id])

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if proc.returncode == 0 and out_file.exists() and out_file.stat().st_size > 0:
            return json.loads(out_file.read_text(encoding="utf-8")), "glasser_api", None
        output = f"{proc.stdout or ''}\n{proc.stderr or ''}".strip()
        if proc.returncode == 2 or "No Key configured" in output or (not has_key and "key" in output.lower()):
            return None, None, GlasserMissingKeyError(handle=f"{provider}:{endpoint}", raw_output=output)
        return None, None, GlasserExecutionError(
            message=f"Glasser {provider}{endpoint} thất bại (code {proc.returncode})",
            handle=f"{provider}:{endpoint}",
            returncode=proc.returncode,
            raw_output=output,
        )
    except subprocess.TimeoutExpired:
        return None, None, GlasserExecutionError(
            message=f"Glasser {provider}{endpoint} timeout sau {timeout:.0f}s",
            handle=f"{provider}:{endpoint}",
        )
    except Exception as exc:
        return None, None, GlasserExecutionError(message=str(exc), handle=f"{provider}:{endpoint}")


def _normalize_youtube(data: Any, query: str) -> List[Dict[str, Any]]:
    items = data.get("videos") or data.get("results") or data.get("items") or (data if isinstance(data, list) else [])
    out: List[Dict[str, Any]] = []
    for v in items:
        if not isinstance(v, dict):
            continue
        vid = str(v.get("id") or v.get("videoId") or "")
        url = str(v.get("url") or v.get("link") or (f"https://www.youtube.com/watch?v={vid}" if vid else ""))
        if not url:
            continue
        ch = v.get("channel") if isinstance(v.get("channel"), dict) else {}
        author_name = str(ch.get("title") or ch.get("name") or v.get("channelName") or v.get("author") or "")
        author_handle = str(ch.get("handle") or ch.get("id") or author_name).lstrip("@")
        raw_ch_url = str(ch.get("url") or ch.get("link") or v.get("channelUrl") or "")
        if not raw_ch_url:
            if ch.get("handle"):
                raw_ch_url = f"https://www.youtube.com/{ch['handle'] if str(ch['handle']).startswith('@') else '@' + str(ch['handle'])}"
            elif ch.get("id"):
                raw_ch_url = f"https://www.youtube.com/channel/{ch['id']}"
        author_url = raw_ch_url
        author_followers = _safe_int(ch.get("subscriberCount") or ch.get("followers") or v.get("channelFollowers"))
        out.append({
            "video_id": vid,
            "title": str(v.get("title") or ""),
            "url": url,
            "reel_url": url,
            "video_url": "",
            "views": _safe_int(v.get("viewCountInt") or v.get("views") or v.get("viewCount")),
            "likes": _safe_int(v.get("likes") or v.get("likeCount")),
            "comments": _safe_int(v.get("comments") or v.get("commentCount")),
            "shares": 0,
            "duration": str(v.get("lengthText") or v.get("duration") or ""),
            "author_name": author_name,
            "author_handle": author_handle,
            "author_url": author_url,
            "author_followers": author_followers,
            "platform": "youtube",
            "matched_query": query,
        })
    return out


def _normalize_serper_videos(data: Any, query: str, platform: str) -> List[Dict[str, Any]]:
    items = data.get("videos") or data.get("organic") or (data if isinstance(data, list) else [])
    out: List[Dict[str, Any]] = []
    for v in items:
        if not isinstance(v, dict):
            continue
        url = str(v.get("link") or v.get("url") or "")
        if not url:
            continue
        author_name = str(v.get("channel") or v.get("source") or "")
        out.append({
            "video_id": str(v.get("videoId") or ""),
            "title": str(v.get("title") or ""),
            "url": url,
            "reel_url": url,
            "video_url": str(v.get("videoUrl") or ""),
            "views": _safe_int(v.get("views")),
            "likes": 0,
            "comments": 0,
            "shares": 0,
            "duration": str(v.get("duration") or ""),
            "author_name": author_name,
            "author_handle": author_name,
            "author_url": "",
            "platform": platform,
            "matched_query": query,
        })
    return out


def _normalize_fb_ads(data: Any, query: str) -> List[Dict[str, Any]]:
    items = data.get("results") or data.get("searchResults") or data.get("data") or (data if isinstance(data, list) else [])
    out: List[Dict[str, Any]] = []
    for v in items:
        if not isinstance(v, dict):
            continue
        snap = v.get("snapshot") if isinstance(v.get("snapshot"), dict) else {}
        videos = snap.get("videos") if isinstance(snap.get("videos"), list) else []
        first_vid = videos[0] if videos and isinstance(videos[0], dict) else {}
        vid = str(v.get("ad_archive_id") or v.get("id") or "")
        url = str(v.get("url") or (f"https://www.facebook.com/ads/library/?id={vid}" if vid else ""))
        if not url:
            continue
        body = snap.get("body") if isinstance(snap.get("body"), dict) else {}
        title = str(snap.get("title") or body.get("text") or v.get("page_name") or "")[:200]
        author_name = str(snap.get("page_name") or v.get("page_name") or "")
        author_url = str(snap.get("page_profile_uri") or "")
        out.append({
            "video_id": vid,
            "title": title,
            "url": url,
            "reel_url": url,
            "video_url": str(first_vid.get("video_hd_url") or first_vid.get("video_sd_url") or ""),
            "views": 0,
            "likes": 0,
            "comments": 0,
            "shares": 0,
            "duration": "",
            "author_name": author_name,
            "author_handle": author_name,
            "author_url": author_url,
            "platform": "facebook",
            "matched_query": query,
        })
    return out


def _normalize_tiktok(data: Any, query: str) -> List[Dict[str, Any]]:
    items = (
        data.get("search_item_list")
        or data.get("aweme_list")
        or data.get("videos")
        or data.get("data")
        or (data if isinstance(data, list) else [])
    )
    out: List[Dict[str, Any]] = []
    for raw in items:
        if not isinstance(raw, dict):
            continue
        v = raw.get("aweme_info") if isinstance(raw.get("aweme_info"), dict) else raw
        vid = str(v.get("aweme_id") or v.get("id") or "")
        author = v.get("author") if isinstance(v.get("author"), dict) else {}
        handle = str(author.get("unique_id") or v.get("author_handle") or "").lstrip("@")
        url = str(v.get("share_url") or v.get("url") or (f"https://www.tiktok.com/@{handle}/video/{vid}" if handle and vid else ""))
        if not url:
            continue
        stats = v.get("statistics") if isinstance(v.get("statistics"), dict) else {}
        out.append({
            "video_id": vid,
            "title": str(v.get("desc") or v.get("title") or ""),
            "url": url,
            "reel_url": url,
            "video_url": "",
            "views": _safe_int(stats.get("play_count") or v.get("views") or v.get("play_count")),
            "likes": _safe_int(stats.get("digg_count") or v.get("likes") or v.get("digg_count")),
            "comments": _safe_int(stats.get("comment_count") or v.get("comments")),
            "shares": _safe_int(stats.get("share_count") or v.get("shares")),
            "duration": str(v.get("duration") or ""),
            "author_name": str(author.get("nickname") or handle),
            "author_handle": handle,
            "author_url": f"https://www.tiktok.com/@{handle}" if handle else "",
            "author_followers": _safe_int(author.get("follower_count") or author.get("followerCount")),
            "platform": "tiktok",
            "matched_query": query,
        })
    return out


def _normalize_instagram(data: Any, query: str) -> List[Dict[str, Any]]:
    items = data.get("reels") or data.get("items") or data.get("data") or (data if isinstance(data, list) else [])
    out: List[Dict[str, Any]] = []
    for v in items:
        if not isinstance(v, dict):
            continue
        code = str(v.get("code") or v.get("shortcode") or "")
        vid = str(v.get("id") or v.get("pk") or code)
        url = str(v.get("url") or (f"https://www.instagram.com/reel/{code}/" if code else ""))
        if not url:
            continue
        user = v.get("user") or v.get("owner") or {}
        if not isinstance(user, dict):
            user = {}
        handle = str(user.get("username") or v.get("author_handle") or "").lstrip("@")
        cap = v.get("caption")
        title = str(cap.get("text") if isinstance(cap, dict) else (cap or v.get("title") or ""))[:200]
        out.append({
            "video_id": vid,
            "title": title,
            "url": url,
            "reel_url": url,
            "video_url": str(v.get("video_url") or ""),
            "views": _safe_int(v.get("play_count") or v.get("view_count") or v.get("views")),
            "likes": _safe_int(v.get("like_count") or v.get("likes")),
            "comments": _safe_int(v.get("comment_count") or v.get("comments")),
            "shares": 0,
            "duration": str(v.get("video_duration") or v.get("duration") or ""),
            "author_name": str(user.get("full_name") or handle),
            "author_handle": handle,
            "author_url": f"https://www.instagram.com/{handle}/" if handle else "",
            "author_followers": _safe_int(user.get("follower_count") or user.get("followers")),
            "platform": "instagram",
            "matched_query": query,
        })
    return out


def search_platform(
    platform: str,
    query: str,
    cache_dir: Optional[Path] = None,
    log: Optional[Callable[[str], None]] = None,
    task_id: Optional[str] = None,
    aggregator: Optional[ErrorAggregator] = None,
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """Search a single platform for a query via Glasser."""
    if platform == "youtube":
        data, src, err = _glasser_run_json(
            "scrapecreators", "/v1/youtube/search", 4,
            {"query": f'"{query}"', "sortBy": "popular"}, cache_dir, task_id=task_id,
        )
        videos = _normalize_youtube(data, query) if data is not None else []
    elif platform == "google":
        data, src, err = _glasser_run_json(
            "serper", "/videos", 2,
            {"q": f'"{query}"', "gl": "vn", "hl": "vi"}, cache_dir, task_id=task_id,
        )
        videos = _normalize_serper_videos(data, query, "google") if data is not None else []
    elif platform == "facebook":
        data, src, err = _glasser_run_json(
            "serper", "/videos", 2,
            {"q": f'site:facebook.com "{query}"', "gl": "vn", "hl": "vi"}, cache_dir, task_id=task_id,
        )
        videos = _normalize_serper_videos(data, query, "facebook") if data is not None else []
        if not videos and err is None:
            ad_data, ad_src, ad_err = _glasser_run_json(
                "scrapecreators", "/v1/facebook/adLibrary/search/ads", 4,
                {"query": query, "media_type": "VIDEO", "search_type": "keyword_exact_phrase"},
                cache_dir, task_id=task_id,
            )
            if ad_data is not None:
                videos = _normalize_fb_ads(ad_data, query)
                src = ad_src or src
            elif ad_err is not None:
                err = ad_err
    elif platform == "tiktok":
        data, src, err = _glasser_run_json(
            "scrapecreators", "/v1/tiktok/search/keyword", 4,
            {"query": query, "sort_by": "most-liked", "trim": True}, cache_dir, task_id=task_id,
        )
        videos = _normalize_tiktok(data, query) if data is not None else []
    elif platform == "instagram":
        data, src, err = _glasser_run_json(
            "scrapecreators", "/v2/instagram/reels/search", 4,
            {"query": query}, cache_dir, task_id=task_id,
        )
        videos = _normalize_instagram(data, query) if data is not None else []
    else:
        return [], None

    if err is not None and aggregator is not None:
        aggregator.add(handle_glasser_error(err, log=log))
    elif err is not None and log:
        log(f"[{platform}] {err}")
    return videos, src


def run_viral_video_search(
    keyword: str,
    run_dir: Path,
    options: Optional[Dict[str, Any]] = None,
    log: Optional[Callable[[str], None]] = None,
    job_id: str = "",
    aggregator: Optional[ErrorAggregator] = None,
) -> Dict[str, Any]:
    """Expand keyword (<=3 terms) and search 5 platforms, returning normalized videos + creators."""
    opts = options or {}
    _log = log or (lambda _msg: None)
    agg = aggregator or ErrorAggregator(job_id=job_id)
    cache_dir = Path(run_dir) / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    queries = expand_keyword(
        keyword,
        agent_id=opts.get("agent"),
        model=opts.get("model"),
        cwd=Path(run_dir),
        log=_log,
    )
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

    task_id = opts.get("glasser_task") or os.environ.get("GLASSER_TASK_ID") or None
    all_videos: List[Dict[str, Any]] = []
    seen_urls = set()
    source_breakdown: Dict[str, List[str]] = {"glasser_api": [], "cache": [], "empty": []}

    tasks = [(q_obj["text"], platform) for q_obj in queries for platform in PLATFORMS]
    with ThreadPoolExecutor(max_workers=min(5, len(tasks) or 1)) as pool:
        futures = [
            (
                q_text,
                platform,
                pool.submit(
                    search_platform,
                    platform,
                    q_text,
                    cache_dir=cache_dir,
                    log=_log,
                    task_id=task_id,
                    aggregator=agg,
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
