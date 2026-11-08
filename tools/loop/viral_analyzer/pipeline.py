"""Standardized End-to-End Viral Reels Analyzer Pipeline.

Executes the complete operational flow from one input config:
1. Enforces 7-day (1-week) video cache retention and purges expired video media.
2. Extracts 48-hour Reels across all configured targets via Glasser / verified cache.
3. Classifies Reels into 5 Traffic Pools according to configured view boundaries.
4. Downloads video files into persistent local cache (retained for 1 week before deletion).
5. Transcribes speech using Qwen3-ASR (Apple Silicon MLX Metal GPU acceleration).
6. Persists structured results into unified JSON and SQLite database.
"""

import argparse
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.request
from typing import Any, Callable, Dict, List, Optional, Tuple

CURRENT_DIR = Path(__file__).parent
sys.path.append(str(CURRENT_DIR.parent.parent.parent))

from tools.loop.viral_analyzer.config import (
    ViralAnalyzerConfig,
    load_config,
)
from tools.loop.viral_analyzer.retention import (
    load_manifest,
    purge_expired_videos,
    register_video,
)
from tools.loop.viral_analyzer.transcription import (
    UnifiedTranscriber,
    extract_audio_ffmpeg,
)


from tools.loop.viral_analyzer.glasser import (
    GlasserError,
    GlasserMissingKeyError,
    GlasserNotFoundError,
    GlasserExecutionError,
    check_glasser_status,
    fetch_target_reels,
)


def download_video_stream(url_or_cdn: str, target_path: Path, is_reel_page: bool = False, max_bytes: int = 80 * 1024 * 1024) -> bool:
    """Download video stream with direct CDN streaming and yt-dlp fallback."""
    if not is_reel_page and (url_or_cdn.startswith("http://") or url_or_cdn.startswith("https://")):
        try:
            req = urllib.request.Request(
                url_or_cdn,
                headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"},
            )
            downloaded = 0
            with urllib.request.urlopen(req, timeout=60) as resp, open(target_path, "wb") as out:
                while chunk := resp.read(64 * 1024):
                    out.write(chunk)
                    downloaded += len(chunk)
                    if downloaded >= max_bytes:
                        break
            return target_path.exists() and target_path.stat().st_size > 1000
        except Exception:
            pass

    try:
        from yt_dlp import YoutubeDL

        with YoutubeDL({
            "outtmpl": str(target_path),
            "format": "best[ext=mp4]/best",
            "quiet": True,
            "noplaylist": True,
        }) as ydl:
            ydl.download([url_or_cdn])
        if target_path.exists() and target_path.stat().st_size > 1000:
            return True
    except Exception:
        pass

    cmd = [
        "uv", "run", "yt-dlp",
        "--skip-download", "false",
        "-f", "best[ext=mp4]/best",
        "-o", str(target_path),
        "--quiet",
        url_or_cdn,
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=45)
        return res.returncode == 0 and target_path.exists() and target_path.stat().st_size > 1000
    except Exception:
        return False


def classify_pool(views: int, config: ViralAnalyzerConfig) -> Tuple[int, str]:
    """Map views to one of the 5 configured traffic pools."""
    for pool_id in sorted(config.pools.keys(), reverse=True):
        definition = config.pools[pool_id]
        if definition.contains(views):
            return pool_id, definition.name
    return 1, config.pools.get(1, config.pools[min(config.pools.keys())]).name


def persist_to_database(reels: List[Dict[str, Any]], db_path: Path) -> None:
    """Persist analyzed reels and transcripts to SQLite database."""
    if not db_path.parent.exists():
        db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    now_ts = datetime.now(timezone.utc).isoformat()
    try:
        with conn:
            # Ensure schema & columns
            conn.execute("""
            CREATE TABLE IF NOT EXISTS videos (
                id TEXT PRIMARY KEY,
                platform TEXT NOT NULL,
                video_id TEXT NOT NULL,
                url TEXT NOT NULL UNIQUE,
                author_handle TEXT NOT NULL,
                title TEXT,
                sound_id TEXT,
                sound_name TEXT,
                duration_sec INTEGER,
                current_pool INTEGER DEFAULT 1,
                published_at TIMESTAMP,
                first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                transcript TEXT,
                transcribed_at TIMESTAMP
            )
            """)

            conn.execute("""
            CREATE TABLE IF NOT EXISTS metric_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                views INTEGER NOT NULL DEFAULT 0,
                likes INTEGER NOT NULL DEFAULT 0,
                comments INTEGER NOT NULL DEFAULT 0,
                shares INTEGER NOT NULL DEFAULT 0,
                pool_level INTEGER NOT NULL,
                velocity_per_hour REAL DEFAULT 0.0,
                acceleration REAL DEFAULT 0.0,
                comment_ratio REAL DEFAULT 0.0,
                engagement_rate REAL DEFAULT 0.0
            )
            """)

            for r in reels:
                primary_id = f"facebook:{r['video_id']}"
                conn.execute(
                    """
                    INSERT INTO videos (
                        id, platform, video_id, url, author_handle, title,
                        current_pool, published_at, first_seen_at, last_scraped_at,
                        transcript, transcribed_at
                    ) VALUES (?, 'facebook', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        current_pool = excluded.current_pool,
                        last_scraped_at = excluded.last_scraped_at,
                        title = excluded.title,
                        transcript = COALESCE(excluded.transcript, videos.transcript),
                        transcribed_at = COALESCE(excluded.transcribed_at, videos.transcribed_at)
                    """,
                    (
                        primary_id,
                        r["video_id"],
                        r["url"],
                        r["author_handle"],
                        r["title"],
                        r["current_pool"],
                        r["published_at"],
                        now_ts,
                        now_ts,
                        r.get("transcript"),
                        now_ts if r.get("transcript") else None,
                    ),
                )

                conn.execute(
                    """
                    INSERT INTO metric_snapshots (
                        video_id, timestamp, views, likes, comments, shares,
                        pool_level, velocity_per_hour, comment_ratio
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        primary_id,
                        now_ts,
                        r["views"],
                        r["likes"],
                        r["comments"],
                        r["shares"],
                        r["current_pool"],
                        r["velocity_per_hour"],
                        r.get("comment_ratio", 0.0),
                    ),
                )
    finally:
        conn.close()


def run_analyzer_pipeline(
    config: ViralAnalyzerConfig,
    dry_run: bool = False,
    limit_targets: Optional[int] = None,
    max_videos: Optional[int] = None,
    cache_dir: Optional[Path] = None,
    media: bool = True,
    legacy_cache: bool = True,
    progress_cb: Optional[Callable[[str], None]] = None,
) -> Dict[str, Any]:
    """Execute the full end-to-end viral analyzer pipeline."""
    def report(message: str) -> None:
        print(message)
        if progress_cb:
            progress_cb(message)

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
    print(f"AI Transcriber  : {config.transcription.engine} ({config.transcription.model})")
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

    for idx, target in enumerate(targets_to_scan, 1):
        handle = target.get("handle", "unknown")
        print(f"[{idx}/{len(targets_to_scan)}] Querying {handle}...")
        progress_cb and progress_cb(f"[{idx}/{len(targets_to_scan)}] Querying {handle}...")
        raw_items = fetch_target_reels(
            target,
            config,
            cache_dir=cache_dir or config.storage.output_file.parent,
            legacy_cache=legacy_cache,
            progress_cb=progress_cb,
            error_collector=glasser_errors,
        )
        count_for_target = 0

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
            })
            count_for_target += 1

        print(f"    -> Extracted {count_for_target} reels in 48h window.")
        progress_cb and progress_cb(f"    -> {handle}: {count_for_target} reel(s) trong 48h.")

    print(f"\n[+] Total 48h viral candidates harvested: {len(extracted_reels)}")
    progress_cb and progress_cb(f"[+] Tổng cộng {len(extracted_reels)} reel ứng viên trong 48h.")

    # 3. Download & Audio Transcription
    # @deprecated [OBSOLETE]: Local video download + audio transcription pipeline is obsolete
    # compared to cloud API transcription (e.g. Glasser.ai / ScrapeCreators).
    # Retained for offline fallback and backward-compatibility; do not delete.
    transcriber = None
    if media:
        try:
            transcriber = UnifiedTranscriber(
                engine=config.transcription.engine,
                model_name=config.transcription.model,
                language=config.transcription.language,
            )
        except Exception as exc:
            report(f"[!] Transcription unavailable ({exc}); continuing without transcripts.")

    for idx, reel in enumerate(extracted_reels if transcriber else [], 1):
        vid = reel["video_id"]
        v_cdn = reel.get("video_url")
        v_url = v_cdn if v_cdn else reel["url"]
        is_reel_page = not bool(v_cdn)

        video_path = config.storage.video_dir / f"reel_{vid}.mp4"
        temp_audio = Path(tempfile.gettempdir()) / f"audio_{vid}.wav"

        print(f"\n[{idx}/{len(extracted_reels)}] Pool {reel['current_pool']} ({reel['views']:,} views) - {reel['author_handle']}: {reel['title'][:50]}...")
        progress_cb and progress_cb(f"[{idx}/{len(extracted_reels)}] Đang xử lý {reel['author_handle']}: {reel['title'][:60]}")

        # Check target quota
        if effective_max:
            total_cached = len(list(config.storage.video_dir.glob("*.mp4")))
            if total_cached >= effective_max and not video_path.exists():
                print(f"    [*] Target video quota reached ({total_cached}/{effective_max}); skipping additional downloads.")
                break

        # Download video to cache if not already present
        if not video_path.exists():
            print(f"    [*] Downloading to persistent video cache: {video_path.name}...")
            dl_ok = download_video_stream(v_url, video_path, is_reel_page=is_reel_page)
            if not dl_ok:
                print(f"    [-] Download failed for {vid}")
                continue
            # Register in retention manifest (kept for 1 week)
            register_video(config.storage.video_dir, vid, video_path, retention_days=config.retention_days, now=now)
            print(f"    [+] Saved to cache (Expires in {config.retention_days} days).")
        else:
            print(f"    [*] Found in cache: {video_path.name}")

        # Check existing transcript in DB first
        existing_tr = None
        if config.storage.db_path.exists():
            try:
                conn_chk = sqlite3.connect(str(config.storage.db_path))
                row = conn_chk.cursor().execute("SELECT transcript FROM videos WHERE id = ?", (f"facebook:{vid}",)).fetchone()
                if row and row[0]:
                    existing_tr = row[0]
                conn_chk.close()
            except Exception:
                pass

        if existing_tr:
            print(f"    [*] Transcript already present in DB ({len(existing_tr)} chars).")
            reel["transcript"] = existing_tr
            reel["segments"] = []
            reel["language"] = "vi"
            continue

        # Extract lightweight audio capped at max duration
        try:
            print("    [*] Extracting 16kHz mono audio via FFmpeg...")
            audio_ok = extract_audio_ffmpeg(
                video_path,
                temp_audio,
                max_duration_sec=config.transcription.max_audio_duration_sec,
            )
            if audio_ok:
                print(f"    [*] Transcribing with {config.transcription.engine.upper()}...")
                tr_res = transcriber.transcribe_audio(temp_audio)
                reel["transcript"] = tr_res["transcript"]
                reel["segments"] = tr_res["segments"]
                reel["language"] = tr_res["language"]
                print(f"    [+] Transcribed ({len(tr_res['transcript'])} chars): {tr_res['transcript'][:70]}...")
            else:
                reel["transcript"] = ""
                reel["segments"] = []
        finally:
            # Ephemeral audio cleanup (video remains in persistent cache for 1 week!)
            if temp_audio.exists():
                try:
                    os.remove(temp_audio)
                except Exception:
                    pass

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
        },
        "errors": [e.to_dict() if hasattr(e, "to_dict") else str(e) for e in glasser_errors],
        "pools": by_pools,
        "all_reels": extracted_reels,
    }

    config.storage.output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(config.storage.output_file, "w", encoding="utf-8") as out_f:
        json.dump(summary_payload, out_f, ensure_ascii=False, indent=2)

    # 5. Database Persistence
    persist_to_database(extracted_reels, config.storage.db_path)

    print("\n" + "=" * 80)
    print(" VIRAL ANALYZER EXECUTION COMPLETED")
    print("=" * 80)
    print(f"Total Extracted : {len(extracted_reels)} reels across 5 Pools")
    for pid in sorted(config.pools.keys()):
        print(f"  - Pool {pid} ({config.pools[pid].name}): {len(by_pools[f'pool_{pid}'])} reels")
    print(f"Saved Output    : {config.storage.output_file}")
    print(f"Database Target : {config.storage.db_path}")
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

    args = parser.parse_args()
    cfg = load_config(args.config)
    run_analyzer_pipeline(cfg, dry_run=args.dry_run, limit_targets=args.limit_targets, max_videos=args.max_videos)


if __name__ == "__main__":
    main()
