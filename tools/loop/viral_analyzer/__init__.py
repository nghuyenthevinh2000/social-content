"""Standardized Viral Analyzer Loop Module.

Provides end-to-end extraction, 5-pool classification, video cache retention (1-week TTL),
and Qwen3-ASR speech-to-text transcription for 48h short-form viral videos.
"""

from tools.loop.viral_analyzer.config import (
    DEFAULT_POOLS,
    PoolDefinition,
    StorageConfig,
    TranscriptionConfig,
    ViralAnalyzerConfig,
    load_config,
)
from tools.loop.viral_analyzer.pipeline import (
    classify_pool,
    run_analyzer_pipeline,
)
from tools.loop.viral_analyzer.retention import (
    load_manifest,
    purge_expired_videos,
    register_video,
)
from tools.loop.viral_analyzer.transcriber import (
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
    "DEFAULT_POOLS",
    "PoolDefinition",
    "StorageConfig",
    "TranscriptionConfig",
    "ViralAnalyzerConfig",
    "load_config",
    "classify_pool",
    "run_analyzer_pipeline",
    "load_manifest",
    "purge_expired_videos",
    "register_video",
    "GlasserTranscriber",
    "LocalTranscriber",
    "UnifiedTranscriber",
    "extract_audio_ffmpeg",
    "fetch_reel_transcript",
    "fetch_top_reels_transcripts",
    "transcribe_reels_glasser",
    "transcribe_reels_local",
]
