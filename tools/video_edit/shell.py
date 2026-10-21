"""Thin-shell mechanics and SVBRDF facade (delegates to ``tools.video_edit.methods``)."""

from __future__ import annotations

from .methods.blender_sim import _BLENDER_SCRIPT, run_blender_simulation
from .methods.pbr_shell import compute_pbr_illumination, extract_svbrdf, warp_shell_flap

__all__ = [
    "_BLENDER_SCRIPT",
    "compute_pbr_illumination",
    "extract_svbrdf",
    "run_blender_simulation",
    "warp_shell_flap",
]
