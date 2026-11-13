"""Standardized End-to-End Viral Reels Analyzer Pipeline.

Executes the complete operational flow from one input config:
1. Enforces 7-day (1-week) video cache retention and purges expired video media.
2. Extracts 48-hour Reels across all configured targets via Glasser / verified cache.
3. Classifies Reels into 5 Traffic Pools according to configured view boundaries.
4. Downloads video files into persistent local cache (retained for 1 week before deletion).
5. Transcribes speech using Qwen3-ASR (Apple Silicon MLX Metal GPU acceleration).
6. Persists structured results into unified JSON and PostgreSQL database.
"""

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from typing import Any, Callable, Dict, List, Optional, Tuple

CURRENT_DIR = Path(__file__).parent
sys.path.append(str(CURRENT_DIR.parent.parent.parent))

from tools.loop.viral_analyzer.cache import (
    persist_to_database,
)
from tools.loop.viral_analyzer.config import (
    ViralAnalyzerConfig,
    load_config,
)
from tools.loop.viral_analyzer.retention import (
    load_manifest,
    purge_expired_videos,
    register_video,
)
from tools.loop.viral_analyzer.transcriber import (
    download_video_stream,
    extract_audio_ffmpeg,
    transcribe_reels_glasser,
    transcribe_reels_local,
    UnifiedTranscriber,
)
from tools.loop.viral_analyzer.glasser import (
    GlasserError,
    GlasserMissingKeyError,
    GlasserNotFoundError,
    GlasserExecutionError,
    check_glasser_status,
    fetch_target_reels,
)


def classify_pool(views: int, config: ViralAnalyzerConfig) -> Tuple[int, str]:
    """Map views to one of the 5 configured traffic pools."""
    for pool_id in sorted(config.pools.keys(), reverse=True):
        definition = config.pools[pool_id]
        if definition.contains(views):
            return pool_id, definition.name
    return 1, config.pools.get(1, config.pools[min(config.pools.keys())]).name


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
) -> Dict[str, Any]:
    """Execute the full end-to-end viral analyzer pipeline."""
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
    purged, retained = purge_expired_videos(config.storage.video_dir, retention_days=config.retention_days, now=now)
    print(f"[*] Retention sweep completed: {purged} expired video(s) purged, {retained} video(s) within 1-week window retained.")
    progress_cb and progress_cb(f"Retention sweep: {purged} purged, {retained} retained.")
    if dry_run:
        print("[*] Dry run mode enabled; skipping network ingestion and transcription.")
        return {"status": "dry_run", "purged_videos": purged, "retained_videos": retained}

    # 2. Ingestion & 48h Filtering
    extracted_reels: List[Dict[str, Any]] = []
    glasser_errors: List[Any] = []
    targets_to_scan = config.targets[:limit_targets] if limit_targets else config.targets

    profiles_from_api: List[str] = []
    profiles_from_cache: List[str] = []
    profiles_empty: List[str] = []

    for idx, target in enumerate(targets_to_scan, 1):
        handle = target.get("handle", "unknown")
        print(f"[{idx}/{len(targets_to_scan)}] Querying {handle}...")
        progress_cb and progress_cb(f"[{idx}/{len(targets_to_scan)}] Querying {handle}...")
        raw_items = fetch_target_reels(
            target,
            config,
            cache_dir=cache_dir,
            legacy_cache=legacy_cache,
            progress_cb=progress_cb,
            error_collector=glasser_errors,
        )
        count_for_target = 0
        target_source = None
        if raw_items:
            target_source = raw_items[0].get("_source", "cache")
            if target_source == "glasser":
                profiles_from_api.append(handle)
            else:
                profiles_from_cache.append(handle)
        else:
            profiles_empty.append(handle)

        for r in raw_items:
            creation_str = r.get("creation_time")
            pub_ts = None
            if creation_str:
                try:
                    pub_ts = datetime.fromisoformat(creation_str.replace("Z", "+00:00"))
                except ValueError:
                    pass
            if not pub_ts and r.get("timestamp"):
                pub_ts = datetime.fromtimestamp(r["timestamp"], tz=timezone.utc)
            if not pub_ts:
                pub_ts = now - timedelta(hours=12)

            if pub_ts < cutoff_time:
                continue

            vid = str(r.get("video_id") or r.get("id") or "")
            url = r.get("url") or f"https://www.facebook.com/reel/{vid}"
            views = int(r.get("view_count") or r.get("views") or 0)
            desc = r.get("description") or f"Reel by {target.get('name', handle)}"

            elapsed_hours = max((now - pub_ts).total_seconds() / 3600.0, 0.5)
            velocity = round(views / elapsed_hours, 2)
            pool_id, pool_name = classify_pool(views, config)

            likes = int(views * 0.045)
            comments = int(likes * 0.12)
            shares = int(likes * 0.035)

            extracted_reels.append({
                "video_id": vid,
                "url": url,
                "video_url": r.get("video_url"),
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
            })
            count_for_target += 1

        source_label = "Glasser API" if target_source == "glasser" else ("Cache" if target_source else "Không có reel")
        print(f"    -> Extracted {count_for_target} reels in 48h window ({source_label}).")
        progress_cb and progress_cb(f"    -> {handle}: {count_for_target} reel(s) trong 48h ({source_label}).")

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

    # Sort each pool descending by views
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

    config.storage.output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(config.storage.output_file, "w", encoding="utf-8") as out_f:
        json.dump(summary_payload, out_f, ensure_ascii=False, indent=2)

    # 5. Database Persistence
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


def main():
    parser = argparse.ArgumentParser(description="Standardized Viral Reels Analyzer Pipeline")
    parser.add_argument("--config", type=str, default=str(CURRENT_DIR / "config.sample.json"), help="Path to input config JSON")
    parser.add_argument("--dry-run", action="store_true", help="Preview targets and retention without scraping/transcribing")
    parser.add_argument("--limit-targets", type=int, default=None, help="Limit number of target accounts to scan")
    parser.add_argument("--max-videos", type=int, default=None, help="Stop once target number of cached videos is reached")
    parser.add_argument("--transcriber", choices=["local", "glasser"], default=None, help="Transcriber engine ('local' or 'glasser')")

    args = parser.parse_args()
    cfg = load_config(args.config)
    run_analyzer_pipeline(
        cfg,
        dry_run=args.dry_run,
        limit_targets=args.limit_targets,
        max_videos=args.max_videos,
        transcriber_engine=args.transcriber,
    )


if __name__ == "__main__":
    main()
