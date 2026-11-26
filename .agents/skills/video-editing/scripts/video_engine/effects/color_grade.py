"""
effects/color_grade.py
──────────────────────
Commercial color grading filter module using FFmpeg eq filter.
"""


def build_color_grade_filter(cg_cfg: dict | None, base_label: str = "", out_label: str = "") -> str:
    """Build FFmpeg eq filter string for contrast, saturation, brightness, and gamma."""
    cg = cg_cfg or {}
    cont = float(cg.get("contrast", 1.05))
    sat = float(cg.get("saturation", 1.08))
    br = float(cg.get("brightness", 0.01))
    gamma = float(cg.get("gamma", 1.00))
    return f"{base_label}eq=contrast={cont:.2f}:saturation={sat:.2f}:brightness={br:.2f}:gamma={gamma:.2f}{out_label}"


def apply_color_grade(cfg: dict, ctx) -> None:
    """Stack color grading onto the video stream."""
    out_lbl = ctx.next_v_label("cg")
    ctx.v_filters.append(build_color_grade_filter(cfg, base_label=ctx.cur_v, out_label=out_lbl))
    ctx.cur_v = out_lbl
