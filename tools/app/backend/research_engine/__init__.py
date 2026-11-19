"""Research Engine entrypoints re-exporting canonical viral_analyzer pipelines & job orchestration."""

from tools.app.backend.research_engine.research import (
    AGENT_PRESETS,
    STORE,
    configured_agent,
    create_job,
    resolve_agent,
    run_job,
)
from tools.loop.viral_analyzer.keyword_research.pipeline import (
    expand_keyword,
    run_viral_video_search,
)
from tools.loop.viral_analyzer.profile_research.pipeline import (
    run_profile_research,
)
from tools.loop.viral_analyzer.video_research.pipeline import (
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

__all__ = [
    "AGENT_PRESETS",
    "STORE",
    "build_topic_prompt",
    "configured_agent",
    "create_job",
    "expand_keyword",
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
    "run_viral_video_search",
    "suggest_topics",
]
