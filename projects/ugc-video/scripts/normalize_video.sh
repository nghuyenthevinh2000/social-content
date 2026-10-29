#!/usr/bin/env bash
set -euo pipefail

# normalize_video.sh: Web & Social Media Transcoding Normalizer
# Converts raw Gemini Omni Flash / AI video outputs into standards-compliant MP4
# for Facebook, Instagram Reels, TikTok, and mobile hardware decoders.

if [ "$#" -lt 2 ]; then
  echo "Usage: $0 <input_video.mp4> <output_video.mp4>"
  exit 1
fi

INPUT="$1"
OUTPUT="$2"

if [ ! -f "$INPUT" ]; then
  echo "Error: Input file '$INPUT' does not exist."
  exit 1
fi

echo "==> Normalizing: $INPUT"
echo "==> Output destination: $OUTPUT"

ffmpeg -y -i "$INPUT" \
  -vf "colorspace=all=bt709:fast=1" \
  -c:v libx264 -preset slow -crf 18 \
  -pix_fmt yuv420p \
  -color_primaries bt709 -color_trc bt709 -colorspace bt709 \
  -g 48 -keyint_min 48 -sc_threshold 0 \
  -c:a aac -b:a 192k -ar 44100 -ac 2 \
  -movflags +faststart \
  -shortest \
  "$OUTPUT"

echo "==> Verification via ffprobe:"
ffprobe -v error -show_entries stream=codec_name,pix_fmt,color_space,color_primaries,color_transfer,sample_rate,channels -of default=noprint_wrappers=1 "$OUTPUT"
echo "==> Done. Ready for immediate social publication."