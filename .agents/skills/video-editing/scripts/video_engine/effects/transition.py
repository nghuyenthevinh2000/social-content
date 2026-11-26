"""
effects/transition.py
─────────────────────
Stackable transition primitive (flash, fade_in, fade_out).
Applies non-splitting FFmpeg overlay / fade filters so transitions compose
cleanly anywhere in the effect stack.
"""


def apply_transition(cfg: dict, ctx) -> None:
    """Stack a flash, fade_in, or fade_out transition onto the video stream."""
    kind = str(cfg.get("kind", "flash")).lower()
    color = str(cfg.get("color", "white" if kind == "flash" else "black"))
    dur = max(0.02, float(cfg.get("duration", 0.15 if kind == "flash" else 0.35)))
    out_lbl = ctx.next_v_label("tr")

    if kind == "flash":
        t = max(0.0, float(cfg.get("time", cfg.get("start", 0.0))))
        tmp_lbl = ctx.next_v_label("flash")
        ctx.v_filters.append(
            f"color=c={color}:s={ctx.width}x{ctx.height}:d={dur:.3f},format=rgba,"
            f"fade=t=out:st=0:d={dur:.3f}:alpha=1,setpts=PTS+{t:.3f}/TB{tmp_lbl}"
        )
        ctx.v_filters.append(
            f"{ctx.cur_v}{tmp_lbl}overlay=0:0:eof_action=pass:enable='between(t,{t:.3f},{t + dur:.3f})'{out_lbl}"
        )
    elif kind == "fade_in":
        st = max(0.0, float(cfg.get("start", cfg.get("time", 0.0))))
        ctx.v_filters.append(f"{ctx.cur_v}fade=t=in:st={st:.3f}:d={dur:.3f}:color={color}{out_lbl}")
    elif kind == "fade_out":
        st = max(0.0, float(cfg.get("start", cfg.get("time", max(0.0, ctx.duration - dur)))))
        ctx.v_filters.append(f"{ctx.cur_v}fade=t=out:st={st:.3f}:d={dur:.3f}:color={color}{out_lbl}")
    else:
        raise ValueError(f"Unsupported transition kind: {kind!r}")

    ctx.cur_v = out_lbl
