"""
effects/hook_card.py
────────────────────
Centered hero card overlay module for high-retention hook messaging.
Generates an anti-aliased pill/card graphic using Pillow and builds
FFmpeg fade-in / fade-out overlay filter graphs.
"""

from pathlib import Path


def generate_hook_card_image(
    card_cfg: dict,
    out_path: Path,
    video_width: int = 720,
    video_height: int = 1280
) -> Path:
    """Generate a high-contrast rounded card image matching viral short-form aesthetics."""
    from PIL import Image, ImageDraw, ImageFont

    out_path = Path(out_path).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    card_w = int(card_cfg.get("width", int(video_width * 0.93)))
    card_h = int(card_cfg.get("height", int(video_height * 0.24)))
    radius = int(card_cfg.get("radius", 32))
    bg_hex = card_cfg.get("bg_color", "#D3403A").lstrip("#")
    bg_rgb = tuple(int(bg_hex[i:i + 2], 16) for i in (0, 2, 4)) + (255,)

    card = Image.new("RGBA", (card_w, card_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(card)
    draw.rounded_rectangle([(0, 0), (card_w - 1, card_h - 1)], radius=radius, fill=bg_rgb)

    # Font lookup with robust cross-platform fallbacks
    repo_root = Path(__file__).resolve().parents[5]
    font_candidates = [
        card_cfg.get("font"),
        repo_root / ".venv/lib/python3.12/site-packages/matplotlib/mpl-data/fonts/ttf/DejaVuSans-Bold.ttf",
        Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
        Path("/Library/Fonts/Arial Unicode.ttf"),
    ]
    font_path = None
    for cand in font_candidates:
        if cand and Path(cand).exists():
            font_path = str(cand)
            break

    font_size = int(card_cfg.get("font_size", 48))
    font = ImageFont.truetype(font_path, font_size) if font_path else ImageFont.load_default()

    lines = card_cfg.get("lines")
    if not lines:
        raw_text = card_cfg.get("text", "")
        lines = [l.strip() for l in raw_text.replace(r"\N", "\n").replace(r"\n", "\n").split("\n") if l.strip()]

    stroke_w = int(card_cfg.get("stroke_width", 2))
    line_boxes = [draw.textbbox((0, 0), line, font=font, stroke_width=stroke_w) for line in lines]
    line_heights = [b[3] - b[1] for b in line_boxes]
    line_gap = int(card_cfg.get("line_gap", 14))
    total_text_h = sum(line_heights) + line_gap * max(0, len(lines) - 1)

    cur_y = (card_h - total_text_h) / 2
    for line, l_box in zip(lines, line_boxes):
        lw = l_box[2] - l_box[0]
        lx = (card_w - lw) / 2
        # Drop shadow
        draw.text((lx + 2, cur_y + 3), line, font=font, fill=(0, 0, 0, 150), stroke_width=stroke_w, stroke_fill=(0, 0, 0, 150))
        # Crisp white text with dark stroke
        draw.text((lx, cur_y), line, font=font, fill=(255, 255, 255, 255), stroke_width=stroke_w, stroke_fill=(20, 20, 20, 255))
        cur_y += (l_box[3] - l_box[1]) + line_gap

    card.save(out_path, format="PNG")
    print(f"  [HookCard] Generated hook card image ({card_w}x{card_h}) at: {out_path.name}")
    return out_path


def build_hook_card_filter(
    hook_card_cfg: dict,
    card_input_idx: int,
    base_label: str,
    out_label: str,
    video_height: int = 1280
) -> list[str]:
    """Build FFmpeg filtergraph segments for card fade-in, fade-out, and overlay."""
    c_st = float(hook_card_cfg.get("start", 0.0))
    c_et = float(hook_card_cfg.get("end", 3.35))
    c_fade_in = float(hook_card_cfg.get("fade_in", 0.12))
    c_fade_out = float(hook_card_cfg.get("fade_out", 0.15))
    pos_y = int(hook_card_cfg.get("pos_y", int(video_height * 0.445)))

    card_fade = (
        f"[{card_input_idx}:v]format=rgba,fade=t=in:st={c_st:.3f}:d={c_fade_in:.2f}:alpha=1,"
        f"fade=t=out:st={c_et - c_fade_out:.3f}:d={c_fade_out:.2f}:alpha=1[c_faded]"
    )
    card_overlay = (
        f"{base_label}[c_faded]overlay=(W-w)/2:{pos_y}:shortest=1:enable='between(t,{c_st:.3f},{c_et:.3f})'{out_label}"
    )
    return [card_fade, card_overlay]
