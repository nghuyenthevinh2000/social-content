#!/usr/bin/env python3
"""Declarative JSON-driven video editor for ACP & video_engine.

Replaces ad-hoc Python rendering scripts by taking a single JSON edit plan and
generating PIL overlay cards, timed kinetic ASS subtitles, synthesized UI SFX,
section punch-zooms, color grading, and a BT.709 H.264/AAC MP4.

Usage:
    python3 json_video_editor.py <edit_plan.json>
    python3 json_video_editor.py --check
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import subprocess
import tempfile
from typing import Any, Dict, List, Optional, Tuple
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def _font(path: str, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default()  # type: ignore[return-value]


def _hex_to_rgba(hex_color: str, alpha: int = 255) -> Tuple[int, int, int, int]:
    s = hex_color.strip().lstrip("#")
    if len(s) == 6:
        return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16), alpha)
    if len(s) == 8:
        return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16), int(s[6:8], 16))
    return (255, 255, 255, alpha)


def _hex_to_ass_bgr(hex_color: str) -> str:
    s = hex_color.strip().lstrip("#")
    if len(s) == 6:
        r, g, b = s[0:2], s[2:4], s[4:6]
        return f"&H00{b.upper()}{g.upper()}{r.upper()}"
    return "&H00FFFFFF"


def format_ass_time(seconds: float) -> str:
    sec = max(0.0, float(seconds))
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec % 60.0
    return f"{h}:{m:02d}:{s:05.2f}"


def _fit_font(
    draw: ImageDraw.ImageDraw,
    lines: List[str],
    font_path: str,
    max_w: int,
    start_size: int,
) -> ImageFont.FreeTypeFont:
    size = start_size
    while size > 14:
        f = _font(font_path, size)
        widest = max((draw.textbbox((0, 0), ln, font=f)[2] for ln in lines), default=0)
        if widest <= max_w:
            return f
        size -= 1
    return _font(font_path, 14)


def _draw_shadowed_card(
    card_w: int,
    card_h: int,
    pad: int,
    radius: int,
    bg_rgba: Tuple[int, int, int, int],
    outline_rgba: Optional[Tuple[int, int, int, int]] = None,
) -> Image.Image:
    cw, ch = card_w + pad * 2, card_h + pad * 2
    shadow = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle([(pad, pad + 4), (pad + card_w - 1, pad + card_h + 3)], radius=radius, fill=(0, 0, 0, 62))
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=7))

    card = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    cd = ImageDraw.Draw(card)
    cd.rounded_rectangle(
        [(pad, pad), (pad + card_w - 1, pad + card_h - 1)],
        radius=radius,
        fill=bg_rgba,
        outline=outline_rgba,
        width=2 if outline_rgba else 0,
    )
    return Image.alpha_composite(shadow, card)


def render_card_png(card_cfg: Dict[str, Any], out_path: Path, video_w: int) -> Path:
    """Render a hook, info, or table overlay card PNG."""
    kind = str(card_cfg.get("type", "hook")).lower()
    pad = 16
    card_w = int(card_cfg.get("width", min(656, video_w - 64)))
    bg_rgba = _hex_to_rgba(str(card_cfg.get("bg_color", "#FFFFFF")), 250)
    text_rgba = _hex_to_rgba(str(card_cfg.get("text_color", "#7A00F5" if kind == "hook" else "#1C2026")), 255)

    if kind == "hook":
        lines = [str(x) for x in (card_cfg.get("lines") or []) if str(x).strip()] or ["HOOK"]
        card_h = int(card_cfg.get("height", max(120, 44 * len(lines) + 56)))
        radius = int(card_cfg.get("radius", 36))
        img = _draw_shadowed_card(card_w, card_h, pad, radius, bg_rgba)
        draw = ImageDraw.Draw(img)
        font = _fit_font(draw, lines, FONT_BOLD, card_w - 56, int(card_cfg.get("font_size", 36)))
        boxes = [draw.textbbox((0, 0), ln, font=font) for ln in lines]
        heights = [b[3] - b[1] for b in boxes]
        gap = 12
        total_h = sum(heights) + gap * (len(lines) - 1)
        y = pad + (card_h - total_h) / 2.0
        for ln, b, h in zip(lines, boxes, heights):
            lw = b[2] - b[0]
            x = pad + (card_w - lw) / 2.0 - b[0]
            draw.text((x, y - b[1]), ln, font=font, fill=text_rgba)
            y += h + gap
    elif kind == "info":
        title = str(card_cfg.get("title", "")).strip()
        body = [str(x) for x in (card_cfg.get("body") or [])]
        tag = str(card_cfg.get("tag", "")).strip()
        card_h = int(card_cfg.get("height", 64 + 28 * max(1, len(body)) + (28 if tag else 12)))
        radius = int(card_cfg.get("radius", 10))
        img = _draw_shadowed_card(card_w, card_h, pad, radius, bg_rgba, outline_rgba=(218, 222, 228, 255))
        draw = ImageDraw.Draw(img)
        draw.ellipse([(pad + 22, pad + 26), (pad + 30, pad + 34)], outline=text_rgba, width=2)
        f_title = _font(FONT_BOLD, 21)
        f_body = _font(FONT_REG, 19)
        f_tag = _font(FONT_REG, 15)
        if title:
            draw.text((pad + 42, pad + 18), title, font=f_title, fill=text_rgba)
        y = pad + 52
        for ln in body:
            draw.text((pad + 42, y), ln, font=f_body, fill=(52, 58, 66, 255))
            y += 28
        if tag:
            draw.text((pad + 42, pad + card_h - 32), tag, font=f_tag, fill=(138, 144, 152, 255))
    else:  # table
        headers = [str(h) for h in (card_cfg.get("headers") or ["Mục", "Chi tiết"])]
        rows = [[str(c) for c in r] for r in (card_cfg.get("rows") or [])]
        card_h = int(card_cfg.get("height", 64 + 38 * max(1, len(rows))))
        radius = int(card_cfg.get("radius", 10))
        img = _draw_shadowed_card(card_w, card_h, pad, radius, bg_rgba, outline_rgba=(218, 222, 228, 255))
        draw = ImageDraw.Draw(img)
        f_hdr = _font(FONT_BOLD, 17)
        f_cell = _font(FONT_REG, 17)
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

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "PNG")
    return out_path


def build_ass_from_items(captions_cfg: Dict[str, Any], out_ass: Path, width: int, height: int) -> Path:
    """Write an ASS subtitle file from timed caption items."""
    style = captions_cfg.get("style") or {}
    color = _hex_to_ass_bgr(str(style.get("color", "#97E12E")))
    outline_color = _hex_to_ass_bgr(str(style.get("outline_color", "#000000")))
    font_size = int(style.get("font_size", 46))
    margin_v = int(style.get("margin_v", int(height * 0.16)))
    uppercase = bool(style.get("uppercase", True))
    pop_in = bool(style.get("pop_in", True))

    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {width}",
        f"PlayResY: {height}",
        "WrapStyle: 2",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Default,DejaVu Sans,{font_size},{color},&H00FFFFFF,{outline_color},&H80000000,-1,0,0,0,100,100,0,0,1,4,1,2,24,24,{margin_v},1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    for item in captions_cfg.get("items") or []:
        text = str(item.get("text", "")).strip()
        if not text:
            continue
        if uppercase:
            text = text.upper()
        text = text.replace("\n", "\\N")
        anim = r"{\fscx85\fscy85\t(0,80,\fscx100\fscy100)}" if pop_in else ""
        start = format_ass_time(float(item.get("start", 0.0)))
        end = format_ass_time(float(item.get("end", 0.0)))
        lines.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{anim}{text}")

    out_ass.parent.mkdir(parents=True, exist_ok=True)
    out_ass.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out_ass


def synthesize_sfx_wav(kind: str, out_path: Path, sample_rate: int = 44100) -> Path:
    """Synthesize a clean UI SFX WAV (pop, ding, or whoosh)."""
    kind = kind.lower().strip()
    if kind == "ding":
        dur = 0.28
        t = np.linspace(0, dur, int(sample_rate * dur), endpoint=False)
        sig = (0.55 * np.sin(2 * math.pi * 1046.5 * t) + 0.25 * np.sin(2 * math.pi * 1568.0 * t)) * np.exp(-t * 11.0)
    elif kind == "whoosh":
        dur = 0.22
        n = int(sample_rate * dur)
        t = np.linspace(0, dur, n, endpoint=False)
        rng = np.random.default_rng(42)
        noise = rng.normal(0, 0.25, n)
        env = np.sin(math.pi * t / dur) ** 1.5
        sig = noise * env
    else:  # pop
        dur = 0.09
        t = np.linspace(0, dur, int(sample_rate * dur), endpoint=False)
        freq = 520.0 * np.exp(-t * 22.0) + 140.0
        sig = 0.65 * np.sin(2 * math.pi * freq * t) * np.exp(-t * 32.0)

    pcm = np.clip(sig * 32767.0, -32768, 32767).astype(np.int16)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm.tobytes())
    return out_path


def _probe_video(video_path: Path) -> Dict[str, Any]:
    res = subprocess.run(
        [
            "ffprobe",
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(video_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(res.stdout)
    streams = data.get("streams", [])
    v_stream = next((s for s in streams if s.get("codec_type") == "video"), {})
    has_audio = any(s.get("codec_type") == "audio" for s in streams)
    return {
        "duration": float(data.get("format", {}).get("duration", 0.0)),
        "width": int(v_stream.get("width", 720)),
        "height": int(v_stream.get("height", 1280)),
        "has_audio": has_audio,
    }


def _punch_zoom_filter(punch_zooms: List[Dict[str, Any]], w: int, h: int, in_label: str, out_label: str) -> str:
    expr_parts: List[str] = []
    for pz in punch_zooms:
        s = float(pz.get("start", 0.0))
        e = float(pz.get("end", 0.0))
        sc = max(1.0, float(pz.get("scale", 1.0)))
        if e > s and sc > 1.001:
            expr_parts.append(f"between(t,{s:.3f},{e:.3f})*{sc:.4f}")
    if not expr_parts:
        return f"{in_label}null{out_label}"
    # Use scale + crop with dynamic zoom expression (headroom-biased y)
    cond = "1.0"
    for pz in reversed(punch_zooms):
        s = float(pz.get("start", 0.0))
        e = float(pz.get("end", 0.0))
        sc = max(1.0, float(pz.get("scale", 1.0)))
        if e > s and sc > 1.001:
            cond = f"if(between(t,{s:.3f},{e:.3f}),{sc:.4f},{cond})"
    return (
        f"{in_label}scale=w='trunc({w}*({cond})/2)*2':h='trunc({h}*({cond})/2)*2':eval=frame,"
        f"crop={w}:{h}:'(iw-{w})/2':'(ih-{h})*0.35'{out_label}"
    )


def build_filtergraph(
    cfg: Dict[str, Any],
    work_dir: Path,
    has_audio: bool,
    duration: float,
) -> Tuple[List[str], str, str, str]:
    """Assemble ffmpeg inputs and filter_complex graph from edit_plan JSON."""
    w = int(cfg.get("width", 720))
    h = int(cfg.get("height", 1280))
    fps = int(cfg.get("fps", 24))

    inputs: List[str] = ["-i", str(cfg["input_video"])]
    idx = 1
    v_parts: List[str] = [
        f"[0:v]fps={fps},scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1[v_base]"
    ]
    cur = "[v_base]"

    pzs = cfg.get("punch_zooms") or []
    if pzs:
        v_parts.append(_punch_zoom_filter(pzs, w, h, cur, "[v_pz]"))
        cur = "[v_pz]"

    cg = cfg.get("color_grade")
    if isinstance(cg, dict) and cg:
        contrast = float(cg.get("contrast", 1.0))
        sat = float(cg.get("saturation", 1.0))
        bright = float(cg.get("brightness", 0.0))
        gamma = float(cg.get("gamma", 1.0))
        v_parts.append(f"{cur}eq=contrast={contrast}:saturation={sat}:brightness={bright}:gamma={gamma}[v_cg]")
        cur = "[v_cg]"

    for i, card in enumerate(cfg.get("cards") or []):
        png_path = render_card_png(card, work_dir / f"card_{i}.png", w)
        inputs.extend(["-loop", "1", "-t", f"{max(0.1, duration):.3f}", "-i", str(png_path)])
        y_pos = int(card.get("y", 90))
        start = float(card.get("start", 0.0))
        end = float(card.get("end", max(start + 0.1, duration)))
        nxt = f"[v_c{i}]"
        v_parts.append(
            f"{cur}[{idx}:v]overlay=x=(W-w)/2:y={y_pos}:shortest=1:enable='between(t,{start:.3f},{end:.3f})'{nxt}"
        )
        cur = nxt
        idx += 1

    captions = cfg.get("captions")
    if isinstance(captions, dict) and (captions.get("items") or []):
        ass_path = build_ass_from_items(captions, work_dir / "captions.ass", w, h)
        escaped = str(ass_path).replace("\\", "/").replace(":", "\\:")
        v_parts.append(f"{cur}subtitles='{escaped}'[vout]")
    else:
        v_parts.append(f"{cur}null[vout]")

    # Audio graph
    a_parts: List[str] = []
    if has_audio:
        a_parts.append("[0:a]aresample=44100[a_main]")
    else:
        a_parts.append(f"anullsrc=channel_layout=stereo:sample_rate=44100,atrim=0:{max(0.1, duration):.3f}[a_main]")

    mix_labels = ["[a_main]"]
    sfx_cache: Dict[str, Path] = {}
    for i, sfx in enumerate(cfg.get("sfx") or []):
        kind = str(sfx.get("type", "pop")).lower()
        if kind not in sfx_cache:
            sfx_cache[kind] = synthesize_sfx_wav(kind, work_dir / f"sfx_{kind}.wav")
        inputs.extend(["-i", str(sfx_cache[kind])])
        delay_ms = max(0, int(float(sfx.get("time", 0.0)) * 1000))
        vol = float(sfx.get("volume", 0.35))
        lbl = f"[a_s{i}]"
        a_parts.append(f"[{idx}:a]adelay={delay_ms}|{delay_ms},volume={vol:.3f}{lbl}")
        mix_labels.append(lbl)
        idx += 1

    loudnorm = bool(cfg.get("loudnorm", True))
    if len(mix_labels) > 1:
        amix_out = "[a_mix]" if loudnorm else "[aout]"
        a_parts.append(f"{''.join(mix_labels)}amix=inputs={len(mix_labels)}:duration=first:normalize=0{amix_out}")
        a_cur = amix_out
    else:
        a_cur = "[a_main]"

    if loudnorm:
        a_parts.append(f"{a_cur}loudnorm=I=-16:TP=-1.5:LRA=11[aout]")
    elif a_cur != "[aout]":
        a_parts.append(f"{a_cur}anull[aout]")

    return inputs, ";".join(v_parts + a_parts), "[vout]", "[aout]"


def run_edit_plan(config_path: Path) -> Path:
    cfg_path = Path(config_path).resolve()
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    in_video = Path(cfg["input_video"]).resolve()
    out_video = Path(cfg["output_video"]).resolve()
    out_video.parent.mkdir(parents=True, exist_ok=True)

    info = _probe_video(in_video)
    work_dir = cfg_path.parent / "build"
    work_dir.mkdir(parents=True, exist_ok=True)

    inputs, filter_complex, v_map, a_map = build_filtergraph(
        cfg=cfg,
        work_dir=work_dir,
        has_audio=info["has_audio"],
        duration=info["duration"],
    )

    cmd = [
        "ffmpeg",
        "-y",
        *inputs,
        "-filter_complex",
        filter_complex,
        "-map",
        v_map,
        "-map",
        a_map,
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "18",
        "-colorspace",
        "bt709",
        "-color_trc",
        "bt709",
        "-color_primaries",
        "bt709",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-ar",
        "44100",
        "-ac",
        "2",
        "-movflags",
        "+faststart",
        str(out_video),
    ]
    subprocess.run(cmd, check=True)
    _probe_video(out_video)
    return out_video


def self_test() -> None:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        card = render_card_png({"type": "hook", "lines": ["TEST HOOK"]}, tmp / "hook.png", 720)
        assert card.exists() and card.stat().st_size > 0
        ass = build_ass_from_items({"items": [{"start": 0.0, "end": 1.0, "text": "Hello"}]}, tmp / "cap.ass", 720, 1280)
        assert "Dialogue:" in ass.read_text(encoding="utf-8")
        wav = synthesize_sfx_wav("pop", tmp / "pop.wav")
        assert wav.exists() and wav.stat().st_size > 44
        inputs, fg, vm, am = build_filtergraph(
            {
                "input_video": str(tmp / "in.mp4"),
                "output_video": str(tmp / "out.mp4"),
                "cards": [{"type": "info", "title": "Title", "body": ["Line 1"], "start": 0.0, "end": 1.0}],
                "captions": {"items": [{"start": 0.1, "end": 0.9, "text": "WORD"}]},
                "sfx": [{"time": 0.2, "type": "ding"}],
            },
            tmp,
            has_audio=True,
            duration=2.0,
        )
        assert vm == "[vout]" and am == "[aout]" and "overlay=" in fg and len(inputs) >= 4
    print("json_video_editor self_test passed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Declarative JSON video editor")
    parser.add_argument("config", nargs="?", help="Path to edit_plan.json")
    parser.add_argument("--check", action="store_true", help="Run self-test")
    args = parser.parse_args()
    if args.check:
        self_test()
    elif args.config:
        run_edit_plan(Path(args.config))
    else:
        parser.error("Provide edit_plan.json or --check")
