#!/usr/bin/env python3
"""
effect_editor.py
────────────────
Unified, declarative, stackable JSON post-production engine for short-form videos.

Every effect in the `effects/` package is a composable primitive that can be
stacked in any order via the `"effects": [...]` array (or legacy flat keys):
- punch_zoom: Dynamic camera zooms & legacy seam transitions
- transition: Flash, fade_in, and fade_out transitions
- color_grade: Commercial color grading via FFmpeg eq
- progress_bar: Animated retention progress bar
- text_box / card / hook_card: Pillow-rendered hook, info, and table overlays
- subtitles / captions: Timed ASS subtitles or ElevenLabs word-level karaoke
- bgm: Background music bed with fade-in/out
- sfx: File-based or synthesized (pop, ding, whoosh) UI sound effects

Usage:
    python3 effect_editor.py <effects_config.json>
    python3 effect_editor.py --check
"""

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from effects import (
    EFFECT_REGISTRY,
    RenderContext,
    finalize_audio_graph,
    format_ass_time,
    format_multiline_text,
    group_words_into_chunks,
)

REPO_ROOT = Path(__file__).resolve().parents[5]
DEFAULT_SFX_DIR = REPO_ROOT / "projects/OpenMontage/.agents/skills/website-to-video/assets/sfx"


def resolve_path(p: str | Path, base_dir: Path | None = None) -> Path:
    """Resolve relative or absolute file paths against base_dir, ugc-video, or repo root."""
    p = Path(p)
    if p.is_absolute():
        return p
    bases = ([base_dir] if base_dir else []) + [REPO_ROOT / "projects/ugc-video", REPO_ROOT]
    for base in bases:
        cand = (base / p).resolve()
        if cand.exists():
            return cand
    if p.parts and (REPO_ROOT / p.parts[0]).exists():
        return (REPO_ROOT / p).resolve()
    return ((base_dir or (REPO_ROOT / "projects/ugc-video")) / p).resolve()


def get_video_info(video_path: Path) -> dict:
    """Retrieve video duration, width, height, and audio presence via ffprobe."""
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_format", "-show_streams", str(video_path)
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
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


def is_effect_enabled(cfg: dict, effect_name: str, has_data: bool = True) -> bool:
    """Determine whether a legacy top-level effect is active."""
    if not has_data:
        return False
    whitelist = cfg.get("enabled_effects")
    if whitelist is not None:
        return effect_name in whitelist
    eff_obj = cfg.get(effect_name)
    if isinstance(eff_obj, dict):
        return bool(eff_obj.get("enabled", True))
    return True


def normalize_effects_stack(cfg: dict) -> list[dict]:
    """Return an ordered list of effect dicts from either `effects` array or legacy flat keys."""
    if isinstance(cfg.get("effects"), list):
        return [e for e in cfg["effects"] if isinstance(e, dict) and e.get("enabled", True)]

    stack: list[dict] = []
    if is_effect_enabled(cfg, "punch_zooms", bool(cfg.get("punch_zooms"))):
        stack.append({
            "type": "punch_zoom",
            "windows": cfg["punch_zooms"],
            "transitions": cfg.get("scene_transitions", []),
        })
    if is_effect_enabled(cfg, "color_grade", "color_grade" in cfg):
        stack.append({"type": "color_grade", **(cfg.get("color_grade") or {})})
    if is_effect_enabled(cfg, "progress_bar", "progress_bar" in cfg):
        stack.append({"type": "progress_bar", **(cfg.get("progress_bar") or {})})

    hook_card = cfg.get("hook_card")
    hook_card_active = is_effect_enabled(cfg, "hook_card", hook_card is not None)
    if hook_card_active:
        stack.append({"type": "hook_card", **hook_card})

    for card in cfg.get("cards") or []:
        if isinstance(card, dict) and card.get("enabled", True):
            stack.append({"type": "text_box", **card})

    if is_effect_enabled(cfg, "subtitles", "alignment_json" in cfg or "subtitles" in cfg):
        if "alignment_json" in cfg:
            badges = cfg.get("badges", []) if is_effect_enabled(cfg, "badges", bool(cfg.get("badges"))) else []
            stack.append({
                "type": "subtitles",
                "alignment_json": cfg["alignment_json"],
                "clause_bounds": cfg.get("clause_bounds"),
                "badges": badges,
                "hook_banner": cfg.get("hook_banner"),
                "hook_card": hook_card if hook_card_active else None,
            })
        elif isinstance(cfg.get("subtitles"), dict):
            stack.append({"type": "subtitles", **cfg["subtitles"]})

    captions = cfg.get("captions")
    if isinstance(captions, dict) and captions.get("items") and is_effect_enabled(cfg, "captions", True):
        stack.append({"type": "subtitles", **captions})

    if is_effect_enabled(cfg, "bgm", "bgm" in cfg):
        stack.append({"type": "bgm", **(cfg.get("bgm") or {})})
    if is_effect_enabled(cfg, "sfx", bool(cfg.get("sfx_events"))):
        stack.append({"type": "sfx", "events": cfg["sfx_events"]})
    if isinstance(cfg.get("sfx"), list) and cfg["sfx"] and is_effect_enabled(cfg, "sfx", True):
        for s in cfg["sfx"]:
            if isinstance(s, dict) and s.get("enabled", True):
                stack.append({"type": "sfx", **s})

    return stack


def build_filtergraph(
    cfg: dict,
    info: dict,
    base_dir: Path,
    work_dir: Path,
) -> tuple[list[str], str]:
    """Assemble FFmpeg inputs and filter_complex graph from a stackable effects config."""
    w = int(cfg.get("width", info["width"]))
    h = int(cfg.get("height", info["height"]))
    fps = int(cfg.get("fps", 24))
    dur = float(info["duration"])
    in_video = resolve_path(cfg["input_video"], base_dir)
    sfx_dir = resolve_path(cfg.get("sfx_dir", DEFAULT_SFX_DIR), base_dir)

    ctx = RenderContext(
        width=w,
        height=h,
        fps=fps,
        duration=dur,
        has_audio=bool(info.get("has_audio", True)),
        base_dir=base_dir,
        work_dir=work_dir,
        sfx_dir=sfx_dir,
        resolve_path=lambda p: resolve_path(p, base_dir),
        ffmpeg_inputs=["-i", str(in_video)],
    )

    if "width" in cfg or "height" in cfg:
        ctx.v_filters.append(
            f"[0:v]fps={fps},scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1,settb=AVTB[v_base]"
        )
    else:
        ctx.v_filters.append(f"[0:v]fps={fps},settb=AVTB[v_base]")

    for eff in normalize_effects_stack(cfg):
        eff_type = str(eff.get("type", "")).strip().lower()
        handler = EFFECT_REGISTRY.get(eff_type)
        if handler is None:
            raise ValueError(f"Unknown effect type {eff_type!r}. Valid types: {', '.join(sorted(EFFECT_REGISTRY))}")
        handler(eff, ctx)

    ctx.v_filters.append(f"{ctx.cur_v}null[vout]")
    full_a_filter = finalize_audio_graph(ctx, loudnorm=bool(cfg.get("loudnorm", True)))
    return ctx.ffmpeg_inputs, ";".join(ctx.v_filters + [full_a_filter])


def run_effect_pipeline(config_path: Path) -> Path:
    """Execute the composite stackable effect rendering pipeline."""
    config_path = Path(config_path).resolve()
    base_dir = config_path.parent
    cfg = json.loads(config_path.read_text(encoding="utf-8"))

    in_video = resolve_path(cfg["input_video"], base_dir)
    out_video = resolve_path(cfg["output_video"], base_dir)
    out_video.parent.mkdir(parents=True, exist_ok=True)
    work_dir = out_video.parent / f".{out_video.stem}_work"
    work_dir.mkdir(parents=True, exist_ok=True)

    info = get_video_info(in_video)
    print(f"=== Effect Editor: Processing '{in_video.name}' ({info['duration']:.2f}s, {info['width']}x{info['height']}) ===")

    ffmpeg_inputs, filter_complex = build_filtergraph(cfg, info, base_dir, work_dir)

    cmd = [
        "ffmpeg", "-y",
        *ffmpeg_inputs,
        "-filter_complex", filter_complex,
        "-map", "[vout]", "-map", "[aout]",
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-colorspace", "bt709", "-color_trc", "bt709", "-color_primaries", "bt709",
        "-pix_fmt", "yuv420p",
        "-g", "48", "-keyint_min", "48", "-sc_threshold", "0",
        "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2",
        "-movflags", "+faststart",
        str(out_video),
    ]

    print(f"  [FFmpeg] Rendering composite filtergraph to: {out_video.name}...")
    subprocess.run(cmd, check=True)

    out_info = get_video_info(out_video)
    out_sz = out_video.stat().st_size / (1024 * 1024)
    print(f"=== Render Finished: {out_video.name} ({out_info['duration']:.2f}s, {out_sz:.2f}MB, {out_info['width']}x{out_info['height']} BT.709) ===")
    return out_video


def self_test() -> None:
    """Minimal self-check covering legacy helpers and stackable effect composition."""
    t_ass = format_ass_time(12.345)
    assert t_ass == "0:00:12.35", f"Expected 0:00:12.35, got {t_ass}"

    t_long = "MẪU GIẤY IN THIỆP CƯỚI: VỪA SANG VỪA KINH TẾ?"
    formatted = format_multiline_text(t_long, max_line_len=24)
    assert formatted == "MẪU GIẤY IN THIỆP CƯỚI\\NVỪA SANG VỪA KINH TẾ?"

    assert format_multiline_text("SHORT", max_line_len=20) == "SHORT"

    sample_words = [
        {"word": "A", "start": 0.0, "end": 0.3},
        {"word": "B", "start": 0.4, "end": 0.8},
        {"word": "C", "start": 0.9, "end": 1.2},
        {"word": "D", "start": 1.3, "end": 1.5},
        {"word": "E", "start": 1.6, "end": 2.0},
    ]
    chunks = group_words_into_chunks(sample_words, max_words=3)
    assert len(chunks) == 2

    test_cfg = {
        "bgm": {"enabled": True},
        "hook_card": {"enabled": False},
        "enabled_effects": ["bgm", "subtitles"],
    }
    assert is_effect_enabled(test_cfg, "bgm", True) is True
    assert is_effect_enabled(test_cfg, "hook_card", True) is False
    assert is_effect_enabled(test_cfg, "color_grade", True) is False

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        stacked_cfg = {
            "input_video": str(tmp / "in.mp4"),
            "output_video": str(tmp / "out.mp4"),
            "width": 360,
            "height": 640,
            "effects": [
                {"type": "punch_zoom", "start": 0.2, "end": 0.8, "scale": 1.08},
                {"type": "transition", "kind": "flash", "time": 0.8, "duration": 0.12},
                {"type": "color_grade", "contrast": 1.05, "saturation": 1.1, "gamma": 1.0},
                {"type": "text_box", "variant": "hook", "lines": ["STACKED"], "start": 0.0, "end": 1.0, "y": 40},
                {"type": "text_box", "variant": "box", "bg_alpha": 0, "shadow": False, "lines": ["EDITORIAL"], "text_color": "#FFFFFF", "brackets": True, "accent_bar_color": "#E8E61E", "start": 0.0, "end": 1.0, "y": 80},
                {"type": "text_box", "variant": "box", "bg_alpha": 0, "shadow": False, "lines": ["NEON HOOK"], "text_color": "#FFFFFF", "stroke_width": 4, "stroke_color": "#127A2A", "outer_stroke_width": 10, "outer_stroke_color": "#35FF68", "glow_radius": 5, "start": 0.0, "end": 1.0, "y": 100},
                {"type": "text_box", "variant": "highlight_lines", "align": "left", "x": 52, "y": 400, "start": 0.0, "end": 1.0, "lines": [{"text": "LINE ONE", "bg_color": "#0D626E"}, {"text": "LINE TWO", "bg_color": "#BA0F18"}]},
                {"type": "text_box", "variant": "info", "title": "Note", "body": ["Detail"], "start": 0.5, "end": 1.5, "y": 240},
                {"type": "subtitles", "alignment": 8, "bold": False, "border_style": 3, "items": [{"start": 0.1, "end": 0.9, "text": "HELLO", "color": "#FF0000", "font_size": 52, "margin_v": 120}], "color": "#FFE119", "outline_color": "#000000", "outer_outline_color": "#FFFFFF", "outer_outline_width": 8},
                {"type": "sfx", "time": 0.2, "sound": "pop"},
                {"type": "sfx", "time": 0.8, "sound": "ding"},
            ],
        }
        inputs, fg = build_filtergraph(
            stacked_cfg,
            {"duration": 2.0, "width": 360, "height": 640, "has_audio": False},
            tmp,
            tmp,
        )
        assert "overlay=" in fg and "subtitles=" in fg and "anullsrc=" in fg and "amix=" in fg
        ass_files = list(tmp.glob("sub_*.ass"))
        assert ass_files and "DefaultOuter" in ass_files[0].read_text(encoding="utf-8")
        assert len(inputs) >= 6
    print("self_test passed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Unified stackable JSON video effect editor")
    parser.add_argument("config", nargs="?", default="projects/ugc-video/scripts/new_system/configs/post_4_effects.json", help="Path to effects config JSON")
    parser.add_argument("--check", action="store_true", help="Run self-test assertion")
    args = parser.parse_args()

    if args.check:
        self_test()
    else:
        run_effect_pipeline(Path(args.config))
