"""Blend modes and colour helpers (delegates to ``tools.video_edit.methods``)."""

from __future__ import annotations

from .methods.pbr_shell import apply_pbr_shading
from .methods.shading import (
    BLEND_MODES,
    _as_three_channel,
    _luminosity,
    _soft_light,
    apply_shading,
    bgr_to_rgb_float,
    blend,
    compute_shading_illumination,
    luminance,
    rgb_float_to_bgr,
)

__all__ = [
    "BLEND_MODES",
    "_as_three_channel",
    "_luminosity",
    "_soft_light",
    "apply_pbr_shading",
    "apply_shading",
    "bgr_to_rgb_float",
    "blend",
    "compute_shading_illumination",
    "luminance",
    "rgb_float_to_bgr",
]
