"""Centralized cache and persistence layer for Viral Reels Analyzer.

Persists into PostgreSQL:
1. `profile_cache`     — TTL-backed raw Glasser profile reels & creator follower cache.
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
    from tools.app.backend.db import tx

    with tx() as conn:
        yield conn


# -- Profile Reels & Follower Cache ------------------------------------------

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


def _resolve_ttl_seconds(ttl_seconds: Optional[float]) -> float:
    if ttl_seconds is not None:
        return ttl_seconds
    return float(int(os.environ.get("VIRAL_APP_CACHE_TTL_HOURS", "24")) * 3600)


def _decode_cached_row(
    reels_json: Any,
    status: Optional[str],
    fetched_at: Any,
    ttl_seconds: float,
    now_ts: float,
    allow_expired: bool,
    source_tag: str,
) -> Optional[Tuple[List[Dict[str, Any]], str, str]]:
    clean_status = status or "ok"
    ts_val = float(fetched_at or 0.0)
    is_fresh = ttl_seconds <= 0 or (now_ts - ts_val) <= ttl_seconds
    if not (is_fresh or allow_expired):
        return None
    try:
        reels = json.loads(reels_json) if isinstance(reels_json, str) else reels_json
        if isinstance(reels, list):
            if allow_expired and not reels and clean_status != "not_found":
                return None
            return _tag_reels_source(reels, source_tag), clean_status, "database"
    except Exception:
        pass
    return None


def read_cached_reels_batch(
    handles: List[str],
    ttl_seconds: Optional[float] = None,
    allow_expired: bool = False,
) -> Dict[str, Tuple[List[Dict[str, Any]], str, str]]:
    """Batch-read profile reels from PostgreSQL `profile_cache` keyed by handle."""
    clean_handles = [h for h in dict.fromkeys(handles) if h]
    if not clean_handles:
        return {}
    from tools.app.backend.db import ro

    eff_ttl = _resolve_ttl_seconds(ttl_seconds)
    now_ts = time.time()
    source_tag = "cache_fallback" if allow_expired else "cache"
    out: Dict[str, Tuple[List[Dict[str, Any]], str, str]] = {}
    with ro() as conn:
        rows = conn.execute(
            "SELECT handle, reels_json, status, fetched_at FROM profile_cache WHERE handle = ANY(%s)",
            (clean_handles,),
        ).fetchall()
    for handle, reels_json, status, fetched_at in rows:
        decoded = _decode_cached_row(reels_json, status, fetched_at, eff_ttl, now_ts, allow_expired, source_tag)
        if decoded is not None:
            out[handle] = decoded
    return out


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
    from tools.app.backend.db import ro

    eff_ttl = _resolve_ttl_seconds(ttl_seconds)
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
            decoded = _decode_cached_row(row[0], row[1], row[2], eff_ttl, now_ts, allow_expired, source_tag)
            if decoded is not None:
                return decoded

    # 2. Check legacy JSON files in cache_dir (auto-imports into DB on hit)
    for c_path in _legacy_json_candidates(slug, cache_dir=cache_dir, legacy_cache=legacy_cache):
        mtime = c_path.stat().st_mtime
        is_fresh = eff_ttl <= 0 or (now_ts - mtime) <= eff_ttl
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


def write_cached_reels_batch(
    entries: List[Tuple[str, List[Dict[str, Any]], str, str, Optional[float]]],
) -> None:
    """Batch-upsert profile reels into PostgreSQL `profile_cache` table."""
    if not entries:
        return
    from tools.app.backend.db import tx

    default_ts = time.time()
    iso = now_iso()
    params = []
    for handle, reels, status, profile_url, fetched_at in entries:
        clean_reels = [
            {k: v for k, v in r.items() if k != "_source"} if isinstance(r, dict) else r
            for r in reels
        ]
        ts = float(fetched_at if fetched_at is not None else default_ts)
        params.append((
            handle,
            profile_url or "",
            json.dumps(clean_reels, ensure_ascii=False),
            status or "ok",
            len(clean_reels),
            ts,
            iso,
        ))

    with tx() as conn:
        with conn.cursor() as cur:
            cur.executemany(
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
                params,
            )


def write_cached_reels(
    handle: str,
    reels: List[Dict[str, Any]],
    status: str = "ok",
    profile_url: str = "",
    fetched_at: Optional[float] = None,
    **_kwargs: Any,
) -> None:
    """Upsert profile reels into PostgreSQL `profile_cache` table."""
    write_cached_reels_batch([(handle, reels, status, profile_url, fetched_at)])


def read_cached_followers(urls: List[str]) -> Dict[str, int]:
    """Batch-read cached public follower counts keyed by creator URL."""
    clean_urls = [u for u in dict.fromkeys(urls) if u]
    if not clean_urls:
        return {}
    keys = [f"followers:{u}" for u in clean_urls]
    try:
        from tools.app.backend.db import ro

        with ro() as conn:
            rows = conn.execute(
                "SELECT handle, reel_count FROM profile_cache WHERE handle = ANY(%s)",
                (keys,),
            ).fetchall()
        out: Dict[str, int] = {}
        for handle, cnt in rows:
            val = int(cnt or 0)
            if val > 0 and isinstance(handle, str) and handle.startswith("followers:"):
                out[handle[len("followers:"):]] = val
        return out
    except Exception:
        return {}


def write_cached_followers(entries: List[Tuple[str, int]]) -> None:
    """Batch-upsert creator follower counts into PostgreSQL `profile_cache`."""
    rows = [(f"followers:{u}", u, int(cnt)) for u, cnt in entries if u and int(cnt or 0) > 0]
    if not rows:
        return
    try:
        from tools.app.backend.db import tx

        ts, iso = time.time(), now_iso()
        with tx() as conn:
            with conn.cursor() as cur:
                cur.executemany(
                    "INSERT INTO profile_cache (handle, profile_url, reels_json, status, reel_count, fetched_at, updated_at) "
                    "VALUES (%s, %s, '[]', 'followers', %s, %s, %s) "
                    "ON CONFLICT (handle) DO UPDATE SET "
                    "reel_count = EXCLUDED.reel_count, fetched_at = EXCLUDED.fetched_at, updated_at = EXCLUDED.updated_at",
                    [(h, u, cnt, ts, iso) for h, u, cnt in rows],
                )
    except Exception:
        pass


# -- Video & Snapshot Persistence --------------------------------------------

NO_TRANSCRIPT_SENTINEL = "__NO_TRANSCRIPT__"


def get_cached_transcript(
    video_id: str,
    include_negative: bool = False,
    platform: Optional[str] = None,
    **_kwargs: Any,
) -> Optional[str]:
    """Retrieve previously transcribed text for a video from PostgreSQL `videos` table."""
    try:
        from tools.app.backend.db import ro

        with ro() as conn:
            row = conn.execute(
                "SELECT transcript FROM videos WHERE id = %s OR video_id = %s "
                "ORDER BY transcribed_at DESC NULLS LAST LIMIT 1",
                (f"{platform or 'facebook'}:{video_id}", str(video_id)),
            ).fetchone()
            if row and row[0]:
                val = str(row[0])
                if val == NO_TRANSCRIPT_SENTINEL and not include_negative:
                    return None
                return val
    except Exception:
        pass
    return None


def save_cached_transcript(
    video_id: str,
    transcript: str,
    url: Optional[str] = None,
    author_handle: str = "",
    title: str = "",
    platform: Optional[str] = None,
    **_kwargs: Any,
) -> None:
    """Save or update video transcript in PostgreSQL `videos` table."""
    if not video_id or not transcript:
        return
    from tools.app.backend.db import tx
    from tools.loop.viral_analyzer.platforms import detect_platform, fallback_video_url

    eff_platform = (platform or (detect_platform(url) if url else "") or "facebook").strip().lower()
    if eff_platform not in {"facebook", "youtube", "tiktok", "instagram"}:
        eff_platform = "facebook"
    primary_id = f"{eff_platform}:{video_id}"
    fallback_url = fallback_video_url(eff_platform, video_id, author_handle=author_handle)
    now_ts = now_iso()
    try:
        with tx() as conn:
            conn.execute(
                """
                INSERT INTO videos (
                    id, platform, video_id, url, author_handle, title,
                    transcript, transcribed_at, first_seen_at, last_scraped_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT(id) DO UPDATE SET
                    transcript = EXCLUDED.transcript,
                    transcribed_at = EXCLUDED.transcribed_at
                """,
                (
                    primary_id,
                    eff_platform,
                    video_id,
                    url or fallback_url,
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
    """Batch-persist analyzed reels, transcripts, and time-series metric snapshots to PostgreSQL."""
    if not reels:
        return
    from tools.app.backend.db import tx
    from tools.loop.viral_analyzer import profiling

    now_ts = now_iso()
    prepared: List[Tuple[str, str, Dict[str, Any]]] = []
    seen_ids: set[str] = set()
    seen_urls: set[str] = set()
    for r in reels:
        url = str(r.get("url") or "").strip()
        vid = str(r.get("video_id") or "").strip()
        if not url or not vid:
            continue
        platform = str(r.get("platform") or "facebook").strip().lower()
        if platform not in {"facebook", "youtube", "tiktok", "instagram"}:
            platform = "facebook"
        primary_id = f"{platform}:{vid}"
        if primary_id in seen_ids or url in seen_urls:
            continue
        seen_ids.add(primary_id)
        seen_urls.add(url)
        prepared.append((primary_id, platform, r))

    if not prepared:
        return

    with profiling.span("cache", "persist_to_database"):
        with tx() as conn:
            with conn.cursor() as cur:
                existing_by_url = dict(
                    cur.execute(
                        "SELECT url, id FROM videos WHERE url = ANY(%s)",
                        ([str(r["url"]).strip() for _, _, r in prepared],),
                    ).fetchall()
                )
                resolved: List[Tuple[str, str, Dict[str, Any]]] = []
                resolved_ids: set[str] = set()
                for primary_id, platform, r in prepared:
                    eff_id = existing_by_url.get(str(r["url"]).strip(), primary_id)
                    if eff_id in resolved_ids:
                        continue
                    resolved_ids.add(eff_id)
                    resolved.append((eff_id, platform, r))

                video_rows: List[Tuple[Any, ...]] = [
                    (
                        eff_id,
                        platform,
                        r["video_id"],
                        str(r["url"]).strip(),
                        r["author_handle"],
                        r["title"],
                        r["current_pool"],
                        r["published_at"],
                        now_ts,
                        now_ts,
                        r.get("transcript"),
                        now_ts if r.get("transcript") else None,
                    )
                    for eff_id, platform, r in resolved
                ]
                primary_ids = [eff_id for eff_id, _, _ in resolved]
                cur.executemany(
                    """
                    INSERT INTO videos (
                        id, platform, video_id, url, author_handle, title,
                        current_pool, published_at, first_seen_at, last_scraped_at,
                        transcript, transcribed_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT(id) DO UPDATE SET
                        current_pool = EXCLUDED.current_pool,
                        last_scraped_at = EXCLUDED.last_scraped_at,
                        title = EXCLUDED.title,
                        transcript = COALESCE(EXCLUDED.transcript, videos.transcript),
                        transcribed_at = COALESCE(EXCLUDED.transcribed_at, videos.transcribed_at)
                    """,
                    video_rows,
                )

                prev_rows = cur.execute(
                    "SELECT DISTINCT ON (video_id) video_id, velocity_per_hour "
                    "FROM metric_snapshots WHERE video_id = ANY(%s) ORDER BY video_id, id DESC",
                    (primary_ids,),
                ).fetchall()
                prev_vel: Dict[str, float] = {row[0]: float(row[1] or 0.0) for row in prev_rows}

                snap_rows: List[Tuple[Any, ...]] = []
                for primary_id, _platform, r in resolved:
                    velocity = float(r.get("velocity_per_hour") or 0.0)
                    acceleration = round(velocity - prev_vel[primary_id], 2) if primary_id in prev_vel else 0.0
                    prev_vel[primary_id] = velocity
                    snap_rows.append((
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
                    ))

                cur.executemany(
                    """
                    INSERT INTO metric_snapshots (
                        video_id, timestamp, views, likes, comments, shares,
                        pool_level, velocity_per_hour, acceleration, comment_ratio
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    snap_rows,
                )
