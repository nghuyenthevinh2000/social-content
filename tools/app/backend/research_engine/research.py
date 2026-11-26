"""Excel ingestion, per-sheet pipeline orchestration and ACP topic suggestions."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import json
import logging
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
import uuid
from typing import Any, Callable, Dict, List, Optional, Tuple

from tools.app.backend import blobs
from tools.app.backend.telemetry import profiling
from tools.app.backend.acp import ACPClient, ACPError
from tools.app.backend.errors import (
    AppError,
    ErrorAggregator,
    ErrorCategory,
    ErrorSeverity,
    handle_acp_error,
    handle_glasser_error,
)
from tools.app.backend.profiles import (
    _normalize_target,
    clean_name,
    facebook_handle,
    is_facebook_url,
    parse_sheets_input,
    parse_workbook,
    slugify,
    SocialProfileStore,
    PROFILE_STORE,
    RUNS_ROOT,
)
from tools.loop.viral_analyzer.glasser import ensure_glasser_env
from tools.loop.viral_analyzer.keyword_research.pipeline import run_viral_video_search
from tools.loop.viral_analyzer.profile_research.pipeline import (
    run_analyzer_pipeline,
    run_profile_research,
)
from tools.loop.viral_analyzer.runtime import submit_with_context
from tools.loop.viral_analyzer.video_research.pipeline import (
    analyze_video_structure,
    build_video_structure_prompt,
    format_director_prompt,
    heuristic_video_analyses,
    is_reel_url,
    normalize_video_analyses,
    parse_video_analyses,
    research_reels,
    research_single_reel,
)
from tools.app.backend.store import JobStore, now_iso
from tools.app.backend.video_engine import get_video_duration

logger = logging.getLogger("research")
ensure_glasser_env()

_facebook_handle = facebook_handle
_is_facebook_url = is_facebook_url
_clean_name = clean_name

WORKSPACE = Path(__file__).resolve().parents[4]

AGENT_PRESETS: List[Dict[str, Any]] = [
    {
        "id": "agy",
        "label": "Antigravity (agy)",
        "command": ["agy", "acp"],
        "detect": "agy",
        "login_hint": "agy",
        "note": "Gemini/Antigravity CLI ở chế độ ACP.",
    },
    {
        "id": "opencode",
        "label": "OpenCode",
        "command": ["opencode", "acp"],
        "detect": "opencode",
        "login_hint": "opencode auth login",
        "note": "Agent mặc định trong repo.",
    },
    {
        "id": "claude",
        "label": "Claude Code",
        "command": ["npx", "-y", "@zed-industries/claude-code-acp"],
        "detect": "npx",
        "login_hint": "claude",
        "note": "Lần đầu sẽ tải ACP adapter qua npx.",
    },
    {
        "id": "codex",
        "label": "Codex",
        "command": ["npx", "-y", "@zed-industries/codex-acp"],
        "detect": "npx",
        "login_hint": "codex login",
        "note": "Lần đầu sẽ tải ACP adapter qua npx.",
    },
]


_MACHO_MAGICS = {
    b"\xcf\xfa\xed\xfe",
    b"\xce\xfa\xed\xfe",
    b"\xfe\xed\xfa\xcf",
    b"\xfe\xed\xfa\xce",
    b"\xca\xfe\xba\xbe",
}
_ELF_MAGIC = b"\x7fELF"


def _check_agent_binary(binary_name: str) -> Tuple[bool, Optional[str]]:
    """Verify binary exists in PATH and matches the host OS executable format."""
    if binary_name == "agy" and os.environ.get("AGY_HOST_BRIDGE", "").strip():
        return True, None
    resolved = shutil.which(binary_name)
    if not resolved:
        return False, None
    if os.path.isfile(resolved):
        try:
            with open(resolved, "rb") as fh:
                magic = fh.read(4)
        except OSError:
            return True, None
        if sys.platform.startswith("linux") and magic in _MACHO_MAGICS:
            return (
                False,
                f"Binary '{binary_name}' tại {resolved} là định dạng macOS (Mach-O), "
                f"không thể chạy trong container Linux (Exec format error).",
            )
        if sys.platform == "darwin" and magic == _ELF_MAGIC:
            return (
                False,
                f"Binary '{binary_name}' tại {resolved} là định dạng Linux (ELF), "
                f"không thể chạy trên macOS (Exec format error).",
            )
    return True, None


def configured_agent() -> Dict[str, Any]:
    """Harness from VIRAL_APP_AGENT, else the first installed preset."""
    agent_id = os.environ.get("VIRAL_APP_AGENT")
    if agent_id:
        try:
            return resolve_agent(agent_id)
        except ACPError:
            pass
    for preset in AGENT_PRESETS:
        if _check_agent_binary(preset["detect"])[0]:
            return resolve_agent(preset["id"])
    raise ACPError("Không tìm thấy harness nào trên máy (agy, opencode, claude, codex).")


def resolve_agent(agent_id: str, model: Optional[str] = None) -> Dict[str, Any]:
    for preset in AGENT_PRESETS:
        if preset["id"] == agent_id:
            ok, reason = _check_agent_binary(preset["detect"])
            if not ok:
                raise ACPError(
                    reason
                    or (
                        f"Không tìm thấy harness '{preset['label']}' trên máy. "
                        f"Cài đặt rồi thử lại (gợi ý đăng nhập: {preset['login_hint']})."
                    )
                )
            result = dict(preset)
            if agent_id == "agy":
                selected_model = (model or os.environ.get("VIRAL_APP_AGY_MODEL", "")).strip()
                if selected_model:
                    result["model"] = selected_model
                    result["command"] = ["agy", "--model", selected_model, "acp"]
            return result
    raise ACPError(f"Harness không hợp lệ: {agent_id}")


@contextmanager
def _harness_lock(log: Callable[[str], None]):
    """One harness session across all workers: serialized via Postgres advisory lock."""
    import psycopg
    from tools.app.backend.db import get_dsn

    with psycopg.connect(get_dsn(), autocommit=True) as conn:
        with profiling.span("worker", "acp_lock_wait"):
            cur = conn.execute("SELECT pg_try_advisory_lock(hashtext('harness_lock'))")
            got_lock = cur.fetchone()[0]
            if not got_lock:
                log("Harness đang bận với job khác; chờ tới lượt...")
                conn.execute("SELECT pg_advisory_lock(hashtext('harness_lock'))")
        try:
            yield
        finally:
            try:
                conn.execute("SELECT pg_advisory_unlock(hashtext('harness_lock'))")
            except Exception:
                pass


# -- Jobs --------------------------------------------------------------------
STORE = JobStore()


def create_job(
    source_bytes: bytes,
    filename: str,
    options: Dict[str, Any],
    client_id: str,
    user_id: Optional[str] = None,
    job_kind: str = "profile",
) -> Dict[str, Any]:
    job_id = uuid.uuid4().hex[:12]
    sheets = parse_sheets_input(source_bytes)
    if job_kind == "reel" and sheets:
        first = dict(sheets[0])
        first["targets"] = list(first.get("targets") or [])[:1]
        sheets = [first]
    if len(sheets) == 1 and sheets[0].get("name"):
        filename = sheets[0]["name"]
    elif filename:
        filename = filename.removesuffix(".json").removesuffix(".xlsx")
    actor_prof = options.get("actor_profile")
    if not actor_prof and user_id:
        try:
            from tools.app.backend.user_profile import USER_PROFILE_STORE
            actor_prof = USER_PROFILE_STORE.get_profile(user_id)
        except Exception:
            actor_prof = None
    job = {
        "id": job_id,
        "job_kind": job_kind if job_kind in {"profile", "reel", "keyword"} else "profile",
        "client_id": client_id,
        "user_id": user_id,
        "actor_profile": actor_prof,
        "status": "queued",
        "filename": filename,
        "agent": options.get("agent"),
        "options": options,
        "created_at": now_iso(),
        "finished_at": None,
        "current_sheet": None,
        "cancel_requested": False,
        "sheets": [
            {
                "name": sheet["name"],
                "slug": sheet["slug"],
                "status": "pending",
                "targets": len(sheet["targets"]),
                "target_list": [
                    {
                        "name": t.get("name") or t.get("handle") or "",
                        "url": t.get("url") or "",
                        **({"author_handle": t["author_handle"]} if t.get("author_handle") else {}),
                        **({"author_name": t["author_name"]} if t.get("author_name") else {}),
                    }
                    for t in sheet["targets"]
                ],
                "reels": 0,
                "pool_distribution": {},
                "topics": [],
                "error": None,
                "notice": None,
                "started_at": None,
                "finished_at": None,
            }
            for sheet in sheets
        ],
        "logs": [],
    }
    STORE.put(job)
    STORE.log(job_id, f"Đã đọc {len(sheets)} sheet từ {filename}.")
    return STORE.snapshot(job_id) or job


def run_job(job: Dict[str, Any]) -> None:
    job_id, options = job["id"], job["options"]
    actor_profile = job.get("actor_profile") or options.get("actor_profile")
    if not actor_profile and job.get("user_id"):
        try:
            from tools.app.backend.user_profile import USER_PROFILE_STORE
            actor_profile = USER_PROFILE_STORE.get_profile(job["user_id"])
        except Exception:
            actor_profile = None
    with tempfile.TemporaryDirectory(prefix=f"job-{job_id}-") as tmpdir:
        run_dir = Path(tmpdir)
        try:
            sheets = [
                {
                    "name": s["name"],
                    "slug": s["slug"],
                    "is_aggregate": s["slug"] == "tong-hop",
                    "targets": [
                        {
                            **_normalize_target(t.get("url", ""), name=t.get("name", ""), category=s["name"]),
                            **({"author_handle": t["author_handle"]} if t.get("author_handle") else {}),
                            **({"author_name": t["author_name"]} if t.get("author_name") else {}),
                        }
                        for t in s.get("target_list", [])
                        if t.get("url")
                    ],
                }
                for s in job.get("sheets", [])
            ]
            for index, sheet in enumerate(sheets, 1):
                cur_job = STORE.snapshot(job_id)
                if not cur_job or cur_job.get("cancel_requested"):
                    STORE.update(job_id, status="cancelled", finished_at=now_iso())
                    STORE.log(job_id, "Đã dừng theo yêu cầu.")
                    return
                _process_sheet(
                    job_id,
                    index,
                    len(sheets),
                    sheet,
                    run_dir,
                    options,
                    actor_profile=actor_profile,
                    job_kind=job.get("job_kind") or "profile",
                    user_id=job.get("user_id") or "default",
                )
            final_snap = STORE.snapshot(job_id) or {}
            final_sheets = final_snap.get("sheets") or []
            all_failed = bool(final_sheets) and all(s.get("status") == "failed" for s in final_sheets)
            final_status = "failed" if all_failed else "completed"
            STORE.update(job_id, status=final_status, current_sheet=None, finished_at=now_iso())
            STORE.log(job_id, "Job thất bại." if all_failed else "Hoàn tất toàn bộ sheet.")
        except Exception as exc:  # keep the job inspectable on unexpected failure
            STORE.update(job_id, status="failed", finished_at=now_iso(), current_sheet=None)
            STORE.log(job_id, f"Lỗi job: {exc}")


_ACTION_BY_JOB_KIND = {
    "keyword": "keyword_search",
    "reel": "reel_research",
    "profile": "profile_research",
}


def _process_sheet(
    job_id: str,
    index: int,
    total: int,
    sheet: Dict[str, Any],
    run_dir: Path,
    options: Dict[str, Any],
    actor_profile: Optional[Dict[str, Any]] = None,
    job_kind: str = "profile",
    user_id: str = "default",
) -> None:
    from tools.app.backend.telemetry import cost_control

    action = _ACTION_BY_JOB_KIND.get(job_kind, "profile_research")
    with cost_control.cost_scope(user_id=user_id, action=action, job_id=job_id, sheet_slug=sheet["slug"]) as cscope:
        _process_sheet_inner(
            job_id=job_id,
            index=index,
            total=total,
            sheet=sheet,
            run_dir=run_dir,
            options=options,
            actor_profile=actor_profile,
            job_kind=job_kind,
            cscope=cscope,
        )


def _process_sheet_inner(
    job_id: str,
    index: int,
    total: int,
    sheet: Dict[str, Any],
    run_dir: Path,
    options: Dict[str, Any],
    actor_profile: Optional[Dict[str, Any]] = None,
    job_kind: str = "profile",
    cscope: Optional[Any] = None,
) -> None:
    sheet_name = sheet["name"]
    STORE.update(job_id, current_sheet=sheet_name)
    STORE.patch_sheet(job_id, sheet["slug"], status="running", started_at=now_iso())
    STORE.log(job_id, f"[{index}/{total}] Bắt đầu sheet '{sheet_name}' ({len(sheet['targets'])} mục tiêu).", sheet_name)

    def log(message: str) -> None:
        STORE.log(job_id, message, sheet_name)

    reels: List[Dict[str, Any]] = []
    topics: List[Dict[str, Any]] = []
    queries: List[Dict[str, str]] = []
    creators: List[Dict[str, Any]] = []
    error: Optional[str] = None
    notice: Optional[str] = None
    source_breakdown: Dict[str, Any] = {}
    pool_distribution: Dict[str, Any] = {}
    aggregator = ErrorAggregator(job_id=job_id)

    targets = sheet.get("targets", [])

    agent_choice = options.get("agent") or os.environ.get("VIRAL_APP_AGENT") or "agy"
    try:
        resolve_agent(agent_choice)
    except ACPError:
        for preset in AGENT_PRESETS:
            if _check_agent_binary(preset["detect"])[0]:
                agent_choice = preset["id"]
                break

    user_language = (actor_profile or {}).get("language") or options.get("language") or "vi"

    if job_kind == "keyword":
        log(f"Tìm kiếm video viral đa nền tảng cho từ khoá: '{sheet_name}'")
        provided_queries = [
            {
                "kind": "original" if idx == 0 else "expanded",
                "text": (t.get("name") or t.get("url") or "").strip(),
            }
            for idx, t in enumerate(targets)
            if (t.get("name") or t.get("url") or "").strip()
        ]
        kw_res = run_viral_video_search(
            keyword=sheet_name,
            run_dir=run_dir,
            options={**options, "agent": agent_choice, "language": user_language},
            log=log,
            job_id=job_id,
            aggregator=aggregator,
            queries=provided_queries or None,
        )
        queries = kw_res.get("queries", [])
        reels = kw_res.get("reels", [])
        creators = kw_res.get("creators", [])
        source_breakdown = kw_res.get("source_breakdown", {})
        error = kw_res.get("error")
        notice = kw_res.get("notice")
        topics = []
    elif job_kind == "reel":
        log("Chạy Reel Research trực tiếp cho 1 video (bỏ qua profile scraper).")
        reel_targets = []
        for t in targets:
            t_url = t.get("url", "")
            if is_reel_url(t_url):
                reel_targets.append((
                    t_url,
                    t.get("name") or sheet_name,
                    t.get("author_handle") or "",
                    t.get("author_name") or "",
                ))
                break
            else:
                log(f"Bỏ qua URL không phải bài viết/video/Reel trực tiếp: {t_url}")

        def _analyze_one_reel(
            t_idx: int, t_url: str, t_name: str, t_author_handle: str = "", t_author_name: str = ""
        ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
            log(f"[{t_idx}/{len(reel_targets)}] Đang phân tích Reel: {t_url}")
            try:
                res = research_single_reel(
                    reel_url=t_url,
                    sheet_name=t_name,
                    actor_profile=actor_profile,
                    agent_id=agent_choice,
                    model=options.get("agy_model") or options.get("model"),
                    log=log,
                    cwd=run_dir,
                    timeout_sec=float(options.get("acp_timeout", 180)),
                    language=user_language,
                    author_handle=t_author_handle or None,
                    author_name=t_author_name or None,
                )
                return res, None
            except Exception as exc:
                log(f"Lỗi khi phân tích Reel {t_url}: {exc}")
                return None, str(exc)

        outcomes = [
            (t_url, t_name, _analyze_one_reel(1, t_url, t_name, t_author_handle, t_author_name))
            for t_url, t_name, t_author_handle, t_author_name in reel_targets
        ]

        for t_url, t_name, (res, err) in outcomes:
            if err is not None:
                error = err
                continue
            if res and res.get("topics"):
                topics.extend(res["topics"])
            if res:
                reels.append({
                    "url": res.get("reel_url") or t_url,
                    "reel_url": res.get("reel_url") or t_url,
                    "video_id": res.get("video_id") or "",
                    "title": t_name,
                    "transcript": res.get("transcript") or "",
                    "visual": res.get("visual") or "",
                    "platform": res.get("platform") or "facebook",
                })

        if not topics and not error:
            notice = "Không trích xuất được chủ đề nào từ danh sách Reel này."
    else:
        # Standard Profile Research across creator/competitor pages: surface 48h viral reels only
        prof_res = run_profile_research(
            targets=targets,
            run_dir=run_dir,
            options={**options, "transcribe": False},
            log=log,
            job_id=job_id,
            sheet_slug=sheet["slug"],
            pipeline_fn=run_analyzer_pipeline,
            aggregator=aggregator,
        )
        reels = prof_res.get("reels", [])
        pool_distribution = prof_res.get("pool_distribution", {})
        source_breakdown = prof_res.get("source_breakdown", {})
        error = prof_res.get("error")
        notice = prof_res.get("notice")

        ranked_reels = sorted(
            reels,
            key=lambda r: (
                int(r.get("views") or 0),
                float(r.get("velocity_per_hour") or 0),
                int(r.get("current_pool") or 0),
            ),
            reverse=True,
        )
        topics = []
        for r in ranked_reels:
            r_url = str(r.get("url") or r.get("reel_url") or "").strip()
            r_plat = str(r.get("platform") or "facebook").strip() or "facebook"
            r_handle = str(r.get("author_handle") or "").strip()
            r_title = str(r.get("title") or "").strip() or f"Video từ @{r_handle or 'reel'}"
            topics.append({
                "title": r_title[:90],
                "hook": "",
                "angle": "",
                "why_viral": "",
                "outline": [],
                "format": "",
                "source_urls": [r_url] if r_url else [],
                "reel_url": r_url,
                "platform": r_plat,
                "video_url": r.get("video_url"),
                "video_id": str(r.get("video_id") or ""),
                "views": int(r.get("views") or 0),
                "velocity_per_hour": float(r.get("velocity_per_hour") or 0),
                "current_pool": r.get("current_pool", 0),
                "pool_name": str(r.get("pool_name") or ""),
                "likes": int(r.get("likes") or 0),
                "comments": int(r.get("comments") or 0),
                "shares": int(r.get("shares") or 0),
                "author_handle": r_handle,
                "author_name": str(r.get("author_name") or ""),
                "transcript": "",
                "visual": "",
                "generated_by": "profile",
            })

    STORE.patch_sheet(
        job_id,
        sheet["slug"],
        reels=len(reels),
        pool_distribution=pool_distribution,
        source_breakdown=source_breakdown,
    )

    cost_summary = cscope.to_dict() if cscope is not None else {}
    result = {
        "sheet": sheet_name,
        "targets": targets,
        "reels": reels,
        "queries": queries,
        "creators": creators,
        "source_breakdown": source_breakdown,
        "topics": topics,
        "cost_summary": cost_summary,
        "error": error,
        "notice": notice,
        "errors": [e.to_dict() for e in aggregator.all_errors()],
    }
    result_path = run_dir / "sheets" / sheet["slug"] / "result.json"
    result_path.parent.mkdir(parents=True, exist_ok=True)
    res_bytes = json.dumps(result, ensure_ascii=False, indent=2).encode("utf-8")
    result_path.write_bytes(res_bytes)
    blobs.put(f"runs/{job_id}/result.json", res_bytes, content_type="application/json")

    STORE.patch_sheet(
        job_id,
        sheet["slug"],
        status="failed" if error else "completed",
        error=error,
        notice=notice,
        topics=topics,
        queries=queries,
        creators=creators,
        source_breakdown=source_breakdown,
        cost_summary=cost_summary,
        finished_at=now_iso(),
    )
    if topics or creators:
        STORE.log(job_id, f"Xong sheet '{sheet_name}': {len(reels)} reel, {len(topics)} chủ đề.", sheet_name)
    else:
        STORE.log(job_id, f"Xong sheet '{sheet_name}': 0 reel. {notice or error or ''}".strip(), sheet_name)
