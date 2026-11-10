"""Video job management, concurrency queue, crash recovery, and execution."""

from __future__ import annotations

import concurrent.futures
from contextlib import contextmanager
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import threading
import time
from typing import Any, Callable, Dict, List, Optional
import uuid

from tools.app.backend.credits import CREDIT_STORE, RATE_PER_SEC_MICRO
from tools.app.backend.media import MEDIA_STORE
from tools.app.backend.profiles import RUNS_ROOT, now_iso
from tools.app.backend.video_engine import generate_video, get_video_duration

DEFAULT_MAX_GLOBAL_JOBS = 2
DEFAULT_MAX_PER_USER_JOBS = 1
VIDEO_COST_MICRO = get_video_duration() * RATE_PER_SEC_MICRO


class VideoJobStore:
    def __init__(self, db_path: Optional[Path] = None, runs_dir: Optional[Path] = None) -> None:
        self.db_path = db_path or (RUNS_ROOT / "video_jobs.db")
        self.runs_dir = runs_dir or (RUNS_ROOT / "videos")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        with self._tx() as db:
            db.execute("""
            CREATE TABLE IF NOT EXISTS video_jobs (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                prompt TEXT NOT NULL,
                profile_media_id TEXT NOT NULL,
                context_media_ids TEXT,
                cost INTEGER NOT NULL,
                status TEXT NOT NULL,
                video_path TEXT,
                error TEXT,
                created_at TEXT NOT NULL,
                started_at TEXT,
                finished_at TEXT
            )
            """)
            db.execute("CREATE INDEX IF NOT EXISTS idx_video_jobs_user ON video_jobs (user_id, status)")
        db = sqlite3.connect(self.db_path)
        db.execute("PRAGMA journal_mode=WAL")
        db.close()

    @contextmanager
    def _tx(self):
        db = sqlite3.connect(self.db_path, timeout=30, isolation_level=None)
        db.execute("PRAGMA busy_timeout = 30000")
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.execute("COMMIT")
        except BaseException:
            if db.in_transaction:
                try:
                    db.execute("ROLLBACK")
                except Exception:
                    pass
            raise
        finally:
            db.close()

    @contextmanager
    def _ro(self):
        db = sqlite3.connect(self.db_path, timeout=30)
        db.execute("PRAGMA busy_timeout = 30000")
        try:
            yield db
        finally:
            db.close()

    def create_job(
        self,
        user_id: str,
        prompt: str,
        profile_media_id: str,
        context_media_ids: Optional[List[str]] = None,
        cost_micro: int = VIDEO_COST_MICRO,
    ) -> Dict[str, Any]:
        prompt = prompt.strip()
        if not prompt:
            raise ValueError("Prompt is required.")
        if not profile_media_id:
            raise ValueError("Profile media ID is required.")

        job_id = uuid.uuid4().hex[:12]

        # Reserve credits atomically
        if not CREDIT_STORE.reserve(user_id, cost_micro, job_id, reason="video_generation_reserve"):
            raise ValueError("INSUFFICIENT_CREDITS")

        created = now_iso()
        ctx_json = json.dumps(context_media_ids or [])
        with self._tx() as db:
            db.execute(
                """
                INSERT INTO video_jobs (
                    id, user_id, prompt, profile_media_id, context_media_ids, cost, status, video_path, error, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (job_id, user_id, prompt, profile_media_id, ctx_json, cost_micro, "pending", None, None, created),
            )

        return self.get_job(user_id, job_id)  # type: ignore

    def get_job(self, user_id: str, job_id: str) -> Optional[Dict[str, Any]]:
        with self._ro() as db:
            row = db.execute(
                """
                SELECT id, user_id, prompt, profile_media_id, context_media_ids, cost, status, video_path, error, created_at, started_at, finished_at
                FROM video_jobs WHERE id = ? AND user_id = ?
                """,
                (job_id, user_id),
            ).fetchone()
        if not row:
            return None
        return self._row_to_dict(row)

    def get_job_any_user(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self._ro() as db:
            row = db.execute(
                """
                SELECT id, user_id, prompt, profile_media_id, context_media_ids, cost, status, video_path, error, created_at, started_at, finished_at
                FROM video_jobs WHERE id = ?
                """,
                (job_id,),
            ).fetchone()
        if not row:
            return None
        return self._row_to_dict(row)

    def list_jobs(self, user_id: str) -> List[Dict[str, Any]]:
        with self._ro() as db:
            rows = db.execute(
                """
                SELECT id, user_id, prompt, profile_media_id, context_media_ids, cost, status, video_path, error, created_at, started_at, finished_at
                FROM video_jobs WHERE user_id = ? ORDER BY created_at DESC
                """,
                (user_id,),
            ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def cancel_job(self, user_id: str, job_id: str) -> bool:
        with self._tx() as db:
            row = db.execute(
                "SELECT status, cost FROM video_jobs WHERE id = ? AND user_id = ?",
                (job_id, user_id),
            ).fetchone()
            if not row:
                return False
            status, cost = row[0], int(row[1])
            if status != "pending":
                return False

            now = now_iso()
            db.execute("UPDATE video_jobs SET status = 'cancelled', finished_at = ? WHERE id = ?", (now, job_id))

        # Refund credits
        CREDIT_STORE.refund(user_id, cost, job_id, reason="job_cancel_refund")
        return True

    def delete_job(self, user_id: str, job_id: str) -> bool:
        with self._tx() as db:
            row = db.execute(
                "SELECT id FROM video_jobs WHERE id = ? AND user_id = ?",
                (job_id, user_id),
            ).fetchone()
            if not row:
                return False
            db.execute("DELETE FROM video_jobs WHERE id = ? AND user_id = ?", (job_id, user_id))

        job_dir = self.runs_dir / user_id / job_id
        if job_dir.exists():
            shutil.rmtree(job_dir, ignore_errors=True)
        return True

    def recover_stale_jobs(self) -> int:
        recovered = 0
        with self._tx() as db:
            rows = db.execute("SELECT id, user_id, cost FROM video_jobs WHERE status = 'running'").fetchall()
            now = now_iso()
            for job_id, user_id, cost in rows:
                db.execute(
                    "UPDATE video_jobs SET status = 'failed', error = 'Server restarted while job was running', finished_at = ? WHERE id = ?",
                    (now, job_id),
                )
                CREDIT_STORE.refund(user_id, int(cost), job_id, reason="crash_recovery_refund")
                recovered += 1
        return recovered

    def count_running(self, user_id: Optional[str] = None) -> int:
        with self._ro() as db:
            if user_id:
                row = db.execute(
                    "SELECT COUNT(*) FROM video_jobs WHERE user_id = ? AND status = 'running'",
                    (user_id,),
                ).fetchone()
            else:
                row = db.execute("SELECT COUNT(*) FROM video_jobs WHERE status = 'running'").fetchone()
            return int(row[0]) if row else 0

    def claim_next_pending(self, max_global: int = DEFAULT_MAX_GLOBAL_JOBS, max_per_user: int = DEFAULT_MAX_PER_USER_JOBS) -> Optional[Dict[str, Any]]:
        with self._tx() as db:
            total_running = db.execute("SELECT COUNT(*) FROM video_jobs WHERE status = 'running'").fetchone()[0]
            if total_running >= max_global:
                return None

            # Find oldest pending job where the user does not exceed max_per_user
            rows = db.execute(
                """
                SELECT id, user_id, prompt, profile_media_id, context_media_ids, cost, status, video_path, error, created_at, started_at, finished_at
                FROM video_jobs WHERE status = 'pending' ORDER BY created_at ASC
                """
            ).fetchall()

            for row in rows:
                candidate = self._row_to_dict(row)
                uid = candidate["user_id"]
                user_running = db.execute(
                    "SELECT COUNT(*) FROM video_jobs WHERE user_id = ? AND status = 'running'",
                    (uid,),
                ).fetchone()[0]
                if user_running < max_per_user:
                    now = now_iso()
                    db.execute("UPDATE video_jobs SET status = 'running', started_at = ? WHERE id = ?", (now, candidate["id"]))
                    candidate["status"] = "running"
                    candidate["started_at"] = now
                    return candidate

        return None

    def mark_completed(self, job_id: str, video_path: str) -> None:
        with self._tx() as db:
            db.execute(
                "UPDATE video_jobs SET status = 'completed', video_path = ?, finished_at = ? WHERE id = ?",
                (video_path, now_iso(), job_id),
            )

    def mark_failed(self, job_id: str, error: str) -> None:
        with self._tx() as db:
            row = db.execute("SELECT user_id, cost FROM video_jobs WHERE id = ?", (job_id,)).fetchone()
            db.execute(
                "UPDATE video_jobs SET status = 'failed', error = ?, finished_at = ? WHERE id = ?",
                (error, now_iso(), job_id),
            )
            if row:
                user_id, cost = row[0], int(row[1])
                CREDIT_STORE.refund(user_id, cost, job_id, reason="job_failed_refund")

    @staticmethod
    def _row_to_dict(row: tuple) -> Dict[str, Any]:
        return {
            "id": row[0],
            "user_id": row[1],
            "prompt": row[2],
            "profile_media_id": row[3],
            "context_media_ids": json.loads(row[4]) if row[4] else [],
            "cost": row[5],
            "cost_usd": round(row[5] / 1_000_000, 4),
            "status": row[6],
            "video_path": row[7],
            "error": row[8],
            "created_at": row[9],
            "started_at": row[10],
            "finished_at": row[11],
        }


class VideoRunner:
    def __init__(
        self,
        store: VideoJobStore,
        media_store=MEDIA_STORE,
        max_workers: int = DEFAULT_MAX_GLOBAL_JOBS,
        max_per_user: int = DEFAULT_MAX_PER_USER_JOBS,
        generator: Optional[Callable] = None,
    ) -> None:
        self.store = store
        self.media_store = media_store
        self.max_workers = max_workers
        self.max_per_user = max_per_user
        self.generator = generator or generate_video
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
        self._lock = threading.Lock()
        self._stop = False

    def trigger(self) -> None:
        """Attempt to dispatch pending jobs up to concurrency limits."""
        with self._lock:
            while True:
                job = self.store.claim_next_pending(self.max_workers, self.max_per_user)
                if not job:
                    break
                self.executor.submit(self._run_job, job)

    def _run_job(self, job: Dict[str, Any]) -> None:
        job_id = job["id"]
        user_id = job["user_id"]
        prompt = job["prompt"]
        profile_media_id = job["profile_media_id"]
        context_media_ids = job["context_media_ids"]

        job_dir = self.store.runs_dir / user_id / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        out_video = job_dir / "output.mp4"

        try:
            profile_media = self.media_store.get_media(user_id, profile_media_id)
            if not profile_media or not Path(profile_media["path"]).exists():
                raise FileNotFoundError("Profile image not found.")

            profile_bytes = Path(profile_media["path"]).read_bytes()
            context_bytes_list: List[bytes] = []
            for cid in context_media_ids:
                c_media = self.media_store.get_media(user_id, cid)
                if c_media and Path(c_media["path"]).exists():
                    context_bytes_list.append(Path(c_media["path"]).read_bytes())

            cost = int(job.get("cost") or VIDEO_COST_MICRO)
            duration_sec = get_video_duration()

            try:
                self.generator(
                    prompt=prompt,
                    profile_image_bytes=profile_bytes,
                    context_images_bytes=context_bytes_list,
                    output_path=out_video,
                    duration_sec=duration_sec,
                )
            except TypeError:
                self.generator(
                    prompt=prompt,
                    profile_image_bytes=profile_bytes,
                    context_images_bytes=context_bytes_list,
                    output_path=out_video,
                )

            self.store.mark_completed(job_id, str(out_video))
        except Exception as exc:
            self.store.mark_failed(job_id, str(exc))
        finally:
            self.trigger()

    def shutdown(self) -> None:
        self.executor.shutdown(wait=False)


VIDEO_STORE = VideoJobStore()
VIDEO_RUNNER = VideoRunner(VIDEO_STORE)
