"""
effects/progress_bar.py
───────────────────────
Dynamic progress bar filter module using FFmpeg drawbox.
"""


def build_progress_bar_filter(
    pb_cfg: dict | None,
    total_dur: float,
    width: int = 720,
    height: int = 1280,
    base_label: str = "",
    out_label: str = ""
) -> str | None:
    """Build FFmpeg drawbox filter for animated video progress bar."""
    if not pb_cfg or not pb_cfg.get("enabled", False):
        return None
    pb_h = int(pb_cfg.get("height", 6))
    pb_col = pb_cfg.get("color", "#FFE600")
    return f"{base_label}drawbox=x=0:y={height - pb_h}:w='{width}*t/{total_dur:.3f}':h={pb_h}:color={pb_col}@0.95:t=fill{out_label}"
