"""Job scheduling: fair queue across clients, one child process per job, kill on Stop."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import multiprocessing
import os
from pathlib import Path
import shutil
import signal
import tempfile
import threading
import time
from typing import Any, Dict, Optional

from tools.app.backend import blobs
from tools.app.backend.db import tx
from tools.app.backend.research import STORE, run_job
from tools.app.backend.store import now_iso

MAX_PROCESSES = int(os.environ.get("VIRAL_APP_MAX_PROCESSES", "2"))
MAX_PER_CLIENT = int(os.environ.get("VIRAL_APP_MAX_PER_CLIENT", "1"))
STALE_AFTER_SEC = 30


def sweep_stale_temp_dirs(max_age_sec: float = 86400) -> None:
    temp_root = Path(tempfile.gettempdir())
    cutoff = time.time() - max_age_sec
    for p in temp_root.glob("job-*"):
        try:
            if p.is_dir() and p.stat().st_mtime < cutoff:
                shutil.rmtree(p, ignore_errors=True)
        except Exception:
            pass


def purge_expired() -> None:
    """Purge completed/failed/cancelled jobs and video jobs older than RETENTION_DAYS."""
    retention_days = int(os.environ.get("RETENTION_DAYS", "30"))
    cutoff = (datetime.now(timezone.utc) - timedelta(days=retention_days)).isoformat()

    expired_job_ids = []
    with tx() as conn:
        cur = conn.execute(
            "SELECT id FROM jobs WHERE status IN ('completed', 'failed', 'cancelled') AND created_at < %s FOR UPDATE",
            (cutoff,),
        )
        expired_job_ids = [r[0] for r in cur.fetchall()]
        if expired_job_ids:
            conn.execute("DELETE FROM jobs WHERE id = ANY(%s)", (expired_job_ids,))

    for jid in expired_job_ids:
        try:
            blobs.delete_prefix(f"runs/{jid}/")
        except Exception:
            pass

    expired_vjobs = []
    with tx() as conn:
        cur = conn.execute(
            "SELECT id, user_id FROM video_jobs WHERE status IN ('completed', 'failed', 'cancelled') AND created_at < %s FOR UPDATE",
            (cutoff,),
        )
        expired_vjobs = cur.fetchall()
        if expired_vjobs:
            conn.execute("DELETE FROM video_jobs WHERE id = ANY(%s)", ([r[0] for r in expired_vjobs],))

    for jid, uid in expired_vjobs:
        try:
            blobs.delete_prefix(f"videos/{uid}/{jid}/")
        except Exception:
            pass


def run_worker(poll_sec: float = 1.0) -> None:
    """Run up to MAX_PROCESSES jobs at once, at most MAX_PER_CLIENT per client (enforced in the store)."""
    sweep_stale_temp_dirs()
    running: Dict[str, multiprocessing.Process] = {}
    last_purge = 0.0
    while True:
        if time.time() - last_purge >= 3600:
            last_purge = time.time()
            try:
                purge_expired()
            except Exception:
                pass
        STORE.heartbeat(list(running))
        for job_id in STORE.stale_running(STALE_AFTER_SEC):
            _finish_stopped_job(job_id, None)
        for job_id, proc in list(running.items()):
            state = STORE.snapshot(job_id) or {}
            if proc.is_alive() and state.get("cancel_requested") and state.get("pid"):
                _kill_job(proc, state["pid"])
            if not proc.is_alive():
                proc.join()
                _finish_stopped_job(job_id, proc.exitcode)
                del running[job_id]
        while len(running) < MAX_PROCESSES:
            job = STORE.claim(MAX_PER_CLIENT)
            if not job:
                break
            proc = multiprocessing.Process(target=_job_process, args=(job, os.getpid()), daemon=True)
            proc.start()
            running[job["id"]] = proc
        time.sleep(poll_sec)


def _job_process(job: Dict[str, Any], worker_pid: int) -> None:
    os.environ["DB_POOL_MAX"] = "2"
    if hasattr(os, "setsid"):
        # Own process group, so a kill also reaches the agent CLI, ffmpeg and yt-dlp children.
        os.setsid()

        def exit_with_worker() -> None:
            while True:
                time.sleep(1)
                try:
                    os.kill(worker_pid, 0)
                except OSError:
                    os.killpg(0, signal.SIGKILL)

        threading.Thread(target=exit_with_worker, daemon=True).start()
    STORE.update(job["id"], pid=os.getpid())
    run_job(job)


def _kill_job(proc: multiprocessing.Process, pid: int) -> None:
    try:
        if hasattr(os, "killpg"):
            os.killpg(pid, signal.SIGKILL)
        else:
            # ponytail: Windows kills only the job process; agent/ffmpeg children may linger. Use a Job Object if that matters.
            os.kill(pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        pass
    proc.kill()
    proc.join(5)


def _finish_stopped_job(job_id: str, exitcode: Optional[int]) -> None:
    """Close out a job that was killed, crashed, or lost its worker (exitcode None) before recording a final status."""
    state = STORE.snapshot(job_id)
    if not state or state["status"] != "running":
        return
    cancelled = bool(state.get("cancel_requested"))
    if cancelled:
        message = "Đã dừng theo yêu cầu."
    elif exitcode is None:
        message = "Worker xử lý job đã dừng giữa chừng."
    else:
        message = f"Tiến trình job thoát bất thường (mã {exitcode})."
    for sheet in state["sheets"]:
        if sheet["status"] == "running":
            STORE.patch_sheet(job_id, sheet["slug"], status="failed", error=message, finished_at=now_iso())
    STORE.update(job_id, status="cancelled" if cancelled else "failed", current_sheet=None, finished_at=now_iso())
    STORE.log(job_id, message)
