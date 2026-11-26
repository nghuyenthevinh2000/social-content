"""Centralized cost control, endpoint policy guards, budget circuit breakers, and PostgreSQL cost ledger.

Always active in production (independent of opt-in `profiling.py`).
Usage:
    python3 tools/app/backend/telemetry/cost_control.py [--user <uid>] [--action <act>] [--days 7]
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import contextvars
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import json
import logging
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
from typing import Any, Callable, Dict, Iterable, Iterator, List, Optional, Tuple

WORKSPACE = Path(__file__).resolve().parents[4]
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from tools.app.backend.db import ro, tx
from tools.app.backend.telemetry.constants import (
    ACTION_POLICIES,
    ActionPolicy,
    CHARGE_RE,
    DEFAULT_ACTION,
    DEFAULT_GLASSER_TIMEOUT_SEC,
    DEFAULT_REPORT_DAYS,
    DEFAULT_SUMMARY_DAYS,
    DEFAULT_USER_AGE,
    DEFAULT_USER_GENDER,
    DEFAULT_USER_ID,
    HTTP_STATUS_RE,
    MAX_CHARGE_CLAUSE_LEN,
    MICRO_PER_USD,
    RECENT_RUNS_LIMIT,
    RUN_ID_RE,
    RUN_URL_RE,
    TRANSCRIPT_ENDPOINT_PLATFORMS,
    TRANSCRIPT_ENDPOINTS,
    WASTED_CALLS_LIMIT,
)
from tools.loop.viral_analyzer.platforms import get_platform

logger = logging.getLogger(__name__)


class CostPolicyError(RuntimeError):
    """Raised when an API call violates endpoint allowlist, URL guard, or action budget."""


@dataclass
class CostScope:
    user_id: str
    action: str
    job_id: Optional[str] = None
    sheet_slug: Optional[str] = None
    api_calls: int = 0
    transcript_calls: int = 0
    cache_hits: int = 0
    wasted_calls: int = 0
    cost_micro: int = 0
    run_urls: List[str] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)

    def to_dict(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "user_id": self.user_id,
                "action": self.action,
                "job_id": self.job_id,
                "sheet_slug": self.sheet_slug,
                "api_calls": self.api_calls,
                "transcript_calls": self.transcript_calls,
                "cache_hits": self.cache_hits,
                "wasted_calls": self.wasted_calls,
                "cost_micro": self.cost_micro,
                "cost_usd": round(self.cost_micro / MICRO_PER_USD, 6),
                "run_urls": list(self.run_urls),
            }


_CURRENT_COST_SCOPE: ContextVar[Optional[CostScope]] = ContextVar("cost_scope", default=None)


def current_cost_scope() -> Optional[CostScope]:
    return _CURRENT_COST_SCOPE.get()


@contextmanager
def cost_scope(
    user_id: str,
    action: str,
    job_id: Optional[str] = None,
    sheet_slug: Optional[str] = None,
) -> Iterator[CostScope]:
    scope = CostScope(
        user_id=user_id or DEFAULT_USER_ID,
        action=action or DEFAULT_ACTION,
        job_id=job_id,
        sheet_slug=sheet_slug,
    )
    token = _CURRENT_COST_SCOPE.set(scope)
    try:
        yield scope
    finally:
        _CURRENT_COST_SCOPE.reset(token)


def submit_with_context(executor: Any, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Submit a callable to a ThreadPoolExecutor preserving the current ContextVars."""
    ctx = contextvars.copy_context()
    return executor.submit(ctx.run, fn, *args, **kwargs)


def _matches_platform_transcript_url(platform: str, url: str) -> bool:
    if not url:
        return False
    spec = get_platform(platform)
    return bool(spec and spec.transcript_url_re and spec.transcript_url_re.match(url.strip()))


def is_valid_facebook_transcript_url(url: str) -> bool:
    return _matches_platform_transcript_url("facebook", url)


def is_valid_youtube_transcript_url(url: str) -> bool:
    return _matches_platform_transcript_url("youtube", url)


def is_valid_tiktok_transcript_url(url: str) -> bool:
    return _matches_platform_transcript_url("tiktok", url)


def is_valid_instagram_transcript_url(url: str) -> bool:
    return _matches_platform_transcript_url("instagram", url)


def parse_glasser_stdout(text: str) -> Dict[str, Any]:
    """Parse Glasser CLI stdout/stderr for Run ID, Run URL, HTTP status, and exact Decimal Charge."""
    raw = text or ""
    run_id_m = RUN_ID_RE.search(raw)
    run_url_m = RUN_URL_RE.search(raw)
    status_m = HTTP_STATUS_RE.search(raw)
    charge_m = CHARGE_RE.search(raw)

    run_id = run_id_m.group(1).strip() if run_id_m else None
    run_url = run_url_m.group(1).strip() if run_url_m else None
    http_status = int(status_m.group(1)) if status_m else None

    cost_micro = 0
    charge_clause = None
    if charge_m:
        try:
            dec = Decimal(charge_m.group(1))
            cost_micro = int((dec * Decimal(MICRO_PER_USD)).quantize(Decimal("1")))
        except (InvalidOperation, ValueError):
            cost_micro = 0
        if charge_m.group(2):
            charge_clause = charge_m.group(2).strip()

    charge_usd = f"{Decimal(cost_micro) / Decimal(MICRO_PER_USD):.6f}"
    wasted = (http_status is not None and http_status >= 400) or (
        charge_clause == "NO_RESULT" and cost_micro > 0
    )

    return {
        "run_id": run_id,
        "run_url": run_url,
        "http_status": http_status,
        "cost_micro": cost_micro,
        "charge_usd": charge_usd,
        "charge_clause": charge_clause,
        "wasted": wasted,
    }


def record_cost_event(
    provider: str,
    endpoint: str,
    cost_micro: int = 0,
    cache_hit: bool = False,
    wasted: bool = False,
    sub_action: Optional[str] = None,
    run_id: Optional[str] = None,
    run_url: Optional[str] = None,
    http_status: Optional[int] = 200,
    charge_clause: Optional[str] = None,
    duration_ms: float = 0.0,
    user_id: Optional[str] = None,
    action: Optional[str] = None,
    job_id: Optional[str] = None,
    sheet_slug: Optional[str] = None,
) -> None:
    """Update active CostScope counters and persist a cost_events row to PostgreSQL."""
    scope = current_cost_scope()
    eff_user_id = user_id or (scope.user_id if scope else DEFAULT_USER_ID)
    eff_action = action or (scope.action if scope else DEFAULT_ACTION)
    eff_job_id = job_id if job_id is not None else (scope.job_id if scope else None)
    eff_sheet_slug = sheet_slug if sheet_slug is not None else (scope.sheet_slug if scope else None)
    eff_cost = int(cost_micro or 0)
    charge_usd = f"{Decimal(eff_cost) / Decimal(MICRO_PER_USD):.6f}"

    if scope is not None:
        with scope._lock:
            if cache_hit:
                scope.cache_hits += 1
            elif http_status != 403:
                scope.api_calls += 1
                if endpoint in TRANSCRIPT_ENDPOINTS:
                    scope.transcript_calls += 1
            if wasted:
                scope.wasted_calls += 1
            scope.cost_micro += eff_cost
            if run_url and run_url not in scope.run_urls:
                scope.run_urls.append(run_url)

    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        with tx() as conn:
            conn.execute(
                """
                INSERT INTO cost_events (
                    user_id, action, sub_action, job_id, sheet_slug,
                    provider, endpoint, run_id, run_url, http_status,
                    cache_hit, wasted, cost_micro, charge_usd, charge_clause,
                    duration_ms, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    eff_user_id,
                    eff_action,
                    sub_action,
                    eff_job_id,
                    eff_sheet_slug,
                    provider,
                    endpoint,
                    run_id,
                    run_url,
                    http_status,
                    bool(cache_hit),
                    bool(wasted),
                    eff_cost,
                    charge_usd,
                    charge_clause,
                    float(duration_ms or 0.0),
                    created_at,
                ),
            )
    except Exception as exc:
        logger.debug("Failed to persist cost_event (%s %s): %s", provider, endpoint, exc)


_POLICY_LOCK = threading.Lock()


def register_action(
    action: str,
    allowed_endpoints: Iterable[Tuple[str, str]],
    *,
    max_calls: Optional[int] = None,
    max_transcript_calls: Optional[int] = None,
    max_cost_micro: Optional[int] = None,
) -> ActionPolicy:
    """Register or update an action's allowed (provider, endpoint) pairs and budget limits."""
    name = (action or "").strip()
    if not name:
        raise ValueError("action name must be non-empty")
    policy = ActionPolicy(
        allowed_endpoints=frozenset((str(p), str(e)) for p, e in allowed_endpoints),
        max_calls=max_calls,
        max_transcript_calls=max_transcript_calls,
        max_cost_micro=max_cost_micro,
    )
    with _POLICY_LOCK:
        ACTION_POLICIES[name] = policy
    return policy


def get_action_policy(action: str) -> Optional[ActionPolicy]:
    """Return the registered ActionPolicy for `action`, if any."""
    with _POLICY_LOCK:
        return ACTION_POLICIES.get(action)


def check_call_allowed(
    provider: str,
    endpoint: str,
    payload: Optional[Dict[str, Any]] = None,
    sub_action: Optional[str] = None,
    raise_on_block: bool = True,
) -> Tuple[bool, str]:
    """Enforce URL guards, registered action/endpoint allowlists, and per-action budget circuit breakers."""
    reason: Optional[str] = None

    platform_entry = TRANSCRIPT_ENDPOINT_PLATFORMS.get(endpoint)
    if platform_entry is not None:
        platform_key, plat_label = platform_entry
        url = str((payload or {}).get("url") or "").strip()
        if not _matches_platform_transcript_url(platform_key, url):
            reason = f"Blocked non-{plat_label} URL for transcript endpoint: {url or '<empty>'}"

    scope = current_cost_scope()
    if reason is None and scope is not None:
        policy = get_action_policy(scope.action)
        if policy is None:
            reason = f"Unregistered action {scope.action!r}; register it in ACTION_POLICIES or via register_action()"
        elif (provider, endpoint) not in policy.allowed_endpoints:
            reason = f"Endpoint ({provider}, {endpoint}) is not allowed for action {scope.action!r}"

        if reason is None and policy is not None:
            with scope._lock:
                if policy.max_calls is not None and scope.api_calls >= policy.max_calls:
                    reason = f"Budget exceeded for {scope.action}: api_calls={scope.api_calls} >= {policy.max_calls}"
                elif (
                    endpoint in TRANSCRIPT_ENDPOINTS
                    and policy.max_transcript_calls is not None
                    and scope.transcript_calls >= policy.max_transcript_calls
                ):
                    reason = (
                        f"Transcript budget exceeded for {scope.action}: "
                        f"transcript_calls={scope.transcript_calls} >= {policy.max_transcript_calls}"
                    )
                elif policy.max_cost_micro is not None and scope.cost_micro >= policy.max_cost_micro:
                    reason = f"Cost budget exceeded for {scope.action}: cost_micro={scope.cost_micro} >= {policy.max_cost_micro}"

    if reason is not None:
        record_cost_event(
            provider=provider,
            endpoint=endpoint,
            cost_micro=0,
            cache_hit=False,
            wasted=True,
            sub_action=sub_action or "policy_blocked",
            http_status=403,
            charge_clause=reason[:MAX_CHARGE_CLAUSE_LEN],
        )
        if raise_on_block:
            raise CostPolicyError(reason)
        return False, reason

    return True, "ok"


def run_glasser_tracked(
    provider: str,
    endpoint: str,
    version: int,
    payload: Dict[str, Any],
    idempotency_key: str,
    out_file: Path,
    task_id: Optional[str] = None,
    timeout: float = DEFAULT_GLASSER_TIMEOUT_SEC,
    sub_action: Optional[str] = None,
) -> Dict[str, Any]:
    """Run Glasser CLI under policy/budget guards, parse stdout Charge/Run URL, and record cost_events."""
    check_call_allowed(provider, endpoint, payload=payload, sub_action=sub_action, raise_on_block=True)

    glasser_bin = shutil.which("glasser")
    if not glasser_bin:
        return {
            "ok": False,
            "not_found": True,
            "returncode": -1,
            "stdout": "",
            "stderr": "glasser binary not found",
            "out_file": Path(out_file),
            "run_id": None,
            "run_url": None,
            "http_status": None,
            "cost_micro": 0,
            "charge_usd": "0.000000",
            "charge_clause": None,
            "wasted": False,
        }

    out_path = Path(out_file)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        glasser_bin,
        "run",
        "-p",
        provider,
        "-e",
        endpoint,
        "-i",
        json.dumps(payload, ensure_ascii=False),
        "--endpoint-version",
        str(version),
        "--idempotency-key",
        idempotency_key,
        "-o",
        str(out_path),
    ]
    if task_id:
        cmd.extend(["--task", task_id])

    t0 = time.perf_counter()
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    duration_ms = (time.perf_counter() - t0) * 1000.0

    combined_output = f"{proc.stdout or ''}\n{proc.stderr or ''}".strip()
    parsed = parse_glasser_stdout(combined_output)
    http_status = parsed["http_status"]
    if http_status is None:
        http_status = 200 if proc.returncode == 0 else 500
        parsed["http_status"] = http_status

    record_cost_event(
        provider=provider,
        endpoint=endpoint,
        cost_micro=parsed["cost_micro"],
        cache_hit=False,
        wasted=parsed["wasted"],
        sub_action=sub_action,
        run_id=parsed["run_id"],
        run_url=parsed["run_url"],
        http_status=http_status,
        charge_clause=parsed["charge_clause"],
        duration_ms=duration_ms,
    )

    return {
        "ok": proc.returncode == 0,
        "not_found": False,
        "returncode": proc.returncode,
        "stdout": proc.stdout or "",
        "stderr": proc.stderr or "",
        "out_file": out_path,
        **parsed,
    }


class CostControlStore:
    """Query interface for per-user, per-action, per-endpoint, and per-job cost reporting."""

    @staticmethod
    def _cutoff_iso(days: int) -> str:
        dt = datetime.now(timezone.utc) - timedelta(days=max(1, int(days)))
        return dt.isoformat(timespec="seconds")

    def get_user_summary(self, user_id: str, days: int = DEFAULT_SUMMARY_DAYS) -> Dict[str, Any]:
        cutoff = self._cutoff_iso(days)
        with ro() as conn:
            prof_row = conn.execute(
                "SELECT name, gender, age FROM user_profiles WHERE user_id = %s",
                (user_id,),
            ).fetchone()
            cred_row = conn.execute(
                "SELECT balance FROM user_credits WHERE user_id = %s",
                (user_id,),
            ).fetchone()

            action_rows = conn.execute(
                """
                SELECT action,
                       COUNT(DISTINCT NULLIF(job_id, '')) AS jobs_count,
                       COUNT(*) FILTER (WHERE NOT cache_hit AND COALESCE(http_status, 200) <> 403) AS api_calls,
                       COUNT(*) FILTER (WHERE cache_hit) AS cache_hits,
                       COUNT(*) FILTER (WHERE wasted) AS wasted_calls,
                       COALESCE(SUM(cost_micro), 0) AS cost_micro
                FROM cost_events
                WHERE user_id = %s AND created_at >= %s
                GROUP BY action
                ORDER BY cost_micro DESC, action ASC
                """,
                (user_id, cutoff),
            ).fetchall()

            endpoint_rows = conn.execute(
                """
                SELECT provider, endpoint,
                       COUNT(*) FILTER (WHERE NOT cache_hit AND COALESCE(http_status, 200) <> 403) AS api_calls,
                       COUNT(*) FILTER (WHERE cache_hit) AS cache_hits,
                       COUNT(*) FILTER (WHERE wasted) AS wasted_calls,
                       COALESCE(SUM(cost_micro), 0) AS cost_micro
                FROM cost_events
                WHERE user_id = %s AND created_at >= %s
                GROUP BY provider, endpoint
                ORDER BY cost_micro DESC, provider ASC, endpoint ASC
                """,
                (user_id, cutoff),
            ).fetchall()

            recent_rows = conn.execute(
                """
                SELECT id, action, sub_action, job_id, sheet_slug, provider, endpoint,
                       run_id, run_url, http_status, cache_hit, wasted, cost_micro,
                       charge_usd, charge_clause, duration_ms, created_at
                FROM cost_events
                WHERE user_id = %s AND created_at >= %s
                ORDER BY id DESC
                LIMIT %s
                """,
                (user_id, cutoff, RECENT_RUNS_LIMIT),
            ).fetchall()

        credit_balance_micro = int(cred_row[0]) if cred_row and cred_row[0] is not None else 0
        user_profile = {
            "user_id": user_id,
            "name": prof_row[0] if prof_row else None,
            "gender": prof_row[1] if prof_row else DEFAULT_USER_GENDER,
            "age": int(prof_row[2]) if prof_row and prof_row[2] is not None else DEFAULT_USER_AGE,
            "credit_balance_usd": round(credit_balance_micro / MICRO_PER_USD, 6),
        }

        by_action = []
        for r in action_rows:
            jobs_count = int(r[1] or 0)
            cost_micro = int(r[5] or 0)
            cost_usd = round(cost_micro / MICRO_PER_USD, 6)
            avg_cost = round(cost_usd / jobs_count, 6) if jobs_count > 0 else cost_usd
            by_action.append({
                "action": r[0],
                "jobs_count": jobs_count,
                "api_calls": int(r[2] or 0),
                "cache_hits": int(r[3] or 0),
                "wasted_calls": int(r[4] or 0),
                "cost_micro": cost_micro,
                "cost_usd": cost_usd,
                "avg_cost_per_job_usd": avg_cost,
            })

        by_endpoint = [
            {
                "provider": r[0],
                "endpoint": r[1],
                "api_calls": int(r[2] or 0),
                "cache_hits": int(r[3] or 0),
                "wasted_calls": int(r[4] or 0),
                "cost_micro": int(r[5] or 0),
                "cost_usd": round(int(r[5] or 0) / MICRO_PER_USD, 6),
            }
            for r in endpoint_rows
        ]

        recent_runs = [
            {
                "id": r[0],
                "action": r[1],
                "sub_action": r[2],
                "job_id": r[3],
                "sheet_slug": r[4],
                "provider": r[5],
                "endpoint": r[6],
                "run_id": r[7],
                "run_url": r[8],
                "http_status": r[9],
                "cache_hit": bool(r[10]),
                "wasted": bool(r[11]),
                "cost_micro": int(r[12] or 0),
                "charge_usd": r[13],
                "charge_clause": r[14],
                "duration_ms": float(r[15] or 0.0),
                "created_at": r[16],
            }
            for r in recent_rows
        ]

        return {
            "days": days,
            "user_profile": user_profile,
            "by_action": by_action,
            "by_endpoint": by_endpoint,
            "recent_runs": recent_runs,
        }

    def get_all_users_summary(self, days: int = DEFAULT_SUMMARY_DAYS) -> List[Dict[str, Any]]:
        cutoff = self._cutoff_iso(days)
        with ro() as conn:
            rows = conn.execute(
                """
                SELECT ce.user_id,
                       COALESCE(up.name, ce.user_id) AS name,
                       COALESCE(uc.balance, 0) AS credit_balance_micro,
                       COUNT(*) FILTER (WHERE NOT ce.cache_hit AND COALESCE(ce.http_status, 200) <> 403) AS api_calls,
                       COUNT(*) FILTER (WHERE ce.cache_hit) AS cache_hits,
                       COUNT(*) FILTER (WHERE ce.wasted) AS wasted_calls,
                       COALESCE(SUM(ce.cost_micro), 0) AS cost_micro
                FROM cost_events ce
                LEFT JOIN user_profiles up ON up.user_id = ce.user_id
                LEFT JOIN user_credits uc ON uc.user_id = ce.user_id
                WHERE ce.created_at >= %s
                GROUP BY ce.user_id, up.name, uc.balance
                ORDER BY cost_micro DESC, ce.user_id ASC
                """,
                (cutoff,),
            ).fetchall()
        return [
            {
                "user_id": r[0],
                "name": r[1],
                "credit_balance_usd": round(int(r[2] or 0) / MICRO_PER_USD, 6),
                "api_calls": int(r[3] or 0),
                "cache_hits": int(r[4] or 0),
                "wasted_calls": int(r[5] or 0),
                "cost_micro": int(r[6] or 0),
                "cost_usd": round(int(r[6] or 0) / MICRO_PER_USD, 6),
            }
            for r in rows
        ]

    def get_job_summary(self, job_id: str) -> Dict[str, Any]:
        with ro() as conn:
            rows = conn.execute(
                """
                SELECT action, sheet_slug, provider, endpoint, run_url,
                       http_status, cache_hit, wasted, cost_micro
                FROM cost_events
                WHERE job_id = %s
                ORDER BY id ASC
                """,
                (job_id,),
            ).fetchall()
        api_calls = 0
        cache_hits = 0
        wasted_calls = 0
        cost_micro = 0
        run_urls: List[str] = []
        for r in rows:
            if r[6]:
                cache_hits += 1
            elif r[5] != 403:
                api_calls += 1
            if r[7]:
                wasted_calls += 1
            cost_micro += int(r[8] or 0)
            if r[4] and r[4] not in run_urls:
                run_urls.append(r[4])
        return {
            "job_id": job_id,
            "api_calls": api_calls,
            "cache_hits": cache_hits,
            "wasted_calls": wasted_calls,
            "cost_micro": cost_micro,
            "cost_usd": round(cost_micro / MICRO_PER_USD, 6),
            "run_urls": run_urls,
        }


COST_STORE = CostControlStore()


def format_cost_report(
    days: int = DEFAULT_REPORT_DAYS,
    user_id: Optional[str] = None,
    action: Optional[str] = None,
) -> str:
    """Query cost_events and render Markdown tables for users, actions, endpoints, and wasted/blocked calls."""
    cutoff = CostControlStore._cutoff_iso(days)
    where_clauses = ["ce.created_at >= %s"]
    params: List[Any] = [cutoff]
    if user_id:
        where_clauses.append("ce.user_id = %s")
        params.append(user_id)
    if action:
        where_clauses.append("ce.action = %s")
        params.append(action)
    where_sql = " AND ".join(where_clauses)

    with ro() as conn:
        user_rows = conn.execute(
            f"""
            SELECT ce.user_id, COALESCE(up.name, ce.user_id),
                   COUNT(*) FILTER (WHERE NOT ce.cache_hit AND COALESCE(ce.http_status, 200) <> 403),
                   COUNT(*) FILTER (WHERE ce.cache_hit),
                   COUNT(*) FILTER (WHERE ce.wasted),
                   COALESCE(SUM(ce.cost_micro), 0)
            FROM cost_events ce
            LEFT JOIN user_profiles up ON up.user_id = ce.user_id
            WHERE {where_sql}
            GROUP BY ce.user_id, up.name
            ORDER BY 6 DESC
            """,
            tuple(params),
        ).fetchall()

        action_rows = conn.execute(
            f"""
            SELECT ce.action,
                   COUNT(DISTINCT NULLIF(ce.job_id, '')),
                   COUNT(*) FILTER (WHERE NOT ce.cache_hit AND COALESCE(ce.http_status, 200) <> 403),
                   COUNT(*) FILTER (WHERE ce.cache_hit),
                   COUNT(*) FILTER (WHERE ce.wasted),
                   COALESCE(SUM(ce.cost_micro), 0)
            FROM cost_events ce
            WHERE {where_sql}
            GROUP BY ce.action
            ORDER BY 6 DESC
            """,
            tuple(params),
        ).fetchall()

        endpoint_rows = conn.execute(
            f"""
            SELECT ce.provider, ce.endpoint,
                   COUNT(*) FILTER (WHERE NOT ce.cache_hit AND COALESCE(ce.http_status, 200) <> 403),
                   COUNT(*) FILTER (WHERE ce.cache_hit),
                   COUNT(*) FILTER (WHERE ce.wasted),
                   COALESCE(SUM(ce.cost_micro), 0)
            FROM cost_events ce
            WHERE {where_sql}
            GROUP BY ce.provider, ce.endpoint
            ORDER BY 6 DESC
            """,
            tuple(params),
        ).fetchall()

        wasted_rows = conn.execute(
            f"""
            SELECT ce.created_at, ce.user_id, ce.action, ce.endpoint,
                   ce.http_status, ce.charge_usd, ce.charge_clause, ce.run_url
            FROM cost_events ce
            WHERE {where_sql} AND ce.wasted = TRUE
            ORDER BY ce.id DESC
            LIMIT %s
            """,
            tuple(params) + (WASTED_CALLS_LIMIT,),
        ).fetchall()

    sections = [
        f"## 1. Spend per User Profile (last {days}d)",
        "| User ID | Name | API Calls | Cache Hits | Wasted | Cost (USD) |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for r in user_rows:
        sections.append(f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} | {r[4]} | ${int(r[5] or 0) / MICRO_PER_USD:.6f} |")
    if not user_rows:
        sections.append("| - | - | 0 | 0 | 0 | $0.000000 |")

    sections.extend([
        "",
        f"## 2. Spend per Action (last {days}d)",
        "| Action | Jobs | API Calls | Cache Hits | Wasted | Cost (USD) |",
        "|---|---:|---:|---:|---:|---:|",
    ])
    for r in action_rows:
        sections.append(f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} | {r[4]} | ${int(r[5] or 0) / MICRO_PER_USD:.6f} |")
    if not action_rows:
        sections.append("| - | 0 | 0 | 0 | 0 | $0.000000 |")

    sections.extend([
        "",
        f"## 3. Endpoint Cache Efficiency (last {days}d)",
        "| Provider | Endpoint | API Calls | Cache Hits | Hit Rate | Wasted | Cost (USD) |",
        "|---|---|---:|---:|---:|---:|---:|",
    ])
    for r in endpoint_rows:
        total = int(r[2] or 0) + int(r[3] or 0)
        hit_rate = f"{(int(r[3] or 0) / total * 100):.1f}%" if total else "0.0%"
        sections.append(f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} | {hit_rate} | {r[4]} | ${int(r[5] or 0) / MICRO_PER_USD:.6f} |")
    if not endpoint_rows:
        sections.append("| - | - | 0 | 0 | 0.0% | 0 | $0.000000 |")

    sections.extend([
        "",
        f"## 4. Wasted / Blocked Call Audit (last {days}d)",
        "| Created At | User | Action | Endpoint | HTTP | Charge | Clause / Reason | Run URL |",
        "|---|---|---|---|---:|---|---|---|",
    ])
    for r in wasted_rows:
        sections.append(
            f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} | {r[4] or '-'} | ${r[5]} | {r[6] or '-'} | {r[7] or '-'} |"
        )
    if not wasted_rows:
        sections.append("| - | - | - | - | - | $0.000000 | None | - |")

    return "\n".join(sections)


def main() -> int:
    parser = argparse.ArgumentParser(description="AIBrand cost_events reporter")
    parser.add_argument("--user", dest="user_id", default=None, help="Filter by user_id")
    parser.add_argument("--action", dest="action", default=None, help="Filter by action")
    parser.add_argument("--days", type=int, default=DEFAULT_REPORT_DAYS, help="Lookback window in days")
    args = parser.parse_args()
    print(format_cost_report(days=args.days, user_id=args.user_id, action=args.action))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
