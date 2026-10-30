#!/usr/bin/env python3
"""Web & Social Media Transcoding Normalizer (BT.709, 44.1kHz Stereo AAC, GOP 48, FastStart)."""

import subprocess
import sys
from pathlib import Path


def normalize_video(input_path: Path, output_path: Path) -> Path:
    if not input_path.exists():
        raise FileNotFoundError(f"Input file does not exist: {input_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"==> Normalizing: {input_path}")
    print(f"==> Output destination: {output_path}")

    subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(input_path),
            "-vf", "colorspace=all=bt709:fast=1",
            "-c:v", "libx264", "-preset", "slow", "-crf", "18",
            "-pix_fmt", "yuv420p",
            "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
            "-g", "48", "-keyint_min", "48", "-sc_threshold", "0",
            "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2",
            "-movflags", "+faststart", "-shortest", str(output_path),
            "-loglevel", "error",
        ],
        check=True,
    )

    probe = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "stream=codec_name,pix_fmt,color_space,color_primaries,color_transfer,sample_rate,channels",
            "-of", "default=noprint_wrappers=1", str(output_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    print(f"==> Verification via ffprobe:\n{probe}")
    assert "color_space=bt709" in probe and "sample_rate=44100" in probe, f"Normalization verification failed:\n{probe}"
    return output_path


def main() -> None:
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <input_video.mp4> <output_video.mp4>", file=sys.stderr)
        sys.exit(1)
    normalize_video(Path(sys.argv[1]), Path(sys.argv[2]))


if __name__ == "__main__":
    main()
