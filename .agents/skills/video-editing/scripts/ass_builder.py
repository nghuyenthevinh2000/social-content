#!/usr/bin/env python3
"""
ass_builder.py
──────────────
Constructs an Advanced SubStation Alpha (.ass) subtitle file with Layer 0
background-masking boxes (BoxBg) to cleanly cover original hardcoded subtitles,
and Layer 1 styled Vietnamese subtitles (ViSub, ViLyric, ViDialogueTop, ViTitle).

Usage:
    uv run python .agents/skills/video-editing/scripts/ass_builder.py \\
        --segments local/random/sub_scan/segments.json \\
        --translations local/random/translations.json \\
        --out local/random/overlay.ass \\
        --res-x 1920 --res-y 1080 \\
        --fps 30.0
"""

import argparse
import json
import os


def fmt_ass_frame(frame_idx, fps=30.0):
    total_cs = int((frame_idx * 100) // int(fps))
    cs = total_cs % 100
    total_s = total_cs // 100
    s = total_s % 60
    total_m = total_s // 60
    m = total_m % 60
    h = total_m // 60
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def get_default_header(res_x=1920, res_y=1080, bg_color="&H00100E0C", font_name="Arial", font_size=35):
    return f"""[Script Info]
ScriptType: v4.00+
PlayResX: {res_x}
PlayResY: {res_y}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: BoxBg,{font_name},{font_size + 1},{bg_color},&H000000FF,{bg_color},&H00000000,0,0,0,0,100,100,0,0,1,8,0,7,0,0,0,1
Style: ViSub,{font_name},{font_size},&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0.5,0,1,2.5,1,5,20,20,20,1
Style: ViDialogue,{font_name},{font_size},&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0.5,0,1,2.5,1,2,20,20,20,1
Style: ViLyric,{font_name},{font_size - 2},&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,1,0,0,100,100,0.5,0,1,2.5,1,2,20,20,20,1
Style: ViDialogueTop,{font_name},{font_size - 1},&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0.5,0,1,2.5,1,2,20,20,20,1
Style: ViTitle,{font_name},{font_size + 1},&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,2.5,0,1,1.2,0,2,20,20,20,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"""


def build_ass(segments, translations, out_path, res_x=1920, res_y=1080, fps=30.0,
              bg_color="&H00100E0C", font_name="Arial", font_size=35,
              default_pos_y=980, box_pad_x=18, box_pad_y=4):
    lines = [get_default_header(res_x, res_y, bg_color, font_name, font_size)]
    center_x = res_x // 2

    for s in segments:
        sid = s.get("id")
        t_entry = None
        if isinstance(translations, dict):
            t_entry = translations.get(str(sid)) or translations.get(sid)
        elif isinstance(translations, list):
            for item in translations:
                if item.get("id") == sid:
                    t_entry = item
                    break

        if not t_entry:
            continue

        if isinstance(t_entry, str):
            vi_text = t_entry
            style = "ViDialogue"
            custom_pos = None
            mask = True
            fade_in = 0
            fade_out = 0
            box_style = "BoxBg"
            box_blur = 0
        else:
            vi_text = t_entry.get("text", "")
            style = t_entry.get("style", "ViDialogue")
            custom_pos = t_entry.get("pos")
            mask = t_entry.get("mask", True)
            fade_in = t_entry.get("fade_in", 0)
            fade_out = t_entry.get("fade_out", 0)
            box_style = t_entry.get("box_style", "BoxBg")
            box_blur = t_entry.get("box_blur", 0)

        sf = s["start_frame"]
        ef = s["end_frame"]
        t_start = fmt_ass_frame(sf, fps)
        t_end = fmt_ass_frame(ef + 1, fps)

        char_w = font_size * 0.53
        est_vi_w = int(len(vi_text) * char_w)

        seg_xmin = s.get("xmin", center_x - est_vi_w // 2)
        seg_xmax = s.get("xmax", center_x + est_vi_w // 2)
        seg_ymin = s.get("ymin", default_pos_y - font_size // 2)
        seg_ymax = s.get("ymax", default_pos_y + font_size // 2)

        if mask and seg_xmax > seg_xmin:
            box_x1 = min(seg_xmin - box_pad_x, int(center_x - est_vi_w // 2 - box_pad_x))
            box_x2 = max(seg_xmax + box_pad_x, int(center_x + est_vi_w // 2 + box_pad_x))
            box_w = max(50, box_x2 - box_x1)

            box_y1 = seg_ymin - box_pad_y
            box_h = max(20, (seg_ymax - seg_ymin) + 2 * box_pad_y)

            box_tags = []
            if fade_out > 0 or fade_in > 0:
                box_tags.append(f"\\fad({fade_in},{fade_out})")
            if box_blur > 0:
                box_tags.append(f"\\blur{box_blur}")
            box_tags.append(f"\\p1\\an7\\pos({box_x1},{box_y1})")
            box_tag_str = "{" + "".join(box_tags) + "}"

            lines.append(
                f"Dialogue: 0,{t_start},{t_end},{box_style},,0,0,0,,{box_tag_str}m 0 0 l {box_w} 0 {box_w} {box_h} 0 {box_h}{{\\p0}}"
            )

        # Layer 1: Subtitle Text (All placed below characters by default)
        text_tags = []
        if fade_in > 0 or fade_out > 0:
            text_tags.append(f"\\fad({fade_in},{fade_out})")

        if custom_pos:
            px, py = custom_pos
            text_tags.append(f"\\pos({px},{py})")
        elif style in ("ViSub", "ViDialogue"):
            text_tags.append(f"\\pos({center_x},{default_pos_y})")
        elif style == "ViLyric":
            text_tags.append(f"\\pos({center_x},{default_pos_y})")
        elif style == "ViDialogueTop":
            text_tags.append(f"\\pos({center_x},{default_pos_y - 50})")
        elif style == "ViTitle":
            text_tags.append(f"\\pos({center_x},{default_pos_y})")
        else:
            text_tags.append(f"\\pos({center_x},{default_pos_y})")

        pos_tag = "{" + "".join(text_tags) + "}"
        lines.append(f"Dialogue: 1,{t_start},{t_end},{style},,0,0,0,,{pos_tag}{vi_text}")

    content = "\n".join(lines) + "\n"
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"Built ASS file at {out_path} with {len(lines) - 1} dialog events.")
    return out_path


def self_check():
    import tempfile
    test_segments = [{"id": "s1", "start_frame": 0, "end_frame": 30, "xmin": 800, "xmax": 1120, "ymin": 960, "ymax": 1000}]
    test_translations = {"s1": {"text": "Xin chào thế giới", "style": "ViDialogue", "fade_in": 500, "fade_out": 300, "box_blur": 3}}
    with tempfile.NamedTemporaryFile("w+", suffix=".ass", delete=False) as tf:
        tmp_path = tf.name
    try:
        build_ass(test_segments, test_translations, tmp_path, res_x=1920, res_y=1080, fps=30.0)
        with open(tmp_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "Style: ViDialogue" in content, "Missing ViDialogue style"
        assert "\\fad(500,300)" in content, "Missing fade tags"
        assert "\\blur3" in content, "Missing blur tag"
        assert "{\\fad(500,300)\\pos(960,980)}Xin chào thế giới" in content, "Missing correct bottom position"
        print("ass_builder self-check passed.")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def main():
    parser = argparse.ArgumentParser(description="Build ASS subtitle overlay with masking boxes")
    parser.add_argument("--segments", help="Path to segments.json from sub_scanner")
    parser.add_argument("--translations", help="Path to translations.json")
    parser.add_argument("--out", help="Output .ass file path")
    parser.add_argument("--res-x", type=int, default=1920, help="PlayResX")
    parser.add_argument("--res-y", type=int, default=1080, help="PlayResY")
    parser.add_argument("--fps", type=float, default=30.0, help="Video frame rate")
    parser.add_argument("--bg-color", default="&H00100E0C", help="BGR box color hex e.g. &H00100E0C")
    parser.add_argument("--font-name", default="Arial", help="Font name")
    parser.add_argument("--font-size", type=int, default=35, help="Font size in pt")
    parser.add_argument("--default-pos-y", type=int, default=980, help="Y position for ViDialogue/ViSub")
    parser.add_argument("--self-check", action="store_true", help="Run minimal internal assert-based check")

    args = parser.parse_args()

    if args.self_check:
        self_check()
        return

    if not args.segments or not args.translations or not args.out:
        parser.error("--segments, --translations, and --out are required unless --self-check is provided.")

    with open(args.segments, "r", encoding="utf-8") as f:
        segments = json.load(f)

    with open(args.translations, "r", encoding="utf-8") as f:
        translations = json.load(f)

    build_ass(
        segments=segments,
        translations=translations,
        out_path=args.out,
        res_x=args.res_x,
        res_y=args.res_y,
        fps=args.fps,
        bg_color=args.bg_color,
        font_name=args.font_name,
        font_size=args.font_size,
        default_pos_y=args.default_pos_y
    )


if __name__ == "__main__":
    main()
