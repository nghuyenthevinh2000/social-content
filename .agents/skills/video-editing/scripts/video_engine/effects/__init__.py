"""
effects package
───────────────
Modular effect components for viral short-form UGC video post-production.
Enables effects.json to independently configure, enable, or omit any effect.
"""

from .hook_card import generate_hook_card_image, build_hook_card_filter
from .subtitles import (
    extract_words_from_alignment,
    group_words_into_chunks,
    format_multiline_text,
    format_ass_time,
    build_ass_subtitles,
    apply_subtitles_filter,
)
from .punch_zoom import build_punch_zooms_filter
from .color_grade import build_color_grade_filter
from .progress_bar import build_progress_bar_filter
from .audio_mix import build_audio_graph

__all__ = [
    "generate_hook_card_image",
    "build_hook_card_filter",
    "extract_words_from_alignment",
    "group_words_into_chunks",
    "format_multiline_text",
    "format_ass_time",
    "build_ass_subtitles",
    "apply_subtitles_filter",
    "build_punch_zooms_filter",
    "build_color_grade_filter",
    "build_progress_bar_filter",
    "build_audio_graph",
]
