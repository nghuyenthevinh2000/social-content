"""Configuration and prompt re-exports for Video Research."""

from __future__ import annotations

import os
from pathlib import Path

from tools.loop.viral_analyzer.video_research.prompt import (
    VISUAL_PROMPT,
    VISUAL_PROMPTS,
    _fallback_reel_url,
    _normalize_actor,
    _reel_digest,
    build_video_structure_prompt,
    format_director_prompt,
    get_visual_prompt,
    resolve_language,
)

# Temporary videos live under the repo's local data dir and are deleted after analysis.
TEMP_DIR = Path(os.environ.get("VIRAL_APP_TEMP", Path(__file__).resolve().parents[4] / "local" / "aibrand" / "temp"))

__all__ = [
    "TEMP_DIR",
    "VISUAL_PROMPT",
    "VISUAL_PROMPTS",
    "_fallback_reel_url",
    "_normalize_actor",
    "_reel_digest",
    "build_video_structure_prompt",
    "format_director_prompt",
    "get_visual_prompt",
    "resolve_language",
]
