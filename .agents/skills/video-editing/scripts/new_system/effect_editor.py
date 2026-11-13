#!/usr/bin/env python3
"""
effect_editor.py
────────────────
Modular, declarative post-production engine for transforming raw UGC & talking-head
videos into high-retention, hyper-engaging viral short-form videos (TikTok / Reels / Shorts).

All effects are modularized in the `effects/` package:
- hook_card: Centered hero card pill overlay
- subtitles: Word-by-word kinetic karaoke ASS typography & badge cards
- punch_zoom: Dynamic camera zooms & seam flash cut transitions
- color_grade: Commercial color grading via FFmpeg eq
- progress_bar: Animated retention progress bar
- audio_mix: BGM ducking, timed SFX events, and EBU R128 loudness normalization

Usage:
    python3 effect_editor.py <effects_config.json>
    python3 effect_editor.py --check
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

# Ensure new_system directory is on sys.path for direct imports
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from effects import (
    generate_hook_card_image,
    build_hook_card_filter,
    extract_words_from_alignment,
    group_words_into_chunks,
    format_multiline_text,
    format_ass_time,
    build_ass_subtitles,
    apply_subtitles_filter,
    build_punch_zooms_filter,
    build_color_grade_filter,
    build_progress_bar_filter,
    build_audio_graph,
)

REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_SFX_DIR = REPO_ROOT / "projects/OpenMontage/.agents/skills/website-to-video/assets/sfx"


def resolve_path(p: str | Path, base_dir: Path | None = None) -> Path:
    """Resolve relative or absolute file paths against base_dir, ugc-video, or repo root."""
    p = Path(p)
    if p.is_absolute() and p.exists():
        return p
    bases = ([base_dir] if base_dir else []) + [REPO_ROOT / "projects/ugc-video", REPO_ROOT]
    for base in bases:
        cand = (base / p).resolve()
        if cand.exists():
            return cand
    return ((base_dir or (REPO_ROOT / "projects/ugc-video")) / p).resolve()


def get_video_info(video_path: Path) -> dict:
    """Retrieve video duration, width, and height via ffprobe."""
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_format", "-show_streams", str(video_path)
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(res.stdout)
    v_stream = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), {})
    duration = float(data.get("format", {}).get("duration", 0.0))
    width = int(v_stream.get("width", 720))
    height = int(v_stream.get("height", 1280))
    return {"duration": duration, "width": width, "height": height}


def is_effect_enabled(cfg: dict, effect_name: str, has_data: bool = True) -> bool:
    """Determine whether an effect is active based on enabled_effects whitelist and per-effect config."""
    if not has_data:
        return False
    whitelist = cfg.get("enabled_effects")
    if whitelist is not None:
        return effect_name in whitelist
    eff_obj = cfg.get(effect_name)
    if isinstance(eff_obj, dict):
        return bool(eff_obj.get("enabled", True))
    return True


def run_effect_pipeline(config_path: Path) -> Path:
    """Execute the composite modular effect rendering pipeline."""
    config_path = Path(config_path).resolve()
    base_dir = config_path.parent
    cfg = json.loads(config_path.read_text(encoding="utf-8"))

    in_video = resolve_path(cfg["input_video"], base_dir)
    out_video = resolve_path(cfg["output_video"], base_dir)
    out_video.parent.mkdir(parents=True, exist_ok=True)

    info = get_video_info(in_video)
    dur = info["duration"]
    w = info["width"]
    h = info["height"]
    print(f"=== Effect Editor: Processing '{in_video.name}' ({dur:.2f}s, {w}x{h}) ===")

    ffmpeg_inputs = ["-i", str(in_video)]
    input_stream_idx = 1
    v_filter_parts = []

    # 1. Modular Punch Zooms & Transitions
    pz_data = cfg.get("punch_zooms", [])
    if is_effect_enabled(cfg, "punch_zooms", bool(pz_data)):
        pz_filter, cur_v_label = build_punch_zooms_filter(
            pz_data, dur, w, h, cfg.get("scene_transitions", [])
        )
        v_filter_parts.append(pz_filter)
    else:
        v_filter_parts.append("[0:v]fps=24,settb=AVTB[v_base]")
        cur_v_label = "[v_base]"

    # 2. Modular Color Grading
    if is_effect_enabled(cfg, "color_grade", "color_grade" in cfg):
        cg_filter = build_color_grade_filter(cfg.get("color_grade"), base_label=cur_v_label, out_label="[v_cg]")
        v_filter_parts.append(cg_filter)
        cur_v_label = "[v_cg]"

    # 3. Modular Progress Bar
    if is_effect_enabled(cfg, "progress_bar", "progress_bar" in cfg):
        pb_filter = build_progress_bar_filter(cfg.get("progress_bar"), dur, w, h, base_label=cur_v_label, out_label="[v_pb]")
        if pb_filter:
            v_filter_parts.append(pb_filter)
            cur_v_label = "[v_pb]"

    # 4. Modular Hook Card Overlay
    hook_card = cfg.get("hook_card")
    if is_effect_enabled(cfg, "hook_card", hook_card is not None):
        card_png = generate_hook_card_image(hook_card, base_dir / "hook_card.png", w, h)
        ffmpeg_inputs.extend(["-loop", "1", "-i", str(card_png)])
        card_input_idx = input_stream_idx
        input_stream_idx += 1

        card_filters = build_hook_card_filter(hook_card, card_input_idx, cur_v_label, "[v_card]", h)
        v_filter_parts.extend(card_filters)
        cur_v_label = "[v_card]"

    # 5. Modular Kinetic Typography & Badges
    has_subtitles = "alignment_json" in cfg or "subtitles" in cfg
    if is_effect_enabled(cfg, "subtitles", has_subtitles):
        align_path = resolve_path(cfg["alignment_json"], base_dir)
        cb_val = cfg.get("clause_bounds")
        if isinstance(cb_val, (str, Path)):
            clause_bounds = json.loads(resolve_path(cb_val, base_dir).read_text(encoding="utf-8"))
        elif isinstance(cb_val, list):
            clause_bounds = cb_val
        else:
            cand_cb = align_path.parent / "clause_bounds.json"
            clause_bounds = json.loads(cand_cb.read_text(encoding="utf-8")) if cand_cb.exists() else None

        words = extract_words_from_alignment(align_path, clause_bounds)
        chunks = group_words_into_chunks(words)
        print(f"  [Captions] Extracted {len(words)} aligned words into {len(chunks)} kinetic chunks")

        ass_path = out_video.parent / f"{out_video.stem}.ass"
        active_card = hook_card if is_effect_enabled(cfg, "hook_card", hook_card is not None) else None
        build_ass_subtitles(
            chunks=chunks,
            badges=cfg.get("badges", []) if is_effect_enabled(cfg, "badges", bool(cfg.get("badges"))) else [],
            hook_banner=cfg.get("hook_banner"),
            out_ass_path=ass_path,
            width=w,
            height=h,
            hook_card=active_card
        )
        print(f"  [ASS] Generated styled kinetic subtitles at: {ass_path.name}")
        sub_filter = apply_subtitles_filter(ass_path, base_label=cur_v_label, out_label="[vout]")
        v_filter_parts.append(sub_filter)
    else:
        v_filter_parts.append(f"{cur_v_label}null[vout]")

    full_v_filter = ";".join(v_filter_parts)

    # 6. Modular Audio Sound Design (BGM + SFX + Broadcast Loudnorm)
    bgm_cfg = cfg.get("bgm") if is_effect_enabled(cfg, "bgm", "bgm" in cfg) else None
    sfx_events = cfg.get("sfx_events", []) if is_effect_enabled(cfg, "sfx", bool(cfg.get("sfx_events"))) else []
    sfx_dir = resolve_path(cfg.get("sfx_dir", DEFAULT_SFX_DIR), base_dir)

    extra_audio_inputs, full_a_filter, _ = build_audio_graph(
        bgm_cfg=bgm_cfg,
        sfx_events=sfx_events,
        sfx_dir=sfx_dir,
        total_dur=dur,
        input_stream_start_idx=input_stream_idx,
        resolve_path_fn=lambda p: resolve_path(p, base_dir)
    )
    ffmpeg_inputs.extend(extra_audio_inputs)

    # Encode with Social BT.709 Profile
    cmd = [
        "ffmpeg", "-y",
        *ffmpeg_inputs,
        "-filter_complex", f"{full_v_filter};{full_a_filter}",
        "-map", "[vout]", "-map", "[aout]",
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-colorspace", "bt709", "-color_trc", "bt709", "-color_primaries", "bt709",
        "-pix_fmt", "yuv420p",
        "-g", "48", "-keyint_min", "48", "-sc_threshold", "0",
        "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2",
        "-movflags", "+faststart",
        str(out_video)
    ]

    print(f"  [FFmpeg] Rendering composite filtergraph to: {out_video.name}...")
    subprocess.run(cmd, check=True)

    # Verification
    res = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration,size",
         "-show_entries", "stream=width,height,codec_name", "-of", "json", str(out_video)],
        capture_output=True, text=True, check=True
    )
    v_data = json.loads(res.stdout)
    out_dur = float(v_data["format"]["duration"])
    out_sz = int(v_data["format"]["size"]) / (1024 * 1024)
    print(f"=== Render Finished: {out_video.name} ({out_dur:.2f}s, {out_sz:.2f}MB, 720x1280 BT.709) ===")
    return out_video


def self_test():
    """Minimal self-check as required by ponytail guidelines."""
    t_ass = format_ass_time(12.345)
    assert t_ass == "0:00:12.35", f"Expected 0:00:12.35, got {t_ass}"

    t_long = "MẪU GIẤY IN THIỆP CƯỚI: VỪA SANG VỪA KINH TẾ?"
    formatted = format_multiline_text(t_long, max_line_len=24)
    assert "\\N" in formatted, f"Expected \\N in formatted text, got {formatted}"
    assert formatted == "MẪU GIẤY IN THIỆP CƯỚI\\NVỪA SANG VỪA KINH TẾ?"

    assert format_multiline_text("SHORT", max_line_len=20) == "SHORT"
    assert format_multiline_text("A\\nB") == "A\\nB"

    sample_words = [
        {"word": "A", "start": 0.0, "end": 0.3},
        {"word": "B", "start": 0.4, "end": 0.8},
        {"word": "C", "start": 0.9, "end": 1.2},
        {"word": "D", "start": 1.3, "end": 1.5},
        {"word": "E", "start": 1.6, "end": 2.0},
    ]
    chunks = group_words_into_chunks(sample_words, max_words=3)
    assert len(chunks) == 2, f"Expected 2 chunks, got {len(chunks)}"
    assert [w["word"] for w in chunks[0]] == ["A", "B", "C"]
    assert [w["word"] for w in chunks[1]] == ["D", "E"]

    # Test is_effect_enabled
    test_cfg = {
        "bgm": {"enabled": True},
        "hook_card": {"enabled": False},
        "enabled_effects": ["bgm", "subtitles"]
    }
    assert is_effect_enabled(test_cfg, "bgm", True) is True
    assert is_effect_enabled(test_cfg, "hook_card", True) is False
    assert is_effect_enabled(test_cfg, "color_grade", True) is False
    print("self_test passed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Multi-track effect & dynamic typography editor")
    parser.add_argument("config", nargs="?", default="projects/ugc-video/scripts/new_system/configs/post_4_effects.json", help="Path to effects config JSON")
    parser.add_argument("--check", action="store_true", help="Run self-test assertion")
    args = parser.parse_args()

    if args.check:
        self_test()
    else:
        run_effect_pipeline(Path(args.config))
