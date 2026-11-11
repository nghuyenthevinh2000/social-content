"""Video job management, concurrency queue, crash recovery, and execution."""

from __future__ import annotations

import concurrent.futures
import json
import os
from pathlib import Path
import tempfile
import threading
import time
from typing import Any, Callable, Dict, List, Optional
import uuid

from tools.app.backend import blobs
from tools.app.backend.credits import CREDIT_STORE, RATE_PER_SEC_MICRO, get_rate_per_sec_micro
from tools.app.backend.db import ro, tx
from tools.app.backend.media import MEDIA_STORE
from tools.app.backend.profiles import now_iso
from tools.app.backend.video_engine import generate_video, get_video_duration

DEFAULT_MAX_GLOBAL_JOBS = 2
DEFAULT_MAX_PER_USER_JOBS = 1


def get_video_cost_micro() -> int:
    return get_video_duration() * get_rate_per_sec_micro()


VIDEO_COST_MICRO = get_video_cost_micro()


class VideoJobStore:
    def __init__(self) -> None:
        pass

    def create_job(
        self,
        user_id: str,
        prompt: str,
        profile_media_id: str,
        context_media_ids: Optional[List[str]] = None,
        cost_micro: Optional[int] = None,
    ) -> Dict[str, Any]:
        prompt = prompt.strip()
        if not prompt:
            raise ValueError("Prompt is required.")
        if not profile_media_id:
            raise ValueError("Profile media ID is required.")
        if cost_micro is None:
            cost_micro = get_video_cost_micro()

        job_id = uuid.uuid4().hex[:12]

        # Reserve credits atomically
        if not CREDIT_STORE.reserve(user_id, cost_micro, job_id, reason="video_generation_reserve"):
            raise ValueError("INSUFFICIENT_CREDITS")

        created = now_iso()
        ctx_json = json.dumps(context_media_ids or [])
        with tx() as conn:
            conn.execute(
                """
                INSERT INTO video_jobs (
                    id, user_id, prompt, profile_media_id, context_media_ids, cost, status, blob_key, error, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (job_id, user_id, prompt, profile_media_id, ctx_json, cost_micro, "pending", None, None, created),
            )

        return self.get_job(user_id, job_id)  # type: ignore

    def get_job(self, user_id: str, job_id: str) -> Optional[Dict[str, Any]]:
        with ro() as conn:
            cur = conn.execute(
                """
                SELECT id, user_id, prompt, profile_media_id, context_media_ids, cost, status, blob_key, error, created_at, started_at, finished_at
                FROM video_jobs WHERE id = %s AND user_id = %s
                """,
                (job_id, user_id),
            )
            row = cur.fetchone()
        if not row:
            return None
        return self._row_to_dict(row)

    def get_job_any_user(self, job_id: str) -> Optional[Dict[str, Any]]:
        with ro() as conn:
            cur = conn.execute(
                """
                SELECT id, user_id, prompt, profile_media_id, context_media_ids, cost, status, blob_key, error, created_at, started_at, finished_at
                FROM video_jobs WHERE id = %s
                """,
                (job_id,),
            )
            row = cur.fetchone()
        if not row:
            return None
        return self._row_to_dict(row)

    def list_jobs(self, user_id: str) -> List[Dict[str, Any]]:
        with ro() as conn:
            cur = conn.execute(
                """
                SELECT id, user_id, prompt, profile_media_id, context_media_ids, cost, status, blob_key, error, created_at, started_at, finished_at
                FROM video_jobs WHERE user_id = %s ORDER BY created_at DESC
                """,
                (user_id,),
            )
            rows = cur.fetchall()
        return [self._row_to_dict(r) for r in rows]

    def cancel_job(self, user_id: str, job_id: str) -> bool:
        with tx() as conn:
            cur = conn.execute(
                "SELECT status, cost FROM video_jobs WHERE id = %s AND user_id = %s FOR UPDATE",
                (job_id, user_id),
            )
            row = cur.fetchone()
            if not row:
                return False
            status, cost = row[0], int(row[1])
            if status != "pending":
                return False

            now = now_iso()
            conn.execute("UPDATE video_jobs SET status = 'cancelled', finished_at = %s WHERE id = %s", (now, job_id))

        # Refund credits
        CREDIT_STORE.refund(user_id, cost, job_id, reason="job_cancel_refund")
        return True

    def delete_job(self, user_id: str, job_id: str) -> bool:
        with tx() as conn:
            cur = conn.execute(
                "DELETE FROM video_jobs WHERE id = %s AND user_id = %s RETURNING id",
                (job_id, user_id),
            )
            if not cur.fetchone():
                return False

        blobs.delete_prefix(f"videos/{user_id}/{job_id}/")
        return True

    def recover_stale_jobs(self) -> int:
        with tx() as conn:
            cur = conn.execute("SELECT id, user_id, cost FROM video_jobs WHERE status = 'running' FOR UPDATE")
            rows = cur.fetchall()
            now = now_iso()
            for job_id, _user_id, _cost in rows:
                conn.execute(
                    "UPDATE video_jobs SET status = 'failed', error = 'Server restarted while job was running', finished_at = %s WHERE id = %s",
                    (now, job_id),
                )
        for job_id, user_id, cost in rows:
            CREDIT_STORE.refund(user_id, int(cost), job_id, reason="crash_recovery_refund")
        return len(rows)

    def count_running(self, user_id: Optional[str] = None) -> int:
        with ro() as conn:
            if user_id:
                cur = conn.execute(
                    "SELECT COUNT(*) FROM video_jobs WHERE user_id = %s AND status = 'running'",
                    (user_id,),
                )
            else:
                cur = conn.execute("SELECT COUNT(*) FROM video_jobs WHERE status = 'running'")
            row = cur.fetchone()
            return int(row[0]) if row else 0

    def claim_next_pending(self, max_global: int = DEFAULT_MAX_GLOBAL_JOBS, max_per_user: int = DEFAULT_MAX_PER_USER_JOBS) -> Optional[Dict[str, Any]]:
        with tx() as conn:
            conn.execute("SELECT pg_advisory_xact_lock(hashtext('claim_video_job'))")
            cur = conn.execute("SELECT COUNT(*) FROM video_jobs WHERE status = 'running'")
            if cur.fetchone()[0] >= max_global:
                return None

            cur = conn.execute(
                """
                SELECT id, user_id, prompt, profile_media_id, context_media_ids, cost, status, blob_key, error, created_at, started_at, finished_at
                FROM video_jobs WHERE status = 'pending' ORDER BY created_at ASC
                FOR UPDATE SKIP LOCKED
                """
            )
            rows = cur.fetchall()

            for row in rows:
                candidate = self._row_to_dict(row)
                uid = candidate["user_id"]
                cur_user = conn.execute(
                    "SELECT COUNT(*) FROM video_jobs WHERE user_id = %s AND status = 'running'",
                    (uid,),
                )
                if cur_user.fetchone()[0] < max_per_user:
                    now = now_iso()
                    conn.execute("UPDATE video_jobs SET status = 'running', started_at = %s WHERE id = %s", (now, candidate["id"]))
                    candidate["status"] = "running"
                    candidate["started_at"] = now
                    return candidate

        return None

    def mark_completed(self, job_id: str, video_path: str) -> None:
        with tx() as conn:
            conn.execute(
                "UPDATE video_jobs SET status = 'completed', blob_key = %s, finished_at = %s WHERE id = %s",
                (video_path, now_iso(), job_id),
            )

    def mark_failed(self, job_id: str, error: str) -> None:
        with tx() as conn:
            cur = conn.execute("SELECT user_id, cost FROM video_jobs WHERE id = %s FOR UPDATE", (job_id,))
            row = cur.fetchone()
            conn.execute(
                "UPDATE video_jobs SET status = 'failed', error = %s, finished_at = %s WHERE id = %s",
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
            "blob_key": row[7],
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

        temp_mp4 = None
        try:
            profile_media = self.media_store.get_media(user_id, profile_media_id)
            if not profile_media:
                raise FileNotFoundError("Profile image not found.")

            profile_bytes = blobs.get(profile_media["path"])
            context_bytes_list: List[bytes] = []
            for cid in context_media_ids:
                c_media = self.media_store.get_media(user_id, cid)
                if c_media:
                    try:
                        context_bytes_list.append(blobs.get(c_media["path"]))
                    except Exception:
                        pass

            cost = int(job.get("cost") or VIDEO_COST_MICRO)
            duration_sec = get_video_duration()

            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
                temp_mp4 = Path(f.name)

            try:
                self.generator(
                    prompt=prompt,
                    profile_image_bytes=profile_bytes,
                    context_images_bytes=context_bytes_list,
                    output_path=temp_mp4,
                    duration_sec=duration_sec,
                )
            except TypeError:
                self.generator(
                    prompt=prompt,
                    profile_image_bytes=profile_bytes,
                    context_images_bytes=context_bytes_list,
                    output_path=temp_mp4,
                )

            blob_key = f"videos/{user_id}/{job_id}/output.mp4"
            blobs.upload_file(blob_key, temp_mp4, content_type="video/mp4")
            self.store.mark_completed(job_id, blob_key)
        except Exception as exc:
            self.store.mark_failed(job_id, str(exc))
        finally:
            if temp_mp4 and temp_mp4.exists():
                try:
                    temp_mp4.unlink()
                except OSError:
                    pass
            self.trigger()

    def shutdown(self) -> None:
        self.executor.shutdown(wait=False)


VIDEO_STORE = VideoJobStore()
VIDEO_RUNNER = VideoRunner(VIDEO_STORE)
