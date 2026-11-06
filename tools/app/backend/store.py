"""SQLite-backed job state shared by the API and worker processes."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import time
from typing import Any, Callable, Dict, List, Optional


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class JobStore:
    """SQLite-backed job state shared by the API and any number of worker processes."""

    # ponytail: SQLite on a shared local disk; swap for Postgres/Firestore when API and workers run on different hosts.
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._tx() as db:
            db.execute("CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, status TEXT NOT NULL, created_at TEXT NOT NULL, data TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS logs (seq INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT NOT NULL, at TEXT, sheet TEXT, message TEXT)")
            db.execute("CREATE INDEX IF NOT EXISTS logs_job ON logs (job_id, seq)")
            columns = {row[1] for row in db.execute("PRAGMA table_info(jobs)")}
            for column, kind in (("client_id", "TEXT"), ("heartbeat", "REAL")):
                if column not in columns:
                    db.execute(f"ALTER TABLE jobs ADD COLUMN {column} {kind}")
        db = sqlite3.connect(path)
        db.execute("PRAGMA journal_mode=WAL")
        db.close()

    @contextmanager
    def _tx(self):
        db = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        try:
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.execute("COMMIT")
        except BaseException:
            if db.in_transaction:
                db.execute("ROLLBACK")
            raise
        finally:
            db.close()

    @staticmethod
    def _write(db: sqlite3.Connection, job: Dict[str, Any]) -> None:
        db.execute("UPDATE jobs SET status = ?, data = ? WHERE id = ?", (job["status"], json.dumps(job, ensure_ascii=False), job["id"]))

    def _mutate(self, job_id: str, change: Callable[[Dict[str, Any]], None]) -> bool:
        with self._tx() as db:
            row = db.execute("SELECT data FROM jobs WHERE id = ?", (job_id,)).fetchone()
            if not row:
                return False
            job = json.loads(row[0])
            change(job)
            self._write(db, job)
            return True

    def put(self, job: Dict[str, Any]) -> None:
        data = {k: v for k, v in job.items() if k != "logs"}
        with self._tx() as db:
            db.execute(
                "INSERT INTO jobs (id, status, created_at, client_id, data) VALUES (?, ?, ?, ?, ?)",
                (job["id"], job["status"], job["created_at"], job.get("client_id"), json.dumps(data, ensure_ascii=False)),
            )

    def update(self, job_id: str, **changes: Any) -> None:
        self._mutate(job_id, lambda job: job.update(changes))

    def patch_sheet(self, job_id: str, slug: str, **changes: Any) -> None:
        def change(job: Dict[str, Any]) -> None:
            for sheet in job["sheets"]:
                if sheet["slug"] == slug:
                    sheet.update(changes)
                    return

        self._mutate(job_id, change)

    def log(self, job_id: str, message: str, sheet: Optional[str] = None) -> None:
        with self._tx() as db:
            db.execute("INSERT INTO logs (job_id, at, sheet, message) VALUES (?, ?, ?, ?)", (job_id, now_iso(), sheet, message))

    def cancel(self, job_id: str) -> bool:
        return self._mutate(job_id, lambda job: job.update(cancel_requested=True))

    def claim(self, max_per_client: int) -> Optional[Dict[str, Any]]:
        """Atomically take the oldest queued job whose client is under its running limit, and mark it running.

        Skipping busy clients is what keeps one client's backlog from starving the others.
        """
        with self._tx() as db:
            row = db.execute(
                "SELECT data FROM jobs AS q WHERE status = 'queued' AND "
                "(SELECT COUNT(*) FROM jobs AS r WHERE r.status = 'running' AND r.client_id IS q.client_id) < ? "
                "ORDER BY created_at, rowid LIMIT 1",
                (max_per_client,),
            ).fetchone()
            if not row:
                return None
            job = json.loads(row[0])
            job["status"] = "running"
            self._write(db, job)
            db.execute("UPDATE jobs SET heartbeat = ? WHERE id = ?", (time.time(), job["id"]))
            return job

    def heartbeat(self, job_ids: List[str]) -> None:
        with self._tx() as db:
            db.executemany("UPDATE jobs SET heartbeat = ? WHERE id = ?", [(time.time(), job_id) for job_id in job_ids])

    def stale_running(self, max_age_sec: float) -> List[str]:
        """Running jobs no worker has touched recently, i.e. their worker died."""
        with self._tx() as db:
            rows = db.execute(
                "SELECT id FROM jobs WHERE status = 'running' AND (heartbeat IS NULL OR heartbeat < ?)",
                (time.time() - max_age_sec,),
            ).fetchall()
        return [row[0] for row in rows]

    def snapshot(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self._tx() as db:
            row = db.execute("SELECT data FROM jobs WHERE id = ?", (job_id,)).fetchone()
            if not row:
                return None
            logs = db.execute(
                "SELECT at, sheet, message FROM (SELECT * FROM logs WHERE job_id = ? ORDER BY seq DESC LIMIT 400) ORDER BY seq",
                (job_id,),
            ).fetchall()
        job = json.loads(row[0])
        job["logs"] = [{"at": at, "sheet": sheet, "message": message} for at, sheet, message in logs]
        return job

