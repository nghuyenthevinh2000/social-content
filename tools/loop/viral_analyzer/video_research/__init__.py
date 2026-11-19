"""Video Research Engine: single-reel analysis, downloads, retention, and transcription."""

from tools.loop.viral_analyzer.platforms import (
    REEL_PATTERNS,
    canonicalize_reel_url,
    detect_platform,
    extract_video_id,
    fallback_video_url,
    is_reel_url,
    resolve_short_url,
)
from tools.loop.viral_analyzer.video_research.collect import (
    download_video_stream,
    load_manifest,
    purge_expired_videos,
    register_video,
)
from tools.loop.viral_analyzer.video_research.config import (
    TEMP_DIR,
    VISUAL_PROMPT,
    build_topic_prompt,
    format_director_prompt,
)
from tools.loop.viral_analyzer.video_research.pipeline import (
    analyze_video_visuals,
    heuristic_topics,
    normalize_topics,
    parse_topics,
    research_reels,
    research_single_reel,
    suggest_topics,
)
from tools.loop.viral_analyzer.video_research.transcriber import (
    GlasserTranscriber,
    LocalTranscriber,
    UnifiedTranscriber,
    extract_audio_ffmpeg,
    fetch_reel_transcript,
    fetch_top_reels_transcripts,
    transcribe_reels_glasser,
    transcribe_reels_local,
)

__all__ = [
    "GlasserTranscriber",
    "LocalTranscriber",
    "REEL_PATTERNS",
    "TEMP_DIR",
    "UnifiedTranscriber",
    "VISUAL_PROMPT",
    "analyze_video_visuals",
    "build_topic_prompt",
    "canonicalize_reel_url",
    "detect_platform",
    "download_video_stream",
    "extract_audio_ffmpeg",
    "extract_video_id",
    "fallback_video_url",
    "fetch_reel_transcript",
    "fetch_top_reels_transcripts",
    "format_director_prompt",
    "heuristic_topics",
    "is_reel_url",
    "load_manifest",
    "normalize_topics",
    "parse_topics",
    "purge_expired_videos",
    "register_video",
    "research_reels",
    "research_single_reel",
    "resolve_short_url",
    "suggest_topics",
    "transcribe_reels_glasser",
    "transcribe_reels_local",
]
