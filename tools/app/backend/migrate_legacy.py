"""Migrate legacy SQLite databases and local run files from local/app-runs to PostgreSQL and S3 blob storage."""

from __future__ import annotations

import glob
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys

import psycopg

from tools.app.backend import blobs
from tools.app.backend.db import get_dsn, init_schema

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
APP_RUNS_DIR = REPO_ROOT / "local" / "app-runs"
DEFAULT_BACKUP_DIR = Path.home() / "social-content-app-runs-backup"


def backup_legacy_data(backup_dir: Path = DEFAULT_BACKUP_DIR) -> Path:
    if not APP_RUNS_DIR.exists():
        print(f"[migrate] Source directory {APP_RUNS_DIR} does not exist, skipping backup.")
        return backup_dir

    if backup_dir.exists():
        print(f"[migrate] Backup already exists at {backup_dir}")
        return backup_dir

    print(f"[migrate] Creating backup: {APP_RUNS_DIR} -> {backup_dir}")
    shutil.copytree(APP_RUNS_DIR, backup_dir)
    print(f"[migrate] Backup created successfully at {backup_dir}")
    return backup_dir


def migrate_jobs(conn: psycopg.Connection, jobs_db_path: Path) -> set[str]:
    print(f"[migrate] Migrating jobs from {jobs_db_path}...")
    sconn = sqlite3.connect(jobs_db_path)
    scur = sconn.cursor()

    # 1. Jobs table
    scur.execute("SELECT id, status, created_at, client_id, user_id, heartbeat, data FROM jobs")
    job_rows = scur.fetchall()
    migrated_job_ids = set()

    for jid, status, created_at, client_id, user_id, heartbeat, data_str in job_rows:
        # ensure data is valid json
        try:
            data_obj = json.loads(data_str) if isinstance(data_str, str) else data_str
            # remove legacy run_dir reference inside json if needed, keep structure
            data_clean = json.dumps(data_obj, ensure_ascii=False)
        except Exception:
            data_clean = json.dumps({"id": jid, "status": status}, ensure_ascii=False)

        conn.execute(
            """
            INSERT INTO jobs (id, status, created_at, client_id, user_id, heartbeat, data)
            VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
            ON CONFLICT (id) DO NOTHING
            """,
            (jid, status, created_at, client_id, user_id, heartbeat, data_clean),
        )
        migrated_job_ids.add(jid)

    # 2. Logs table -> job_logs
    scur.execute("SELECT seq, job_id, at, sheet, message FROM logs")
    log_rows = scur.fetchall()
    migrated_logs_count = 0
    for seq, job_id, at, sheet, message in log_rows:
        if job_id not in migrated_job_ids:
            continue
        conn.execute(
            """
            INSERT INTO job_logs (seq, job_id, at, sheet, message)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (seq) DO NOTHING
            """,
            (seq, job_id, at, sheet, message),
        )
        migrated_logs_count += 1

    # Reset job_logs sequence
    conn.execute("SELECT setval(pg_get_serial_sequence('job_logs', 'seq'), COALESCE(MAX(seq), 1)) FROM job_logs;")

    sconn.close()
    print(f"[migrate] Migrated {len(migrated_job_ids)} jobs and {migrated_logs_count} log entries.")
    return migrated_job_ids


def migrate_profiles(conn: psycopg.Connection, profiles_db_path: Path) -> None:
    print(f"[migrate] Migrating profiles from {profiles_db_path}...")
    sconn = sqlite3.connect(profiles_db_path)
    scur = sconn.cursor()

    # 1. Topics
    scur.execute("SELECT user_id, slug, name, created_at FROM topics")
    topic_rows = scur.fetchall()
    for row in topic_rows:
        conn.execute(
            """
            INSERT INTO topics (user_id, slug, name, created_at)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (user_id, slug) DO NOTHING
            """,
            row,
        )

    # 2. Profiles
    scur.execute("SELECT id, user_id, topic_slug, name, url, handle, created_at FROM profiles")
    profile_rows = scur.fetchall()
    for row in profile_rows:
        conn.execute(
            """
            INSERT INTO profiles (id, user_id, topic_slug, name, url, handle, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (user_id, topic_slug, url) DO NOTHING
            """,
            row,
        )

    # Reset profiles sequence
    conn.execute("SELECT setval(pg_get_serial_sequence('profiles', 'id'), COALESCE(MAX(id), 1)) FROM profiles;")

    sconn.close()
    print(f"[migrate] Migrated {len(topic_rows)} topics and {len(profile_rows)} profiles.")


def migrate_traffic_pools(conn: psycopg.Connection, traffic_db_path: Path) -> None:
    print(f"[migrate] Migrating traffic pools from {traffic_db_path}...")
    sconn = sqlite3.connect(traffic_db_path)
    scur = sconn.cursor()

    # 1. profile_cache
    scur.execute("SELECT handle, profile_url, reels_json, status, reel_count, fetched_at, updated_at FROM profile_cache")
    cache_rows = scur.fetchall()
    for row in cache_rows:
        conn.execute(
            """
            INSERT INTO profile_cache (handle, profile_url, reels_json, status, reel_count, fetched_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (handle) DO NOTHING
            """,
            row,
        )

    # 2. videos
    scur.execute(
        """
        SELECT id, platform, video_id, url, author_handle, title, sound_id, sound_name,
               duration_sec, current_pool, published_at, first_seen_at, last_scraped_at,
               transcript, transcribed_at
        FROM videos
        """
    )
    video_rows = scur.fetchall()
    for row in video_rows:
        conn.execute(
            """
            INSERT INTO videos (
                id, platform, video_id, url, author_handle, title, sound_id, sound_name,
                duration_sec, current_pool, published_at, first_seen_at, last_scraped_at,
                transcript, transcribed_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO NOTHING
            """,
            row,
        )

    # 3. metric_snapshots
    scur.execute(
        """
        SELECT id, video_id, timestamp, views, likes, comments, shares, pool_level,
               velocity_per_hour, acceleration, comment_ratio, engagement_rate
        FROM metric_snapshots
        """
    )
    snapshot_rows = scur.fetchall()
    for row in snapshot_rows:
        conn.execute(
            """
            INSERT INTO metric_snapshots (
                id, video_id, timestamp, views, likes, comments, shares, pool_level,
                velocity_per_hour, acceleration, comment_ratio, engagement_rate
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO NOTHING
            """,
            row,
        )

    # Reset metric_snapshots sequence
    conn.execute(
        "SELECT setval(pg_get_serial_sequence('metric_snapshots', 'id'), COALESCE(MAX(id), 1)) FROM metric_snapshots;"
    )

    sconn.close()
    print(f"[migrate] Migrated {len(cache_rows)} cache entries, {len(video_rows)} videos, {len(snapshot_rows)} snapshots.")


def migrate_files_to_blobs(job_ids: set[str]) -> None:
    print("[migrate] Uploading job input and result files to S3 blob storage...")
    uploaded_files = 0
    orphan_dirs = []

    for item in sorted(APP_RUNS_DIR.iterdir()):
        if not item.is_dir():
            continue
        jid = item.name
        if jid in ("cache", "lost+found"):
            continue

        if jid not in job_ids:
            orphan_dirs.append(jid)
            continue

        # Upload input.xlsx
        input_xlsx = item / "input.xlsx"
        if input_xlsx.exists():
            blobs.upload_file(
                f"runs/{jid}/input.xlsx",
                input_xlsx,
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            uploaded_files += 1

        # Upload result.json if present in sheets
        result_files = list(item.glob("sheets/*/result.json"))
        if result_files:
            blobs.upload_file(
                f"runs/{jid}/result.json",
                result_files[0],
                content_type="application/json",
            )
            uploaded_files += 1

    print(f"[migrate] Uploaded {uploaded_files} files to blob storage for {len(job_ids)} jobs.")
    if orphan_dirs:
        print(f"[migrate] Skipped {len(orphan_dirs)} orphan run directories: {orphan_dirs}")


def verify_row_counts(conn: psycopg.Connection) -> None:
    print("[migrate] Verifying row counts...")
    checks = [
        ("jobs.db", "jobs", "jobs", "SELECT count(*) FROM jobs"),
        ("jobs.db", "logs", "job_logs", "SELECT count(*) FROM job_logs"),
        ("profiles.db", "topics", "topics", "SELECT count(*) FROM topics"),
        ("profiles.db", "profiles", "profiles", "SELECT count(*) FROM profiles"),
        ("traffic_pools.db", "profile_cache", "profile_cache", "SELECT count(*) FROM profile_cache"),
        ("traffic_pools.db", "videos", "videos", "SELECT count(*) FROM videos"),
        ("traffic_pools.db", "metric_snapshots", "metric_snapshots", "SELECT count(*) FROM metric_snapshots"),
    ]

    for db_name, sqlite_tbl, pg_tbl, pg_query in checks:
        db_path = APP_RUNS_DIR / db_name
        if not db_path.exists():
            continue
        with sqlite3.connect(db_path) as sconn:
            scur = sconn.cursor()
            scur.execute(f'SELECT count(*) FROM "{sqlite_tbl}"')
            expected = scur.fetchone()[0]

        cur = conn.execute(pg_query)
        actual = cur.fetchone()[0]

        print(f"  {pg_tbl}: SQLite={expected}, Postgres={actual}")
        if expected != actual:
            raise AssertionError(f"Count mismatch on {pg_tbl}: expected {expected}, got {actual}")

    print("[migrate] All row counts verified successfully!")


def run_migration() -> None:
    print("=== Starting Legacy Data Migration ===")
    backup_legacy_data()

    dsn = get_dsn()
    print(f"[migrate] Connecting to PostgreSQL via {dsn}...")
    init_schema(dsn)

    with psycopg.connect(dsn, autocommit=True) as conn:
        job_ids: set[str] = set()
        jobs_db = APP_RUNS_DIR / "jobs.db"
        if jobs_db.exists():
            job_ids = migrate_jobs(conn, jobs_db)

        profiles_db = APP_RUNS_DIR / "profiles.db"
        if profiles_db.exists():
            migrate_profiles(conn, profiles_db)

        traffic_db = APP_RUNS_DIR / "traffic_pools.db"
        if traffic_db.exists():
            migrate_traffic_pools(conn, traffic_db)

        # Upload files to blob storage
        migrate_files_to_blobs(job_ids)

        # Verify
        verify_row_counts(conn)

    print("=== Migration Completed Successfully ===")


if __name__ == "__main__":
    try:
        run_migration()
    except Exception as e:
        print(f"[migrate] ERROR: {e}", file=sys.stderr)
        sys.exit(1)
