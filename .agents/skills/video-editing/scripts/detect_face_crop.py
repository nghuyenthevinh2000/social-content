#!/usr/bin/env python3
"""
detect_face_crop.py
────────────────────────────────────────────────────────────────────────────────
Detects a face in sampled frames extracted from a portrait speech video and
outputs the ffmpeg crop filter string needed to center the face inside a
square crop region.

Usage
─────
    python detect_face_crop.py [OPTIONS]

    # Minimal — use defaults (expects frames already extracted to /tmp/facedetect/):
    python detect_face_crop.py

    # Custom frame dir, output square size, model path:
    python detect_face_crop.py \
        --frame-dir  /tmp/myframes \
        --frame-glob "frame_*.png" \
        --model      /tmp/yunet.onnx \
        --frame-w    1080 \
        --frame-h    1920 \
        --crop-size  1080

Requirements
────────────
    opencv-python-headless >= 5.0   (OpenCV 5 — uses FaceDetectorYN, NOT CascadeClassifier)
    numpy

    Install via uv (recommended):
        uv venv /tmp/facedetect/.venv
        uv pip install opencv-python-headless numpy \\
            --python /tmp/facedetect/.venv/bin/python3

    Download YuNet model (~230 KB):
        curl -L -o /tmp/facedetect/face_detection_yunet_2023mar.onnx \\
          "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"

Output
──────
    Prints per-frame detections, then a summary block:

        === CROP RESULT ===
        Face center  : (488, 1011)
        Crop origin  : x=0, y=471
        Crop size    : 1080x1080

        ffmpeg filter : crop=1080:1080:0:471

    The last line is machine-parseable: grep "^ffmpeg filter" | awk '{print $NF}'

Notes
─────
  - Frames must be pre-extracted from the video (see §Extract frames in SKILL.md).
  - True decoded frame dimensions (--frame-w/h) must match the extracted PNG size,
    NOT the raw stream metadata. For portrait iPhones these differ:
      raw metadata: 1920x1080 (landscape coded)
      decoded PNG:  1080x1920 (portrait after rotation)
    Verify with: python3 -c "import cv2; img=cv2.imread('frame.png'); print(img.shape)"
  - When no face is detected in any frame, a heuristic fallback is used
    (upper-center: cx = frame_w//2, cy = frame_h//3).
  - Crop origin is clamped to keep the crop window within frame bounds.
  - Face center is computed as a confidence-weighted average across all frames,
    making it robust to momentary head turns or occlusions.
────────────────────────────────────────────────────────────────────────────────
"""

import argparse
import glob
import os
import sys

import cv2
import numpy as np


# ── Default paths ─────────────────────────────────────────────────────────────

DEFAULT_FRAME_DIR  = "/tmp/facedetect"
DEFAULT_FRAME_GLOB = "speech_frame_*.png"
DEFAULT_MODEL      = "/tmp/facedetect/face_detection_yunet_2023mar.onnx"
DEFAULT_FRAME_W    = 1080
DEFAULT_FRAME_H    = 1920
DEFAULT_CROP_SIZE  = 1080


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Detect face in portrait frames and output ffmpeg crop filter string."
    )
    p.add_argument(
        "--frame-dir", default=DEFAULT_FRAME_DIR,
        help=f"Directory containing extracted PNG frames (default: {DEFAULT_FRAME_DIR})"
    )
    p.add_argument(
        "--frame-glob", default=DEFAULT_FRAME_GLOB,
        help=f"Glob pattern for frame files (default: {DEFAULT_FRAME_GLOB})"
    )
    p.add_argument(
        "--model", default=DEFAULT_MODEL,
        help=f"Path to YuNet .onnx model file (default: {DEFAULT_MODEL})"
    )
    p.add_argument(
        "--frame-w", type=int, default=DEFAULT_FRAME_W,
        help=f"True decoded frame width in pixels (default: {DEFAULT_FRAME_W})"
    )
    p.add_argument(
        "--frame-h", type=int, default=DEFAULT_FRAME_H,
        help=f"True decoded frame height in pixels (default: {DEFAULT_FRAME_H})"
    )
    p.add_argument(
        "--crop-size", type=int, default=DEFAULT_CROP_SIZE,
        help=f"Square crop side length in pixels (default: {DEFAULT_CROP_SIZE})"
    )
    p.add_argument(
        "--score-threshold", type=float, default=0.5,
        help="YuNet confidence threshold (default: 0.5)"
    )
    p.add_argument(
        "--quiet", action="store_true",
        help="Suppress per-frame output; only print final crop filter line"
    )
    return p.parse_args()


# ── Helpers ───────────────────────────────────────────────────────────────────

def check_model(model_path: str) -> None:
    if not os.path.isfile(model_path):
        print(
            f"ERROR: YuNet model not found at '{model_path}'\n"
            f"Download with:\n"
            f"  curl -L -o '{model_path}' \\\n"
            f"    'https://github.com/opencv/opencv_zoo/raw/main/models/"
            f"face_detection_yunet/face_detection_yunet_2023mar.onnx'",
            file=sys.stderr,
        )
        sys.exit(1)


def verify_frame_dimensions(img: np.ndarray, expected_w: int, expected_h: int,
                             path: str, quiet: bool) -> bool:
    """Warn if extracted frame dimensions don't match declared --frame-w/h."""
    actual_h, actual_w = img.shape[:2]
    if actual_w != expected_w or actual_h != expected_h:
        if not quiet:
            print(
                f"  ⚠️  Dimension mismatch in {os.path.basename(path)}: "
                f"got {actual_w}x{actual_h}, expected {expected_w}x{expected_h}. "
                f"Using actual dimensions for detection.",
                file=sys.stderr,
            )
        return False
    return True


def detect_faces_in_frame(
    img: np.ndarray,
    model_path: str,
    score_threshold: float,
) -> list[tuple[int, int, int, int, float]]:
    """
    Run YuNet on a single frame.
    Returns list of (cx, cy, fw, fh, confidence) for each detected face.
    """
    h, w = img.shape[:2]
    detector = cv2.FaceDetectorYN_create(
        model_path,
        "",
        (w, h),
        score_threshold=score_threshold,
        nms_threshold=0.3,
        top_k=5,
    )
    _, faces = detector.detect(img)
    if faces is None or len(faces) == 0:
        return []

    results = []
    for face in faces:
        x, y, fw, fh = int(face[0]), int(face[1]), int(face[2]), int(face[3])
        conf = float(face[14])
        cx, cy = x + fw // 2, y + fh // 2
        results.append((cx, cy, fw, fh, conf))
    return results


def compute_crop_origin(
    cx: int, cy: int,
    frame_w: int, frame_h: int,
    crop_size: int,
) -> tuple[int, int]:
    """
    Compute crop origin (top-left corner) that centers (cx, cy) inside a
    crop_size × crop_size square, clamped to frame bounds.
    """
    crop_x = cx - crop_size // 2
    crop_y = cy - crop_size // 2
    crop_x = max(0, min(crop_x, frame_w - crop_size))
    crop_y = max(0, min(crop_y, frame_h - crop_size))
    return crop_x, crop_y


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    args = parse_args()

    check_model(args.model)

    pattern = os.path.join(args.frame_dir, args.frame_glob)
    frame_paths = sorted(glob.glob(pattern))

    if not frame_paths:
        print(
            f"ERROR: No frames matched '{pattern}'.\n"
            f"Extract frames first with:\n"
            f"  ffmpeg -y -i INPUT.MOV -vf fps=1 -frames:v 10 "
            f"'{args.frame_dir}/speech_frame_%02d.png'",
            file=sys.stderr,
        )
        sys.exit(1)

    if not args.quiet:
        print(f"Scanning {len(frame_paths)} frame(s) in '{args.frame_dir}' …\n")

    all_detections: list[tuple[int, int, float]] = []  # (cx, cy, confidence)

    for fpath in frame_paths:
        img = cv2.imread(fpath)
        if img is None:
            if not args.quiet:
                print(f"  SKIP (unreadable): {os.path.basename(fpath)}")
            continue

        actual_h, actual_w = img.shape[:2]
        verify_frame_dimensions(img, args.frame_w, args.frame_h, fpath, args.quiet)

        detections = detect_faces_in_frame(img, args.model, args.score_threshold)

        if not args.quiet:
            name = os.path.basename(fpath)
            if not detections:
                print(f"  {name}: {actual_w}x{actual_h}  → no face detected")
            else:
                for cx, cy, fw, fh, conf in detections:
                    print(
                        f"  {name}: {actual_w}x{actual_h}  "
                        f"→ bbox=({cx - fw//2},{cy - fh//2},{fw},{fh})  "
                        f"center=({cx},{cy})  conf={conf:.3f}"
                    )

        # Keep only the highest-confidence detection per frame
        if detections:
            best = max(detections, key=lambda d: d[4])
            all_detections.append((best[0], best[1], best[4]))

    # ── Aggregate face center ─────────────────────────────────────────────────
    if all_detections:
        cxs   = np.array([d[0] for d in all_detections], dtype=float)
        cys   = np.array([d[1] for d in all_detections], dtype=float)
        confs = np.array([d[2] for d in all_detections], dtype=float)
        face_cx = int(np.average(cxs, weights=confs))
        face_cy = int(np.average(cys, weights=confs))
        method = f"weighted average across {len(all_detections)} detection(s)"
    else:
        # Heuristic fallback: upper-center (typical for portrait talking-head videos)
        face_cx = args.frame_w // 2
        face_cy = args.frame_h // 3
        method  = "heuristic fallback (no face detected)"
        if not args.quiet:
            print(
                "\n⚠️  No faces detected in any frame.\n"
                f"   Falling back to upper-center heuristic: ({face_cx}, {face_cy})\n"
                "   Tip: check that extracted frames contain a visible face and\n"
                "   try lowering --score-threshold (e.g. 0.3)."
            )

    crop_x, crop_y = compute_crop_origin(
        face_cx, face_cy,
        args.frame_w, args.frame_h,
        args.crop_size,
    )

    filter_str = f"crop={args.crop_size}:{args.crop_size}:{crop_x}:{crop_y}"

    # ── Output ────────────────────────────────────────────────────────────────
    if not args.quiet:
        print(f"\n=== CROP RESULT ({method}) ===")
        print(f"Frame size   : {args.frame_w}x{args.frame_h}")
        print(f"Face center  : ({face_cx}, {face_cy})")
        print(f"Crop origin  : x={crop_x}, y={crop_y}")
        print(f"Crop size    : {args.crop_size}x{args.crop_size}")
        print()

    print(f"ffmpeg filter : {filter_str}")


if __name__ == "__main__":
    main()
