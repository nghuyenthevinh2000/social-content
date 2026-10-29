#!/usr/bin/env python3
"""
sub_scanner.py
──────────────
Scans video frames using OpenCV to detect hardcoded on-screen subtitle segments,
computes bounding boxes and frame ranges, and exports mid-frame preview crops
along with a segments.json manifest for translation.

Usage:
    uv run python .agents/skills/video-editing/scripts/sub_scanner.py \\
        --video local/random/sample.mp4 \\
        --out-dir local/random/sub_scan \\
        --roi 968:1010,400:1520 \\
        --start-sec 318 \\
        --end-sec 340
"""

import argparse
import json
import os
import cv2
import numpy as np


def parse_roi(roi_str):
    # Format: ymin:ymax,xmin:xmax
    y_part, x_part = roi_str.split(",")
    ymin, ymax = map(int, y_part.split(":"))
    xmin, xmax = map(int, x_part.split(":"))
    return ymin, ymax, xmin, xmax


def get_text_mask(roi, min_val=215, max_sat_diff=25, lap_thresh=60):
    b, g, r = roi[:, :, 0], roi[:, :, 1], roi[:, :, 2]
    max_c = np.maximum(np.maximum(r, g), b)
    min_c = np.minimum(np.minimum(r, g), b)
    white = (min_c > min_val) & ((max_c - min_c) < max_sat_diff)

    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    lap = np.abs(cv2.Laplacian(gray, cv2.CV_16S))
    edge = lap > lap_thresh
    kernel = np.ones((3, 3), np.uint8)
    edge_dil = cv2.dilate(edge.astype(np.uint8), kernel, iterations=1) > 0
    return (white & edge_dil).astype(np.uint8)


def scan_subtitles(video_path, out_dir, roi, start_sec=0.0, end_sec=None,
                   min_pixels=60, iou_thresh=0.35, min_frames=4):
    os.makedirs(out_dir, exist_ok=True)
    ymin, ymax, xmin, xmax = roi

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    start_frame = int(start_sec * fps)
    end_frame = int(end_sec * fps) if end_sec is not None else total_frames - 1
    end_frame = min(end_frame, total_frames - 1)

    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

    records = []
    prev_mask = None
    f_idx = start_frame

    while f_idx <= end_frame:
        ret, frame = cap.read()
        if not ret:
            break
        roi_img = frame[ymin:ymax, xmin:xmax]
        mask = get_text_mask(roi_img)
        count = int(mask.sum())

        iou = 0.0
        if prev_mask is not None and (count > min_pixels or prev_mask.sum() > min_pixels):
            inter = np.logical_and(mask, prev_mask).sum()
            union = np.logical_or(mask, prev_mask).sum()
            iou = float(inter) / float(union) if union > 0 else 0.0

        # Calculate bounding box of text within ROI if present
        if count >= min_pixels:
            y_indices, x_indices = np.where(mask > 0)
            box_xmin = int(xmin + x_indices.min())
            box_xmax = int(xmin + x_indices.max())
            box_ymin = int(ymin + y_indices.min())
            box_ymax = int(ymin + y_indices.max())
        else:
            box_xmin = box_xmax = box_ymin = box_ymax = 0

        prev_mask = mask
        records.append({
            "frame": f_idx,
            "count": count,
            "iou": iou,
            "xmin": box_xmin,
            "xmax": box_xmax,
            "ymin": box_ymin,
            "ymax": box_ymax
        })
        f_idx += 1

    cap.release()

    # Group into segments
    segments = []
    cur = None
    for r in records:
        active = r["count"] >= min_pixels
        if active:
            if cur is None:
                cur = {
                    "start_frame": r["frame"],
                    "end_frame": r["frame"],
                    "max_count": r["count"],
                    "xmin": r["xmin"],
                    "xmax": r["xmax"],
                    "ymin": r["ymin"],
                    "ymax": r["ymax"],
                }
            else:
                if r["iou"] < iou_thresh and (r["frame"] - cur["start_frame"]) >= min_frames:
                    segments.append(cur)
                    cur = {
                        "start_frame": r["frame"],
                        "end_frame": r["frame"],
                        "max_count": r["count"],
                        "xmin": r["xmin"],
                        "xmax": r["xmax"],
                        "ymin": r["ymin"],
                        "ymax": r["ymax"],
                    }
                else:
                    cur["end_frame"] = r["frame"]
                    cur["max_count"] = max(cur["max_count"], r["count"])
                    cur["xmin"] = min(cur["xmin"], r["xmin"])
                    cur["xmax"] = max(cur["xmax"], r["xmax"])
                    cur["ymin"] = min(cur["ymin"], r["ymin"])
                    cur["ymax"] = max(cur["ymax"], r["ymax"])
        else:
            if cur is not None:
                if (cur["end_frame"] - cur["start_frame"] + 1) >= min_frames:
                    segments.append(cur)
                cur = None

    if cur is not None and (cur["end_frame"] - cur["start_frame"] + 1) >= min_frames:
        segments.append(cur)

    # Export mid-frame preview crops
    cap = cv2.VideoCapture(video_path)
    for i, seg in enumerate(segments):
        seg["id"] = i + 1
        seg["start_sec"] = round(seg["start_frame"] / fps, 3)
        seg["end_sec"] = round((seg["end_frame"] + 1) / fps, 3)
        mid_f = (seg["start_frame"] + seg["end_frame"]) // 2

        cap.set(cv2.CAP_PROP_POS_FRAMES, mid_f)
        ret, frame = cap.read()
        if ret:
            # Crop a padded window around the ROI
            pad_y1 = max(0, ymin - 20)
            pad_y2 = min(frame.shape[0], ymax + 50)
            pad_x1 = max(0, xmin - 50)
            pad_x2 = min(frame.shape[1], xmax + 50)
            crop = frame[pad_y1:pad_y2, pad_x1:pad_x2].copy()

            info = f"#{seg['id']} {seg['start_sec']:.2f}s-{seg['end_sec']:.2f}s (f{seg['start_frame']}-{seg['end_frame']})"
            cv2.putText(crop, info, (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
            cv2.imwrite(os.path.join(out_dir, f"seg_{seg['id']:03d}.png"), crop)

    cap.release()

    manifest_path = os.path.join(out_dir, "segments.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(segments, f, indent=2, ensure_ascii=False)

    print(f"Scanned {len(records)} frames. Found {len(segments)} segments.")
    print(f"Output saved to {out_dir}")
    return segments


def main():
    parser = argparse.ArgumentParser(description="Scan video for hardcoded subtitle segments")
    parser.add_argument("--video", required=True, help="Path to input video")
    parser.add_argument("--out-dir", required=True, help="Directory to save segment crops and JSON")
    parser.add_argument("--roi", default="960:1060,300:1620", help="ROI ymin:ymax,xmin:xmax")
    parser.add_argument("--start-sec", type=float, default=0.0, help="Start time in seconds")
    parser.add_argument("--end-sec", type=float, default=None, help="End time in seconds")
    parser.add_argument("--min-pixels", type=int, default=60, help="Min white edge pixels for active text")
    parser.add_argument("--iou-thresh", type=float, default=0.35, help="IoU change threshold for cut")
    parser.add_argument("--min-frames", type=int, default=4, help="Min segment duration in frames")

    args = parser.parse_args()
    roi = parse_roi(args.roi)
    scan_subtitles(
        video_path=args.video,
        out_dir=args.out_dir,
        roi=roi,
        start_sec=args.start_sec,
        end_sec=args.end_sec,
        min_pixels=args.min_pixels,
        iou_thresh=args.iou_thresh,
        min_frames=args.min_frames
    )


if __name__ == "__main__":
    main()
