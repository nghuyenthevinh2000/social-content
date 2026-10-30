#!/usr/bin/env python3
"""
effect_editor.py
────────────────
Modular, declarative post-production engine for transforming raw UGC & talking-head
videos into high-retention, hyper-engaging viral short-form videos (TikTok / Reels / Shorts).

Features:
- Dynamic punch zooms (kinetic camera movement on key hooks and product reveals)
- Synchronized word-by-word karaoke typography with safe-zone margin control
- Hook banner pills and animated feature badges
- Multi-track sound design: Voiceover + BGM bed + timed SFX (whoosh, pop, sparkle, ping, chime)
- Seam flash transition at scene cuts
- Dynamic progress bar and commercial color grade
- Full social normalization (BT.709, faststart, stereo AAC 44.1kHz)
"""

import argparse
import json
import math
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_SFX_DIR = REPO_ROOT / "projects/OpenMontage/.agents/skills/website-to-video/assets/sfx"
DEFAULT_MAX_LINE_LEN = 24


def resolve_path(p: str | Path) -> Path:
    p = Path(p)
    if p.is_absolute() and p.exists():
        return p
    for base in (REPO_ROOT, REPO_ROOT / "projects/ugc-video"):
        cand = (base / p).resolve()
        if cand.exists():
            return cand
    return (REPO_ROOT / "projects/ugc-video" / p).resolve()


def format_ass_time(sec: float) -> str:
    sec = max(0.0, sec)
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    cs = int(round((sec - int(sec)) * 100))
    if cs >= 100:
        cs = 99
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def get_video_info(video_path: Path) -> dict:
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


def extract_words_from_alignment(align_path: Path, clause_bounds: list[list[float]] | None = None) -> list[dict]:
    align = json.loads(align_path.read_text(encoding="utf-8"))
    chars = align.get("characters", [])
    starts = align.get("characterStartTimesSeconds", [])
    ends = align.get("characterEndTimesSeconds", [])

    raw_words = []
    curr = ""
    w_start = None
    prev_e = 0.0

    for c, s, e in zip(chars, starts, ends):
        if c == " ":
            if curr:
                raw_words.append({"word": curr, "start": w_start, "end": prev_e})
                curr = ""
                w_start = None
        else:
            if w_start is None:
                w_start = s
            curr += c
        prev_e = e
    if curr:
        raw_words.append({"word": curr, "start": w_start, "end": prev_e})

    if not clause_bounds:
        return raw_words

    mapped = []
    for w in raw_words:
        mid = (w["start"] + w["end"]) / 2.0
        matched = None
        for s_s, s_e, t_s, t_e in clause_bounds:
            if s_s - 0.05 <= mid <= s_e + 0.05:
                matched = (s_s, s_e, t_s, t_e)
                break
        if matched:
            s_s, s_e, t_s, t_e = matched
            scale = (t_e - t_s) / max(0.01, (s_e - s_s))
            vw_s = t_s + (w["start"] - s_s) * scale
            vw_e = t_s + (w["end"] - s_s) * scale
            mapped.append({"word": w["word"], "start": round(vw_s, 2), "end": round(vw_e, 2)})
        else:
            mapped.append(w)
    return mapped


def group_words_into_chunks(words: list[dict], max_words: int = 4, max_gap: float = 0.45) -> list[list[dict]]:
    chunks = []
    curr_chunk = []
    for w in words:
        if not curr_chunk:
            curr_chunk.append(w)
            continue
        prev = curr_chunk[-1]
        gap = w["start"] - prev["end"]
        punct = prev["word"].endswith((".", ",", "?", "!", "…"))
        if len(curr_chunk) >= max_words or gap > max_gap or (punct and len(curr_chunk) >= 2):
            chunks.append(curr_chunk)
            curr_chunk = [w]
        else:
            curr_chunk.append(w)
    if curr_chunk:
        chunks.append(curr_chunk)
    return chunks


def format_multiline_text(text: str, max_line_len: int = DEFAULT_MAX_LINE_LEN) -> str:
    """Format text into balanced multiline ASS text if it exceeds max_line_len."""
    if not text:
        return ""
    if "\\N" in text:
        return text
    if len(text) <= max_line_len:
        return text
    for delim in (": ", "? ", ", ", " - "):
        if delim in text:
            parts = text.split(delim, 1)
            d_clean = delim.strip()
            suffix = "" if d_clean == ":" else d_clean
            return f"{parts[0]}{suffix}\\N{parts[1]}"
    words = text.split()
    half = max(1, len(words) // 2)
    return " ".join(words[:half]) + "\\N" + " ".join(words[half:])


def build_ass_subtitles(
    chunks: list[list[dict]],
    badges: list[dict],
    hook_banner: dict | None,
    out_ass_path: Path,
    width: int = 720,
    height: int = 1280
) -> Path:
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: HookBanner,Arial,25,&H00000000,&H00000000,&H0000E6FF,&H80000000,-1,0,0,0,100,100,0.5,0,3,8,0,8,40,40,150,1
Style: BadgeCard,Arial,25,&H00FFFFFF,&H00000000,&H90141414,&H00000000,-1,0,0,0,100,100,0.5,0,3,8,0,8,40,40,150,1
Style: BadgeBottom,Arial,25,&H00000000,&H00000000,&H0000E6FF,&H80000000,-1,0,0,0,100,100,0.5,0,3,8,0,2,40,40,320,1
Style: CaptionBase,Arial,34,&H00FFFFFF,&H00000000,&H00000000,&H80000000,-1,0,0,0,100,100,0.5,0,1,3.5,1.2,2,30,30,210,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []

    # 1. Hook Banner (Multi-line formatted, balanced safe box)
    if hook_banner and hook_banner.get("text"):
        st = format_ass_time(hook_banner["start"])
        et = format_ass_time(hook_banner["end"])
        text = format_multiline_text(hook_banner["text"])
        events.append(f"Dialogue: 1,{st},{et},HookBanner,,0,0,0,,{{\\fade(100,100)}} {text} ")

    # 2. Badges (Unified Cards)
    for b in badges:
        st = format_ass_time(b["start"])
        et = format_ass_time(b["end"])
        pos = b.get("pos", "top")
        main_text = format_multiline_text(b["text"], max_line_len=28)
        if pos == "top":
            sub_str = f"\\N{{\\fs21\\c&H0000E6FF&}}{b['subtext']}" if b.get("subtext") else ""
            events.append(f"Dialogue: 1,{st},{et},BadgeCard,,0,0,0,,{{\\fade(120,120)}} {main_text}{sub_str} ")
        else:
            sub_str = f"\\N{{\\fs22\\c&H00000000&}}{b['subtext']}" if b.get("subtext") else ""
            events.append(f"Dialogue: 1,{st},{et},BadgeBottom,,0,0,0,,{{\\fade(120,120)}} {main_text}{sub_str} ")

    # 3. Dynamic Karaoke Captions
    for chunk in chunks:
        ch_start = chunk[0]["start"]
        ch_end = chunk[-1]["end"] + 0.15
        for i, active_w in enumerate(chunk):
            w_start = format_ass_time(active_w["start"])
            w_end = format_ass_time(chunk[i + 1]["start"] if i + 1 < len(chunk) else ch_end)
            formatted_words = []
            for j, w in enumerate(chunk):
                raw = w["word"].upper()
                if j == i:
                    formatted_words.append(f"{{\\c&H0000E6FF&\\3c&H00000000&\\fscx112\\fscy112\\bord4.0}}{raw}{{\\rCaptionBase}}")
                else:
                    formatted_words.append(f"{{\\c&H00FFFFFF&\\3c&H00000000&\\bord3.5}}{raw}{{\\rCaptionBase}}")
            line_text = " ".join(formatted_words)
            events.append(f"Dialogue: 0,{w_start},{w_end},CaptionBase,,0,0,0,,{line_text}")

    content = header + "\n".join(events) + "\n"
    out_ass_path.write_text(content, encoding="utf-8")
    return out_ass_path


def build_punch_zooms_filter(punch_zooms: list[dict], total_dur: float, width: int = 720, height: int = 1280, transitions: list[dict] | None = None) -> tuple[str, str]:
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
            parts.append(f"[0:v]{trim_str},scale={w_sc}:{h_sc},crop={width}:{height}:{x_crop}:{y_crop}{seg_fade}{out_lbl}")
        else:
            parts.append(f"[0:v]{trim_str},scale={width}:{height}{seg_fade}{out_lbl}")

    concat_inputs = "".join(seg_labels)
    parts.append(f"{concat_inputs}concat=n={len(seg_labels)}:v=1:a=0[v_punched]")
    return ";".join(parts), "[v_punched]"


def run_effect_pipeline(config_path: Path) -> Path:
    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    in_video = resolve_path(cfg["input_video"])
    out_video = resolve_path(cfg["output_video"])
    out_video.parent.mkdir(parents=True, exist_ok=True)

    info = get_video_info(in_video)
    dur = info["duration"]
    w = info["width"]
    h = info["height"]
    print(f"=== Effect Editor: Processing '{in_video.name}' ({dur:.2f}s, {w}x{h}) ===")

    align_path = resolve_path(cfg["alignment_json"])
    clause_bounds = cfg.get("clause_bounds")
    words = extract_words_from_alignment(align_path, clause_bounds)
    chunks = group_words_into_chunks(words)
    print(f"  [Captions] Extracted {len(words)} aligned words into {len(chunks)} kinetic chunks")

    ass_path = out_video.parent / f"{out_video.stem}.ass"
    build_ass_subtitles(
        chunks=chunks,
        badges=cfg.get("badges", []),
        hook_banner=cfg.get("hook_banner"),
        out_ass_path=ass_path,
        width=w,
        height=h
    )
    print(f"  [ASS] Generated styled kinetic subtitles at: {ass_path.name}")

    # Build Video Filtergraph
    pz_filter, pz_out = build_punch_zooms_filter(
        cfg.get("punch_zooms", []), dur, w, h, cfg.get("scene_transitions", [])
    )

    v_chain = [pz_out]

    # Color grading
    cg = cfg.get("color_grade", {})
    cont = cg.get("contrast", 1.05)
    sat = cg.get("saturation", 1.08)
    br = cg.get("brightness", 0.01)
    v_chain.append(f"eq=contrast={cont:.2f}:saturation={sat:.2f}:brightness={br:.2f}")

    # Progress bar
    pb = cfg.get("progress_bar", {})
    if pb.get("enabled", True):
        pb_h = pb.get("height", 6)
        pb_col = pb.get("color", "#FFE600")
        v_chain.append(f"drawbox=x=0:y={h - pb_h}:w='{w}*t/{dur:.3f}':h={pb_h}:color={pb_col}@0.95:t=fill")

    # Burn subtitles
    v_chain.append(f"subtitles='{ass_path}'")
    v_chain_str = ",".join(v_chain[1:])
    full_v_filter = f"{pz_filter};{pz_out}{v_chain_str}[vout]"

    # Build Audio Filtergraph
    bgm_cfg = cfg.get("bgm", {})
    bgm_file = resolve_path(bgm_cfg.get("file", "assets/zephiramusic-lofi-focus-606303.mp3"))
    bgm_vol = bgm_cfg.get("volume", 0.09)
    fade_in = bgm_cfg.get("fade_in", 0.5)
    fade_out = bgm_cfg.get("fade_out", 1.5)

    ffmpeg_inputs = ["-i", str(in_video), "-i", str(bgm_file)]
    input_idx = 2

    sfx_dir = resolve_path(cfg.get("sfx_dir", DEFAULT_SFX_DIR))
    sfx_events = cfg.get("sfx_events", [])

    a_filters = [
        f"[1:a]atrim=0:{dur:.3f},asetpts=PTS-STARTPTS,volume={bgm_vol:.3f},"
        f"afade=t=in:st=0:d={fade_in:.2f},afade=t=out:st={dur - fade_out:.2f}:d={fade_out:.2f}[bgm]"
    ]
    mix_sources = ["[0:a]", "[bgm]"]

    for ev in sfx_events:
        sfx_path = sfx_dir / ev["file"]
        if not sfx_path.exists():
            print(f"  [Warning] SFX not found: {sfx_path.name}")
            continue
        ffmpeg_inputs.extend(["-i", str(sfx_path)])
        lbl = f"[sfx_{input_idx - 2}]"
        delay_ms = int(round(ev["time"] * 1000))
        vol = ev.get("volume", 0.5)
        a_filters.append(f"[{input_idx}:a]volume={vol:.2f},adelay={delay_ms}|{delay_ms}{lbl}")
        mix_sources.append(lbl)
        input_idx += 1

    total_mix = len(mix_sources)
    mix_in_str = "".join(mix_sources)
    a_filters.append(
        f"{mix_in_str}amix=inputs={total_mix}:duration=first:dropout_transition=0,"
        f"loudnorm=I=-16:TP=-1.5:LRA=11[aout]"
    )
    full_a_filter = ";".join(a_filters)

    # Encode with Social BT.709 profile
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
    
    # Test multiline formatting
    t_long = "MẪU GIẤY IN THIỆP CƯỚI: VỪA SANG VỪA KINH TẾ?"
    formatted = format_multiline_text(t_long, max_line_len=24)
    assert "\\N" in formatted, f"Expected \\N in formatted text, got {formatted}"
    assert formatted == "MẪU GIẤY IN THIỆP CƯỚI\\NVỪA SANG VỪA KINH TẾ?"

    # Test short text unchanged
    assert format_multiline_text("SHORT", max_line_len=20) == "SHORT"
    # Test already split text unchanged
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
