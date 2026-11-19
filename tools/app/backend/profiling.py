"""Centralized stdlib-only backend profiling, instrumentation, and isolated context benchmarks.

Usage:
    python3 tools/app/backend/profiling.py --context db
    python3 tools/app/backend/profiling.py --context http,supervisor --iterations 20
    python3 tools/app/backend/profiling.py --context all --cprofile
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from contextvars import ContextVar
import cProfile
from dataclasses import dataclass, field
import http.client
import io
import json
import os
from pathlib import Path
import pstats
import resource
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import tracemalloc
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple

WORKSPACE = Path(__file__).resolve().parents[3]
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

ALL_CONTEXTS = ("db", "http", "supervisor", "worker", "video")
SLOW_SQL_MS = 20.0


def _parse_bool(val: Optional[str]) -> bool:
    return (val or "").strip().lower() in {"1", "true", "yes", "on"}


def _parse_contexts(val: Optional[str]) -> set[str]:
    raw = (val or "").strip().lower()
    if not raw or raw == "all":
        return set(ALL_CONTEXTS)
    return {c.strip() for c in raw.split(",") if c.strip() in ALL_CONTEXTS}


ENABLED = _parse_bool(os.environ.get("PROFILE_BACKEND"))
ACTIVE_CONTEXTS: set[str] = _parse_contexts(os.environ.get("PROFILE_CONTEXTS"))


def configure(enabled: Optional[bool] = None, contexts: Optional[str] = None) -> None:
    """Update runtime profiling flags (useful for benchmarks and tests)."""
    global ENABLED, ACTIVE_CONTEXTS
    if enabled is not None:
        ENABLED = enabled
    if contexts is not None:
        ACTIVE_CONTEXTS = _parse_contexts(contexts)


def is_enabled(context: Optional[str] = None) -> bool:
    if not ENABLED:
        return False
    if context is None:
        return True
    return context in ACTIVE_CONTEXTS


def rss_kb() -> int:
    """Return process max RSS in kilobytes (normalizing macOS bytes vs Linux KB)."""
    usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(usage // 1024) if sys.platform == "darwin" else int(usage)


@dataclass
class ScopeStats:
    name: str
    context: str
    sql_count: int = 0
    sql_ms: float = 0.0
    pool_wait_ms: float = 0.0
    blob_count: int = 0
    blob_ms: float = 0.0
    blob_bytes: int = 0
    spans: List[Tuple[str, float]] = field(default_factory=list)


_CURRENT_SCOPE: ContextVar[Optional[ScopeStats]] = ContextVar("profiling_scope", default=None)
_ACTIVE_COLLECTOR: Optional["MetricsCollector"] = None


class MetricsCollector:
    """Thread-safe collector for benchmark iterations."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.samples: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}

    def add(self, context: str, name: str, elapsed_ms: float, scope: Optional[ScopeStats] = None, rss_delta_kb: int = 0) -> None:
        entry = {
            "ms": elapsed_ms,
            "sql_count": scope.sql_count if scope else 0,
            "sql_ms": scope.sql_ms if scope else 0.0,
            "blob_count": scope.blob_count if scope else 0,
            "blob_bytes": scope.blob_bytes if scope else 0,
            "rss_delta_kb": rss_delta_kb,
        }
        with self._lock:
            self.samples.setdefault((context, name), []).append(entry)

    def format_markdown(self) -> str:
        lines = [
            "| Context | Operation | N | p50 (ms) | p95 (ms) | max (ms) | Avg SQL | SQL (ms) | Blob (KB) | RSS Δ (KB) |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
        with self._lock:
            items = sorted(self.samples.items(), key=lambda kv: (kv[0][0], kv[0][1]))
        for (ctx, name), rows in items:
            times = sorted(r["ms"] for r in rows)
            n = len(times)
            p50 = statistics.median(times)
            p95 = times[min(n - 1, max(0, int(0.95 * n) - 1))] if n > 1 else times[0]
            mx = times[-1]
            avg_sql = sum(r["sql_count"] for r in rows) / n
            avg_sql_ms = sum(r["sql_ms"] for r in rows) / n
            avg_blob_kb = sum(r["blob_bytes"] for r in rows) / n / 1024.0
            max_rss = max(r["rss_delta_kb"] for r in rows)
            lines.append(
                f"| `{ctx}` | `{name}` | {n} | {p50:.2f} | {p95:.2f} | {mx:.2f} | "
                f"{avg_sql:.1f} | {avg_sql_ms:.2f} | {avg_blob_kb:.1f} | {max_rss} |"
            )
        return "\n".join(lines)


@contextmanager
def span(context: str, name: str) -> Iterator[None]:
    """Time a named operation when profiling is enabled for `context`."""
    if not is_enabled(context) and _ACTIVE_COLLECTOR is None:
        yield
        return
    t0 = time.perf_counter()
    try:
        yield
    finally:
        ms = (time.perf_counter() - t0) * 1000.0
        scope = _CURRENT_SCOPE.get()
        if scope is not None:
            scope.spans.append((f"{context}:{name}", ms))
        if _ACTIVE_COLLECTOR is not None:
            _ACTIVE_COLLECTOR.add(context, name, ms, scope=None)
        elif is_enabled(context):
            sys.stderr.write(f"[profile:{context}] {name} {ms:.2f}ms\n")


@contextmanager
def request_scope(method: str, path: str, context: str = "http") -> Iterator[Optional[ScopeStats]]:
    """Aggregate SQL, blob, and RSS deltas for one HTTP request or benchmark unit."""
    if not is_enabled(context) and _ACTIVE_COLLECTOR is None:
        yield None
        return
    scope = ScopeStats(name=f"{method} {path}", context=context)
    token = _CURRENT_SCOPE.set(scope)
    rss0 = rss_kb()
    t0 = time.perf_counter()
    try:
        yield scope
    finally:
        ms = (time.perf_counter() - t0) * 1000.0
        rss_delta = max(0, rss_kb() - rss0)
        _CURRENT_SCOPE.reset(token)
        if _ACTIVE_COLLECTOR is not None:
            _ACTIVE_COLLECTOR.add(context, scope.name, ms, scope=scope, rss_delta_kb=rss_delta)
        elif is_enabled(context):
            sys.stderr.write(
                f"[profile:{context}] {scope.name} total={ms:.2f}ms "
                f"sql={scope.sql_count} ({scope.sql_ms:.2f}ms, wait={scope.pool_wait_ms:.2f}ms) "
                f"blob={scope.blob_count} ({scope.blob_ms:.2f}ms, {scope.blob_bytes}B) "
                f"rss_delta={rss_delta}KB\n"
            )


def record_sql(sql: str, elapsed_ms: float, pool_wait_ms: float = 0.0) -> None:
    scope = _CURRENT_SCOPE.get()
    if scope is not None:
        scope.sql_count += 1
        scope.sql_ms += elapsed_ms
        scope.pool_wait_ms += pool_wait_ms
    if is_enabled("db") and elapsed_ms >= SLOW_SQL_MS and _ACTIVE_COLLECTOR is None:
        snippet = " ".join(sql.split())[:100]
        sys.stderr.write(f"[profile:db:slow] {elapsed_ms:.2f}ms (wait={pool_wait_ms:.2f}ms) {snippet}\n")


def record_blob(op: str, key: str, size_bytes: int, elapsed_ms: float) -> None:
    scope = _CURRENT_SCOPE.get()
    if scope is not None:
        scope.blob_count += 1
        scope.blob_ms += elapsed_ms
        scope.blob_bytes += max(0, int(size_bytes))
    if is_enabled() and _ACTIVE_COLLECTOR is None and elapsed_ms >= SLOW_SQL_MS:
        sys.stderr.write(f"[profile:blob] {op} {key} {size_bytes}B {elapsed_ms:.2f}ms\n")


def profile_callable(fn: Callable[..., Any], *args: Any, top_n: int = 15, **kwargs: Any) -> Tuple[Any, str, float]:
    """Run `fn` under cProfile and tracemalloc, returning (result, pstats_text, peak_kb)."""
    prof = cProfile.Profile()
    tracemalloc.start()
    try:
        prof.enable()
        result = fn(*args, **kwargs)
        prof.disable()
        _cur, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    buf = io.StringIO()
    pstats.Stats(prof, stream=buf).sort_stats("cumtime").print_stats(top_n)
    return result, buf.getvalue(), peak / 1024.0


# -- Isolated Context Benchmarks ---------------------------------------------
def _setup_test_env(dsn: Optional[str] = None) -> str:
    target_dsn = dsn or os.environ.get("TEST_DATABASE_URL") or "postgresql://postgres:postgres@localhost:5432/aibrand_test"
    os.environ["DATABASE_URL"] = target_dsn
    os.environ.setdefault("BLOB_ENDPOINT", "http://localhost:9000")
    os.environ["BLOB_BUCKET"] = os.environ.get("TEST_BLOB_BUCKET", "test-aibrand")
    os.environ.setdefault("BLOB_ACCESS_KEY", "rustfsadmin")
    os.environ.setdefault("BLOB_SECRET_KEY", "rustfsadmin")
    os.environ.setdefault("BLOB_REGION", "us-east-1")
    from tools.app.backend import blobs
    from tools.app.backend.db import close_pools, init_schema

    blobs.reset_client()
    close_pools()
    init_schema(target_dsn)
    return target_dsn


def _seed_db_fixtures(user_id: str = "prof_user") -> Dict[str, Any]:
    from tools.app.backend.credits import CREDIT_STORE
    from tools.app.backend.profiles import PROFILE_STORE
    from tools.app.backend.store import JobStore, now_iso

    store = JobStore()
    job_id = "deadbeef0001"
    sheets = [
        {
            "name": f"Topic {i}",
            "slug": f"topic-{i}",
            "status": "completed",
            "targets": 2,
            "target_list": [{"name": "Chan", "url": "https://www.facebook.com/test"}],
            "reels": 2,
            "topics": [
                {
                    "title": f"Idea {i}-{j}",
                    "video_url": "https://example.com/v.mp4",
                    "transcript": "Sample transcript text",
                    "views": 1000 * (j + 1),
                }
                for j in range(3)
            ],
        }
        for i in range(4)
    ]
    with __import__("tools.app.backend.db", fromlist=["tx"]).tx() as conn:
        conn.execute("DELETE FROM jobs WHERE user_id = %s", (user_id,))
        conn.execute("DELETE FROM profiles WHERE user_id = %s", (user_id,))
        conn.execute("DELETE FROM topics WHERE user_id = %s", (user_id,))
    store.put({
        "id": job_id,
        "job_kind": "profile",
        "client_id": "prof-client",
        "user_id": user_id,
        "status": "running",
        "filename": "bench.xlsx",
        "created_at": now_iso(),
        "sheets": sheets,
    })
    for idx in range(10):
        PROFILE_STORE.upsert_topic(
            f"Bench Topic {idx}",
            [{"name": f"Channel {idx}-{k}", "url": f"https://www.facebook.com/chan_{idx}_{k}"} for k in range(3)],
            user_id=user_id,
        )
    CREDIT_STORE.grant(user_id, 1_000_000, reason="profile_seed")
    return {"job_id": job_id, "user_id": user_id}


def run_db_context(iterations: int, collector: MetricsCollector) -> List[str]:
    from tools.app.backend.credits import CREDIT_STORE
    from tools.app.backend.db import ro
    from tools.app.backend.profiles import PROFILE_STORE
    from tools.app.backend.store import JobStore

    fx = _seed_db_fixtures()
    store = JobStore()
    uid, jid = fx["user_id"], fx["job_id"]

    ops = [
        ("JobStore.snapshot", lambda: store.snapshot(jid, user_id=uid)),
        ("JobStore.list_jobs", lambda: store.list_jobs(user_id=uid)),
        ("JobStore.update", lambda: store.update(jid, current_sheet="Topic 0")),
        ("ProfileStore.list_topics", lambda: PROFILE_STORE.list_topics(user_id=uid)),
        ("CreditStore.get_balance", lambda: CREDIT_STORE.get_balance(uid)),
    ]
    for name, fn in ops:
        for _ in range(iterations):
            with request_scope("DB", name, context="db"):
                fn()

    explain_notes: List[str] = []
    with ro() as conn:
        for label, sql, params in [
            ("jobs_list", "EXPLAIN (ANALYZE, BUFFERS) SELECT id, status FROM jobs WHERE user_id = %s ORDER BY created_at DESC LIMIT 50", (uid,)),
            ("profiles_by_user", "EXPLAIN (ANALYZE, BUFFERS) SELECT name, url FROM profiles WHERE user_id = %s AND topic_slug = %s", (uid, "bench-topic-0")),
        ]:
            rows = conn.execute(sql, params).fetchall()
            plan_tail = " | ".join(r[0] for r in rows[-2:])
            explain_notes.append(f"- `{label}`: {plan_tail}")
    return explain_notes


def run_http_context(iterations: int, collector: MetricsCollector) -> None:
    from tools.app.backend.server import BoundedHTTPServer, Handler

    fx = _seed_db_fixtures()
    uid, jid = fx["user_id"], fx["job_id"]
    server = BoundedHTTPServer(("127.0.0.1", 0), Handler, max_workers=8)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    headers = {"X-User-Id": uid, "X-User-Email": "prof@example.com", "X-Client-Id": "profclient1"}
    routes = [
        ("GET", "/api/health"),
        ("GET", "/api/jobs"),
        ("GET", f"/api/jobs/{jid}"),
        ("GET", "/api/sources/topics"),
        ("GET", "/api/credits"),
        ("GET", "/api/logs"),
    ]
    try:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        for method, path in routes:
            for _ in range(iterations):
                conn.request(method, path, headers=headers)
                resp = conn.getresponse()
                resp.read()
        conn.close()
    finally:
        server.shutdown()
        server.server_close()


def run_supervisor_context(iterations: int, collector: MetricsCollector) -> None:
    from tools.app.backend.store import JobStore

    fx = _seed_db_fixtures()
    store = JobStore()
    jid = fx["job_id"]
    for _ in range(iterations):
        with request_scope("SUPERVISOR", "tick", context="supervisor"):
            store.heartbeat([jid])
            store.stale_running(30)
            store.control_state(jid)
            store.claim(1)


def run_worker_context(iterations: int, collector: MetricsCollector, live: bool = False) -> None:
    from tools.app.backend.research_engine import keyword_search, reel_research

    sample_reels = [
        {
            "video_id": f"vid{i}",
            "url": f"https://www.facebook.com/reel/1000{i}",
            "title": f"Sample Viral Reel {i}",
            "views": 10000 * (i + 1),
            "velocity_per_hour": 500.0,
            "current_pool": 3,
            "author_handle": f"creator{i}",
            "transcript": "Sample transcript",
        }
        for i in range(6)
    ]

    orig_glasser = keyword_search._glasser_run_json
    if not live:
        def _fake_glasser(provider, endpoint, version, payload, cache_dir, task_id=None, timeout=45.0):
            time.sleep(0.01)
            return {"videos": [{"id": "yt1", "title": "Demo", "url": "https://youtube.com/watch?v=1", "viewCountInt": 5000}]}, "cache", None
        keyword_search._glasser_run_json = _fake_glasser

    try:
        with tempfile.TemporaryDirectory(prefix="prof-worker-") as tmp:
            run_dir = Path(tmp)
            for _ in range(max(1, min(iterations, 5))):
                with request_scope("WORKER", "keyword_search", context="worker"):
                    keyword_search.run_viral_video_search("gyno conditions", run_dir, options={})
                with request_scope("WORKER", "heuristic_topics", context="worker"):
                    reel_research.heuristic_topics("Bench Sheet", sample_reels)
    finally:
        keyword_search._glasser_run_json = orig_glasser


def run_video_context(iterations: int, collector: MetricsCollector, live: bool = False) -> None:
    from tools.app.backend import video_engine
    from tools.app.backend.video_jobs import VideoJobStore

    fx = _seed_db_fixtures()
    uid = fx["user_id"]
    vstore = VideoJobStore()
    for _ in range(iterations):
        with request_scope("VIDEO", "get_duration_and_prompt", context="video"):
            video_engine.get_video_duration()
            video_engine.build_prompt("Test video prompt")
        with request_scope("VIDEO", "claim_next_pending", context="video"):
            vstore.claim_next_pending()

    if live or __import__("shutil").which("ffmpeg"):
        with tempfile.TemporaryDirectory(prefix="prof-video-") as tmp:
            src = Path(tmp) / "in.mp4"
            dst = Path(tmp) / "out.mp4"
            gen = subprocess.run(
                ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=360x640:d=1", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", "1", str(src)],
                capture_output=True,
            )
            if gen.returncode == 0:
                with request_scope("VIDEO", "normalize_video_1s", context="video"):
                    video_engine.normalize_video(src, dst)


def run_contexts(
    contexts: List[str],
    iterations: int = 10,
    live: bool = False,
    dsn: Optional[str] = None,
    use_cprofile: bool = False,
) -> Dict[str, Any]:
    global _ACTIVE_COLLECTOR
    _setup_test_env(dsn)
    configure(enabled=True, contexts=",".join(contexts))
    collector = MetricsCollector()
    _ACTIVE_COLLECTOR = collector
    explain_notes: List[str] = []
    cprofile_text = ""

    def _exec() -> None:
        if "db" in contexts:
            explain_notes.extend(run_db_context(iterations, collector))
        if "http" in contexts:
            run_http_context(iterations, collector)
        if "supervisor" in contexts:
            run_supervisor_context(iterations, collector)
        if "worker" in contexts:
            run_worker_context(iterations, collector, live=live)
        if "video" in contexts:
            run_video_context(iterations, collector, live=live)

    try:
        if use_cprofile:
            _, cprofile_text, peak_kb = profile_callable(_exec)
        else:
            _exec()
            peak_kb = 0.0
    finally:
        _ACTIVE_COLLECTOR = None
        configure(enabled=False)

    return {
        "table": collector.format_markdown(),
        "explain": explain_notes,
        "cprofile": cprofile_text,
        "peak_kb": peak_kb,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Profile tools/app/backend in isolated contexts")
    parser.add_argument("--context", default="db", help="Comma-separated: db,http,supervisor,worker,video,all")
    parser.add_argument("--iterations", type=int, default=10, help="Iterations per operation (default: 10)")
    parser.add_argument("--live", action="store_true", help="Allow live Glasser/external calls in worker/video contexts")
    parser.add_argument("--cprofile", action="store_true", help="Attach cProfile + tracemalloc summary")
    parser.add_argument("--dsn", default=None, help="Override Postgres DSN (defaults to TEST_DATABASE_URL)")
    args = parser.parse_args()

    selected = list(ALL_CONTEXTS) if args.context.strip().lower() == "all" else [
        c.strip() for c in args.context.split(",") if c.strip() in ALL_CONTEXTS
    ]
    if not selected:
        raise SystemExit(f"No valid contexts in {args.context!r}. Choose from {', '.join(ALL_CONTEXTS)}, all.")

    t0 = time.perf_counter()
    res = run_contexts(selected, iterations=args.iterations, live=args.live, dsn=args.dsn, use_cprofile=args.cprofile)
    elapsed = time.perf_counter() - t0
    print(f"# Backend Profile ({', '.join(selected)}) — {elapsed:.2f}s\n")
    print(res["table"])
    if res["explain"]:
        print("\n## EXPLAIN (ANALYZE, BUFFERS)\n" + "\n".join(res["explain"]))
    if res["cprofile"]:
        print(f"\n## cProfile (tracemalloc peak: {res['peak_kb']:.1f} KB)\n```text\n{res['cprofile']}```")


if __name__ == "__main__":
    from tools.app.backend.profiling import main as _pkg_main
    _pkg_main()
