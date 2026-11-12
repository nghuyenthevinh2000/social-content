"""Profile Research Engine: Crawls competitor channels and extracts viral candidate reels.

Focuses on:
- Scraping candidate posts/reels within the configured window (e.g. 48 hours).
- Tracking metrics: views, velocity per hour, likes, comments, shares.
- Classifying reels into 5 traffic pools (P1 to P5).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from tools.app.backend.errors import (
    ErrorAggregator,
    ErrorCategory,
    ErrorSeverity,
    handle_glasser_error,
)
from tools.loop.viral_analyzer.config import load_config
from tools.loop.viral_analyzer.glasser import ensure_glasser_env
from tools.loop.viral_analyzer.pipeline import run_analyzer_pipeline

logger = logging.getLogger("profile_research")
ensure_glasser_env()


def run_profile_research(
    targets: List[Dict[str, Any]],
    run_dir: Path,
    options: Dict[str, Any],
    log: Optional[Callable[[str], None]] = None,
    job_id: str = "adhoc",
    sheet_slug: str = "sheet",
    pipeline_fn: Optional[Callable[..., Any]] = None,
    aggregator: Optional[ErrorAggregator] = None,
) -> Dict[str, Any]:
    """Execute profile research across a list of creator/channel targets.

    Returns:
        Dict containing:
        - reels: List of candidate reels filtered to the configured time window.
        - pool_distribution: Distribution of reels across traffic pools P1-P5.
        - source_breakdown: Breakdown of sources scraped.
        - error: Primary error message if scraping failed.
        - notice: Helpful notice message if no reels were found.
        - errors: List of serialized ErrorItem objects.
    """
    _log = log or (lambda msg: logger.info(msg))
    sheet_dir = run_dir / "sheets" / sheet_slug
    sheet_dir.mkdir(parents=True, exist_ok=True)
    shared_cache = run_dir / "cache"
    shared_cache.mkdir(parents=True, exist_ok=True)

    aggregator = aggregator or ErrorAggregator(job_id=job_id)
    reels: List[Dict[str, Any]] = []
    error: Optional[str] = None
    notice: Optional[str] = None
    payload: Dict[str, Any] = {}

    if not targets:
        _log("Danh sách kênh trống; không có link profile/kênh để nghiên cứu.")
        return {
            "reels": [],
            "pool_distribution": {},
            "source_breakdown": {},
            "error": None,
            "notice": "Chưa có kênh đối thủ nào. Vui lòng cập nhật thêm danh sách kênh.",
            "errors": [],
        }

    window_hours = int(options.get("window_hours", 48))
    config = load_config(
        {
            "window_hours": window_hours,
            "retention_days": 7,
            "max_videos": options.get("max_videos"),
            "storage": {
                "video_dir": str(shared_cache / "videos"),
                "output_file": str(sheet_dir / "viral_reels_48h.json"),
            },
            "transcription": {"engine": "local", "model": "Qwen/Qwen3-ASR-0.6B", "language": None},
            "targets": targets,
        }
    )

    runner = pipeline_fn or run_analyzer_pipeline
    try:
        payload = runner(
            config,
            max_videos=options.get("max_videos"),
            cache_dir=shared_cache,
            media=bool(options.get("media")),
            legacy_cache=False,
            progress_cb=_log,
        )
        reels = payload.get("all_reels", [])
        for err_item in payload.get("errors", []):
            handle_name = err_item.get("handle") if isinstance(err_item, dict) else None
            app_err = handle_glasser_error(err_item, handle=handle_name, log=_log)
            aggregator.add(app_err)
    except Exception as exc:
        app_err = handle_glasser_error(exc, log=_log)
        aggregator.add(app_err)
        error = app_err.message

    pool_distribution = payload.get("metadata", {}).get("pool_distribution", {})
    source_breakdown = payload.get("source_breakdown") or payload.get("metadata", {}).get("source_breakdown", {})

    if not reels and not error:
        glasser_errs = aggregator.filter(category=ErrorCategory.GLASSER.value)
        if glasser_errs:
            critical = next(
                (e for e in glasser_errs if e.severity == ErrorSeverity.CRITICAL.value),
                glasser_errs[0],
            )
            notice = critical.format_notice()
            error = critical.message
            _log(f"[Cảnh báo API] {notice}")
        else:
            notice = f"Không tìm thấy reel mới nào trong {window_hours} giờ qua. Vui lòng cập nhật thêm danh sách kênh."
            _log(notice)

    return {
        "reels": reels,
        "pool_distribution": pool_distribution,
        "source_breakdown": source_breakdown,
        "error": error,
        "notice": notice,
        "errors": [e.to_dict() for e in aggregator.all_errors()],
    }
