"""Video generation and editing engine package."""

from tools.app.backend.video_engine.edit import (
    build_video_edit_acp_prompt,
    edit_video,
    extract_reference_url,
    plan_edit_video,
    ref_cache_dir,
    resolve_rea_video_bin,
)
from tools.app.backend.video_engine.generate import (
    DEFAULT_MODEL,
    _apply_actor_profile_to_structured_prompt,
    _get_agent_platform_credentials,
    _load_env,
    build_prompt,
    generate_video,
    get_video_duration,
    normalize_video,
)

__all__ = [
    "DEFAULT_MODEL",
    "_apply_actor_profile_to_structured_prompt",
    "_get_agent_platform_credentials",
    "_load_env",
    "build_prompt",
    "build_video_edit_acp_prompt",
    "edit_video",
    "extract_reference_url",
    "generate_video",
    "get_video_duration",
    "normalize_video",
    "plan_edit_video",
    "ref_cache_dir",
    "resolve_rea_video_bin",
]
