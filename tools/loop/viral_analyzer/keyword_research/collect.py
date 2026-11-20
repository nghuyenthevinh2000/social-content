"""Collection helpers for cross-platform keyword search and follower enrichment."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import re
import time
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import quote, urlparse
import urllib.request

from tools.app.backend.acp import ACPClient, ACPError
from tools.app.backend.errors import ErrorAggregator, handle_glasser_error
from tools.loop.viral_analyzer import cache, glasser, normalize, platforms, runtime
from tools.loop.viral_analyzer.keyword_research import config
from tools.loop.viral_analyzer.keyword_research import prompt as prompt_lib


def _fetch_public_followers(url: str, timeout: float = 4.0, use_db_cache: bool = True) -> int:
    """Fetch public follower/subscriber count from channel HTML (<head> 32KB for FB/IG/TT)."""
    if not url or not url.startswith("http"):
        return 0
    if use_db_cache:
        cached = cache.read_cached_followers([url])
        if cached.get(url):
            return cached[url]

    is_yt = "youtube.com" in url
    if is_yt:
        ua = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    elif "tiktok.com" in url:
        ua = "facebookexternalhit/1.1"
    else:
        ua = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"

    count = 0
    for attempt in range(2):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": ua, "Accept-Language": "en-US,en;q=0.9"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read() if is_yt else resp.read(32_768)
                html = raw.decode("utf-8", errors="ignore")
            if is_yt:
                m_yt = re.search(
                    r'"metadataParts":\[\{"text":\{"content":"([0-9]+(?:[.,][0-9]+)*\s*[KMB]?)\s+subscribers"',
                    html,
                    re.IGNORECASE,
                )
                if m_yt:
                    count = normalize.parse_compact_count(m_yt.group(1))
            if not count:
                m_json = re.search(r'"followerCount"\s*:\s*(\d+)', html)
                if m_json:
                    count = int(m_json.group(1))
            if not count:
                m = re.search(
                    r'([0-9]+(?:[.,][0-9]+)*\s*(?:TR|[KMBN])?)\s+(?:subscribers|Followers|followers|người theo dõi|lượt thích|members|thành viên)',
                    html,
                    re.IGNORECASE,
                )
                if m:
                    count = normalize.parse_compact_count(m.group(1))
            if count > 0:
                break
        except Exception:
            pass
        if attempt == 0:
            time.sleep(0.3)

    if use_db_cache and count > 0:
        cache.write_cached_followers([(url, count)])
    return count


def _enrich_creator_followers(creators: List[Dict[str, Any]]) -> None:
    """Batch-read cached follower counts, fetch missing ones, and batch-upsert."""
    missing = [c for c in creators if not c.get("followers") and c.get("url")]
    if not missing:
        return
    cached_map = cache.read_cached_followers([c["url"] for c in missing])
    for c in missing:
        hit = cached_map.get(c["url"])
        if hit:
            c["followers"] = hit

    still_missing = [c for c in missing if not c.get("followers")]
    if not still_missing:
        return

    new_entries: List[Tuple[str, int]] = []
    with ThreadPoolExecutor(max_workers=min(6, len(still_missing))) as fpool:
        results = fpool.map(lambda item: _fetch_public_followers(item["url"], use_db_cache=False), still_missing)
        for c, cnt in zip(still_missing, results):
            if cnt > 0:
                c["followers"] = cnt
                new_entries.append((c["url"], cnt))

    if new_entries:
        cache.write_cached_followers(new_entries)


def _run_acp_prompt(
    prompt: str,
    agent_id: Optional[str] = None,
    model: Optional[str] = None,
    cwd: Optional[Path] = None,
    log: Optional[Callable[[str], None]] = None,
    ctx: Optional[runtime.EngineContext] = None,
    timeout_sec: float = 30.0,
) -> Optional[str]:
    """Run a single ACP/agent_runner prompt, returning raw text or None when unconfigured."""
    if ctx is not None and ctx.agent_runner is not None:
        return ctx.agent_runner(prompt)
    if agent_id:
        from tools.app.backend.research_engine.research import _harness_lock, resolve_agent

        with _harness_lock(log or (lambda _msg: None)):
            preset = resolve_agent(agent_id, model=model)
            client = ACPClient(preset["command"], cwd=cwd or Path.cwd(), timeout_sec=timeout_sec, log=log)
            client.initialize()
            sid = client.new_session()
            return client.prompt(sid, prompt)
    return None


def _parse_json_object(raw: Optional[str]) -> Optional[Dict[str, Any]]:
    match = re.search(r"\{[\s\S]*\}", raw or "")
    if not match:
        return None
    parsed = json.loads(match.group(0))
    return parsed if isinstance(parsed, dict) else None


def expand_keyword(
    keyword: str,
    agent_id: Optional[str] = None,
    model: Optional[str] = None,
    cwd: Optional[Path] = None,
    log: Optional[Callable[[str], None]] = None,
    ctx: Optional[runtime.EngineContext] = None,
    language: Optional[str] = None,
) -> List[Dict[str, str]]:
    """Expand keyword into at most 3 queries: [original, abbreviation, vi]."""
    kw = re.sub(r"\s+", " ", (keyword or "")).strip()
    if not kw:
        return []
    _log = log or (lambda _msg: None)
    queries: List[Dict[str, str]] = [{"kind": "original", "text": kw}]

    known = config.FALLBACK_EXPANSIONS.get(kw.lower())
    if known:
        abbr, vi = known
        return config.dedup_queries([
            {"kind": "original", "text": kw},
            {"kind": "abbreviation", "text": abbr},
            {"kind": "vi", "text": vi},
        ])

    prompt = prompt_lib.build_expand_keyword_prompt(kw, language=language)

    try:
        raw = _run_acp_prompt(prompt, agent_id=agent_id, model=model, cwd=cwd, log=_log, ctx=ctx, timeout_sec=30.0)
        parsed = _parse_json_object(raw)
        if parsed:
            if parsed.get("abbreviation"):
                queries.append({"kind": "abbreviation", "text": str(parsed["abbreviation"])})
            if parsed.get("vi"):
                queries.append({"kind": "vi", "text": str(parsed["vi"])})
    except (ACPError, Exception) as exc:
        _log(f"Bỏ qua mở rộng từ khoá qua ACP ({exc}); dùng từ khoá gốc.")

    return config.dedup_queries(queries, limit=3)


def analyze_creator_relevance(
    keyword: str,
    creators: List[Dict[str, Any]],
    reels: List[Dict[str, Any]],
    agent_id: Optional[str] = None,
    model: Optional[str] = None,
    cwd: Optional[Path] = None,
    log: Optional[Callable[[str], None]] = None,
    ctx: Optional[runtime.EngineContext] = None,
    timeout_sec: float = 240.0,
    language: Optional[str] = None,
) -> None:
    """Ask ACP why each creator is relevant to keyword; mutates creators in place."""
    if not creators:
        return
    _log = log or (lambda _msg: None)
    titles_by_url: Dict[str, List[str]] = {}
    for r in reels:
        u = (r.get("author_url") or "").strip()
        title = re.sub(r"\s+", " ", (r.get("title") or "")).strip()[:160]
        if u and title:
            titles_by_url.setdefault(u, []).append(title)

    items = [
        {
            "key": c["url"],
            "name": c.get("name") or c.get("handle") or "",
            "platform": c.get("platform") or "",
            "followers": c.get("followers") or 0,
            "titles": titles_by_url.get(c["url"], [])[:3],
        }
        for c in creators
    ]
    prompt = prompt_lib.build_creator_relevance_prompt(keyword, items, language=language)
    try:
        raw = _run_acp_prompt(prompt, agent_id=agent_id, model=model, cwd=cwd, log=_log, ctx=ctx, timeout_sec=timeout_sec)
        parsed = _parse_json_object(raw)
        if not parsed:
            return
        for c in creators:
            entry = parsed.get(c["url"]) or parsed.get(c.get("handle", ""))
            if isinstance(entry, dict):
                c["relevance"] = str(entry.get("relevance") or "").strip()
                c["why_relevant"] = str(entry.get("why_relevant") or "").strip()
    except (ACPError, Exception) as exc:
        _log(f"Bỏ qua phân tích độ liên quan qua ACP ({exc}).")


def _glasser_run_json(
    provider: str,
    endpoint: str,
    version: int,
    payload: Dict[str, Any],
    cache_dir: Optional[Path],
    task_id: Optional[str] = None,
    timeout: float = 45.0,
    ctx: Optional[runtime.EngineContext] = None,
) -> Tuple[Optional[Any], Optional[str], Optional[Exception]]:
    """Run a single Glasser endpoint via the shared single-flight, semaphore-bounded runner."""
    return glasser.run_glasser_json(
        provider=provider,
        endpoint=endpoint,
        version=version,
        payload=payload,
        cache_dir=cache_dir,
        task_id=task_id,
        timeout=timeout,
        sub_action="keyword_search",
        cache_sub_action="keyword_cache",
        ctx=ctx,
    )


def _infer_serper_author(url: str, real_platform: str, fallback_name: str) -> Tuple[str, str]:
    parsed = urlparse(url)
    parts = [p for p in parsed.path.split("/") if p]
    if real_platform == "tiktok" and parts and parts[0].startswith("@"):
        return platforms.social_handle(url)
    if real_platform == "facebook" and parts:
        if parts[0] == "groups" and len(parts) >= 2:
            return fallback_name or f"group_{parts[1]}", f"https://www.facebook.com/groups/{parts[1]}"
        if parts[0] not in {
            "reel", "reels", "watch", "share", "groups", "ads", "events", "permalink.php", "story.php", "video.php",
        }:
            return platforms.social_handle(url)
    if real_platform == "instagram" and parts and parts[0] not in {"reel", "reels", "p", "tv", "stories"}:
        return platforms.social_handle(url)
    if real_platform == "youtube":
        if parts and (parts[0].startswith("@") or parts[0] in {"channel", "c", "user"}):
            return platforms.social_handle(url)
        try:
            oembed_url = f"https://www.youtube.com/oembed?url={quote(url, safe=':/?=&')}&format=json"
            with urllib.request.urlopen(oembed_url, timeout=3.0) as resp:
                au = str(json.loads(resp.read().decode("utf-8")).get("author_url") or "")
                if au:
                    return platforms.social_handle(au)
        except Exception:
            pass
    return fallback_name, ""


def _normalize_search_result(parser_kind: str, data: Any, query: str, platform: str) -> List[Dict[str, Any]]:
    if data is None:
        return []
    if parser_kind == "youtube":
        return normalize.normalize_search_youtube(data, query)
    if parser_kind in ("google", "facebook_serper"):
        return normalize.normalize_search_serper(
            data,
            query,
            platform,
            detect_platform_fn=platforms.detect_platform,
            infer_author_fn=_infer_serper_author,
        )
    if parser_kind == "facebook_ads":
        return normalize.normalize_search_fb_ads(data, query)
    if parser_kind == "tiktok":
        return normalize.normalize_search_tiktok(data, query)
    if parser_kind == "instagram":
        return normalize.normalize_search_instagram(data, query)
    spec = platforms.get_platform(platform)
    if spec is not None and spec.normalize_search_fn is not None:
        return spec.normalize_search_fn(data, query)
    return []


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
    """Search a single platform for a query via PlatformSpec + Glasser."""
    spec = platforms.get_platform(platform)
    if spec is None or spec.search_queries_fn is None:
        return [], None
    query_specs = spec.search_queries_fn(query)
    if not query_specs:
        return [], None

    run_json = glasser_fn or _glasser_run_json

    def _call(provider: str, endpoint: str, version: int, payload: Dict[str, Any]):
        if run_json is _glasser_run_json and ctx is not None:
            return run_json(provider, endpoint, version, payload, cache_dir, task_id=task_id, ctx=ctx)
        return run_json(provider, endpoint, version, payload, cache_dir, task_id=task_id)

    provider, endpoint, version, payload, parser_kind = query_specs[0]
    data, src, err = _call(provider, endpoint, version, payload)
    videos = _normalize_search_result(parser_kind, data, query, platform)

    for fb_provider, fb_endpoint, fb_version, fb_payload, fb_parser in query_specs[1:]:
        if videos or err is not None:
            break
        fb_data, fb_src, fb_err = _call(fb_provider, fb_endpoint, fb_version, fb_payload)
        if fb_data is not None:
            videos = _normalize_search_result(fb_parser, fb_data, query, platform)
            src = fb_src or src
        elif fb_err is not None:
            err = fb_err

    if err is not None and aggregator is not None:
        aggregator.add(handle_glasser_error(err, log=log))
    elif err is not None and log:
        log(f"[{platform}] {err}")
    return videos, src
