"""Keyword research, campaign hashtag verification, and gated scraping subpackage."""

from tools.loop.viral_analyzer.keyword_research import campaign, collect, config, pipeline
from tools.loop.viral_analyzer.keyword_research.collect import (
    expand_keyword,
    search_platform,
)
from tools.loop.viral_analyzer.keyword_research.config import PLATFORMS
from tools.loop.viral_analyzer.keyword_research.pipeline import (
    build_prompt,
    build_review_prompt,
    collect_probes,
    history_report,
    import_response,
    plan_probes,
    record_review,
    report_collection,
    run_viral_video_search,
    scrape,
)

__all__ = [
    "PLATFORMS",
    "build_prompt",
    "build_review_prompt",
    "campaign",
    "collect",
    "collect_probes",
    "config",
    "expand_keyword",
    "history_report",
    "import_response",
    "pipeline",
    "plan_probes",
    "record_review",
    "report_collection",
    "run_viral_video_search",
    "scrape",
    "search_platform",
]
