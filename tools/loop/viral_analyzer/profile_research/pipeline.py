"""Standardized Profile Viral Reels Analyzer Pipeline & Runner."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json
import logging
from pathlib import Path
import re
import sys
from typing import Any, Callable, Dict, List, Optional, Tuple

CURRENT_DIR = Path(__file__).parent
sys.path.append(str(CURRENT_DIR.resolve().parents[3]))

from tools.app.backend.errors import (
    ErrorAggregator,
    ErrorCategory,
    ErrorSeverity,
    handle_glasser_error,
)
from tools.loop.viral_analyzer import platforms, profiling, runtime
from tools.loop.viral_analyzer.cache import (
    persist_to_database,
)
from tools.loop.viral_analyzer.glasser import (
    GlasserError,
    GlasserExecutionError,
    GlasserMissingKeyError,
    GlasserNotFoundError,
    check_glasser_status,
    ensure_glasser_env,
)
from tools.loop.viral_analyzer.profile_research.collect import (
    fetch_target_reels,
)
from tools.loop.viral_analyzer.profile_research.config import (
    ViralAnalyzerConfig,
    load_config,
)
from tools.loop.viral_analyzer.video_research.collect import (
    download_video_stream,
    load_manifest,
    purge_expired_videos,
    register_video,
)
from tools.loop.viral_analyzer.video_research.transcriber import (
    UnifiedTranscriber,
    extract_audio_ffmpeg,
    transcribe_reels_glasser,
    transcribe_reels_local,
)

logger = logging.getLogger("profile_research")
ensure_glasser_env()


def classify_pool(views: int, config: ViralAnalyzerConfig) -> Tuple[int, str]:
    """Map views to one of the 5 configured traffic pools."""
    for pool_id in sorted(config.pools.keys(), reverse=True):
        definition = config.pools[pool_id]
        if definition.contains(views):
            return pool_id, definition.name
    return 1, config.pools.get(1, config.pools[min(config.pools.keys())]).name


def _parse_reel_pub_ts(r: Dict[str, Any], now: datetime) -> datetime:
    creation_str = r.get("creation_time")
    pub_ts = None
    if creation_str:
        raw_str = str(creation_str).strip()
        try:
            pub_ts = datetime.fromisoformat(raw_str.replace("Z", "+00:00"))
            if pub_ts.tzinfo is None:
                pub_ts = pub_ts.replace(tzinfo=timezone.utc)
        except ValueError:
            m = re.search(
                r"(\d+)\s+(second|minute|hour|day|week|month|year)s?\s+ago",
                raw_str,
                re.IGNORECASE,
            )
            if m:
                qty = int(m.group(1))
                unit = m.group(2).lower()
                mult_hours = {
                    "second": 1 / 3600.0,
                    "minute": 1 / 60.0,
                    "hour": 1.0,
                    "day": 24.0,
                    "week": 24.0 * 7,
                    "month": 24.0 * 30,
                    "year": 24.0 * 365,
                }[unit]
                pub_ts = now - timedelta(hours=qty * mult_hours)
    if not pub_ts and r.get("timestamp"):
        try:
            pub_ts = datetime.fromtimestamp(float(r["timestamp"]), tz=timezone.utc)
        except (TypeError, ValueError, OSError):
            pass
    return pub_ts or (now - timedelta(hours=12))


def _build_extracted_reel(
    r: Dict[str, Any],
    target: Dict[str, Any],
    target_platform: str,
    target_source: Optional[str],
    pub_ts: datetime,
    now: datetime,
    config: ViralAnalyzerConfig,
) -> Dict[str, Any]:
    handle = target.get("handle", "unknown")
    platform = str(r.get("platform") or target_platform or "facebook").strip().lower()
    if platforms.get_platform(platform) is None or platform == "google":
        platform = "facebook"
    vid = str(r.get("video_id") or r.get("id") or "")
    url = str(r.get("url") or "").strip()
    if not url and vid:
        url = platforms.fallback_video_url(platform, vid, author_handle=handle)

    views = int(r.get("view_count") or r.get("views") or 0)
    desc = str(r.get("description") or r.get("title") or f"Reel by {target.get('name', handle)}")

    elapsed_hours = max((now - pub_ts).total_seconds() / 3600.0, 0.5)
    velocity = round(views / elapsed_hours, 2)
    pool_id, pool_name = classify_pool(views, config)

    likes = int(r["likes"]) if r.get("likes") is not None else int(views * 0.045)
    comments = int(r["comments"]) if r.get("comments") is not None else int(likes * 0.12)
    shares = int(r["shares"]) if r.get("shares") is not None else int(likes * 0.035)

    return {
        "video_id": vid,
        "url": url,
        "reel_url": url,
        "video_url": r.get("video_url"),
        "platform": platform,
        "author_handle": handle,
        "author_name": target.get("name", handle),
        "category": target.get("category", "general"),
        "title": desc[:120].strip(),
        "views": views,
        "likes": likes,
        "comments": comments,
        "shares": shares,
        "published_at": pub_ts.isoformat(),
        "elapsed_hours": round(elapsed_hours, 1),
        "current_pool": pool_id,
        "pool_name": pool_name,
        "velocity_per_hour": velocity,
        "comment_ratio": round(comments / max(likes, 1), 3),
        "source": r.get("_source", target_source or "cache"),
    }


def run_analyzer_pipeline(
    config: ViralAnalyzerConfig,
    dry_run: bool = False,
    limit_targets: Optional[int] = None,
    max_videos: Optional[int] = None,
    cache_dir: Optional[Path] = None,
    transcribe: bool = True,
    legacy_cache: bool = True,
    progress_cb: Optional[Callable[[str], None]] = None,
    transcriber_engine: Optional[str] = None,
    max_workers: Optional[int] = None,
    ctx: Optional[runtime.EngineContext] = None,
) -> Dict[str, Any]:
    """Execute the full end-to-end viral analyzer pipeline."""
    eng_ctx = ctx or runtime.default_context()
    eff_workers = max(1, max_workers if max_workers is not None else eng_ctx.max_workers)
    resolved_transcriber = (transcriber_engine or config.transcription.engine or "local").strip().lower()

    now = datetime.now(timezone.utc)
    cutoff_time = now - timedelta(hours=config.window_hours)
    effective_max = max_videos or config.max_videos

    print("=" * 80)
    print(" VIRAL REELS ANALYZER: STANDARDIZED OPERATION PIPELINE")
    print("=" * 80)
    print(f"Time Window     : Last {config.window_hours} Hours ({cutoff_time.isoformat()} to {now.isoformat()})")
    print(f"Video Retention : {config.retention_days} Days (1 Week) in {config.storage.video_dir}")
    pool_desc = ", ".join([f"P{k}:{v.min_views}-{v.max_views or '+'}" for k, v in config.pools.items()])
    print(f"Pool Thresholds : {pool_desc}")
    print(f"AI Transcriber  : {resolved_transcriber} ({config.transcription.model})")
    print(f"Target Accounts : {len(config.targets)} accounts")
    print("=" * 80)

    # 1. Retention Management Sweep
    config.storage.video_dir.mkdir(parents=True, exist_ok=True)
    with profiling.span("profile", "retention_sweep"):
        purged, retained = purge_expired_videos(config.storage.video_dir, retention_days=config.retention_days, now=now)
    print(f"[*] Retention sweep completed: {purged} expired video(s) purged, {retained} video(s) within 1-week window retained.")
    progress_cb and progress_cb(f"Retention sweep: {purged} purged, {retained} retained.")
    if dry_run:
        print("[*] Dry run mode enabled; skipping network ingestion and transcription.")
        return {"status": "dry_run", "purged_videos": purged, "retained_videos": retained}

    # 2. Bounded Parallel Ingestion & 48h Filtering
    targets_to_scan = config.targets[:limit_targets] if limit_targets else config.targets
    total_targets = len(targets_to_scan)

    def _crawl_target(idx: int, target: Dict[str, Any]) -> Tuple[str, Optional[str], List[Dict[str, Any]], List[GlasserError]]:
        handle = target.get("handle", "unknown")
        print(f"[{idx}/{total_targets}] Querying {handle}...")
        progress_cb and progress_cb(f"[{idx}/{total_targets}] Querying {handle}...")
        local_errors: List[GlasserError] = []
        raw_items = fetch_target_reels(
            target,
            config,
            cache_dir=cache_dir,
            legacy_cache=legacy_cache,
            progress_cb=progress_cb,
            error_collector=local_errors,
            ctx=eng_ctx,
        )
        target_source = raw_items[0].get("_source", "cache") if raw_items else None
        raw_plat = str(target.get("platform") or platforms.detect_platform(target.get("url") or "")).strip().lower()
        target_platform = raw_plat if (platforms.get_platform(raw_plat) is not None and raw_plat != "google") else "facebook"

        target_reels: List[Dict[str, Any]] = []
        for r in raw_items:
            pub_ts = _parse_reel_pub_ts(r, now)
            if pub_ts < cutoff_time:
                continue
            target_reels.append(
                _build_extracted_reel(r, target, target_platform, target_source, pub_ts, now, config)
            )

        source_label = "Glasser API" if target_source == "glasser" else ("Cache" if target_source else "Không có reel")
        print(f"    -> Extracted {len(target_reels)} reels in 48h window ({source_label}).")
        progress_cb and progress_cb(f"    -> {handle}: {len(target_reels)} reel(s) trong 48h ({source_label}).")
        return handle, target_source, target_reels, local_errors

    with profiling.span("profile", "crawl_targets"):
        if total_targets > 1 and eff_workers > 1:
            with ThreadPoolExecutor(max_workers=min(eff_workers, total_targets)) as pool:
                futures = [
                    eng_ctx.submit_fn(pool, _crawl_target, idx, target)
                    for idx, target in enumerate(targets_to_scan, 1)
                ]
                crawled = [fut.result() for fut in futures]
        else:
            crawled = [_crawl_target(idx, target) for idx, target in enumerate(targets_to_scan, 1)]

    extracted_reels: List[Dict[str, Any]] = []
    glasser_errors: List[Any] = []
    profiles_from_api: List[str] = []
    profiles_from_cache: List[str] = []
    profiles_empty: List[str] = []

    for handle, target_source, target_reels, local_errors in crawled:
        glasser_errors.extend(local_errors)
        if target_source == "glasser":
            profiles_from_api.append(handle)
        elif target_source is not None:
            profiles_from_cache.append(handle)
        else:
            profiles_empty.append(handle)
        extracted_reels.extend(target_reels)

    print(f"\n[+] Total 48h viral candidates harvested: {len(extracted_reels)}")
    progress_cb and progress_cb(f"[+] Tổng cộng {len(extracted_reels)} reel ứng viên trong 48h.")

    source_summary = (
        f"Thống kê nguồn cào: "
        f"Glasser API ({len(profiles_from_api)} kênh: {', '.join(profiles_from_api) or '0'}) | "
        f"Cache ({len(profiles_from_cache)} kênh: {', '.join(profiles_from_cache) or '0'})"
    )
    if profiles_empty:
        source_summary += f" | Không có reel ({len(profiles_empty)} kênh: {', '.join(profiles_empty)})"
    print(f"[*] {source_summary}")
    progress_cb and progress_cb(f"[*] {source_summary}")

    # 3. Transcription ("local" vs "glasser")
    with profiling.span("profile", "transcribe"):
        if transcribe or transcriber_engine is not None:
            if resolved_transcriber == "local":
                transcribe_reels_local(
                    extracted_reels,
                    config=config,
                    effective_max=effective_max,
                    now=now,
                    progress_cb=progress_cb,
                )
            elif resolved_transcriber == "glasser":
                transcribe_reels_glasser(
                    extracted_reels,
                    progress_cb=progress_cb,
                )
            else:
                raise ValueError(
                    f"Unsupported transcriber_engine: {resolved_transcriber!r}. Expected 'local' or 'glasser'."
                )

    # 4. Group by Pool & Save Outputs
    by_pools: Dict[str, List[Dict[str, Any]]] = {
        f"pool_{pid}": [] for pid in sorted(config.pools.keys())
    }
    for reel in extracted_reels:
        key = f"pool_{reel['current_pool']}"
        by_pools[key].append(reel)

    for k in by_pools:
        by_pools[k].sort(key=lambda x: x["views"], reverse=True)

    summary_payload = {
        "metadata": {
            "generated_at": now.isoformat(),
            "window_hours": config.window_hours,
            "retention_days": config.retention_days,
            "total_extracted": len(extracted_reels),
            "pool_distribution": {k: len(v) for k, v in by_pools.items()},
            "video_cache_dir": str(config.storage.video_dir),
            "retained_cached_videos": len(list(config.storage.video_dir.glob("*.mp4"))),
            "errors": [e.to_dict() if hasattr(e, "to_dict") else str(e) for e in glasser_errors],
            "source_breakdown": {
                "glasser_api": profiles_from_api,
                "cache": profiles_from_cache,
                "empty": profiles_empty,
            },
        },
        "errors": [e.to_dict() if hasattr(e, "to_dict") else str(e) for e in glasser_errors],
        "source_breakdown": {
            "glasser_api": profiles_from_api,
            "cache": profiles_from_cache,
            "empty": profiles_empty,
        },
        "pools": by_pools,
        "all_reels": extracted_reels,
    }

    runtime.atomic_write_json(config.storage.output_file, summary_payload)

    # 5. Database Persistence
    with profiling.span("profile", "persist_db"):
        persist_to_database(extracted_reels)

    print("\n" + "=" * 80)
    print(" VIRAL ANALYZER EXECUTION COMPLETED")
    print("=" * 80)
    print(f"Total Extracted : {len(extracted_reels)} reels across 5 Pools")
    for pid in sorted(config.pools.keys()):
        print(f"  - Pool {pid} ({config.pools[pid].name}): {len(by_pools[f'pool_{pid}'])} reels")
    print(f"Data Sources    : Glasser API: {len(profiles_from_api)} kênh, Cache: {len(profiles_from_cache)} kênh")
    if profiles_empty:
        print(f"Empty Targets   : {len(profiles_empty)} kênh ({', '.join(profiles_empty)})")
    print(f"Saved Output    : {config.storage.output_file}")
    print(f"Cached Videos   : {len(list(config.storage.video_dir.glob('*.mp4')))} stored in {config.storage.video_dir} (1-week retention)")
    print("=" * 80)
    progress_cb and progress_cb(f"Hoàn tất: {len(extracted_reels)} reel, {len(list(config.storage.video_dir.glob('*.mp4')))} video trong cache.")

    return summary_payload


def run_profile_research(
    targets: List[Dict[str, Any]],
    run_dir: Path,
    options: Dict[str, Any],
    log: Optional[Callable[[str], None]] = None,
    job_id: str = "adhoc",
    sheet_slug: str = "sheet",
    pipeline_fn: Optional[Callable[..., Any]] = None,
    aggregator: Optional[ErrorAggregator] = None,
) -> Dict[str, Any]:
    """Execute profile research across a list of creator/channel targets."""
    _log = log or (lambda msg: logger.info(msg))
    sheet_dir = run_dir / "sheets" / sheet_slug
    sheet_dir.mkdir(parents=True, exist_ok=True)
    shared_cache = run_dir / "cache"
    shared_cache.mkdir(parents=True, exist_ok=True)

    aggregator = aggregator or ErrorAggregator(job_id=job_id)
    reels: List[Dict[str, Any]] = []
    error: Optional[str] = None
    notice: Optional[str] = None
    payload: Dict[str, Any] = {}

    if not targets:
        _log("Danh sách kênh trống; không có link profile/kênh để nghiên cứu.")
        return {
            "reels": [],
            "pool_distribution": {},
            "source_breakdown": {},
            "error": None,
            "notice": "Chưa có kênh đối thủ nào. Vui lòng cập nhật thêm danh sách kênh.",
            "errors": [],
        }

    window_hours = int(options.get("window_hours", 48))
    config = load_config(
        {
            "window_hours": window_hours,
            "retention_days": 7,
            "max_videos": options.get("max_videos"),
            "storage": {
                "video_dir": str(shared_cache / "videos"),
                "output_file": str(sheet_dir / "viral_reels_48h.json"),
            },
            "transcription": {"engine": "local", "model": "Qwen/Qwen3-ASR-0.6B", "language": None},
            "targets": targets,
        }
    )

    runner = pipeline_fn or run_analyzer_pipeline
    try:
        payload = runner(
            config,
            max_videos=options.get("max_videos"),
            cache_dir=shared_cache,
            transcribe=bool(options.get("transcribe")),
            legacy_cache=False,
            progress_cb=_log,
        )
        reels = payload.get("all_reels", [])
        for err_item in payload.get("errors", []):
            handle_name = err_item.get("handle") if isinstance(err_item, dict) else None
            app_err = handle_glasser_error(err_item, handle=handle_name, log=_log)
            aggregator.add(app_err)
    except Exception as exc:
        app_err = handle_glasser_error(exc, log=_log)
        aggregator.add(app_err)
        error = app_err.message

    pool_distribution = payload.get("metadata", {}).get("pool_distribution", {})
    source_breakdown = payload.get("source_breakdown") or payload.get("metadata", {}).get("source_breakdown", {})

    if not reels and not error:
        glasser_errs = aggregator.filter(category=ErrorCategory.GLASSER.value)
        if glasser_errs:
            critical = next(
                (e for e in glasser_errs if e.severity == ErrorSeverity.CRITICAL.value),
                glasser_errs[0],
            )
            notice = critical.format_notice()
            error = critical.message
            _log(f"[Cảnh báo API] {notice}")
        else:
            notice = f"Không tìm thấy reel mới nào trong {window_hours} giờ qua. Vui lòng cập nhật thêm danh sách kênh."
            _log(notice)

    return {
        "reels": reels,
        "pool_distribution": pool_distribution,
        "source_breakdown": source_breakdown,
        "error": error,
        "notice": notice,
        "errors": [e.to_dict() for e in aggregator.all_errors()],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Standardized Viral Reels Analyzer Pipeline")
    parser.add_argument("--config", type=str, default=None, help="Optional path to input config JSON; uses ViralAnalyzerConfig defaults when omitted")
    parser.add_argument("--target", action="append", default=[], help="Optional target profile URL (repeatable)")
    parser.add_argument("--dry-run", action="store_true", help="Preview targets and retention without scraping/transcribing")
    parser.add_argument("--limit-targets", type=int, default=None, help="Limit number of target accounts to scan")
    parser.add_argument("--max-videos", type=int, default=None, help="Stop once target number of cached videos is reached")
    parser.add_argument("--transcriber", choices=["local", "glasser"], default=None, help="Transcriber engine ('local' or 'glasser')")

    args = parser.parse_args()
    cfg = load_config(args.config) if args.config else ViralAnalyzerConfig()
    for raw_url in args.target:
        handle, canon_url = platforms.social_handle(raw_url)
        detected = platforms.detect_platform(canon_url or raw_url)
        cfg.targets.append({
            "handle": handle,
            "url": canon_url or raw_url,
            "platform": detected if detected != "web" else "facebook",
        })
    run_analyzer_pipeline(
        cfg,
        dry_run=args.dry_run,
        limit_targets=args.limit_targets,
        max_videos=args.max_videos,
        transcriber_engine=args.transcriber,
    )


if __name__ == "__main__":
    main()
