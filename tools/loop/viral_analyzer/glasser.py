"""Glasser CLI client, error detection, and response caching for Facebook Reels.

Handles authentication checks, ScrapeCreators reel harvesting, TTL-based caching,
and detailed error classification (e.g. missing API key, missing binary, execution failure).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

CURRENT_DIR = Path(__file__).parent.resolve()


# -- Error definitions -------------------------------------------------------

class GlasserError(RuntimeError):
    """Base exception for Glasser scraping errors."""

    def __init__(
        self,
        message: str,
        handle: Optional[str] = None,
        returncode: Optional[int] = None,
        raw_output: Optional[str] = None,
        suggestion: Optional[str] = None,
    ):
        super().__init__(message)
        self.message = message
        self.handle = handle
        self.returncode = returncode
        self.raw_output = raw_output
        self.suggestion = suggestion or "Kiểm tra kết nối mạng hoặc đường dẫn Facebook."

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "handle": self.handle,
            "returncode": self.returncode,
            "suggestion": self.suggestion,
        }


class GlasserMissingKeyError(GlasserError):
    """Raised when GLASSER_API_KEY is missing or unauthenticated."""

    def __init__(
        self,
        message: str = "Chưa cấu hình GLASSER_API_KEY cho Glasser CLI.",
        handle: Optional[str] = None,
        returncode: Optional[int] = None,
        raw_output: Optional[str] = None,
        suggestion: Optional[str] = None,
    ):
        sugg = suggestion or (
            "Thêm 'GLASSER_API_KEY=<key>' vào file .env (hoặc local/deployment-service/.env) "
            "rồi khởi động lại backend."
        )
        super().__init__(
            message=message,
            handle=handle,
            returncode=returncode,
            raw_output=raw_output,
            suggestion=sugg,
        )


class GlasserNotFoundError(GlasserError):
    """Raised when the glasser executable is not found in PATH."""

    def __init__(
        self,
        message: str = "Không tìm thấy lệnh 'glasser' trong hệ thống.",
        handle: Optional[str] = None,
    ):
        suggestion = "Chạy 'npm install -g @glasser-ai/cli' hoặc script install_binaries.sh."
        super().__init__(message=message, handle=handle, suggestion=suggestion)


class GlasserExecutionError(GlasserError):
    """Raised when glasser run returns a non-zero exit code or invalid response."""
    pass


# -- Health & Auth Checks ---------------------------------------------------

def ensure_glasser_env() -> Optional[str]:
    """Ensure GLASSER_API_KEY is available in os.environ by reading known .env files."""
    key = os.environ.get("GLASSER_API_KEY", "").strip()
    if key:
        return key

    repo_root = CURRENT_DIR.resolve().parents[2]
    candidate_files = [
        repo_root / "local" / "deployment-service" / ".env",
        repo_root / "tools" / "app" / "backend" / ".env",
        repo_root / ".env",
        Path(".env"),
    ]
    for env_path in candidate_files:
        if env_path.exists():
            try:
                for line in env_path.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line.startswith("GLASSER_API_KEY=") or line.startswith("export GLASSER_API_KEY="):
                        val = line.split("=", 1)[1].strip().strip('"\'')
                        if val:
                            os.environ["GLASSER_API_KEY"] = val
                            return val
            except Exception:
                pass
    return None


def check_glasser_key() -> Tuple[bool, Optional[str]]:
    """Check if GLASSER_API_KEY is set in environment or configured in Glasser CLI."""
    key = ensure_glasser_env() or os.environ.get("GLASSER_API_KEY", "").strip()
    if key:
        if len(key) < 10:
            return False, "GLASSER_API_KEY quá ngắn hoặc không hợp lệ."
        return True, None

    # Fallback: check if Glasser CLI has a locally stored key (glasser keys list)
    glasser_bin = shutil.which("glasser")
    if glasser_bin:
        try:
            res = subprocess.run([glasser_bin, "keys", "list"], capture_output=True, text=True, timeout=3.0)
            if res.returncode == 0 and "*" in res.stdout:
                return True, None
        except Exception:
            pass

    return False, "Thiếu biến môi trường GLASSER_API_KEY hoặc chưa cấu hình Glasser CLI."


def check_glasser_status() -> Dict[str, Any]:
    """Comprehensive status check for Glasser CLI and credentials."""
    glasser_bin = shutil.which("glasser")
    has_key, key_err = check_glasser_key()

    installed = glasser_bin is not None
    ok = installed and has_key
    error = None
    if not installed:
        error = "Chưa cài đặt CLI glasser (@glasser-ai/cli)."
    elif not has_key:
        error = key_err

    return {
        "ok": ok,
        "installed": installed,
        "has_key": has_key,
        "bin_path": glasser_bin,
        "error": error,
    }


# -- Execution --------------------------------------------------------------

def execute_glasser_query(
    profile_url: str,
    provider: str,
    endpoint: str,
    endpoint_version: int,
    idempotency_key: str,
    temp_out: Path,
    handle: str = "unknown",
    timeout: float = 45.0,
    payload: Optional[Dict[str, Any]] = None,
) -> Tuple[bool, Optional[str], Optional[GlasserError]]:
    """Execute glasser run command and classify any failure."""
    from tools.app.backend import cost_control

    has_key, _ = check_glasser_key()

    try:
        res = cost_control.run_glasser_tracked(
            provider=provider,
            endpoint=endpoint,
            version=endpoint_version,
            payload=payload if payload is not None else {"url": profile_url},
            idempotency_key=idempotency_key,
            out_file=temp_out,
            timeout=timeout,
            sub_action="profile_scrape",
        )
        if res.get("not_found"):
            err = GlasserNotFoundError(handle=handle)
            return False, err.message, err
        if res["ok"] and temp_out.exists() and temp_out.stat().st_size > 0:
            return True, None, None

        # Analyze failure or 404 output across both stdout and stderr
        stdout_text = res["stdout"].strip()
        stderr_text = res["stderr"].strip()
        output_text = f"{stdout_text}\n{stderr_text}".strip()

        # Handle Facebook 404 / no reels tab (COMPLETED run with HTTP 404 or empty output)
        is_not_found = res["returncode"] == 0 and (
            "HTTP 404" in output_text
            or '"errorStatus": 404' in output_text
            or '"error": "not_found"' in output_text
            or "doesn't exist or is private" in output_text
            or "don't have a reels tab" in output_text
            or "NO_RESULT" in output_text
            or "Response: HTTP 404" in output_text
            or '"http_status": 404' in output_text
            or (
                "only a COMPLETED Run with output is saved" in output_text
                and ("Status:   COMPLETED" in output_text or '"status": "COMPLETED"' in output_text)
            )
        )
        if is_not_found:
            try:
                temp_out.write_text(json.dumps({"reels": [], "status": "not_found", "handle": handle}), encoding="utf-8")
                return True, None, None
            except Exception:
                pass

        # Parse specific failure cause, skipping banners and updater notices
        ignored_prefixes = (
            "Idempotency-Key:",
            "Update available:",
            "upgrade:",
            "skill:",
            "Run ID:",
            "Run URL:",
        )
        err_lines = [
            line.strip() for line in output_text.splitlines()
            if line.strip() and not any(line.strip().startswith(p) for p in ignored_prefixes)
        ]
        err_first_line = err_lines[0] if err_lines else "Lỗi không xác định"

        if res["returncode"] == 2 or ("No Key configured" in output_text) or (not has_key and "key" in output_text.lower()):
            err = GlasserMissingKeyError(
                message=f"Glasser thiếu API Key: {err_first_line}",
                handle=handle,
                returncode=res["returncode"],
                raw_output=output_text,
                suggestion="Thêm 'GLASSER_API_KEY=gl_...' vào file local/deployment-service/.env rồi khởi động lại backend.",
            )
        else:
            err = GlasserExecutionError(
                message=f"Glasser query thất bại (code {res['returncode']}): {err_first_line}",
                handle=handle,
                returncode=res["returncode"],
                raw_output=output_text,
            )
        return False, err.message, err
    except cost_control.CostPolicyError as exc:
        err = GlasserExecutionError(message=str(exc), handle=handle)
        return False, err.message, err
    except subprocess.TimeoutExpired:
        err = GlasserExecutionError(
            message=f"Glasser query bị timeout sau {timeout:.0f}s",
            handle=handle,
            suggestion="Kiểm tra kết nối internet hoặc thử lại sau.",
        )
        return False, err.message, err
    except Exception as exc:
        err = GlasserExecutionError(
            message=f"Lỗi khi thực thi Glasser: {exc}",
            handle=handle,
        )
        return False, err.message, err


from tools.loop.viral_analyzer.cache import (
    read_cached_reels,
    write_cached_reels,
)

# -- Fetching with Cache & Error Tracking ------------------------------------

def _safe_int(val: Any) -> int:
    if isinstance(val, (int, float)):
        return int(val)
    if isinstance(val, str):
        digits = re.sub(r"[^\d]", "", val)
        return int(digits) if digits else 0
    return 0


def _first_int(*vals: Any) -> Optional[int]:
    for val in vals:
        if val is not None:
            return _safe_int(val)
    return None


def _resolve_profile_query(
    target: Dict[str, Any],
    config: Any,
) -> Tuple[str, str, str, str, str, int, Dict[str, Any]]:
    from tools.app.backend.profiles import detect_platform, social_handle

    raw_url = str(target.get("url") or "").strip()
    platform = str(target.get("platform") or (detect_platform(raw_url) if raw_url else "") or "facebook").strip().lower()
    if platform not in {"facebook", "youtube", "tiktok", "instagram"}:
        platform = "facebook"

    handle = str(target.get("handle") or "").strip()
    canonical_url = raw_url
    if not handle or handle == "unknown":
        if raw_url:
            try:
                h, canonical = social_handle(raw_url)
                handle = h or "unknown"
                canonical_url = canonical or raw_url
            except Exception:
                handle = "unknown"
        else:
            handle = "unknown"

    profile_url = canonical_url or raw_url
    clean_h = handle.lstrip("@")
    if not profile_url:
        if platform == "youtube":
            profile_url = f"https://www.youtube.com/@{clean_h}"
        elif platform == "tiktok":
            profile_url = f"https://www.tiktok.com/@{clean_h}"
        elif platform == "instagram":
            profile_url = f"https://www.instagram.com/{clean_h}/"
        else:
            profile_url = f"https://www.facebook.com/{handle}"

    if platform == "youtube":
        is_shorts = "/shorts" in profile_url.lower()
        endpoint = "/v1/youtube/channel/shorts" if is_shorts else "/v1/youtube/channel-videos"
        payload: Dict[str, Any] = {
            "handle": clean_h,
            "sort": "newest" if is_shorts else "latest",
        }
        if "/channel/" in profile_url or (clean_h.startswith("UC") and len(clean_h) >= 20):
            payload["channelId"] = clean_h
        return platform, handle, profile_url, "scrapecreators", endpoint, 4, payload

    if platform == "tiktok":
        return (
            platform,
            handle,
            profile_url,
            "scrapecreators",
            "/v3/tiktok/profile/videos",
            4,
            {"handle": clean_h, "sort_by": "latest"},
        )

    if platform == "instagram":
        return (
            platform,
            handle,
            profile_url,
            "scrapecreators",
            "/v1/instagram/user/reels",
            4,
            {"handle": clean_h},
        )

    return (
        platform,
        handle,
        profile_url,
        getattr(config, "glasser_provider", "scrapecreators"),
        getattr(config, "glasser_endpoint", "/v1/facebook/profile/reels"),
        getattr(config, "glasser_endpoint_version", 2),
        {"url": profile_url},
    )


def _normalize_profile_reels(data: Any, platform: str, handle: str) -> List[Dict[str, Any]]:
    if not isinstance(data, dict):
        return []

    if platform == "facebook":
        reels = data.get("reels", [])
        return reels if isinstance(reels, list) else []

    out: List[Dict[str, Any]] = []
    if platform == "youtube":
        items = data.get("videos") or data.get("shorts") or data.get("reels") or []
        if not isinstance(items, list):
            return []
        for v in items:
            if not isinstance(v, dict):
                continue
            vid = str(v.get("id") or v.get("videoId") or v.get("video_id") or "")
            url = str(v.get("url") or v.get("link") or (f"https://www.youtube.com/watch?v={vid}" if vid else ""))
            if not url and not vid:
                continue
            views = _first_int(v.get("viewCountInt"), v.get("views"), v.get("viewCount"), v.get("view_count")) or 0
            likes = _first_int(v.get("likeCountInt"), v.get("likes"), v.get("likeCount"))
            comments = _first_int(v.get("commentCountInt"), v.get("comments"), v.get("commentCount"))
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

    if platform == "tiktok":
        items = data.get("aweme_list") or data.get("videos") or data.get("reels") or data.get("data") or []
        if not isinstance(items, list):
            return []
        for raw in items:
            if not isinstance(raw, dict):
                continue
            v = raw.get("aweme_info") if isinstance(raw.get("aweme_info"), dict) else raw
            vid = str(v.get("aweme_id") or v.get("id") or v.get("video_id") or "")
            author = v.get("author") if isinstance(v.get("author"), dict) else {}
            author_h = str(author.get("unique_id") or v.get("author_handle") or handle).lstrip("@")
            url = str(
                v.get("url")
                or (f"https://www.tiktok.com/@{author_h}/video/{vid}" if author_h and vid else "")
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
            views = _first_int(stats.get("play_count"), v.get("views"), v.get("play_count"), v.get("view_count")) or 0
            likes = _first_int(stats.get("digg_count"), v.get("likes"), v.get("digg_count"))
            comments = _first_int(stats.get("comment_count"), v.get("comments"), v.get("comment_count"))
            shares = _first_int(stats.get("share_count"), v.get("shares"), v.get("share_count"))
            item = {
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

    if platform == "instagram":
        items = data.get("items") or data.get("reels") or data.get("data") or []
        if not isinstance(items, list):
            return []
        for raw in items:
            if not isinstance(raw, dict):
                continue
            v = raw.get("media") if isinstance(raw.get("media"), dict) else raw
            code = str(v.get("code") or v.get("shortcode") or "")
            vid = str(v.get("pk") or v.get("id") or v.get("video_id") or code)
            url = str(v.get("url") or (f"https://www.instagram.com/reel/{code}/" if code else ""))
            if not url and not vid:
                continue
            versions = v.get("video_versions") if isinstance(v.get("video_versions"), list) else []
            first_ver = versions[0] if versions and isinstance(versions[0], dict) else {}
            video_url = v.get("video_url") or first_ver.get("url")
            views = _first_int(
                v.get("play_count"),
                v.get("ig_play_count"),
                v.get("view_count"),
                v.get("views"),
            ) or 0
            likes = _first_int(v.get("like_count"), v.get("likes"))
            comments = _first_int(v.get("comment_count"), v.get("comments"))
            cap = v.get("caption")
            desc = str(
                cap.get("text") if isinstance(cap, dict) else (cap or v.get("description") or v.get("title") or f"Reel by @{handle}")
            )
            item = {
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

    return []


def fetch_target_reels(
    target: Dict[str, Any],
    config: Any,
    cache_dir: Optional[Path] = None,
    legacy_cache: bool = True,
    progress_cb: Optional[Callable[[str], None]] = None,
    error_collector: Optional[List[GlasserError]] = None,
) -> List[Dict[str, Any]]:
    """Fetch profile reels/videos via Glasser ScrapeCreators or centralized cache.

    Appends encountered GlasserErrors to error_collector if provided.
    """
    platform, handle, profile_url, provider, endpoint, endpoint_version, query_payload = _resolve_profile_query(
        target, config
    )
    cache_key = handle if platform == "facebook" else f"{platform}:{handle}"
    slug = cache_key.replace(":", "_").replace(".", "_")

    # 1. Check centralized cache (with legacy JSON auto-import)
    cached = read_cached_reels(
        cache_key,
        cache_dir=cache_dir,
        legacy_cache=legacy_cache,
        allow_expired=False,
    )
    if cached is None and cache_key != handle:
        cached = read_cached_reels(
            handle,
            cache_dir=cache_dir,
            legacy_cache=legacy_cache,
            allow_expired=False,
        )
    if cached is not None:
        from tools.app.backend import cost_control

        reels, _status, src_label = cached
        cost_control.record_cost_event(
            provider=provider,
            endpoint=endpoint,
            cost_micro=0,
            cache_hit=True,
            sub_action="profile_cache",
        )
        msg = f"    [cache] Dùng cache ({len(reels)} reel) cho {handle} ({src_label})."
        print(msg)
        if progress_cb:
            progress_cb(f"[cache] Dùng cache ({len(reels)} reel) cho {handle} ({src_label})")
        return reels

    # 2. Glasser CLI Fetch
    msg = f"    [api] Gọi Glasser ({platform}) cho {handle}..."
    print(msg)
    if progress_cb:
        progress_cb(f"[api] Gọi Glasser ({platform}) cho {handle}...")

    temp_out = Path(tempfile.gettempdir()) / f"glasser_{slug}.json"
    idempotency_key = f"viral-loop-{slug}-{int(time.time() // 86400)}"

    ok, err_msg, glasser_err = execute_glasser_query(
        profile_url=profile_url,
        provider=provider,
        endpoint=endpoint,
        endpoint_version=endpoint_version,
        idempotency_key=idempotency_key,
        temp_out=temp_out,
        handle=handle,
        timeout=45.0,
        payload=query_payload,
    )

    if ok and temp_out.exists():
        try:
            with open(temp_out, "r", encoding="utf-8") as f:
                data = json.load(f)
                reels = _normalize_profile_reels(data, platform, handle)
                status = data.get("status", "ok") if isinstance(data, dict) else "ok"
                write_cached_reels(
                    handle=cache_key,
                    reels=reels,
                    status=status,
                    profile_url=profile_url,
                )
                for r in reels:
                    if isinstance(r, dict):
                        r["_source"] = "glasser"
                if status == "not_found":
                    status_msg = f"    [api] Kênh {handle} không tồn tại hoặc không có reels (not_found)."
                    print(status_msg)
                    if progress_cb:
                        progress_cb(f"[api] Kênh {handle} không tồn tại hoặc không có reels (not_found)")
                else:
                    success_msg = f"    [api] Glasser thành công ({len(reels)} reel) cho {handle}."
                    print(success_msg)
                    if progress_cb:
                        progress_cb(f"[api] Glasser thành công ({len(reels)} reel mới từ API) cho {handle}")
                return reels
        except Exception as read_err:
            glasser_err = GlasserExecutionError(
                message=f"Không đọc được file kết quả JSON từ Glasser: {read_err}",
                handle=handle,
            )
        finally:
            if temp_out.exists():
                try:
                    os.remove(temp_out)
                except Exception:
                    pass

    # Record error if Glasser query failed
    if glasser_err:
        if error_collector is not None:
            error_collector.append(glasser_err)
        log_msg = f"    [!] Glasser lỗi cho {handle}: {glasser_err.message}"
        print(log_msg)
        if progress_cb:
            progress_cb(log_msg)

    # 3. Fallback to expired cache if Glasser query failed or was unavailable
    expired = read_cached_reels(
        cache_key,
        cache_dir=cache_dir,
        legacy_cache=legacy_cache,
        allow_expired=True,
    )
    if expired is None and cache_key != handle:
        expired = read_cached_reels(
            handle,
            cache_dir=cache_dir,
            legacy_cache=legacy_cache,
            allow_expired=True,
        )
    if expired is not None:
        reels, _status, _src_label = expired
        if reels:
            fallback_msg = f"    [!] Glasser lỗi; dùng lại cache cũ ({len(reels)} reel) cho {handle}."
            print(fallback_msg)
            if progress_cb:
                progress_cb(f"[cache-fallback] {handle}: Glasser lỗi, dùng lại cache cũ ({len(reels)} reel)")
            return reels

    return []


# -- Transcript Fetching & Caching (delegated to transcriber.glasser) --------

from tools.loop.viral_analyzer.transcriber.glasser import (
    GlasserTranscriber,
    fetch_reel_transcript,
    fetch_top_reels_transcripts,
    transcribe_reels_glasser,
)


