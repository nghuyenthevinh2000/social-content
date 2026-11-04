#!/usr/bin/env python3
"""
match_lighting.py
──────────────────────────────────────────────────────────────────────────────
ML-driven inter-scene lighting & color harmonization for multi-scene UGC videos.

Extracts 3D facial skin landmarks (MediaPipe FaceLandmarker), face-masked upper
ambient background, and seam boundary frames across N scenes; auto-selects the
lowest-drift scene as the lighting anchor; and computes Ridge-regularized RGB
gain LUTs in unified gbrp space for FFmpeg.
──────────────────────────────────────────────────────────────────────────────
"""

import argparse
import json
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent.parent
DEFAULT_MODEL = PROJECT_DIR / "models/face_landmarker.task"

# MediaPipe 478-landmark indices for forehead, nose bridge, and left/right malar cheeks
SKIN_LANDMARKS = [10, 151, 108, 337, 50, 101, 205, 280, 330, 425, 4, 195]


def resolve_persona_config(path_or_persona: str | Path) -> tuple[Path, dict, Path]:
    """Resolve render config + persona-wide <persona>/config.json and return (config_path, merged_cfg, persona_dir)."""
    p = Path(path_or_persona)
    cfg_path = next(
        (
            c.resolve()
            for c in (p, p / "config.json", PROJECT_DIR / p, PROJECT_DIR / p / "config.json")
            if c.is_file()
        ),
        p.resolve(),
    )
    raw_cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    creator = raw_cfg.get("creator")
    if not creator:
        for parent in [cfg_path.parent, *cfg_path.parents]:
            if parent.parent == PROJECT_DIR and (PROJECT_DIR / parent.name).is_dir():
                creator = parent.name
                break
    persona_dir = (PROJECT_DIR / creator).resolve() if creator and (PROJECT_DIR / creator).is_dir() else cfg_path.parent.resolve()
    persona_cfg_path = persona_dir / "config.json"
    persona_cfg = json.loads(persona_cfg_path.read_text(encoding="utf-8")) if persona_cfg_path.is_file() else {}
    merged_cfg = {**persona_cfg, **raw_cfg}
    if "scenes" not in merged_cfg and (persona_dir / "renders").is_dir():
        render_cfgs = sorted((persona_dir / "renders").glob("*/config.json"))
        if render_cfgs:
            cfg_path = render_cfgs[0].resolve()
            merged_cfg = {**persona_cfg, **json.loads(cfg_path.read_text(encoding="utf-8"))}
    return cfg_path, merged_cfg, persona_dir


def extract_ml_lighting_profile(
    video_path: Path, model_path: Path = DEFAULT_MODEL, lighting_cfg: dict | None = None
) -> dict[str, np.ndarray | float]:
    """Extract MediaPipe facial skin ROI, face-masked background ROI, seam RGB, and temporal drift."""
    l_cfg = lighting_cfg or {}
    rad = int(l_cfg.get("skin_patch_radius", 8))
    w_seam, w_bg, w_skin = l_cfg.get("feature_weights", [0.75, 0.15, 0.10])
    opts = mp.tasks.vision.FaceLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(model_path)),
        running_mode=mp.tasks.vision.RunningMode.IMAGE,
        num_faces=1,
    )
    cap = cv2.VideoCapture(str(video_path))
    n_frames = max(1, int(cap.get(cv2.CAP_PROP_FRAME_COUNT)))
    sample_idxs = sorted(
        {
            0,
            1,
            2,
            n_frames // 4,
            n_frames // 2,
            3 * n_frames // 4,
            max(0, n_frames - 3),
            max(0, n_frames - 2),
            n_frames - 1,
        }
    )

    full_rgb, skin_rgb, bg_rgb = {}, {}, {}
    with mp.tasks.vision.FaceLandmarker.create_from_options(opts) as landmarker:
        for idx in sample_idxs:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ok, frame = cap.read()
            if not ok or frame is None:
                continue
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, _ = rgb.shape
            full_rgb[idx] = rgb.mean(axis=(0, 1))
            res = landmarker.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb))
            if res.face_landmarks:
                lms = res.face_landmarks[0]
                patches = [
                    rgb[
                        max(0, int(lms[li].y * h) - rad) : min(h, int(lms[li].y * h) + rad + 1),
                        max(0, int(lms[li].x * w) - rad) : min(w, int(lms[li].x * w) + rad + 1),
                    ].reshape(-1, 3)
                    for li in SKIN_LANDMARKS
                ]
                patches = [p for p in patches if p.size > 0]
                if patches:
                    skin_rgb[idx] = np.vstack(patches).mean(axis=0)
                xs = [int(l.x * w) for l in lms]
                ys = [int(l.y * h) for l in lms]
                mask = np.ones((h // 4, w), dtype=bool)
                mask[
                    max(0, min(ys)) : min(h // 4, max(ys)),
                    max(0, min(xs) - 30) : min(w, max(xs) + 30),
                ] = False
                bg_px = rgb[: h // 4][mask]
                if bg_px.size > 0:
                    bg_rgb[idx] = bg_px.mean(axis=0)
    cap.release()

    def composite_feature(seam_idx: int, win_idxs: list[int]) -> np.ndarray:
        f_val = full_rgb.get(seam_idx, next(iter(full_rgb.values())))
        s_val = (
            np.mean([skin_rgb[i] for i in win_idxs if i in skin_rgb], axis=0)
            if any(i in skin_rgb for i in win_idxs)
            else f_val
        )
        b_val = (
            np.mean([bg_rgb[i] for i in win_idxs if i in bg_rgb], axis=0)
            if any(i in bg_rgb for i in win_idxs)
            else f_val
        )
        return np.maximum(w_seam * f_val + w_bg * b_val + w_skin * s_val, 1e-6)

    start_feat = composite_feature(0, [0, 1, 2])
    end_feat = composite_feature(n_frames - 1, [max(0, n_frames - 3), max(0, n_frames - 2), n_frames - 1])
    skin_mean = np.mean(list(skin_rgb.values()), axis=0) if skin_rgb else start_feat
    bg_mean = np.mean(list(bg_rgb.values()), axis=0) if bg_rgb else start_feat
    temporal_drift = float(np.std([v.mean() for v in full_rgb.values()]))
    return {
        "start_feat": start_feat,
        "end_feat": end_feat,
        "skin_mean": skin_mean,
        "bg_mean": bg_mean,
        "temporal_drift": temporal_drift,
    }


def compute_ml_scene_luts(
    scene_videos: list[Path], model_path: Path = DEFAULT_MODEL, lighting_cfg: dict | None = None
) -> list[str]:
    """Auto-select lowest-drift anchor scene and fit Ridge-regularized RGB LUTs via MediaPipe skin + BG + seam features."""
    if len(scene_videos) <= 1:
        return [",lutrgb=r='val':g='val':b='val'"] * len(scene_videos)

    l_cfg = lighting_cfg or {}
    reg_lambda = float(l_cfg.get("reg_lambda", 0.01))
    profiles = [extract_ml_lighting_profile(v, model_path, l_cfg) for v in scene_videos]
    anchor_idx = int(np.argmin([p["temporal_drift"] for p in profiles]))
    print(
        f"\n[ML Lighting] Auto-selected Scene {anchor_idx + 1} as anchor "
        f"(lowest drift={profiles[anchor_idx]['temporal_drift']:.2f})"
    )

    gains = [np.ones(3, dtype=np.float64) for _ in scene_videos]
    for i in range(anchor_idx - 1, -1, -1):
        tgt = profiles[i + 1]["start_feat"] * gains[i + 1]
        src = profiles[i]["end_feat"]
        gains[i] = (1.0 - reg_lambda) * (tgt / src) + reg_lambda * 1.0

    for i in range(anchor_idx + 1, len(scene_videos)):
        tgt = profiles[i - 1]["end_feat"] * gains[i - 1]
        src = profiles[i]["start_feat"]
        gains[i] = (1.0 - reg_lambda) * (tgt / src) + reg_lambda * 1.0

    luts = []
    for i, g in enumerate(gains):
        r_g, g_g, b_g = g
        print(
            f"  [Scene {i + 1}] skin_RGB={np.round(profiles[i]['skin_mean'], 1).tolist()} "
            f"drift={profiles[i]['temporal_drift']:.2f} -> gain=({r_g:.4f}, {g_g:.4f}, {b_g:.4f})"
        )
        if np.max(np.abs(g - 1.0)) < 1e-3:
            luts.append(",lutrgb=r='val':g='val':b='val'")
        else:
            luts.append(
                f",lutrgb=r='clip(val*{r_g:.4f},0,255)':g='clip(val*{g_g:.4f},0,255)':b='clip(val*{b_g:.4f},0,255)'"
            )
    return luts


def run_self_check() -> None:
    single = compute_ml_scene_luts([Path("dummy.mp4")])
    assert single == [",lutrgb=r='val':g='val':b='val'"], single
    print("match_lighting.py self_check passed.")


def main() -> None:
    parser = argparse.ArgumentParser(description="ML lighting & color harmonization across UGC scenes.")
    parser.add_argument("--config", type=Path, default=None, help="Path to UGC engine config JSON.")
    parser.add_argument("--scenes", type=Path, nargs="*", default=None, help="Explicit list of scene MP4 paths.")
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL, help="Path to face_landmarker.task.")
    parser.add_argument("--check", action="store_true", help="Run fast self-check.")
    args = parser.parse_args()

    if args.check:
        run_self_check()
        return

    l_cfg = {}
    if args.scenes:
        scene_videos = list(args.scenes)
    elif args.config:
        _, cfg, persona_dir = resolve_persona_config(args.config)
        l_cfg = cfg.get("lighting", {})
        work_dir = persona_dir / cfg.get("work_dir", f"renders/{cfg['slug']}")
        scene_videos = [work_dir / f"scene{i + 1}_raw.mp4" for i in range(len(cfg["scenes"]))]
    else:
        parser.error("Provide --config <path_or_persona>, --scenes <mp4...>, or --check")

    luts = compute_ml_scene_luts(scene_videos, args.model, l_cfg)
    print(json.dumps(luts, indent=2))


if __name__ == "__main__":
    main()
