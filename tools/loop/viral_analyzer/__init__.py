"""Standardized Viral Analyzer Engine.

Subpackages:
- ``profile_research``: 48h creator/channel scraper, 5-pool classification, and runner
- ``video_research``: Single-reel visuals, topic prompts, 7-day retention, and transcription
- ``keyword_research``: Cross-platform keyword search, campaign hashtag verification, and gated scraping
"""

from __future__ import annotations

import importlib
from typing import Any, Dict, Optional, Tuple

_LAZY_EXPORTS: Dict[str, Tuple[str, Optional[str]]] = {
    "profile_research": ("tools.loop.viral_analyzer.profile_research", None),
    "video_research": ("tools.loop.viral_analyzer.video_research", None),
    "keyword_research": ("tools.loop.viral_analyzer.keyword_research", None),
    "profiling": ("tools.loop.viral_analyzer.profiling", None),
    "DEFAULT_POOLS": ("tools.loop.viral_analyzer.profile_research.config", "DEFAULT_POOLS"),
    "PoolDefinition": ("tools.loop.viral_analyzer.profile_research.config", "PoolDefinition"),
    "StorageConfig": ("tools.loop.viral_analyzer.profile_research.config", "StorageConfig"),
    "TranscriptionConfig": ("tools.loop.viral_analyzer.profile_research.config", "TranscriptionConfig"),
    "ViralAnalyzerConfig": ("tools.loop.viral_analyzer.profile_research.config", "ViralAnalyzerConfig"),
    "load_config": ("tools.loop.viral_analyzer.profile_research.config", "load_config"),
    "fetch_target_reels": ("tools.loop.viral_analyzer.profile_research.collect", "fetch_target_reels"),
    "classify_pool": ("tools.loop.viral_analyzer.profile_research.pipeline", "classify_pool"),
    "run_analyzer_pipeline": ("tools.loop.viral_analyzer.profile_research.pipeline", "run_analyzer_pipeline"),
    "run_profile_research": ("tools.loop.viral_analyzer.profile_research.pipeline", "run_profile_research"),
    "load_manifest": ("tools.loop.viral_analyzer.video_research.collect", "load_manifest"),
    "purge_expired_videos": ("tools.loop.viral_analyzer.video_research.collect", "purge_expired_videos"),
    "register_video": ("tools.loop.viral_analyzer.video_research.collect", "register_video"),
    "download_video_stream": ("tools.loop.viral_analyzer.video_research.collect", "download_video_stream"),
    "research_single_reel": ("tools.loop.viral_analyzer.video_research.pipeline", "research_single_reel"),
    "research_reels": ("tools.loop.viral_analyzer.video_research.pipeline", "research_reels"),
    "suggest_topics": ("tools.loop.viral_analyzer.video_research.pipeline", "suggest_topics"),
    "heuristic_topics": ("tools.loop.viral_analyzer.video_research.pipeline", "heuristic_topics"),
    "GlasserTranscriber": ("tools.loop.viral_analyzer.video_research.transcriber", "GlasserTranscriber"),
    "LocalTranscriber": ("tools.loop.viral_analyzer.video_research.transcriber", "LocalTranscriber"),
    "UnifiedTranscriber": ("tools.loop.viral_analyzer.video_research.transcriber", "UnifiedTranscriber"),
    "extract_audio_ffmpeg": ("tools.loop.viral_analyzer.video_research.transcriber", "extract_audio_ffmpeg"),
    "fetch_reel_transcript": ("tools.loop.viral_analyzer.video_research.transcriber", "fetch_reel_transcript"),
    "fetch_top_reels_transcripts": ("tools.loop.viral_analyzer.video_research.transcriber", "fetch_top_reels_transcripts"),
    "transcribe_reels_glasser": ("tools.loop.viral_analyzer.video_research.transcriber", "transcribe_reels_glasser"),
    "transcribe_reels_local": ("tools.loop.viral_analyzer.video_research.transcriber", "transcribe_reels_local"),
    "expand_keyword": ("tools.loop.viral_analyzer.keyword_research.collect", "expand_keyword"),
    "search_platform": ("tools.loop.viral_analyzer.keyword_research.pipeline", "search_platform"),
    "run_viral_video_search": ("tools.loop.viral_analyzer.keyword_research.pipeline", "run_viral_video_search"),
}

__all__ = list(_LAZY_EXPORTS.keys())


def __getattr__(name: str) -> Any:
    target = _LAZY_EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    mod_path, attr = target
    mod = importlib.import_module(mod_path)
    value = mod if attr is None else getattr(mod, attr)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
