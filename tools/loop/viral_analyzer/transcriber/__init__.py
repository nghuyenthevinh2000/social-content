"""Unified Transcriber Package for Viral Reels Analyzer.

Provides two distinct transcription engines:
- "local"   : Local video download + FFmpeg audio extraction + Qwen3-ASR / Whisper (`local.py`)
- "glasser" : Direct cloud transcript retrieval via Glasser ScrapeCreators (`glasser.py`)
"""

from tools.loop.viral_analyzer.transcriber.download_models import (
    DEFAULT_MODEL,
    download_model,
)
from tools.loop.viral_analyzer.transcriber.glasser import (
    GlasserTranscriber,
    fetch_reel_transcript,
    fetch_top_reels_transcripts,
    transcribe_reels_glasser,
)
from tools.loop.viral_analyzer.transcriber.local import (
    LocalTranscriber,
    UnifiedTranscriber,
    download_video_stream,
    extract_audio_ffmpeg,
    ffmpeg_bin,
    transcribe_reels_local,
)

__all__ = [
    "DEFAULT_MODEL",
    "GlasserTranscriber",
    "LocalTranscriber",
    "UnifiedTranscriber",
    "download_model",
    "download_video_stream",
    "extract_audio_ffmpeg",
    "fetch_reel_transcript",
    "fetch_top_reels_transcripts",
    "ffmpeg_bin",
    "transcribe_reels_glasser",
    "transcribe_reels_local",
]
