"""
effects package
───────────────
Modular, stackable effect components for short-form video post-production.
Every effect exposes an `apply_<name>(cfg, ctx)` function registered in `EFFECT_REGISTRY`.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .audio_mix import apply_bgm, apply_sfx, build_audio_graph, finalize_audio_graph, synthesize_sfx_wav
from .color_grade import apply_color_grade, build_color_grade_filter
from .hook_card import apply_hook_card, build_hook_card_filter, generate_hook_card_image
from .progress_bar import apply_progress_bar, build_progress_bar_filter
from .punch_zoom import apply_punch_zoom, build_punch_zooms_filter
from .subtitles import (
    apply_subtitles,
    apply_subtitles_filter,
    build_ass_from_items,
    build_ass_subtitles,
    extract_words_from_alignment,
    format_ass_time,
    format_multiline_text,
    group_words_into_chunks,
)
from .text_box import apply_text_box, render_text_box_png
from .transition import apply_transition


@dataclass
class RenderContext:
    """Mutable filtergraph assembly state shared across stacked effects."""

    width: int
    height: int
    fps: int
    duration: float
    has_audio: bool
    base_dir: Path
    work_dir: Path
    sfx_dir: Path
    resolve_path: Callable[[str | Path], Path]
    ffmpeg_inputs: list[str] = field(default_factory=list)
    v_filters: list[str] = field(default_factory=list)
    a_filters: list[str] = field(default_factory=list)
    a_mix_labels: list[str] = field(default_factory=list)
    cur_v: str = "[v_base]"
    sfx_cache: dict[str, Path] = field(default_factory=dict)
    _input_idx: int = 1
    _counters: dict[str, int] = field(default_factory=dict)

    def add_input(self, args: list[str]) -> int:
        idx = self._input_idx
        self.ffmpeg_inputs.extend(args)
        self._input_idx += 1
        return idx

    def next_id(self, prefix: str) -> str:
        n = self._counters.get(prefix, 0)
        self._counters[prefix] = n + 1
        return f"{prefix}_{n}"

    def next_v_label(self, prefix: str = "v") -> str:
        return f"[{self.next_id(prefix)}]"

    def next_a_label(self, prefix: str = "a") -> str:
        return f"[{self.next_id(prefix)}]"


EFFECT_REGISTRY: dict[str, Callable[[dict, RenderContext], None]] = {
    "punch_zoom": apply_punch_zoom,
    "transition": apply_transition,
    "color_grade": apply_color_grade,
    "progress_bar": apply_progress_bar,
    "text_box": apply_text_box,
    "card": apply_text_box,
    "hook_card": apply_hook_card,
    "subtitles": apply_subtitles,
    "captions": apply_subtitles,
    "bgm": apply_bgm,
    "sfx": apply_sfx,
}

__all__ = [
    "RenderContext",
    "EFFECT_REGISTRY",
    "apply_bgm",
    "apply_color_grade",
    "apply_hook_card",
    "apply_progress_bar",
    "apply_punch_zoom",
    "apply_sfx",
    "apply_subtitles",
    "apply_subtitles_filter",
    "apply_text_box",
    "apply_transition",
    "build_ass_from_items",
    "build_ass_subtitles",
    "build_audio_graph",
    "build_color_grade_filter",
    "build_hook_card_filter",
    "build_progress_bar_filter",
    "build_punch_zooms_filter",
    "extract_words_from_alignment",
    "finalize_audio_graph",
    "format_ass_time",
    "format_multiline_text",
    "generate_hook_card_image",
    "group_words_into_chunks",
    "render_text_box_png",
    "synthesize_sfx_wav",
]
