"""Profile-level reel/video acquisition and single-flight cache management."""

from __future__ import annotations

import json
from pathlib import Path
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from tools.loop.viral_analyzer import platforms, runtime
from tools.loop.viral_analyzer.cache import (
    read_cached_reels,
    write_cached_reels,
)
from tools.loop.viral_analyzer.glasser import (
    GlasserError,
    GlasserExecutionError,
    execute_glasser_query,
)


def _resolve_profile_query(
    target: Dict[str, Any],
    config: Any,
) -> Tuple[str, str, str, str, str, int, Dict[str, Any]]:
    raw_url = str(target.get("url") or "").strip()
    detected = platforms.detect_platform(raw_url) if raw_url else ""
    platform = str(target.get("platform") or detected or "facebook").strip().lower()
    spec = platforms.get_platform(platform)
    if spec is None or spec.profile_query_fn is None:
        platform = "facebook"
        spec = platforms.get_platform("facebook")

    handle = str(target.get("handle") or "").strip()
    canonical_url = raw_url
    if not handle or handle == "unknown":
        if raw_url:
            try:
                h, canonical = platforms.social_handle(raw_url)
                handle = h or "unknown"
                canonical_url = canonical or raw_url
            except Exception:
                handle = "unknown"
        else:
            handle = "unknown"

    profile_url = canonical_url or raw_url or platforms.default_profile_url(platform, handle)
    assert spec is not None and spec.profile_query_fn is not None
    provider, endpoint, endpoint_version, query_payload = spec.profile_query_fn(handle, profile_url, config)
    return platform, handle, profile_url, provider, endpoint, endpoint_version, query_payload


def _normalize_profile_reels(data: Any, platform: str, handle: str) -> List[Dict[str, Any]]:
    spec = platforms.get_platform(platform)
    if spec is not None and spec.normalize_profile_fn is not None:
        return spec.normalize_profile_fn(data, handle)
    return []


def fetch_target_reels(
    target: Dict[str, Any],
    config: Any,
    cache_dir: Optional[Path] = None,
    legacy_cache: bool = True,
    progress_cb: Optional[Callable[[str], None]] = None,
    error_collector: Optional[List[GlasserError]] = None,
    ctx: Optional[runtime.EngineContext] = None,
) -> List[Dict[str, Any]]:
    """Fetch profile reels/videos via single-flight Glasser ScrapeCreators or centralized cache."""
    eng_ctx = ctx or runtime.default_context()
    platform, handle, profile_url, provider, endpoint, endpoint_version, query_payload = _resolve_profile_query(
        target, config
    )
    cache_key = handle if platform == "facebook" else f"{platform}:{handle}"
    slug = cache_key.replace(":", "_").replace(".", "_")

    with eng_ctx.single_flight.acquire(f"profile:{cache_key}"):
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

        temp_out = runtime.unique_temp_path(f"glasser_{slug}", ".json")
        idempotency_key = f"viral-loop-{slug}-{int(time.time() // 86400)}"

        ok, _err_msg, glasser_err = execute_glasser_query(
            profile_url=profile_url,
            provider=provider,
            endpoint=endpoint,
            endpoint_version=endpoint_version,
            idempotency_key=idempotency_key,
            temp_out=temp_out,
            handle=handle,
            timeout=45.0,
            payload=query_payload,
            ctx=eng_ctx,
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
                        temp_out.unlink()
                    except OSError:
                        pass
        elif temp_out.exists():
            try:
                temp_out.unlink()
            except OSError:
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
