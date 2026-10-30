#!/usr/bin/env python3
"""Seamlessly combine Post 4 Scene 1 (0-10s) and Scene 2 (10-20s) with unified eleven_v3 voice (FXJGVNPXC71BGT9PjlMX)."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path("/Users/thevinhnguyen/Documents/computer-science/projects/social-content/projects/ugc-video")
OMNI_DIR = PROJECT_DIR / "renders" / "omni-1.1-flash"
RENDERS_DIR = PROJECT_DIR / "renders"
VIDEO_ASSETS_DIR = PROJECT_DIR / "assets" / "video"
NORMALIZE_SH = PROJECT_DIR / "scripts" / "normalize_video.sh"

# Exact spoken clauses and their target mouth-movement windows [target_start_s, target_end_s] across the 20s timeline
CLAUSES = [
    ("Xưởng ơi, có mẫu giấy in thiệp cưới nào vừa sang vừa kinh tế không?", 0.18, 3.22),
    ("Dòng Giấy Ánh Kim một trăm tám mươi bên em bề mặt nhũ xà cừ cực mịn, ăn mực sắc nét, lên máy bế hay gấp nếp không lo nứt gãy.", 3.40, 9.35),
    ("Khổ tiêu chuẩn bảy mươi chín nhân một trăm linh chín luôn sẵn tại kho xưởng,", 10.10, 13.20),
    ("nhận đơn từ hai gam cho xưởng in test máy.", 13.48, 15.50),
    ("Đặc biệt lên thiệp in cực kỳ sắc nét.", 15.88, 17.70),
    ("Nhắn tin xưởng em gửi mẫu miễn phí nhé!", 18.25, 19.92),
]


def parse_clause_bounds(align_path: Path) -> list[tuple[float, float, float, float]]:
    align = json.loads(align_path.read_text(encoding="utf-8"))
    chars = align["characters"]
    starts = align["characterStartTimesSeconds"]
    ends = align["characterEndTimesSeconds"]
    full_str = "".join(chars)
    bounds = []
    search_from = 0
    for text, t_start, t_end in CLAUSES:
        idx = full_str.find(text, search_from)
        assert idx != -1, f"Clause not found in alignment: {text}"
        end_idx = idx + len(text) - 1
        bounds.append((starts[idx], ends[end_idx], t_start, t_end))
        search_from = end_idx + 1
    return bounds


def build_aligned_audio(raw_mp3: Path, align_path: Path, out_wav: Path) -> None:
    bounds = parse_clause_bounds(align_path)
    filter_parts = []
    mix_inputs = []
    for i, (s_start, s_end, t_start, t_end) in enumerate(bounds):
        src_dur = s_end - s_start
        tgt_dur = t_end - t_start
        tempo = max(0.5, min(2.0, src_dur / tgt_dur))
        delay_ms = int(round(t_start * 1000))
        filter_parts.append(
            f"[0:a]atrim=start={s_start:.3f}:end={s_end:.3f},asetpts=PTS-STARTPTS,"
            f"atempo={tempo:.4f},adelay={delay_ms}|{delay_ms}[c{i}]"
        )
        mix_inputs.append(f"[c{i}]")

    filter_parts.append(
        f"{''.join(mix_inputs)}amix=inputs={len(bounds)}:normalize=0,"
        f"loudnorm=I=-16:TP=-1.5:LRA=11,apad=whole_dur=20.0,atrim=0:20.0[aout]"
    )
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(raw_mp3),
            "-filter_complex", ";".join(filter_parts),
            "-map", "[aout]", "-ar", "44100", "-ac", "2", str(out_wav),
            "-loglevel", "error",
        ],
        check=True,
    )


def main() -> None:
    scene1_raw = OMNI_DIR / "scene1_raw.mp4"
    scene2_raw = OMNI_DIR / "scene2_omni11_raw.mp4"
    raw_mp3 = OMNI_DIR / "tts_v3_raw.mp3"
    align_json = OMNI_DIR / "tts_v3_alignment.json"
    aligned_wav = OMNI_DIR / "tts_v3_20s_aligned.wav"

    for p in (scene1_raw, scene2_raw, raw_mp3, align_json):
        if not p.exists():
            print(f"Error: Missing required input: {p}", file=sys.stderr)
            sys.exit(1)

    print("1. Aligning single-pass eleven_v3 clauses to 20s mouth windows...")
    build_aligned_audio(raw_mp3, align_json, aligned_wav)

    print("2. Stitching Scene 1 (0-10s) + Scene 2 (10-20s) + unified eleven_v3 voice...")
    raw_muxed = OMNI_DIR / "post_4_omni11_20s_raw_muxed.mp4"
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", str(scene1_raw),
            "-i", str(scene2_raw),
            "-i", str(aligned_wav),
            "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[vout]",
            "-map", "[vout]", "-map", "2:a:0",
            "-c:v", "libx264", "-crf", "18", "-preset", "fast", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2",
            "-shortest", str(raw_muxed),
            "-loglevel", "error",
        ],
        check=True,
    )

    print("3. Running v3.1 social normalization (BT.709, GOP 48, FastStart)...")
    final_omni = OMNI_DIR / "post_4_omni11_20s_web_optimized.mp4"
    subprocess.run([str(NORMALIZE_SH), str(raw_muxed), str(final_omni)], check=True)
    raw_muxed.unlink(missing_ok=True)

    shutil.copyfile(final_omni, RENDERS_DIR / "post_4_20s_web_optimized.mp4")
    shutil.copyfile(final_omni, VIDEO_ASSETS_DIR / "post_4_20s_web_optimized.mp4")
    print(f"Success! Seamless 20s deliverable written to:\n  - {final_omni}\n  - {RENDERS_DIR / 'post_4_20s_web_optimized.mp4'}")


if __name__ == "__main__":
    main()
