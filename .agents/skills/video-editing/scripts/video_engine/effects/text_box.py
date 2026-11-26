"""
effects/text_box.py
───────────────────
Stackable card and text-box overlay primitive.
Renders anti-aliased hook, info, and table cards via Pillow and overlays
them onto the video stream with optional fade-in/fade-out and time windows.
"""

from pathlib import Path
from typing import Any

FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def _find_font(preferred: str | None = None, bold: bool = True) -> str | None:
    repo_root = Path(__file__).resolve().parents[5]
    candidates = [
        preferred,
        FONT_BOLD if bold else FONT_REG,
        repo_root / ".venv/lib/python3.12/site-packages/matplotlib/mpl-data/fonts/ttf/DejaVuSans-Bold.ttf",
        Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
        Path("/Library/Fonts/Arial Unicode.ttf"),
    ]
    for cand in candidates:
        if cand and Path(cand).exists():
            return str(cand)
    return None


def _font(path: str | None, size: int) -> Any:
    from PIL import ImageFont

    if path:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default()


def _hex_to_rgba(hex_color: str, alpha: int = 255) -> tuple[int, int, int, int]:
    s = hex_color.strip().lstrip("#")
    if len(s) == 6:
        return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16), alpha)
    if len(s) == 8:
        return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16), int(s[6:8], 16))
    return (255, 255, 255, alpha)


def _fit_font(
    draw: Any,
    lines: list[str],
    font_path: str | None,
    max_w: int,
    start_size: int,
    stroke_width: int = 0,
) -> Any:
    size = start_size
    while size > 14:
        f = _font(font_path, size)
        widest = max((draw.textbbox((0, 0), ln, font=f, stroke_width=stroke_width)[2] for ln in lines), default=0)
        if widest <= max_w:
            return f
        size -= 1
    return _font(font_path, 14)


def _draw_shadowed_card(
    card_w: int,
    card_h: int,
    pad: int,
    radius: int,
    bg_rgba: tuple[int, int, int, int],
    outline_rgba: tuple[int, int, int, int] | None = None,
    shadow: bool = True,
) -> Any:
    from PIL import Image, ImageDraw, ImageFilter

    cw, ch = card_w + pad * 2, card_h + pad * 2
    card = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    cd = ImageDraw.Draw(card)
    cd.rounded_rectangle(
        [(pad, pad), (pad + card_w - 1, pad + card_h - 1)],
        radius=radius,
        fill=bg_rgba,
        outline=outline_rgba,
        width=2 if outline_rgba else 0,
    )
    if not shadow:
        return card
    sh_img = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    sd = ImageDraw.Draw(sh_img)
    sd.rounded_rectangle([(pad, pad + 4), (pad + card_w - 1, pad + card_h + 3)], radius=radius, fill=(0, 0, 0, 62))
    sh_img = sh_img.filter(ImageFilter.GaussianBlur(radius=7))
    return Image.alpha_composite(sh_img, card)


def render_text_box_png(
    cfg: dict,
    out_path: Path,
    video_w: int = 720,
    video_h: int = 1280,
) -> Path:
    """Render a hook, box, info, or table overlay card PNG."""
    from PIL import ImageDraw

    variant = str(cfg.get("variant", cfg.get("kind", "hook"))).lower()
    pad = int(cfg.get("pad", 16))
    shadow = bool(cfg.get("shadow", True))
    card_w = int(cfg.get("width", min(656, video_w - 64)))
    bg_rgba = _hex_to_rgba(str(cfg.get("bg_color", "#FFFFFF")), int(cfg.get("bg_alpha", 250)))
    default_fg = "#7A00F5" if variant in ("hook", "box") else "#1C2026"
    text_rgba = _hex_to_rgba(str(cfg.get("text_color", default_fg)), 255)
    bold_font = _find_font(cfg.get("font"), bold=True)
    reg_font = _find_font(cfg.get("font"), bold=False)

    if variant in ("hook", "box"):
        lines = [str(x) for x in (cfg.get("lines") or []) if str(x).strip()]
        if not lines:
            raw_text = str(cfg.get("text", ""))
            lines = [ln.strip() for ln in raw_text.replace(r"\N", "\n").replace(r"\n", "\n").split("\n") if ln.strip()]
        if not lines:
            lines = ["HOOK"]
        card_h = int(cfg.get("height", max(120, 44 * len(lines) + 56)))
        radius = int(cfg.get("radius", 36))
        stroke_w = int(cfg.get("stroke_width", 0))
        img = _draw_shadowed_card(card_w, card_h, pad, radius, bg_rgba, shadow=shadow)
        draw = ImageDraw.Draw(img)
        font = _fit_font(draw, lines, bold_font, card_w - 56, int(cfg.get("font_size", 36)), stroke_width=stroke_w)
        boxes = [draw.textbbox((0, 0), ln, font=font, stroke_width=stroke_w) for ln in lines]
        heights = [b[3] - b[1] for b in boxes]
        gap = int(cfg.get("line_gap", 12))
        total_h = sum(heights) + gap * max(0, len(lines) - 1)
        y = pad + (card_h - total_h) / 2.0
        for ln, b, h in zip(lines, boxes, heights):
            lw = b[2] - b[0]
            x = pad + (card_w - lw) / 2.0 - b[0]
            if stroke_w > 0:
                draw.text((x + 2, y - b[1] + 3), ln, font=font, fill=(0, 0, 0, 150), stroke_width=stroke_w, stroke_fill=(0, 0, 0, 150))
                draw.text((x, y - b[1]), ln, font=font, fill=text_rgba, stroke_width=stroke_w, stroke_fill=(20, 20, 20, 255))
            else:
                draw.text((x, y - b[1]), ln, font=font, fill=text_rgba)
            y += h + gap
    elif variant == "info":
        title = str(cfg.get("title", "")).strip()
        body = [str(x) for x in (cfg.get("body") or [])]
        tag = str(cfg.get("tag", "")).strip()
        card_h = int(cfg.get("height", 64 + 28 * max(1, len(body)) + (28 if tag else 12)))
        radius = int(cfg.get("radius", 10))
        img = _draw_shadowed_card(card_w, card_h, pad, radius, bg_rgba, outline_rgba=(218, 222, 228, 255), shadow=shadow)
        draw = ImageDraw.Draw(img)
        draw.ellipse([(pad + 22, pad + 26), (pad + 30, pad + 34)], outline=text_rgba, width=2)
        f_title = _font(bold_font, 21)
        f_body = _font(reg_font, 19)
        f_tag = _font(reg_font, 15)
        if title:
            draw.text((pad + 42, pad + 18), title, font=f_title, fill=text_rgba)
        y = pad + 52
        for ln in body:
            draw.text((pad + 42, y), ln, font=f_body, fill=(52, 58, 66, 255))
            y += 28
        if tag:
            draw.text((pad + 42, pad + card_h - 32), tag, font=f_tag, fill=(138, 144, 152, 255))
    else:  # table
        headers = [str(h) for h in (cfg.get("headers") or ["Mục", "Chi tiết"])]
        rows = [[str(c) for c in r] for r in (cfg.get("rows") or [])]
        card_h = int(cfg.get("height", 64 + 38 * max(1, len(rows))))
        radius = int(cfg.get("radius", 10))
        img = _draw_shadowed_card(card_w, card_h, pad, radius, bg_rgba, outline_rgba=(218, 222, 228, 255), shadow=shadow)
        draw = ImageDraw.Draw(img)
        f_hdr = _font(bold_font, 17)
        f_cell = _font(reg_font, 17)
        cols = [pad + 20 + i * ((card_w - 40) // max(1, len(headers))) for i in range(len(headers))]
        for cx, h_txt in zip(cols, headers):
            draw.text((cx, pad + 16), h_txt, font=f_hdr, fill=text_rgba)
        draw.line([(pad + 16, pad + 46), (pad + card_w - 16, pad + 46)], fill=(224, 228, 234, 255), width=2)
        ry = pad + 58
        for idx, row in enumerate(rows):
            for cx, val in zip(cols, row):
                draw.text((cx, ry), val, font=f_cell, fill=(56, 62, 70, 255))
            if idx < len(rows) - 1:
                draw.line([(pad + 16, ry + 32), (pad + card_w - 16, ry + 32)], fill=(224, 228, 234, 255), width=1)
            ry += 38

    out_path = Path(out_path).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "PNG")
    return out_path


def apply_text_box(cfg: dict, ctx) -> None:
    """Stack a rendered text box / card overlay onto the video stream."""
    png_path = render_text_box_png(cfg, ctx.work_dir / f"{ctx.next_id('tb')}.png", ctx.width, ctx.height)
    in_idx = ctx.add_input(["-loop", "1", "-t", f"{max(0.1, ctx.duration):.3f}", "-i", str(png_path)])

    start = float(cfg.get("start", 0.0))
    end = float(cfg.get("end", max(start + 0.1, ctx.duration)))
    x_expr = str(cfg.get("x", "(W-w)/2"))
    y_val = cfg.get("y", cfg.get("pos_y", 90))
    fade_in = float(cfg.get("fade_in", 0.0))
    fade_out = float(cfg.get("fade_out", 0.0))

    if fade_in > 0.0 or fade_out > 0.0:
        f_lbl = ctx.next_v_label("tb_f")
        chain = [f"[{in_idx}:v]format=rgba"]
        if fade_in > 0.0:
            chain.append(f"fade=t=in:st={start:.3f}:d={fade_in:.2f}:alpha=1")
        if fade_out > 0.0:
            chain.append(f"fade=t=out:st={max(start, end - fade_out):.3f}:d={fade_out:.2f}:alpha=1")
        ctx.v_filters.append(",".join(chain) + f_lbl)
        src_lbl = f_lbl
    else:
        src_lbl = f"[{in_idx}:v]"

    out_lbl = ctx.next_v_label("tb")
    ctx.v_filters.append(
        f"{ctx.cur_v}{src_lbl}overlay=x={x_expr}:y={y_val}:shortest=1:enable='between(t,{start:.3f},{end:.3f})'{out_lbl}"
    )
    ctx.cur_v = out_lbl
