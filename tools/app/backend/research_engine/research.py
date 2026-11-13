"""Excel ingestion, per-sheet pipeline orchestration and ACP topic suggestions."""

from __future__ import annotations

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
    clean_name,
    facebook_handle,
    is_facebook_url,
    parse_workbook,
    resolve_xlsx_bytes,
    slugify,
    SocialProfileStore,
    PROFILE_STORE,
    RUNS_ROOT,
)
from tools.app.backend.research_engine.profile_research import run_profile_research
from tools.app.backend.research_engine.reel_research import (
    build_topic_prompt,
    format_director_prompt,
    heuristic_topics,
    is_reel_url,
    normalize_topics,
    parse_topics,
    research_reels,
    research_single_reel,
    suggest_topics,
)
from tools.app.backend.store import JobStore, now_iso
from tools.app.backend.video_engine import get_video_duration
from tools.loop.viral_analyzer.glasser import ensure_glasser_env
from tools.loop.viral_analyzer.pipeline import run_analyzer_pipeline

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


def configured_agent() -> Dict[str, Any]:
    """Harness from VIRAL_APP_AGENT, else the first installed preset."""
    agent_id = os.environ.get("VIRAL_APP_AGENT")
    if agent_id:
        try:
            return resolve_agent(agent_id)
        except ACPError:
            pass
    for preset in AGENT_PRESETS:
        if shutil.which(preset["detect"]):
            return resolve_agent(preset["id"])
    raise ACPError("Không tìm thấy harness nào trên máy (agy, opencode, claude, codex).")


def resolve_agent(agent_id: str, model: Optional[str] = None) -> Dict[str, Any]:
    for preset in AGENT_PRESETS:
        if preset["id"] == agent_id:
            if shutil.which(preset["detect"]) is None:
                raise ACPError(
                    f"Không tìm thấy harness '{preset['label']}' trên máy. "
                    f"Cài đặt rồi thử lại (gợi ý đăng nhập: {preset['login_hint']})."
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
    xlsx_bytes: bytes,
    filename: str,
    options: Dict[str, Any],
    client_id: str,
    user_id: Optional[str] = None,
    job_kind: str = "profile",
) -> Dict[str, Any]:
    xlsx_bytes, filename = resolve_xlsx_bytes(xlsx_bytes, filename)
    job_id = uuid.uuid4().hex[:12]
    blobs.put(
        f"runs/{job_id}/input.xlsx",
        xlsx_bytes,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    sheets = parse_workbook(xlsx_bytes)
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
        "job_kind": job_kind if job_kind in {"profile", "reel"} else "profile",
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
                    {"name": t.get("name") or t.get("handle") or "", "url": t.get("url") or ""}
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
            input_path = run_dir / "input.xlsx"
            blobs.download(f"runs/{job_id}/input.xlsx", input_path)
            sheets = parse_workbook(input_path)
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
                )
            STORE.update(job_id, status="completed", current_sheet=None, finished_at=now_iso())
            STORE.log(job_id, "Hoàn tất toàn bộ sheet.")
        except Exception as exc:  # keep the job inspectable on unexpected failure
            STORE.update(job_id, status="failed", finished_at=now_iso(), current_sheet=None)
            STORE.log(job_id, f"Lỗi job: {exc}")


def _process_sheet(
    job_id: str,
    index: int,
    total: int,
    sheet: Dict[str, Any],
    run_dir: Path,
    options: Dict[str, Any],
    actor_profile: Optional[Dict[str, Any]] = None,
    job_kind: str = "profile",
) -> None:
    sheet_name = sheet["name"]
    STORE.update(job_id, current_sheet=sheet_name)
    STORE.patch_sheet(job_id, sheet["slug"], status="running", started_at=now_iso())
    STORE.log(job_id, f"[{index}/{total}] Bắt đầu sheet '{sheet_name}' ({len(sheet['targets'])} mục tiêu).", sheet_name)

    def log(message: str) -> None:
        STORE.log(job_id, message, sheet_name)

    reels: List[Dict[str, Any]] = []
    topics: List[Dict[str, Any]] = []
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
            if shutil.which(preset["detect"]):
                agent_choice = preset["id"]
                break

    if job_kind == "reel":
        log(f"Phát hiện {len(targets)} Reel đơn lẻ; chạy Reel Research trực tiếp (bỏ qua profile scraper).")
        for t_idx, target in enumerate(targets, 1):
            t_url = target.get("url", "")
            t_name = target.get("name") or sheet_name
            if not is_reel_url(t_url):
                continue
            log(f"[{t_idx}/{len(targets)}] Đang phân tích Reel: {t_url}")
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
                )
                if res.get("topics"):
                    topics.extend(res["topics"])
                reels.append({
                    "url": res.get("reel_url") or t_url,
                    "reel_url": res.get("reel_url") or t_url,
                    "video_id": res.get("video_id") or "",
                    "title": t_name,
                    "transcript": res.get("transcript") or "",
                    "visual": res.get("visual") or "",
                    "platform": res.get("platform") or "facebook",
                })
            except Exception as exc:
                log(f"Lỗi khi phân tích Reel {t_url}: {exc}")
                error = str(exc)

        if not topics and not error:
            notice = "Không trích xuất được chủ đề nào từ danh sách Reel này."
    else:
        # Standard Profile Research across creator/competitor pages
        prof_res = run_profile_research(
            targets=targets,
            run_dir=run_dir,
            options=options,
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

        if reels:
            topics, topic_error = suggest_topics(
                agent_id=agent_choice,
                sheet_name=sheet_name,
                targets=targets,
                reels=reels,
                cwd=run_dir,
                timeout_sec=float(options.get("acp_timeout", 240)),
                log=log,
                model=options.get("agy_model") or options.get("model"),
                actor_profile=actor_profile,
            )
            if topic_error and not error:
                acp_err = handle_acp_error(topic_error, agent_id=agent_choice, log=log)
                aggregator.add(acp_err)
                error = acp_err.message

    STORE.patch_sheet(
        job_id,
        sheet["slug"],
        reels=len(reels),
        pool_distribution=pool_distribution,
        source_breakdown=source_breakdown,
    )

    result = {
        "sheet": sheet_name,
        "targets": targets,
        "reels": reels,
        "source_breakdown": source_breakdown,
        "topics": topics,
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
        source_breakdown=source_breakdown,
        finished_at=now_iso(),
    )
    if topics:
        STORE.log(job_id, f"Xong sheet '{sheet_name}': {len(reels)} reel, {len(topics)} chủ đề.", sheet_name)
    else:
        STORE.log(job_id, f"Xong sheet '{sheet_name}': 0 reel. {notice or error or ''}".strip(), sheet_name)
