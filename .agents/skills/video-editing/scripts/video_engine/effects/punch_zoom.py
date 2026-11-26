"""
effects/punch_zoom.py
─────────────────────
Kinetic punch zoom and seam flash transition module.
Generates dynamic camera zooms on key hooks and flash transitions
at clip boundaries via FFmpeg trim/scale/crop and concat filters.
"""


def build_punch_zooms_filter(
    punch_zooms: list[dict],
    total_dur: float,
    width: int = 720,
    height: int = 1280,
    transitions: list[dict] | None = None
) -> tuple[str, str]:
    """Build FFmpeg filtergraph string for punch zooms and cut transitions."""
    if not punch_zooms:
        return "[0:v]fps=24,settb=AVTB[v_base]", "[v_base]"

    parts = []
    seg_labels = []
    transitions = transitions or []

    for idx, pz in enumerate(punch_zooms):
        st = max(0.0, float(pz["start"]))
        et = min(total_dur, float(pz["end"]))
        zoom = float(pz.get("zoom", 1.0))
        y_focus = float(pz.get("y_focus", 0.5))

        out_lbl = f"[v_pz_{idx}]"
        seg_labels.append(out_lbl)

        seg_fade = ""
        for trans in transitions:
            if trans.get("type") == "flash" and abs(st - trans["time"]) < 0.15 and st > 0.05:
                t_dur = trans.get("duration", 0.12)
                seg_fade = f",fade=t=in:st=0:d={t_dur:.3f}:color=white"
                break

        trim_str = f"trim=start={st:.3f}:end={et:.3f},setpts=PTS-STARTPTS"
        if zoom > 1.001:
            w_sc = int(round(zoom * width))
            h_sc = int(round(zoom * height))
            if w_sc % 2 != 0:
                w_sc += 1
            if h_sc % 2 != 0:
                h_sc += 1
            x_crop = int(max(0, (w_sc - width) // 2))
            y_crop = int(max(0, min(h_sc - height, (h_sc - height) * y_focus)))
            filt = f"[0:v]{trim_str},scale={w_sc}x{h_sc},crop={width}:{height}:{x_crop}:{y_crop}{seg_fade}{out_lbl}"
        else:
            filt = f"[0:v]{trim_str}{seg_fade}{out_lbl}"
        parts.append(filt)

    concat_inputs = "".join(seg_labels)
    concat_filter = f"{concat_inputs}concat=n={len(seg_labels)}:v=1:a=0[v_pz_concat]"
    parts.append(concat_filter)

    full_filter = ";".join(parts)
    return full_filter, "[v_pz_concat]"


def apply_punch_zoom(cfg: dict, ctx) -> None:
    """Stack dynamic punch zooms onto the video stream."""
    if cfg.get("transitions"):
        pz_filter, pz_out = build_punch_zooms_filter(
            cfg.get("windows", []),
            ctx.duration,
            ctx.width,
            ctx.height,
            cfg.get("transitions"),
        )
        ctx.v_filters.append(pz_filter)
        ctx.cur_v = pz_out
        return

    windows = cfg.get("windows")
    if windows is None:
        windows = [cfg]

    cond = "1.0"
    y_focus = 0.35
    has_zoom = False
    for pz in reversed(windows):
        st = max(0.0, float(pz.get("start", 0.0)))
        et = min(ctx.duration, float(pz.get("end", 0.0)))
        sc = max(1.0, float(pz.get("scale", pz.get("zoom", 1.0))))
        if "y_focus" in pz:
            y_focus = float(pz["y_focus"])
        if et > st and sc > 1.001:
            cond = f"if(between(t,{st:.3f},{et:.3f}),{sc:.4f},{cond})"
            has_zoom = True

    if not has_zoom:
        return

    out_lbl = ctx.next_v_label("pz")
    w, h = ctx.width, ctx.height
    ctx.v_filters.append(
        f"{ctx.cur_v}scale=w='trunc({w}*({cond})/2)*2':h='trunc({h}*({cond})/2)*2':eval=frame,"
        f"crop={w}:{h}:'(iw-{w})/2':'(ih-{h})*{y_focus:.3f}'{out_lbl}"
    )
    ctx.cur_v = out_lbl
