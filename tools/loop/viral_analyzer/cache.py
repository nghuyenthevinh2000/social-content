"""Centralized cache and persistence layer for Viral Reels Analyzer.

Persists into PostgreSQL:
1. `profile_cache`     — TTL-backed raw Glasser profile reels cache (including 404s).
2. `videos`            — Canonical reel metadata and reusable AI transcripts.
3. `metric_snapshots`  — Cross-run view/velocity/acceleration time-series snapshots.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
from typing import Any, Dict, Iterator, List, Optional, Tuple

from tools.app.backend.db import ro, tx

CURRENT_DIR = Path(__file__).parent.resolve()
WORKSPACE = CURRENT_DIR.parents[2]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_runs_root() -> Path:
    if os.environ.get("VIRAL_APP_RUNS"):
        return Path(os.environ["VIRAL_APP_RUNS"])
    return WORKSPACE / "local" / "app-runs"


def default_video_dir() -> Path:
    if os.environ.get("VIRAL_APP_VIDEO_DIR"):
        return Path(os.environ["VIRAL_APP_VIDEO_DIR"])
    return default_runs_root() / "cache" / "videos"


@contextmanager
def connect_db(*_args: Any, **_kwargs: Any) -> Iterator[Any]:
    """Provide a database connection context using centralized PostgreSQL."""
    with tx() as conn:
        yield conn


# -- Profile Reels Cache -----------------------------------------------------

def _tag_reels_source(reels: List[Dict[str, Any]], source: str) -> List[Dict[str, Any]]:
    for r in reels:
        if isinstance(r, dict):
            r["_source"] = source
    return reels


def _legacy_json_candidates(
    slug: str,
    cache_dir: Optional[Path] = None,
    legacy_cache: bool = False,
) -> List[Path]:
    dirs: List[Path] = []
    if cache_dir:
        dirs.append(Path(cache_dir))
    env_cache = os.environ.get("VIRAL_APP_CACHE_DIR")
    if env_cache and Path(env_cache) not in dirs:
        dirs.append(Path(env_cache))
    if legacy_cache:
        for extra in (default_runs_root() / "cache", Path("local/social-listening-test"), CURRENT_DIR):
            if extra not in dirs:
                dirs.append(extra)

    files: List[Path] = []
    for d in dirs:
        if not d or not d.exists() or d.is_file():
            continue
        for fname in (f"glasser_{slug}.json", f"temp_{slug}.json"):
            candidate = d / fname
            if candidate.exists() and candidate.stat().st_size > 10:
                files.append(candidate)
    return files


def read_cached_reels(
    handle: str,
    cache_dir: Optional[Path] = None,
    legacy_cache: bool = False,
    ttl_seconds: Optional[float] = None,
    allow_expired: bool = False,
    **_kwargs: Any,
) -> Optional[Tuple[List[Dict[str, Any]], str, str]]:
    """Read profile reels from PostgreSQL `profile_cache` (with legacy JSON auto-import).

    Returns:
        Tuple of (reels_list, status, source_label) on hit, or None on miss.
    """
    if ttl_seconds is None:
        ttl_hours = int(os.environ.get("VIRAL_APP_CACHE_TTL_HOURS", "24"))
        ttl_seconds = float(ttl_hours * 3600)

    now_ts = time.time()
    slug = handle.replace(".", "_")
    source_tag = "cache_fallback" if allow_expired else "cache"

    # 1. Check centralized profile_cache table
    with ro() as conn:
        row = conn.execute(
            "SELECT reels_json, status, fetched_at FROM profile_cache WHERE handle = %s",
            (handle,),
        ).fetchone()
        if row:
            reels_json, status, fetched_at = row[0], row[1] or "ok", float(row[2] or 0.0)
            is_fresh = ttl_seconds <= 0 or (now_ts - fetched_at) <= ttl_seconds
            if is_fresh or allow_expired:
                try:
                    reels = json.loads(reels_json) if isinstance(reels_json, str) else reels_json
                    if isinstance(reels, list):
                        if allow_expired and not reels and status != "not_found":
                            pass
                        else:
                            return _tag_reels_source(reels, source_tag), status, "database"
                except Exception:
                    pass

    # 2. Check legacy JSON files in cache_dir (auto-imports into DB on hit)
    for c_path in _legacy_json_candidates(slug, cache_dir=cache_dir, legacy_cache=legacy_cache):
        mtime = c_path.stat().st_mtime
        is_fresh = ttl_seconds <= 0 or (now_ts - mtime) <= ttl_seconds
        if not is_fresh and not allow_expired:
            continue
        try:
            data = json.loads(c_path.read_text(encoding="utf-8"))
            reels = data.get("reels", [])
            status = data.get("status", "ok")
            if isinstance(reels, list) and (reels or status == "not_found"):
                write_cached_reels(
                    handle=handle,
                    reels=reels,
                    status=status,
                    fetched_at=mtime,
                )
                return _tag_reels_source(reels, source_tag), status, c_path.name
        except Exception:
            pass

    return None


def write_cached_reels(
    handle: str,
    reels: List[Dict[str, Any]],
    status: str = "ok",
    profile_url: str = "",
    fetched_at: Optional[float] = None,
    **_kwargs: Any,
) -> None:
    """Upsert profile reels into PostgreSQL `profile_cache` table."""
    clean_reels = [
        {k: v for k, v in r.items() if k != "_source"} if isinstance(r, dict) else r
        for r in reels
    ]
    ts = float(fetched_at if fetched_at is not None else time.time())
    with tx() as conn:
        conn.execute(
            """
            INSERT INTO profile_cache (handle, profile_url, reels_json, status, reel_count, fetched_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT(handle) DO UPDATE SET
                profile_url = CASE WHEN EXCLUDED.profile_url != '' THEN EXCLUDED.profile_url ELSE profile_cache.profile_url END,
                reels_json = EXCLUDED.reels_json,
                status = EXCLUDED.status,
                reel_count = EXCLUDED.reel_count,
                fetched_at = EXCLUDED.fetched_at,
                updated_at = EXCLUDED.updated_at
            """,
            (
                handle,
                profile_url,
                json.dumps(clean_reels, ensure_ascii=False),
                status,
                len(clean_reels),
                ts,
                now_iso(),
            ),
        )


# -- Video & Snapshot Persistence --------------------------------------------

def get_cached_transcript(video_id: str, **_kwargs: Any) -> Optional[str]:
    """Retrieve previously transcribed text for a video from PostgreSQL `videos` table."""
    try:
        with ro() as conn:
            row = conn.execute(
                "SELECT transcript FROM videos WHERE id = %s",
                (f"facebook:{video_id}",),
            ).fetchone()
            if row and row[0]:
                return str(row[0])
    except Exception:
        pass
    return None


def save_cached_transcript(
    video_id: str,
    transcript: str,
    url: Optional[str] = None,
    author_handle: str = "",
    title: str = "",
    **_kwargs: Any,
) -> None:
    """Save or update video transcript in PostgreSQL `videos` table."""
    if not video_id or not transcript:
        return
    primary_id = f"facebook:{video_id}"
    now_ts = now_iso()
    try:
        with tx() as conn:
            conn.execute(
                """
                INSERT INTO videos (
                    id, platform, video_id, url, author_handle, title,
                    transcript, transcribed_at, first_seen_at, last_scraped_at
                ) VALUES (%s, 'facebook', %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT(id) DO UPDATE SET
                    transcript = EXCLUDED.transcript,
                    transcribed_at = EXCLUDED.transcribed_at
                """,
                (
                    primary_id,
                    video_id,
                    url or f"https://www.facebook.com/reel/{video_id}",
                    author_handle or "unknown",
                    title or "",
                    transcript,
                    now_ts,
                    now_ts,
                    now_ts,
                ),
            )
    except Exception:
        pass


def persist_to_database(reels: List[Dict[str, Any]], **_kwargs: Any) -> None:
    """Persist analyzed reels, transcripts, and time-series metric snapshots to PostgreSQL."""
    now_ts = now_iso()
    with tx() as conn:
        for r in reels:
            primary_id = f"facebook:{r['video_id']}"
            conn.execute(
                """
                INSERT INTO videos (
                    id, platform, video_id, url, author_handle, title,
                    current_pool, published_at, first_seen_at, last_scraped_at,
                    transcript, transcribed_at
                ) VALUES (%s, 'facebook', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT(id) DO UPDATE SET
                    current_pool = EXCLUDED.current_pool,
                    last_scraped_at = EXCLUDED.last_scraped_at,
                    title = EXCLUDED.title,
                    transcript = COALESCE(EXCLUDED.transcript, videos.transcript),
                    transcribed_at = COALESCE(EXCLUDED.transcribed_at, videos.transcribed_at)
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

            prev_row = conn.execute(
                "SELECT velocity_per_hour FROM metric_snapshots WHERE video_id = %s ORDER BY id DESC LIMIT 1",
                (primary_id,),
            ).fetchone()
            velocity = float(r.get("velocity_per_hour") or 0.0)
            acceleration = round(velocity - float(prev_row[0] or 0.0), 2) if prev_row else 0.0

            conn.execute(
                """
                INSERT INTO metric_snapshots (
                    video_id, timestamp, views, likes, comments, shares,
                    pool_level, velocity_per_hour, acceleration, comment_ratio
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    primary_id,
                    now_ts,
                    r["views"],
                    r["likes"],
                    r["comments"],
                    r["shares"],
                    r["current_pool"],
                    velocity,
                    acceleration,
                    r.get("comment_ratio", 0.0),
                ),
            )
