"""Modular Research Engine for AI Viral Studio.

Comprises:
- `profile_research`: Channel & profile crawling within 48-hour window, pool metrics.
- `reel_research`: Deep analysis of transcripts, style, hooks, and why-viral catalysts.
- `research`: Sheet orchestration, job execution, and backward-compatible harnesses.
"""

from tools.app.backend.research_engine.profile_research import (
    run_profile_research,
)
from tools.app.backend.research_engine.reel_research import (
    build_topic_prompt,
    extract_video_id,
    format_director_prompt,
    heuristic_topics,
    is_reel_url,
    normalize_topics,
    parse_topics,
    research_reels,
    research_single_reel,
    suggest_topics,
)
from tools.app.backend.research_engine.research import (
    AGENT_PRESETS,
    STORE,
    configured_agent,
    create_job,
    resolve_agent,
    run_job,
)

__all__ = [
    "AGENT_PRESETS",
    "STORE",
    "build_topic_prompt",
    "configured_agent",
    "create_job",
    "extract_video_id",
    "format_director_prompt",
    "heuristic_topics",
    "is_reel_url",
    "normalize_topics",
    "parse_topics",
    "research_reels",
    "research_single_reel",
    "resolve_agent",
    "run_job",
    "run_profile_research",
    "suggest_topics",
]
