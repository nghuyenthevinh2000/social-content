"""Pure-stdlib declarative platform registry, URL/handle parsers, and endpoint routing."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Callable, Dict, List, Optional, Tuple
import urllib.error
from urllib.parse import parse_qs, urlparse
import urllib.request

from tools.loop.viral_analyzer import normalize

SUPPORTED_PLATFORMS = ("facebook", "youtube", "tiktok", "instagram")


@dataclass(frozen=True)
class PlatformSpec:
    """Declarative specification for one supported social/video platform."""

    name: str
    domains: Tuple[str, ...]
    reel_patterns: Tuple[re.Pattern[str], ...]
    handle_fn: Callable[[str], Tuple[str, str]]
    fallback_url_fn: Callable[[str, str], str]
    default_profile_url_fn: Optional[Callable[[str], str]] = None
    profile_query_fn: Optional[Callable[[str, str, Any], Tuple[str, str, int, Dict[str, Any]]]] = None
    search_queries_fn: Optional[Callable[[str], List[Tuple[str, str, int, Dict[str, Any], str]]]] = None
    transcript_endpoint: Optional[Tuple[str, int]] = None
    transcript_url_re: Optional[re.Pattern[str]] = None
    normalize_profile_fn: Optional[Callable[[Any, str], List[Dict[str, Any]]]] = None
    normalize_search_fn: Optional[Callable[..., List[Dict[str, Any]]]] = None


PLATFORMS_REGISTRY: Dict[str, PlatformSpec] = {}
REEL_PATTERNS: List[re.Pattern[str]] = []


def _sync_reel_patterns() -> None:
    patterns: List[re.Pattern[str]] = []
    for spec in PLATFORMS_REGISTRY.values():
        patterns.extend(spec.reel_patterns)
    REEL_PATTERNS[:] = patterns


def register_platform(spec: PlatformSpec) -> PlatformSpec:
    """Register or replace a PlatformSpec and refresh compiled URL patterns."""
    PLATFORMS_REGISTRY[spec.name.strip().lower()] = spec
    _sync_reel_patterns()
    return spec


def unregister_platform(name: str) -> Optional[PlatformSpec]:
    """Remove a registered PlatformSpec (primarily for tests) and refresh patterns."""
    removed = PLATFORMS_REGISTRY.pop(name.strip().lower(), None)
    _sync_reel_patterns()
    return removed


def get_platform(name: str) -> Optional[PlatformSpec]:
    """Return PlatformSpec by normalized platform name."""
    return PLATFORMS_REGISTRY.get((name or "").strip().lower())


def facebook_handle(url: str) -> Tuple[str, str]:
    """Return (handle, canonical_url) from a Facebook profile/reel/page URL."""
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    if "profile.php" in parsed.path and query.get("id"):
        profile_id = query["id"][0]
        return f"profile_{profile_id}", f"https://www.facebook.com/profile.php?id={profile_id}"
    parts = [part for part in parsed.path.split("/") if part]
    if parts:
        handle = parts[0]
        return handle, f"https://www.facebook.com/{handle}"
    return parsed.netloc or "unknown", url


def _youtube_handle(url: str) -> Tuple[str, str]:
    parsed = urlparse(url)
    parts = [part for part in parsed.path.split("/") if part]
    if parts and parts[0].startswith("@"):
        handle = parts[0].lstrip("@")
        return handle, f"https://www.youtube.com/@{handle}"
    if len(parts) >= 2 and parts[0] in {"channel", "c", "user"}:
        return parts[1], f"https://www.youtube.com/{parts[0]}/{parts[1]}"
    return (parts[0] if parts else parsed.netloc or "youtube"), url


def _tiktok_handle(url: str) -> Tuple[str, str]:
    parsed = urlparse(url)
    parts = [part for part in parsed.path.split("/") if part]
    if parts and parts[0].startswith("@"):
        handle = parts[0].lstrip("@")
        return handle, f"https://www.tiktok.com/@{handle}"
    return (parts[0] if parts else parsed.netloc or "tiktok"), url


def _instagram_handle(url: str) -> Tuple[str, str]:
    parsed = urlparse(url)
    parts = [part for part in parsed.path.split("/") if part]
    if parts and parts[0] not in {"reel", "reels", "p", "tv", "stories"}:
        handle = parts[0].lstrip("@")
        return handle, f"https://www.instagram.com/{handle}/"
    return (parts[0] if parts else parsed.netloc or "instagram"), url


def detect_platform(url: str) -> str:
    """Identify social platform from a URL."""
    lowered = (url or "").lower()
    for spec in PLATFORMS_REGISTRY.values():
        if any(dom in lowered for dom in spec.domains):
            return spec.name
    return "web"


def social_handle(url: str) -> Tuple[str, str]:
    """Return (handle, canonical_url) preserving platform URLs."""
    cleaned = (url or "").strip()
    if not cleaned.lower().startswith(("http://", "https://")):
        return cleaned or "unknown", cleaned
    platform = detect_platform(cleaned)
    spec = get_platform(platform)
    if spec is not None:
        return spec.handle_fn(cleaned)
    parsed = urlparse(cleaned)
    parts = [part for part in parsed.path.split("/") if part]
    return (parts[0] if parts else parsed.netloc or platform), cleaned


def resolve_short_url(url: str, timeout: float = 3.0) -> str:
    """Resolve short share URLs (fb.watch, facebook.com/share/*, vm.tiktok.com) to target URL."""
    if not url or not any(x in url for x in ("facebook.com/share/", "fb.watch/", "tiktok.com/")):
        return url
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"},
        )

        class _NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None

        opener = urllib.request.build_opener(_NoRedirect)
        try:
            resp = opener.open(req, timeout=timeout)
            loc = resp.headers.get("Location")
        except urllib.error.HTTPError as exc:
            loc = exc.headers.get("Location")
        if loc:
            return loc
    except Exception:
        pass
    return url


def canonicalize_reel_url(
    url: str,
    resolve_redirects: bool = True,
    resolver: Optional[Callable[[str], str]] = None,
) -> Optional[Tuple[str, str]]:
    """Clean tracking params from Reel URL and detect platform."""
    if not url:
        return None
    resolve_fn = resolver or resolve_short_url
    target_url = resolve_fn(url) if resolve_redirects else url
    for spec in PLATFORMS_REGISTRY.values():
        for pattern in spec.reel_patterns:
            match = pattern.search(target_url)
            if match:
                clean = match.group(0).rstrip("/")
                lowered = clean.lower()
                if spec.name == "youtube":
                    vid = match.group(1)
                    if "/shorts/" in lowered:
                        return f"https://www.youtube.com/shorts/{vid}", "youtube"
                    return f"https://www.youtube.com/watch?v={vid}", "youtube"
                return clean, spec.name
    return None


def is_reel_url(url: str) -> bool:
    """Return True if the URL points directly to an individual Reel or video."""
    if not url:
        return False
    return any(p.search(url) for spec in PLATFORMS_REGISTRY.values() for p in spec.reel_patterns)


def extract_video_id(url: str) -> Optional[str]:
    """Extract numeric or alphanumeric video ID from a reel/video URL."""
    if not url:
        return None
    for spec in PLATFORMS_REGISTRY.values():
        for pattern in spec.reel_patterns:
            m = pattern.search(url)
            if m and m.groups():
                return m.group(1)
    return None


def fallback_video_url(platform: str, video_id: str, author_handle: str = "") -> str:
    """Build a canonical platform video URL from platform, video_id, and optional handle."""
    vid = str(video_id or "").strip()
    if not vid:
        return ""
    spec = get_platform(platform) or get_platform("facebook")
    if spec is not None:
        return spec.fallback_url_fn(vid, author_handle)
    return f"https://www.facebook.com/reel/{vid}"


def default_profile_url(platform: str, handle: str) -> str:
    """Build a canonical creator profile URL from platform and handle."""
    spec = get_platform(platform) or get_platform("facebook")
    if spec is not None and spec.default_profile_url_fn is not None:
        return spec.default_profile_url_fn(handle)
    return f"https://www.facebook.com/{handle}"


def resolve_transcript_endpoint(reel_url: str) -> Optional[Tuple[str, str, int]]:
    """Map an individual video URL to (platform, gl_endpoint, endpoint_version)."""
    cleaned = (reel_url or "").strip()
    if not cleaned:
        return None
    for spec in PLATFORMS_REGISTRY.values():
        if spec.transcript_endpoint and spec.transcript_url_re and spec.transcript_url_re.match(cleaned):
            ep, ver = spec.transcript_endpoint
            return (spec.name, ep, ver)
    return None


# -- Built-in platform registrations ----------------------------------------

def _yt_profile_query(handle: str, profile_url: str, _config: Any) -> Tuple[str, str, int, Dict[str, Any]]:
    clean_h = handle.lstrip("@")
    is_shorts = "/shorts" in profile_url.lower()
    endpoint = "/v1/youtube/channel/shorts" if is_shorts else "/v1/youtube/channel-videos"
    payload: Dict[str, Any] = {
        "handle": clean_h,
        "sort": "newest" if is_shorts else "latest",
    }
    if "/channel/" in profile_url or (clean_h.startswith("UC") and len(clean_h) >= 20):
        payload["channelId"] = clean_h
    return "scrapecreators", endpoint, 4, payload


def _tt_profile_query(handle: str, _profile_url: str, _config: Any) -> Tuple[str, str, int, Dict[str, Any]]:
    return "scrapecreators", "/v3/tiktok/profile/videos", 4, {"handle": handle.lstrip("@"), "sort_by": "latest"}


def _ig_profile_query(handle: str, _profile_url: str, _config: Any) -> Tuple[str, str, int, Dict[str, Any]]:
    return "scrapecreators", "/v1/instagram/user/reels", 4, {"handle": handle.lstrip("@")}


def _fb_profile_query(_handle: str, profile_url: str, config: Any) -> Tuple[str, str, int, Dict[str, Any]]:
    return (
        getattr(config, "glasser_provider", "scrapecreators"),
        getattr(config, "glasser_endpoint", "/v1/facebook/profile/reels"),
        getattr(config, "glasser_endpoint_version", 2),
        {"url": profile_url},
    )


register_platform(PlatformSpec(
    name="youtube",
    domains=("youtube.com", "youtu.be"),
    reel_patterns=(
        re.compile(r"https?://(?:(?:www|m)\.)?youtube\.com/watch/?\?(?:[^#\s]*&)?v=([a-zA-Z0-9_-]{6,})", re.I),
        re.compile(r"https?://(?:(?:www|m)\.)?youtube\.com/shorts/([a-zA-Z0-9_-]{6,})", re.I),
        re.compile(r"https?://youtu\.be/([a-zA-Z0-9_-]{6,})", re.I),
    ),
    handle_fn=_youtube_handle,
    fallback_url_fn=lambda vid, _h="": f"https://www.youtube.com/watch?v={vid}",
    default_profile_url_fn=lambda h: f"https://www.youtube.com/@{h.lstrip('@')}",
    profile_query_fn=_yt_profile_query,
    search_queries_fn=lambda q: [
        ("scrapecreators", "/v1/youtube/search", 4, {"query": f'"{q}"', "sortBy": "popular"}, "youtube"),
    ],
    transcript_endpoint=("/v1/youtube/video/transcript", 4),
    transcript_url_re=re.compile(
        r"^https?://(?:(?:[\w.-]+\.)?youtube\.com/(?:watch/?\?(?:[^#]*&)?v=|shorts/)[A-Za-z0-9_-]{6,}|youtu\.be/[A-Za-z0-9_-]{6,})",
        re.I,
    ),
    normalize_profile_fn=normalize.normalize_profile_youtube,
    normalize_search_fn=normalize.normalize_search_youtube,
))

register_platform(PlatformSpec(
    name="tiktok",
    domains=("tiktok.com",),
    reel_patterns=(
        re.compile(r"https?://(?:www\.)?tiktok\.com/@[\w.-]+/(?:video|photo)/(\d+)", re.I),
        re.compile(r"https?://(?:vm|vt)\.tiktok\.com/([a-zA-Z0-9_-]+)", re.I),
        re.compile(r"https?://(?:www\.)?tiktok\.com/t/([a-zA-Z0-9_-]+)", re.I),
    ),
    handle_fn=_tiktok_handle,
    fallback_url_fn=lambda vid, h="": (
        f"https://www.tiktok.com/@{str(h).strip().lstrip('@')}/video/{vid}"
        if str(h or "").strip().lstrip("@")
        else f"https://www.tiktok.com/video/{vid}"
    ),
    default_profile_url_fn=lambda h: f"https://www.tiktok.com/@{h.lstrip('@')}",
    profile_query_fn=_tt_profile_query,
    search_queries_fn=lambda q: [
        ("scrapecreators", "/v1/tiktok/search/keyword", 4, {"query": q, "sort_by": "most-liked", "trim": True}, "tiktok"),
    ],
    transcript_endpoint=("/v1/tiktok/video/transcript", 4),
    transcript_url_re=re.compile(
        r"^https?://(?:[\w.-]+\.)?tiktok\.com/(?:@[\w.-]+/(?:video|photo)/\d+|t/[A-Za-z0-9_-]+|[A-Za-z0-9_-]+)",
        re.I,
    ),
    normalize_profile_fn=normalize.normalize_profile_tiktok,
    normalize_search_fn=normalize.normalize_search_tiktok,
))

register_platform(PlatformSpec(
    name="instagram",
    domains=("instagram.com",),
    reel_patterns=(
        re.compile(r"https?://(?:www\.)?instagram\.com/(?:[a-zA-Z0-9_.-]+/)?reels?/([a-zA-Z0-9_-]+)", re.I),
        re.compile(r"https?://(?:www\.)?instagram\.com/(?:[a-zA-Z0-9_.-]+/)?(?:p|tv)/([a-zA-Z0-9_-]+)", re.I),
    ),
    handle_fn=_instagram_handle,
    fallback_url_fn=lambda vid, _h="": f"https://www.instagram.com/reel/{vid}/",
    default_profile_url_fn=lambda h: f"https://www.instagram.com/{h.lstrip('@')}/",
    profile_query_fn=_ig_profile_query,
    search_queries_fn=lambda q: [
        ("scrapecreators", "/v2/instagram/reels/search", 4, {"query": q}, "instagram"),
    ],
    transcript_endpoint=("/v2/instagram/media/transcript", 6),
    transcript_url_re=re.compile(
        r"^https?://(?:[\w.-]+\.)?instagram\.com/(?:[\w.-]+/)?(?:reels?|p|tv)/[A-Za-z0-9_-]+",
        re.I,
    ),
    normalize_profile_fn=normalize.normalize_profile_instagram,
    normalize_search_fn=normalize.normalize_search_instagram,
))

register_platform(PlatformSpec(
    name="facebook",
    domains=("facebook.com", "fb.com", "fb.watch"),
    reel_patterns=(
        re.compile(r"https?://(?:www\.)?facebook\.com/reel/(\d+)", re.I),
        re.compile(r"https?://(?:www\.)?facebook\.com/share/[rvp]/([a-zA-Z0-9_-]+)", re.I),
        re.compile(r"https?://(?:www\.)?facebook\.com/watch/?\?(?:[^#\s]*&)?v=(\d+)", re.I),
        re.compile(r"https?://(?:www\.)?facebook\.com/[a-zA-Z0-9_.-]+/videos/(\d+)", re.I),
        re.compile(r"https?://(?:www\.)?facebook\.com/ads/library/\?(?:[^#\s]*&)?id=(\d+)", re.I),
        re.compile(r"https?://fb\.watch/([a-zA-Z0-9_-]+)", re.I),
    ),
    handle_fn=facebook_handle,
    fallback_url_fn=lambda vid, _h="": f"https://www.facebook.com/reel/{vid}",
    default_profile_url_fn=lambda h: f"https://www.facebook.com/{h}",
    profile_query_fn=_fb_profile_query,
    search_queries_fn=lambda q: [
        ("serper", "/videos", 2, {"q": f'site:facebook.com "{q}"', "gl": "vn", "hl": "vi"}, "facebook_serper"),
        ("scrapecreators", "/v1/facebook/adLibrary/search/ads", 4, {"query": q, "media_type": "VIDEO", "search_type": "keyword_exact_phrase"}, "facebook_ads"),
    ],
    transcript_endpoint=("/v1/facebook/post/transcript", 4),
    transcript_url_re=re.compile(
        r"^https?://(?:[\w.-]+\.)?facebook\.com/(?:reel/\d+|[^/]+/videos/\d+|watch/?\?(?:[^#]*&)?v=\d+)",
        re.I,
    ),
    normalize_profile_fn=normalize.normalize_profile_facebook,
    normalize_search_fn=normalize.normalize_search_fb_ads,
))

register_platform(PlatformSpec(
    name="google",
    domains=(),
    reel_patterns=(),
    handle_fn=lambda u: (urlparse(u).netloc or "google", u),
    fallback_url_fn=lambda vid, _h="": vid,
    search_queries_fn=lambda q: [
        ("serper", "/videos", 2, {"q": f'"{q}"', "gl": "vn", "hl": "vi"}, "google"),
    ],
))
