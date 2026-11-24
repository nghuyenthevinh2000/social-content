"""
effects/color_grade.py
──────────────────────
Commercial color grading filter module using FFmpeg eq filter.
"""


def build_color_grade_filter(cg_cfg: dict | None, base_label: str = "", out_label: str = "") -> str:
    """Build FFmpeg eq filter string for contrast, saturation, and brightness."""
    cg = cg_cfg or {}
    cont = float(cg.get("contrast", 1.05))
    sat = float(cg.get("saturation", 1.08))
    br = float(cg.get("brightness", 0.01))
    return f"{base_label}eq=contrast={cont:.2f}:saturation={sat:.2f}:brightness={br:.2f}{out_label}"
