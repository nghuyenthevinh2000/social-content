"""Pluggable rendering and tracking methods for ``tools.video_edit``."""

from .blender_sim import run_blender_simulation
from .flow_track import track_surface_flow
from .pbr_shell import (
    apply_pbr_shading,
    compute_pbr_illumination,
    extract_svbrdf,
    warp_shell_flap,
)
from .shading import (
    BLEND_MODES,
    apply_shading,
    bgr_to_rgb_float,
    blend,
    compute_shading_illumination,
    luminance,
    rgb_float_to_bgr,
)

METHODS = ("shading", "pbr", "sim", "flow")
TRACK_MODES = ("quad", "flow")

__all__ = [
    "BLEND_MODES",
    "METHODS",
    "TRACK_MODES",
    "apply_pbr_shading",
    "apply_shading",
    "bgr_to_rgb_float",
    "blend",
    "compute_pbr_illumination",
    "compute_shading_illumination",
    "extract_svbrdf",
    "luminance",
    "rgb_float_to_bgr",
    "run_blender_simulation",
    "track_surface_flow",
    "warp_shell_flap",
]
