"""PostgreSQL-backed job state shared by the API and worker processes."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import time
from typing import Any, Callable, Dict, List, Optional

from tools.app.backend.db import ro, tx


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class JobStore:
    """PostgreSQL-backed job state shared by the API and any number of worker processes."""

    def __init__(self) -> None:
        pass

    @staticmethod
    def _write(conn, job: Dict[str, Any]) -> None:
        conn.execute(
            "UPDATE jobs SET status = %s, data = %s::jsonb WHERE id = %s",
            (job["status"], json.dumps(job, ensure_ascii=False), job["id"]),
        )

    def _mutate(self, job_id: str, change: Callable[[Dict[str, Any]], None]) -> bool:
        with tx() as conn:
            cur = conn.execute("SELECT data FROM jobs WHERE id = %s FOR UPDATE", (job_id,))
            row = cur.fetchone()
            if not row:
                return False
            raw_data = row[0]
            job = raw_data if isinstance(raw_data, dict) else json.loads(raw_data)
            change(job)
            self._write(conn, job)
            return True

    def put(self, job: Dict[str, Any]) -> None:
        data = {k: v for k, v in job.items() if k != "logs"}
        with tx() as conn:
            conn.execute(
                "INSERT INTO jobs (id, status, created_at, client_id, user_id, data) VALUES (%s, %s, %s, %s, %s, %s::jsonb)",
                (
                    job["id"],
                    job["status"],
                    job["created_at"],
                    job.get("client_id"),
                    job.get("user_id"),
                    json.dumps(data, ensure_ascii=False),
                ),
            )

    def update(self, job_id: str, **changes: Any) -> None:
        self._mutate(job_id, lambda job: job.update(changes))

    def patch_sheet(self, job_id: str, slug: str, **changes: Any) -> None:
        def change(job: Dict[str, Any]) -> None:
            for sheet in job.get("sheets", []):
                if sheet.get("slug") == slug:
                    sheet.update(changes)
                    return

        self._mutate(job_id, change)

    def log(self, job_id: str, message: str, sheet: Optional[str] = None) -> None:
        with tx() as conn:
            conn.execute(
                "INSERT INTO job_logs (job_id, at, sheet, message) VALUES (%s, %s, %s, %s)",
                (job_id, now_iso(), sheet, message),
            )

    def cancel(self, job_id: str, user_id: Optional[str] = None) -> bool:
        if user_id is not None:
            with ro() as conn:
                cur = conn.execute("SELECT user_id FROM jobs WHERE id = %s", (job_id,))
                row = cur.fetchone()
                if not row or (row[0] and row[0] != user_id):
                    return False
        return self._mutate(job_id, lambda job: job.update(cancel_requested=True))

    def claim_legacy_jobs(self, user_id: str) -> None:
        with tx() as conn:
            conn.execute("UPDATE jobs SET user_id = %s WHERE user_id IS NULL OR user_id = 'default'", (user_id,))

    def claim(self, max_per_client: int) -> Optional[Dict[str, Any]]:
        """Atomically take the oldest queued job whose client is under its running limit, and mark it running."""
        with tx() as conn:
            conn.execute("SELECT pg_advisory_xact_lock(hashtext('claim_job'))")
            cur = conn.execute(
                """
                SELECT id, data FROM jobs AS q
                WHERE status = 'queued' AND (
                    SELECT COUNT(*) FROM jobs AS r WHERE r.status = 'running' AND r.client_id IS NOT DISTINCT FROM q.client_id
                ) < %s
                ORDER BY created_at ASC
                FOR UPDATE SKIP LOCKED
                LIMIT 1
                """,
                (max_per_client,),
            )
            row = cur.fetchone()
            if not row:
                return None
            job_id, raw_data = row
            job = raw_data if isinstance(raw_data, dict) else json.loads(raw_data)
            job["status"] = "running"
            conn.execute(
                "UPDATE jobs SET status = 'running', heartbeat = %s, data = %s::jsonb WHERE id = %s",
                (time.time(), json.dumps(job, ensure_ascii=False), job_id),
            )
            return job

    def heartbeat(self, job_ids: List[str]) -> None:
        if not job_ids:
            return
        with tx() as conn:
            now_ts = time.time()
            for jid in job_ids:
                conn.execute("UPDATE jobs SET heartbeat = %s WHERE id = %s", (now_ts, jid))

    def stale_running(self, max_age_sec: float) -> List[str]:
        """Running jobs no worker has touched recently, i.e. their worker died."""
        with ro() as conn:
            cur = conn.execute(
                "SELECT id FROM jobs WHERE status = 'running' AND (heartbeat IS NULL OR heartbeat < %s)",
                (time.time() - max_age_sec,),
            )
            rows = cur.fetchall()
        return [row[0] for row in rows]

    def snapshot(self, job_id: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        with ro() as conn:
            cur = conn.execute("SELECT data, user_id FROM jobs WHERE id = %s", (job_id,))
            row = cur.fetchone()
            if not row:
                return None
            data_val, job_user = row
            if user_id is not None:
                if job_user and job_user != user_id:
                    return None
                if not job_user and user_id != "default":
                    return None
            cur_logs = conn.execute(
                "SELECT at, sheet, message FROM (SELECT seq, at, sheet, message FROM job_logs WHERE job_id = %s ORDER BY seq DESC LIMIT 400) AS sub ORDER BY seq ASC",
                (job_id,),
            )
            logs = cur_logs.fetchall()
        job = data_val if isinstance(data_val, dict) else json.loads(data_val)
        sheets = job.get("sheets") or []
        if len(sheets) == 1 and sheets[0].get("name"):
            job["filename"] = sheets[0]["name"]
        elif job.get("filename"):
            job["filename"] = job["filename"].removesuffix(".json").removesuffix(".xlsx")
            if job["filename"] in ("all_topics", "tong-hop"):
                job["filename"] = "Tất cả chủ đề"
        elif not job.get("filename") and sheets:
            job["filename"] = sheets[0].get("name") or "Phân tích"
        else:
            job["filename"] = job.get("filename") or "Phân tích"
        job["logs"] = [{"at": at, "sheet": sheet, "message": message} for at, sheet, message in logs]
        return job

    def list_jobs(self, user_id: Optional[str] = None, limit: int = 500) -> List[Dict[str, Any]]:
        with ro() as conn:
            if user_id and user_id != "default":
                cur = conn.execute(
                    "SELECT data FROM jobs WHERE user_id = %s ORDER BY created_at DESC LIMIT %s",
                    (user_id, limit),
                )
            else:
                cur = conn.execute(
                    "SELECT data FROM jobs WHERE user_id = 'default' OR user_id IS NULL ORDER BY created_at DESC LIMIT %s",
                    (limit,),
                )
            rows = cur.fetchall()
        jobs = []
        for (data_val,) in rows:
            try:
                j = data_val if isinstance(data_val, dict) else json.loads(data_val)
                sheets = j.get("sheets") or []
                total_sheets = len(sheets)
                completed_sheets = sum(1 for s in sheets if s.get("status") in ("completed", "failed"))
                total_topics = sum(len(s.get("topics") or []) for s in sheets)
                fn = j.get("filename") or ""
                if len(sheets) == 1 and sheets[0].get("name"):
                    fn = sheets[0]["name"]
                elif fn:
                    fn = fn.removesuffix(".json").removesuffix(".xlsx")
                    if fn in ("all_topics", "tong-hop"):
                        fn = "Tất cả chủ đề"
                elif not fn and sheets:
                    fn = sheets[0].get("name") or "Phân tích"
                else:
                    fn = "Phân tích"
                jobs.append({
                    "id": j.get("id"),
                    "status": j.get("status"),
                    "filename": fn,
                    "created_at": j.get("created_at"),
                    "finished_at": j.get("finished_at"),
                    "current_sheet": j.get("current_sheet"),
                    "total_sheets": total_sheets,
                    "completed_sheets": completed_sheets,
                    "total_topics": total_topics,
                })
            except Exception:
                pass
        return jobs

    def delete(self, job_id: str, user_id: Optional[str] = None) -> bool:
        with tx() as conn:
            if user_id and user_id != "default":
                cur = conn.execute("SELECT id FROM jobs WHERE id = %s AND user_id = %s", (job_id, user_id))
            else:
                cur = conn.execute("SELECT id FROM jobs WHERE id = %s AND (user_id IS NULL OR user_id = 'default')", (job_id,))
            if not cur.fetchone():
                return False
            conn.execute("DELETE FROM jobs WHERE id = %s", (job_id,))
            return True
