"""Pure-stdlib payload normalization, metric parsing, and transcript extraction."""

from __future__ import annotations

import re
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

CONTAINERS: Tuple[Tuple[str, ...], ...] = (
    ("output", "reels"),
    ("output", "search_item_list"),
    ("output", "item_list"),
    ("output", "aweme_list"),
    ("output", "posts"),
    ("output", "items"),
    ("data", "reels"),
    ("data", "items"),
    ("data", "search_item_list"),
    ("reels",),
    ("items",),
    ("search_item_list",),
    ("item_list",),
    ("data",),
)

METRIC_PATHS: Dict[str, Tuple[str, ...]] = {
    "views": (
        "play_count",
        "view_count",
        "views",
        "playCount",
        "viewCount",
        "video_view_count",
        "statistics.play_count",
        "stats.play_count",
    ),
    "likes": (
        "like_count",
        "digg_count",
        "likes",
        "likeCount",
        "diggCount",
        "statistics.digg_count",
        "stats.digg_count",
    ),
    "comments": (
        "comment_count",
        "comments",
        "commentCount",
        "statistics.comment_count",
        "stats.comment_count",
    ),
    "shares": (
        "share_count",
        "shares",
        "shareCount",
        "statistics.share_count",
        "stats.share_count",
    ),
}


def parse_int(val: Any) -> int:
    """Coerce an int, float, or digit string to int (0 on missing/invalid)."""
    if isinstance(val, (int, float)) and not isinstance(val, bool):
        return int(val)
    if isinstance(val, str):
        digits = re.sub(r"[^\d]", "", val)
        return int(digits) if digits else 0
    return 0


def first_int(*vals: Any) -> Optional[int]:
    """Return first non-None value coerced via parse_int, else None."""
    for val in vals:
        if val is not None:
            return parse_int(val)
    return None


def parse_compact_count(raw: str) -> int:
    """Parse compact human-readable follower/view counts (e.g. '1.2M', '15K', '2TR')."""
    s = (raw or "").strip().upper().replace(" ", "")
    if not s:
        return 0
    mult = 1
    if s.endswith("TR"):
        mult, s = 1_000_000, s[:-2].replace(",", ".")
    elif s.endswith("K") or s.endswith("N"):
        mult, s = 1_000, s[:-1].replace(",", ".")
    elif s.endswith("M"):
        mult, s = 1_000_000, s[:-1].replace(",", ".")
    elif s.endswith("B"):
        mult, s = 1_000_000_000, s[:-1].replace(",", ".")
    else:
        s = s.replace(",", "").replace(".", "")
    try:
        return int(float(s) * mult)
    except ValueError:
        return 0


def dig(item: Any, path: str) -> Any:
    """Safely traverse a dotted key path inside nested dicts."""
    value = item
    for key in path.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def unwrap_item(item: Any) -> Any:
    """Unwrap common provider item wrappers (aweme_info, media, item, post, reel)."""
    if not isinstance(item, dict):
        return item
    for key in ("aweme_info", "media", "item", "post", "reel"):
        inner = item.get(key)
        if isinstance(inner, dict) and inner:
            return inner
    return item


def extract_metric(item: Any, name: str) -> Optional[Union[int, float]]:
    """Extract numeric metric while preserving None for absent values."""
    for path in METRIC_PATHS[name]:
        value = dig(item, path)
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            return value
        if isinstance(value, str):
            try:
                text = value.replace(",", "").strip()
                return int(text) if text.isdigit() else float(text)
            except ValueError:
                continue
    return None


def raw_media_items(
    response: Any,
    fallback_extractor: Optional[Callable[[Any], List[Dict[str, Any]]]] = None,
) -> List[Dict[str, Any]]:
    """Extract ordered provider items across common response containers."""
    for path in CONTAINERS:
        value = dig(response, ".".join(path))
        if isinstance(value, list) and value:
            return [unwrap_item(item) for item in value if isinstance(item, dict)]
    if fallback_extractor is not None:
        return fallback_extractor(response)
    return []


def clean_webvtt(raw: str) -> str:
    """Strip WebVTT headers and cue timestamps into plain text."""
    lines: List[str] = []
    for line in (raw or "").splitlines():
        stripped = line.strip()
        if not stripped or stripped == "WEBVTT" or stripped.isdigit() or "-->" in stripped:
            continue
        if stripped.startswith(("NOTE", "Kind:", "Language:")):
            continue
        lines.append(stripped)
    return " ".join(lines).strip()


def extract_transcript_text(data: Any, platform: str) -> Optional[str]:
    """Normalize provider transcript payloads for Facebook, YouTube, TikTok, and Instagram."""
    if not isinstance(data, dict):
        return None
    if platform == "youtube":
        txt = data.get("transcript_only_text")
        if isinstance(txt, str) and txt.strip():
            return txt.strip()
        tr = data.get("transcript")
        if isinstance(tr, list):
            parts = [str(seg.get("text") or "").strip() for seg in tr if isinstance(seg, dict) and str(seg.get("text") or "").strip()]
            return " ".join(parts) if parts else None
        return tr.strip() if isinstance(tr, str) and tr.strip() else None
    if platform == "tiktok":
        tr = data.get("transcript")
        if isinstance(tr, str) and tr.strip():
            cleaned = clean_webvtt(tr)
            if cleaned:
                return cleaned
        twt = data.get("transcript_with_timestamp")
        if isinstance(twt, list):
            parts = [str(seg.get("text") or "").strip() for seg in twt if isinstance(seg, dict) and str(seg.get("text") or "").strip()]
            return " ".join(parts) if parts else None
        return None
    if platform == "instagram":
        trs = data.get("transcripts")
        if isinstance(trs, list):
            parts = [
                str(t.get("text") or "").strip()
                for t in trs
                if isinstance(t, dict) and isinstance(t.get("text"), str) and t.get("text").strip()
            ]
            return " ".join(parts) if parts else None
        tr = data.get("transcript")
        return tr.strip() if isinstance(tr, str) and tr.strip() else None
    tr = data.get("transcript")
    return tr.strip() if isinstance(tr, str) and tr.strip() else None


def _resolve_fallback(
    platform: str,
    vid: str,
    handle: str = "",
    fallback_url_fn: Optional[Callable[[str, str], str]] = None,
) -> str:
    if not vid:
        return ""
    if fallback_url_fn is not None:
        return fallback_url_fn(vid, handle)
    from tools.loop.viral_analyzer.platforms import fallback_video_url

    return fallback_video_url(platform, vid, author_handle=handle)


def normalize_profile_facebook(
    data: Any,
    handle: str,
    fallback_url_fn: Optional[Callable[[str, str], str]] = None,
) -> List[Dict[str, Any]]:
    del handle, fallback_url_fn
    if not isinstance(data, dict):
        return []
    reels = data.get("reels", [])
    return reels if isinstance(reels, list) else []


def normalize_profile_youtube(
    data: Any,
    handle: str,
    fallback_url_fn: Optional[Callable[[str, str], str]] = None,
) -> List[Dict[str, Any]]:
    if not isinstance(data, dict):
        return []
    items = data.get("videos") or data.get("shorts") or data.get("reels") or []
    if not isinstance(items, list):
        return []
    out: List[Dict[str, Any]] = []
    for v in items:
        if not isinstance(v, dict):
            continue
        vid = str(v.get("id") or v.get("videoId") or v.get("video_id") or "")
        url = str(v.get("url") or v.get("link") or _resolve_fallback("youtube", vid, handle, fallback_url_fn))
        if not url and not vid:
            continue
        views = first_int(v.get("viewCountInt"), v.get("views"), v.get("viewCount"), v.get("view_count")) or 0
        likes = first_int(v.get("likeCountInt"), v.get("likes"), v.get("likeCount"))
        comments = first_int(v.get("commentCountInt"), v.get("comments"), v.get("commentCount"))
        item: Dict[str, Any] = {
            "video_id": vid,
            "url": url,
            "video_url": v.get("video_url"),
            "view_count": views,
            "description": str(v.get("title") or v.get("description") or f"Video by @{handle}"),
            "creation_time": v.get("creation_time") or v.get("publishDate") or v.get("publishedTime") or v.get("publishedTimeText"),
            "platform": "youtube",
        }
        if likes is not None:
            item["likes"] = likes
        if comments is not None:
            item["comments"] = comments
        out.append(item)
    return out


def normalize_profile_tiktok(
    data: Any,
    handle: str,
    fallback_url_fn: Optional[Callable[[str, str], str]] = None,
) -> List[Dict[str, Any]]:
    if not isinstance(data, dict):
        return []
    items = data.get("aweme_list") or data.get("videos") or data.get("reels") or data.get("data") or []
    if not isinstance(items, list):
        return []
    out: List[Dict[str, Any]] = []
    for raw in items:
        if not isinstance(raw, dict):
            continue
        v = unwrap_item(raw)
        vid = str(v.get("aweme_id") or v.get("id") or v.get("video_id") or "")
        author = v.get("author") if isinstance(v.get("author"), dict) else {}
        author_h = str(author.get("unique_id") or v.get("author_handle") or handle).lstrip("@")
        url = str(
            v.get("url")
            or (_resolve_fallback("tiktok", vid, author_h, fallback_url_fn) if author_h and vid else "")
            or v.get("share_url")
            or ""
        )
        if not url and not vid:
            continue
        video_obj = v.get("video") if isinstance(v.get("video"), dict) else {}
        play_addr = video_obj.get("play_addr") if isinstance(video_obj.get("play_addr"), dict) else {}
        url_list = play_addr.get("url_list") if isinstance(play_addr.get("url_list"), list) else []
        video_url = v.get("video_url") or play_addr.get("url") or (url_list[0] if url_list else None)
        stats = v.get("statistics") if isinstance(v.get("statistics"), dict) else {}
        views = first_int(stats.get("play_count"), v.get("views"), v.get("play_count"), v.get("view_count")) or 0
        likes = first_int(stats.get("digg_count"), v.get("likes"), v.get("digg_count"))
        comments = first_int(stats.get("comment_count"), v.get("comments"), v.get("comment_count"))
        shares = first_int(stats.get("share_count"), v.get("shares"), v.get("share_count"))
        item: Dict[str, Any] = {
            "video_id": vid,
            "url": url,
            "video_url": video_url,
            "view_count": views,
            "description": str(v.get("desc") or v.get("description") or v.get("title") or f"TikTok by @{author_h}"),
            "creation_time": v.get("creation_time") or v.get("create_time_utc"),
            "timestamp": v.get("create_time") or v.get("timestamp"),
            "platform": "tiktok",
        }
        if likes is not None:
            item["likes"] = likes
        if comments is not None:
            item["comments"] = comments
        if shares is not None:
            item["shares"] = shares
        out.append(item)
    return out


def normalize_profile_instagram(
    data: Any,
    handle: str,
    fallback_url_fn: Optional[Callable[[str, str], str]] = None,
) -> List[Dict[str, Any]]:
    if not isinstance(data, dict):
        return []
    items = data.get("items") or data.get("reels") or data.get("data") or []
    if not isinstance(items, list):
        return []
    out: List[Dict[str, Any]] = []
    for raw in items:
        if not isinstance(raw, dict):
            continue
        v = unwrap_item(raw)
        code = str(v.get("code") or v.get("shortcode") or "")
        vid = str(v.get("pk") or v.get("id") or v.get("video_id") or code)
        url = str(v.get("url") or _resolve_fallback("instagram", code, handle, fallback_url_fn))
        if not url and not vid:
            continue
        versions = v.get("video_versions") if isinstance(v.get("video_versions"), list) else []
        first_ver = versions[0] if versions and isinstance(versions[0], dict) else {}
        video_url = v.get("video_url") or first_ver.get("url")
        views = first_int(
            v.get("play_count"),
            v.get("ig_play_count"),
            v.get("view_count"),
            v.get("views"),
        ) or 0
        likes = first_int(v.get("like_count"), v.get("likes"))
        comments = first_int(v.get("comment_count"), v.get("comments"))
        cap = v.get("caption")
        desc = str(
            cap.get("text") if isinstance(cap, dict) else (cap or v.get("description") or v.get("title") or f"Reel by @{handle}")
        )
        item: Dict[str, Any] = {
            "video_id": vid,
            "url": url,
            "video_url": video_url,
            "view_count": views,
            "description": desc,
            "creation_time": v.get("creation_time") or v.get("created_at"),
            "timestamp": v.get("taken_at") or v.get("timestamp") or (cap.get("created_at") if isinstance(cap, dict) else None),
            "platform": "instagram",
        }
        if likes is not None:
            item["likes"] = likes
        if comments is not None:
            item["comments"] = comments
        out.append(item)
    return out


def normalize_search_youtube(
    data: Any,
    query: str,
    fallback_url_fn: Optional[Callable[[str, str], str]] = None,
) -> List[Dict[str, Any]]:
    items = data.get("videos") or data.get("results") or data.get("items") or (data if isinstance(data, list) else [])
    out: List[Dict[str, Any]] = []
    for v in items:
        if not isinstance(v, dict):
            continue
        vid = str(v.get("id") or v.get("videoId") or "")
        url = str(v.get("url") or v.get("link") or _resolve_fallback("youtube", vid, "", fallback_url_fn))
        if not url:
            continue
        ch = v.get("channel") if isinstance(v.get("channel"), dict) else {}
        author_name = str(ch.get("title") or ch.get("name") or v.get("channelName") or v.get("author") or "")
        raw_handle = str(ch.get("handle") or "").strip().lstrip("/")
        author_handle = (raw_handle or str(ch.get("id") or author_name)).lstrip("@")
        raw_ch_url = str(ch.get("url") or ch.get("link") or v.get("channelUrl") or "")
        if not raw_ch_url:
            if raw_handle:
                path = raw_handle if raw_handle.startswith(("@", "channel/", "c/", "user/")) else f"@{raw_handle}"
                raw_ch_url = f"https://www.youtube.com/{path}"
            elif ch.get("id"):
                raw_ch_url = f"https://www.youtube.com/channel/{ch['id']}"
        author_followers = parse_int(ch.get("subscriberCount") or ch.get("followers") or v.get("channelFollowers"))
        out.append({
            "video_id": vid,
            "title": str(v.get("title") or ""),
            "url": url,
            "reel_url": url,
            "video_url": "",
            "views": parse_int(v.get("viewCountInt") or v.get("views") or v.get("viewCount")),
            "likes": parse_int(v.get("likes") or v.get("likeCount")),
            "comments": parse_int(v.get("comments") or v.get("commentCount")),
            "shares": 0,
            "duration": str(v.get("lengthText") or v.get("duration") or ""),
            "author_name": author_name,
            "author_handle": author_handle,
            "author_url": raw_ch_url,
            "author_followers": author_followers,
            "platform": "youtube",
            "matched_query": query,
        })
    return out


def normalize_search_serper(
    data: Any,
    query: str,
    platform: str,
    detect_platform_fn: Optional[Callable[[str], str]] = None,
    infer_author_fn: Optional[Callable[[str, str, str], Tuple[str, str]]] = None,
) -> List[Dict[str, Any]]:
    if detect_platform_fn is None:
        from tools.loop.viral_analyzer.platforms import detect_platform as detect_platform_fn
    items = data.get("videos") or data.get("organic") or (data if isinstance(data, list) else [])
    out: List[Dict[str, Any]] = []
    for v in items:
        if not isinstance(v, dict):
            continue
        url = str(v.get("link") or v.get("url") or "")
        if not url:
            continue
        real_platform = detect_platform_fn(url)
        if real_platform not in {"youtube", "tiktok", "instagram", "facebook"}:
            if platform in {"youtube", "tiktok", "instagram", "facebook"}:
                real_platform = platform
            else:
                continue
        author_name = str(v.get("channel") or v.get("source") or "")
        author_handle, author_url = (
            infer_author_fn(url, real_platform, author_name)
            if infer_author_fn is not None
            else (author_name, "")
        )
        out.append({
            "video_id": str(v.get("videoId") or ""),
            "title": str(v.get("title") or ""),
            "url": url,
            "reel_url": url,
            "video_url": str(v.get("videoUrl") or ""),
            "views": parse_int(v.get("views")),
            "likes": 0,
            "comments": 0,
            "shares": 0,
            "duration": str(v.get("duration") or ""),
            "author_name": author_name or author_handle,
            "author_handle": author_handle or author_name,
            "author_url": author_url,
            "platform": real_platform,
            "matched_query": query,
        })
    return out


def normalize_search_fb_ads(data: Any, query: str) -> List[Dict[str, Any]]:
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


def normalize_search_tiktok(
    data: Any,
    query: str,
    fallback_url_fn: Optional[Callable[[str, str], str]] = None,
) -> List[Dict[str, Any]]:
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
        v = unwrap_item(raw)
        vid = str(v.get("aweme_id") or v.get("id") or "")
        author = v.get("author") if isinstance(v.get("author"), dict) else {}
        handle = str(author.get("unique_id") or v.get("author_handle") or "").lstrip("@")
        url = str(v.get("share_url") or v.get("url") or (_resolve_fallback("tiktok", vid, handle, fallback_url_fn) if handle and vid else ""))
        if not url:
            continue
        stats = v.get("statistics") if isinstance(v.get("statistics"), dict) else {}
        out.append({
            "video_id": vid,
            "title": str(v.get("desc") or v.get("title") or ""),
            "url": url,
            "reel_url": url,
            "video_url": "",
            "views": parse_int(stats.get("play_count") or v.get("views") or v.get("play_count")),
            "likes": parse_int(stats.get("digg_count") or v.get("likes") or v.get("digg_count")),
            "comments": parse_int(stats.get("comment_count") or v.get("comments")),
            "shares": parse_int(stats.get("share_count") or v.get("shares")),
            "duration": str(v.get("duration") or ""),
            "author_name": str(author.get("nickname") or handle),
            "author_handle": handle,
            "author_url": f"https://www.tiktok.com/@{handle}" if handle else "",
            "author_followers": parse_int(author.get("follower_count") or author.get("followerCount")),
            "platform": "tiktok",
            "matched_query": query,
        })
    return out


def normalize_search_instagram(
    data: Any,
    query: str,
    fallback_url_fn: Optional[Callable[[str, str], str]] = None,
) -> List[Dict[str, Any]]:
    items = data.get("reels") or data.get("items") or data.get("data") or (data if isinstance(data, list) else [])
    out: List[Dict[str, Any]] = []
    for v in items:
        if not isinstance(v, dict):
            continue
        code = str(v.get("code") or v.get("shortcode") or "")
        vid = str(v.get("id") or v.get("pk") or code)
        url = str(v.get("url") or _resolve_fallback("instagram", code, "", fallback_url_fn))
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
            "views": parse_int(v.get("play_count") or v.get("view_count") or v.get("views")),
            "likes": parse_int(v.get("like_count") or v.get("likes")),
            "comments": parse_int(v.get("comment_count") or v.get("comments")),
            "shares": 0,
            "duration": str(v.get("video_duration") or v.get("duration") or ""),
            "author_name": str(user.get("full_name") or handle),
            "author_handle": handle,
            "author_url": f"https://www.instagram.com/{handle}/" if handle else "",
            "author_followers": parse_int(user.get("follower_count") or user.get("followers")),
            "platform": "instagram",
            "matched_query": query,
        })
    return out
