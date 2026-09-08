#!/usr/bin/env python3
"""
make_pip.py - Programmatic circular Video-in-Video (Picture-in-Picture) composite generator.
Supports positioning, crisp circular antialiasing, sleek border ring, and intelligent audio mixing.
"""

import argparse
import os
import subprocess
from PIL import Image, ImageDraw


def generate_assets(size=360, border_w=6, out_dir="."):
    """Generate high-res antialiased circle mask and border ring."""
    scale = 4
    large_size = size * scale
    large_border = border_w * scale

    # 1. Grayscale mask for alphamerge (255 inside, 0 outside)
    mask = Image.new("L", (large_size, large_size), 0)
    d_mask = ImageDraw.Draw(mask)
    d_mask.ellipse((0, 0, large_size - 1, large_size - 1), fill=255)
    mask = mask.resize((size, size), Image.Resampling.LANCZOS)
    mask_path = os.path.join(out_dir, "mask.png")
    mask.save(mask_path)

    # 2. White ring overlay
    ring = Image.new("RGBA", (large_size, large_size), (0, 0, 0, 0))
    d_ring = ImageDraw.Draw(ring)
    d_ring.ellipse(
        (large_border // 2, large_border // 2, large_size - large_border // 2, large_size - large_border // 2),
        outline=(255, 255, 255, 255),
        width=large_border,
    )
    ring = ring.resize((size, size), Image.Resampling.LANCZOS)
    ring_path = os.path.join(out_dir, "ring.png")
    ring.save(ring_path)

    return mask_path, ring_path


import json


def get_duration(file_path):
    """Retrieve media duration in seconds via ffprobe."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "json",
        file_path,
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, text=True, check=True)
    return float(json.loads(res.stdout)["format"]["duration"])


def render_pip(
    main_video="app.mov",
    pip_video="talk.MOV",
    output="output.mp4",
    position="bottom_right",
    size=360,
    border=6,
    margin=32,
    fade_duration=0.5,
):
    mask_path, ring_path = generate_assets(size=size, border_w=border)

    main_dur = get_duration(main_video)
    pip_dur = get_duration(pip_video)
    print(f"Main video duration: {main_dur:.2f}s | PiP video duration: {pip_dur:.2f}s")

    # Calculate overlay coordinates
    pos_coords = {
        "bottom_right": f"x=W-w-{margin}:y=H-h-{margin}",
        "bottom_center": f"x=(W-w)/2:y=H-h-{margin*3}",
        "top_right": f"x=W-w-{margin}:y={margin*2}",
        "top_left": f"x={margin}:y={margin*2}",
        "middle_right": f"x=W-w-{margin}:y=(H-h)/2",
    }
    overlay_xy = pos_coords.get(position, pos_coords["bottom_right"])

    if pip_dur < main_dur - 0.2:
        fade_start = max(0.0, pip_dur - fade_duration)
        filter_complex = (
            f"[1:v]crop=1000:1000:40:455,scale={size}:{size},format=yuva420p[pip_crop]; "
            f"[pip_crop][2:v]alphamerge,fade=t=out:st={fade_start:.2f}:d={fade_duration:.2f}:alpha=1[pip_circle]; "
            f"[3:v]format=yuva420p,fade=t=out:st={fade_start:.2f}:d={fade_duration:.2f}:alpha=1[ring_faded]; "
            f"[0:v][pip_circle]overlay={overlay_xy}:enable='between(t,0,{pip_dur:.2f})':eof_action=pass[base_pip]; "
            f"[base_pip][ring_faded]overlay={overlay_xy}:enable='between(t,0,{pip_dur:.2f})':eof_action=pass[vout]; "
            f"[0:a]volume=0.5[app_a];[1:a]volume=1.2[talk_a]; "
            f"[app_a][talk_a]amix=inputs=2:duration=first:dropout_transition=2[aout]"
        )
    else:
        filter_complex = (
            f"[1:v]crop=1000:1000:40:455,scale={size}:{size},format=yuva420p[pip_crop]; "
            f"[pip_crop][2:v]alphamerge[pip_circle]; "
            f"[0:v][pip_circle]overlay={overlay_xy}:shortest=1[base_pip]; "
            f"[base_pip][3:v]overlay={overlay_xy}:shortest=1[vout]; "
            f"[0:a]volume=0.4[app_a];[1:a]volume=1.2[talk_a]; "
            f"[talk_a][app_a]amix=inputs=2:duration=first:dropout_transition=2[aout]"
        )

    cmd = [
        "ffmpeg", "-y",
        "-i", main_video,
        "-i", pip_video,
        "-loop", "1", "-i", mask_path,
        "-loop", "1", "-i", ring_path,
        "-filter_complex", filter_complex,
        "-map", "[vout]",
        "-map", "[aout]",
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "19",
        "-c:a", "aac",
        "-b:a", "192k",
        output,
    ]

    print(f"Rendering {output} with position '{position}'...")
    subprocess.run(cmd, check=True)
    print(f"Render complete: {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Render circular PiP video composite")
    parser.add_argument("--main", default="app.mov", help="Main background video")
    parser.add_argument("--pip", default="talk.MOV", help="Talking-head video")
    parser.add_argument("--output", default="output.mp4", help="Output video path")
    parser.add_argument(
        "--position",
        default="bottom_right",
        choices=["bottom_right", "bottom_center", "top_right", "top_left", "middle_right"],
        help="Overlay placement",
    )
    parser.add_argument("--size", type=int, default=360, help="Circle diameter in pixels")
    parser.add_argument("--border", type=int, default=6, help="Border ring thickness")
    args = parser.parse_args()

    render_pip(
        main_video=args.main,
        pip_video=args.pip,
        output=args.output,
        position=args.position,
        size=args.size,
        border=args.border,
    )
