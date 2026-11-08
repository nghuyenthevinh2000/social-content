"""Centralized SQLite cache and persistence layer for Viral Reels Analyzer.

Consolidates three previously fragmented storage layers into one WAL-mode SQLite
database (`local/app-runs/traffic_pools.db` by default):
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
import shutil
import sqlite3
import time
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple

CURRENT_DIR = Path(__file__).parent.resolve()
WORKSPACE = CURRENT_DIR.parents[2]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_runs_root() -> Path:
    if os.environ.get("VIRAL_APP_RUNS"):
        return Path(os.environ["VIRAL_APP_RUNS"])
    return WORKSPACE / "local" / "app-runs"


def default_db_path() -> Path:
    if os.environ.get("VIRAL_APP_DB_PATH"):
        return Path(os.environ["VIRAL_APP_DB_PATH"])
    return default_runs_root() / "traffic_pools.db"


def default_video_dir() -> Path:
    if os.environ.get("VIRAL_APP_VIDEO_DIR"):
        return Path(os.environ["VIRAL_APP_VIDEO_DIR"])
    return default_runs_root() / "cache" / "videos"


def resolve_db_path(config: Any = None, cache_dir: Optional[Path] = None) -> Path:
    """Resolve target SQLite database path from config, cache_dir, or central default."""
    if config is not None and getattr(config, "storage", None) and getattr(config.storage, "db_path", None):
        return Path(config.storage.db_path)
    if cache_dir is not None:
        c_path = Path(cache_dir)
        if c_path.suffix in {".db", ".sqlite", ".sqlite3"}:
            return c_path
        return c_path / "traffic_pools.db"
    return default_db_path()


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS profile_cache (
    handle TEXT PRIMARY KEY,
    profile_url TEXT,
    reels_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ok',
    reel_count INTEGER NOT NULL DEFAULT 0,
    fetched_at REAL NOT NULL,
    updated_at TEXT NOT NULL
);

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
);

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
);

CREATE INDEX IF NOT EXISTS idx_videos_author ON videos (author_handle);
CREATE INDEX IF NOT EXISTS idx_snapshots_video ON metric_snapshots (video_id, timestamp);
"""


@contextmanager
def connect_db(db_path: Optional[Path] = None) -> Iterator[sqlite3.Connection]:
    """Open a WAL-mode SQLite connection with schema initialized."""
    target = Path(db_path) if db_path else default_db_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(target), timeout=30.0)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        conn.executescript(SCHEMA_SQL)
        yield conn
        conn.commit()
    except BaseException:
        if conn.in_transaction:
            try:
                conn.rollback()
            except Exception:
                pass
        raise
    finally:
        conn.close()


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
    db_path: Optional[Path] = None,
    cache_dir: Optional[Path] = None,
    legacy_cache: bool = False,
    ttl_seconds: Optional[float] = None,
    allow_expired: bool = False,
) -> Optional[Tuple[List[Dict[str, Any]], str, str]]:
    """Read profile reels from SQLite `profile_cache` (with legacy JSON auto-import).

    Returns:
        Tuple of (reels_list, status, source_label) on hit, or None on miss.
    """
    if ttl_seconds is None:
        ttl_hours = int(os.environ.get("VIRAL_APP_CACHE_TTL_HOURS", "24"))
        ttl_seconds = float(ttl_hours * 3600)

    now_ts = time.time()
    slug = handle.replace(".", "_")
    source_tag = "cache_fallback" if allow_expired else "cache"

    # 1. Check centralized SQLite profile_cache table
    with connect_db(db_path) as conn:
        row = conn.execute(
            "SELECT reels_json, status, fetched_at FROM profile_cache WHERE handle = ?",
            (handle,),
        ).fetchone()
        if row:
            reels_json, status, fetched_at = row[0], row[1] or "ok", float(row[2] or 0.0)
            is_fresh = ttl_seconds <= 0 or (now_ts - fetched_at) <= ttl_seconds
            if is_fresh or allow_expired:
                try:
                    reels = json.loads(reels_json)
                    if isinstance(reels, list):
                        # If allow_expired fallback is requested, only use if non-empty
                        if allow_expired and not reels and status != "not_found":
                            pass
                        else:
                            return _tag_reels_source(reels, source_tag), status, "traffic_pools.db"
                except Exception:
                    pass

    # 2. Check legacy JSON files in cache_dir (auto-imports into SQLite on hit)
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
                    db_path=db_path,
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
    db_path: Optional[Path] = None,
    fetched_at: Optional[float] = None,
) -> None:
    """Upsert profile reels into SQLite `profile_cache` table."""
    clean_reels = [
        {k: v for k, v in r.items() if k != "_source"} if isinstance(r, dict) else r
        for r in reels
    ]
    ts = float(fetched_at if fetched_at is not None else time.time())
    with connect_db(db_path) as conn:
        conn.execute(
            """
            INSERT INTO profile_cache (handle, profile_url, reels_json, status, reel_count, fetched_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(handle) DO UPDATE SET
                profile_url = CASE WHEN excluded.profile_url != '' THEN excluded.profile_url ELSE profile_cache.profile_url END,
                reels_json = excluded.reels_json,
                status = excluded.status,
                reel_count = excluded.reel_count,
                fetched_at = excluded.fetched_at,
                updated_at = excluded.updated_at
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

def get_cached_transcript(video_id: str, db_path: Optional[Path] = None) -> Optional[str]:
    """Retrieve previously transcribed text for a video from SQLite `videos` table."""
    target = Path(db_path) if db_path else default_db_path()
    if not target.exists():
        return None
    try:
        with connect_db(target) as conn:
            row = conn.execute(
                "SELECT transcript FROM videos WHERE id = ?",
                (f"facebook:{video_id}",),
            ).fetchone()
            if row and row[0]:
                return str(row[0])
    except Exception:
        pass
    return None


def persist_to_database(reels: List[Dict[str, Any]], db_path: Optional[Path] = None) -> None:
    """Persist analyzed reels, transcripts, and time-series metric snapshots to SQLite."""
    now_ts = now_iso()
    with connect_db(db_path) as conn:
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

            prev_row = conn.execute(
                "SELECT velocity_per_hour FROM metric_snapshots WHERE video_id = ? ORDER BY id DESC LIMIT 1",
                (primary_id,),
            ).fetchone()
            velocity = float(r.get("velocity_per_hour") or 0.0)
            acceleration = round(velocity - float(prev_row[0] or 0.0), 2) if prev_row else 0.0

            conn.execute(
                """
                INSERT INTO metric_snapshots (
                    video_id, timestamp, views, likes, comments, shares,
                    pool_level, velocity_per_hour, acceleration, comment_ratio
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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


# -- Migration Utility -------------------------------------------------------

def migrate_fragmented_storage(
    runs_root: Optional[Path] = None,
    central_db: Optional[Path] = None,
    cleanup: bool = True,
) -> Dict[str, int]:
    """Consolidate fragmented per-sheet traffic_pools.db and loose glasser_*.json files."""
    root = Path(runs_root) if runs_root else default_runs_root()
    target_db = Path(central_db) if central_db else (root / "traffic_pools.db")
    stats = {
        "migrated_dbs": 0,
        "migrated_videos": 0,
        "migrated_snapshots": 0,
        "migrated_json_caches": 0,
        "removed_files": 0,
    }
    if not root.exists():
        return stats

    with connect_db(target_db) as conn:
        # 1. Consolidate per-sheet traffic_pools.db files
        for frag_db in sorted(root.rglob("traffic_pools.db")):
            if frag_db.resolve() == target_db.resolve():
                continue
            try:
                src = sqlite3.connect(str(frag_db))
                tables = {r[0] for r in src.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                if "videos" in tables:
                    for row in src.execute(
                        "SELECT id, platform, video_id, url, author_handle, title, current_pool, "
                        "published_at, first_seen_at, last_scraped_at, transcript, transcribed_at FROM videos"
                    ):
                        conn.execute(
                            """
                            INSERT INTO videos (
                                id, platform, video_id, url, author_handle, title, current_pool,
                                published_at, first_seen_at, last_scraped_at, transcript, transcribed_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ON CONFLICT(id) DO UPDATE SET
                                current_pool = MAX(videos.current_pool, excluded.current_pool),
                                first_seen_at = MIN(videos.first_seen_at, excluded.first_seen_at),
                                last_scraped_at = MAX(videos.last_scraped_at, excluded.last_scraped_at),
                                transcript = COALESCE(videos.transcript, excluded.transcript),
                                transcribed_at = COALESCE(videos.transcribed_at, excluded.transcribed_at)
                            """,
                            row,
                        )
                        stats["migrated_videos"] += 1
                if "metric_snapshots" in tables:
                    for row in src.execute(
                        "SELECT video_id, timestamp, views, likes, comments, shares, "
                        "pool_level, velocity_per_hour, acceleration, comment_ratio, engagement_rate "
                        "FROM metric_snapshots"
                    ):
                        conn.execute(
                            """
                            INSERT INTO metric_snapshots (
                                video_id, timestamp, views, likes, comments, shares,
                                pool_level, velocity_per_hour, acceleration, comment_ratio, engagement_rate
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            row,
                        )
                        stats["migrated_snapshots"] += 1
                src.close()
                stats["migrated_dbs"] += 1
                if cleanup:
                    for ext in ("", "-wal", "-shm"):
                        p = Path(str(frag_db) + ext)
                        if p.exists():
                            p.unlink()
                            stats["removed_files"] += 1
            except Exception:
                pass

    # 2. Consolidate loose glasser_*.json files
    for json_file in sorted(root.rglob("glasser_*.json")):
        handle = json_file.stem.removeprefix("glasser_")
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
            reels = data.get("reels", [])
            status = data.get("status", "ok")
            if isinstance(reels, list):
                write_cached_reels(
                    handle=handle,
                    reels=reels,
                    status=status,
                    db_path=target_db,
                    fetched_at=json_file.stat().st_mtime,
                )
                stats["migrated_json_caches"] += 1
            if cleanup:
                json_file.unlink()
                stats["removed_files"] += 1
        except Exception:
            pass

    # 3. Clean up orphaned per-sheet empty video cache directories & manifests
    if cleanup:
        central_video_dir = root / "cache" / "videos"
        central_video_dir.mkdir(parents=True, exist_ok=True)
        for manifest_file in sorted(root.glob("*/sheets/*/cache/videos/retention_manifest.json")):
            sheet_video_dir = manifest_file.parent
            for mp4 in sheet_video_dir.glob("*.mp4"):
                dest = central_video_dir / mp4.name
                if not dest.exists():
                    shutil.move(str(mp4), str(dest))
                else:
                    mp4.unlink()
            try:
                manifest_file.unlink()
                stats["removed_files"] += 1
                if not any(sheet_video_dir.iterdir()):
                    sheet_video_dir.rmdir()
                if not any(sheet_video_dir.parent.iterdir()):
                    sheet_video_dir.parent.rmdir()
            except Exception:
                pass

    return stats
