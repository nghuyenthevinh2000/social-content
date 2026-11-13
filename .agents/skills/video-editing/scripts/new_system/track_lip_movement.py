#!/usr/bin/env python3
"""
track_lip_movement.py
──────────────────────────────────────────────────────────────────────────────
Multimodal lip movement & acoustic burst tracking for multi-scene UGC avatars.

Fuses Google MediaPipe FaceLandmarker (jawOpen blendshape + inner-lip MAR) with
10ms native audio RMS burst detection and ElevenLabs TTS silence trimming across
all punctuation-delimited utterances (commas, semicolons, periods).

Key capabilities:
1. Punctuation-level utterance segmentation: splits clauses on [, ; : . ! ?] so
   intra-clause pauses (e.g., after counting numbers) stay silent while lips rest.
2. Pre-phonatory jaw-opening alignment: shifts window onset to match visual
   mouth opening (jawOpen > 0.12) and centers vocal peaks over maximum jaw open.
3. ElevenLabs TTS acoustic trimming: strips 200ms-390ms of leading/trailing dead
   silence from character alignment bounds before computing atempo (0.88x-1.20x).
4. Dynamic N-scene color-matched muxing: equalizes inter-cut RGB luminance and
   concatenates arbitrary scene counts without xfade frame drops.
──────────────────────────────────────────────────────────────────────────────
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np

from match_lighting import compute_ml_scene_luts, resolve_persona_config

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent.parent


def extract_scene_lip_signal(
    video_path: Path,
    model_path: Path,
) -> tuple[np.ndarray, np.ndarray, float, int]:
    """Extract per-frame jawOpen blendshape and inner-lip MAR using MediaPipe FaceLandmarker."""
    options = mp.tasks.vision.FaceLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(model_path)),
        running_mode=mp.tasks.vision.RunningMode.VIDEO,
        output_face_blendshapes=True,
        num_faces=1,
    )

    cap = cv2.VideoCapture(str(video_path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    jaws, mars = [], []

    with mp.tasks.vision.FaceLandmarker.create_from_options(options) as landmarker:
        frame_idx = 0
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            res = landmarker.detect_for_video(mp_image, int(round(frame_idx * 1000.0 / fps)))

            jaw = 0.0
            if res.face_blendshapes:
                for b in res.face_blendshapes[0]:
                    if b.category_name == "jawOpen":
                        jaw = b.score
                        break
            mar = 0.0
            if res.face_landmarks:
                lm = res.face_landmarks[0]
                mar = abs(lm[13].y - lm[14].y) / (abs(lm[78].x - lm[308].x) + 1e-6)

            jaws.append(jaw)
            mars.append(mar)
            frame_idx += 1

    cap.release()
    return np.array(jaws), np.array(mars), fps, frame_count


def detect_scene_utterance_bursts(
    video_path: Path, expected_count: int, burst_rms_thresh: float = 0.018
) -> list[tuple[float, float]]:
    """Detect punctuation-level utterance bursts at 10ms resolution from scene audio."""
    pr = subprocess.run(
        ["ffmpeg", "-i", str(video_path), "-vn", "-ar", "16000", "-ac", "1", "-f", "f32le", "-loglevel", "error", "-"],
        capture_output=True,
        check=True,
    )
    sa = np.frombuffer(pr.stdout, dtype=np.float32)
    rms = np.array([np.sqrt(np.mean(sa[k : k + 320] ** 2)) for k in range(0, len(sa) - 320, 160)])
    active = rms > burst_rms_thresh

    gap = 0
    for i in range(len(active)):
        if not active[i]:
            gap += 1
        else:
            if 0 < gap <= 14 and i - gap > 0:
                active[i - gap : i] = True
            gap = 0

    bursts: list[tuple[float, float]] = []
    st = None
    for i, a in enumerate(active):
        t = i * 0.01
        if a and st is None:
            st = t
        elif not a and st is not None:
            if t - st >= 0.14:
                bursts.append((round(st, 2), round(t, 2)))
            st = None
    if st is not None and len(active) * 0.01 - st >= 0.14:
        bursts.append((round(st, 2), round(len(active) * 0.01, 2)))

    while len(bursts) > expected_count and len(bursts) > 1:
        gaps = [(bursts[i + 1][0] - bursts[i][1], i) for i in range(len(bursts) - 1)]
        _, idx = min(gaps)
        bursts[idx : idx + 2] = [(bursts[idx][0], bursts[idx + 1][1])]

    while 0 < len(bursts) < expected_count:
        # Split the burst containing the deepest internal RMS valley
        best_split = None
        for idx, (b_s, b_e) in enumerate(bursts):
            i0, i1 = int((b_s + 0.18) * 100), int((b_e - 0.18) * 100)
            if i1 > i0:
                v_idx = i0 + int(np.argmin(rms[i0:i1]))
                cand = (float(rms[v_idx]), idx, round(v_idx * 0.01, 2))
                if best_split is None or cand[0] < best_split[0]:
                    best_split = cand
        if best_split is None:
            break
        _, idx, split_t = best_split
        b_s, b_e = bursts[idx]
        bursts[idx : idx + 1] = [(b_s, round(split_t - 0.02, 2)), (round(split_t + 0.02, 2), b_e)]

    return bursts


def compute_ml_lip_synced_bounds(
    cfg: dict,
    scene_videos: list[Path],
    raw_mp3: Path,
    align_path: Path,
    model_path: Path,
) -> tuple[list[tuple[float, float, float, float]], float]:
    """Fuse MediaPipe lip opening, native utterance bursts, and silence-trimmed TTS slices."""
    align = json.loads(align_path.read_text(encoding="utf-8"))
    chars = align["characters"]
    starts = align["characterStartTimesSeconds"]
    ends = align["characterEndTimesSeconds"]
    full_text = "".join(chars)

    pr = subprocess.run(
        ["ffmpeg", "-i", str(raw_mp3), "-ar", "16000", "-ac", "1", "-f", "f32le", "-loglevel", "error", "-"],
        capture_output=True,
        check=True,
    )
    tts_audio = np.frombuffer(pr.stdout, dtype=np.float32)

    ls_cfg = cfg.get("lip_sync", {})
    burst_rms_thresh = float(ls_cfg.get("burst_rms_threshold", 0.018))
    jaw_open_thresh = float(ls_cfg.get("jaw_open_threshold", 0.12))
    tts_trim_thresh = float(ls_cfg.get("tts_trim_rms_threshold", 0.015))
    min_tempo = float(ls_cfg.get("min_tempo", 0.88))
    max_tempo = float(ls_cfg.get("max_tempo", 1.20))

    all_bounds: list[tuple[float, float, float, float]] = []
    search_idx = 0
    cum_offset = 0.0

    for s_idx, (scene, video_path) in enumerate(zip(cfg["scenes"], scene_videos)):
        raw_text = " ".join(c["text"] if isinstance(c, dict) else c for c in scene["clauses"])
        phrases = [p.strip() for p in re.findall(r"[^,;:.!?]+[,;:.!?]?", raw_text) if p.strip()]

        jaws, _, fps, frame_count = extract_scene_lip_signal(video_path, model_path)
        scene_dur = frame_count / fps
        bursts = detect_scene_utterance_bursts(video_path, len(phrases), burst_rms_thresh)
        assert len(bursts) == len(phrases), f"Scene {s_idx + 1}: {len(bursts)} bursts != {len(phrases)} phrases"

        print(f"\n--- Scene {s_idx + 1}: {video_path.name} ({len(phrases)} utterances) ---")
        for b_idx, (phrase, (b_s, b_e)) in enumerate(zip(phrases, bursts)):
            prev_end = bursts[b_idx - 1][1] + 0.08 if b_idx > 0 else 0.10
            next_start = bursts[b_idx + 1][0] - 0.08 if b_idx + 1 < len(bursts) else scene_dur - 0.10
            f0 = max(0, int(max(prev_end, b_s - 0.35) * fps))
            f1 = min(len(jaws), int(min(next_start, b_e + 0.20) * fps) + 1)

            wide_frames = [f for f in range(f0, f1) if jaws[f] > jaw_open_thresh]
            v_s, v_e = b_s, b_e
            if wide_frames:
                lip_s = round(wide_frames[0] / fps, 2)
                lip_e = round((wide_frames[-1] + 1) / fps, 2)
                if lip_s < v_s:
                    v_s = lip_s
                if len(phrase.split()) == 1 and lip_e < v_e and jaws[min(len(jaws) - 1, int(v_e * fps))] < 0.035:
                    v_e = max(lip_e, v_s + 0.28)

            idx = full_text.find(phrase, search_idx)
            assert idx != -1, f"Phrase not found in alignment JSON: {phrase}"
            end_idx = idx + len(phrase) - 1
            s_s, s_e_full = starts[idx], ends[end_idx]

            i0, i1 = int(s_s * 16000), int(s_e_full * 16000)
            chunk = tts_audio[i0:i1]
            c_rms = np.array([np.sqrt(np.mean(chunk[k : k + 160] ** 2)) for k in range(0, len(chunk) - 160, 160)])
            act = np.where(c_rms > tts_trim_thresh)[0]
            r_s = round(max(s_s, s_s + (act[0] * 0.01 - 0.015)), 3) if len(act) else round(s_s, 3)
            r_e = round(min(s_e_full, s_s + ((act[-1] + 2) * 0.01 + 0.020)), 3) if len(act) else round(s_e_full, 3)

            src_dur = r_e - r_s
            tgt_dur = v_e - v_s
            clamped_tempo = max(min_tempo, min(max_tempo, src_dur / tgt_dur))
            eff_dur = src_dur / clamped_tempo
            if eff_dur < tgt_dur:
                pad = (tgt_dur - eff_dur) / 2.0
                t_s = round(cum_offset + v_s + pad, 2)
                t_e = round(t_s + eff_dur, 2)
            else:
                t_s = round(cum_offset + v_s, 2)
                t_e = round(t_s + eff_dur, 2)

            print(
                f"  {phrase:36s} | TTS [{r_s:6.3f}-{r_e:6.3f}] ({src_dur:4.2f}s) -> "
                f"Vid [{t_s:5.2f}-{t_e:5.2f}] ({t_e - t_s:4.2f}s) | tempo={src_dur / (t_e - t_s):5.3f}x"
            )
            all_bounds.append((r_s, r_e, t_s, t_e))
            search_idx = end_idx + 1

        cum_offset += scene_dur

    return all_bounds, round(cum_offset, 2)


def build_lip_synced_audio(
    raw_mp3: Path,
    scene1_video: Path,
    clause_bounds: list[tuple[float, float, float, float]],
    out_wav: Path,
    total_dur: float,
    audio_mix_cfg: dict | None = None,
) -> None:
    """Assemble the utterance-aligned TTS track with sample-accurate delays and room tone."""
    am = audio_mix_cfg or {}
    rt_s = float(am.get("room_tone_start", 0.02))
    rt_e = float(am.get("room_tone_end", 0.18))
    rt_vol = float(am.get("room_tone_volume", 0.05))
    lufs = float(am.get("target_lufs", -16.0))
    tp = float(am.get("true_peak", -1.5))
    lra = float(am.get("lra", 11.0))

    filter_parts, mix_inputs = [], []

    for i, (s_start, s_end, t_start, t_end) in enumerate(clause_bounds):
        src_dur = s_end - s_start
        tgt_dur = t_end - t_start
        tempo = src_dur / tgt_dur if tgt_dur > 0 else 1.0
        delay_ms = int(round(t_start * 1000))
        fade_out_st = max(0.0, tgt_dur - 0.018)

        filter_parts.append(
            f"[0:a]atrim=start={s_start:.3f}:end={s_end:.3f},asetpts=PTS-STARTPTS,"
            f"atempo={tempo:.4f},afade=t=in:st=0:d=0.012,afade=t=out:st={fade_out_st:.3f}:d=0.018,"
            f"adelay={delay_ms}|{delay_ms}[c{i}]"
        )
        mix_inputs.append(f"[c{i}]")

    filter_parts.append(
        f"[1:a]atrim={rt_s:.2f}:{rt_e:.2f},asetpts=PTS-STARTPTS,aloop=loop=-1:size=8000,atrim=0:{total_dur:.2f},volume={rt_vol:.3f}[amb]"
    )
    mix_inputs.append("[amb]")

    filter_parts.append(
        f"{''.join(mix_inputs)}amix=inputs={len(mix_inputs)}:normalize=0,"
        f"loudnorm=I={lufs}:TP={tp}:LRA={lra},apad=whole_dur={total_dur:.2f},atrim=0:{total_dur:.2f}[aout]"
    )

    subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(raw_mp3), "-i", str(scene1_video),
            "-filter_complex", ";".join(filter_parts),
            "-map", "[aout]", "-ar", "44100", "-ac", "2", str(out_wav), "-loglevel", "error",
        ],
        check=True,
    )
    print(f"\n[OK] Aligned audio synthesized: {out_wav}")


def mux_final_video(
    scene_videos: list[Path],
    audio_wav: Path,
    out_raw_mp4: Path,
    out_web_mp4: Path,
    normalize_script: Path,
    model_path: Path,
    lighting_cfg: dict | None = None,
) -> None:
    """Concatenate N scenes with ML Face+BG lighting stabilization in unified gbrp space, mux audio, and normalize."""
    v_inputs, v_chains, v_labels = [], [], []
    luts = compute_ml_scene_luts(scene_videos, model_path, lighting_cfg)
    for i, (v_path, lut) in enumerate(zip(scene_videos, luts)):
        v_inputs.extend(["-i", str(v_path)])
        v_chains.append(f"[{i}:v]fps=24,settb=AVTB,setpts=PTS-STARTPTS{lut}[v{i}]")
        v_labels.append(f"[v{i}]")

    filter_complex = f"{';'.join(v_chains)};{''.join(v_labels)}concat=n={len(scene_videos)}:v=1:a=0[vout]"
    subprocess.run(
        [
            "ffmpeg", "-y", *v_inputs, "-i", str(audio_wav),
            "-filter_complex", filter_complex,
            "-map", "[vout]", "-map", f"{len(scene_videos)}:a:0",
            "-c:v", "libx264", "-crf", "18", "-preset", "fast", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2", "-shortest",
            str(out_raw_mp4), "-loglevel", "error",
        ],
        check=True,
    )
    subprocess.run([sys.executable, str(normalize_script), str(out_raw_mp4), str(out_web_mp4)], check=True)
    print(f"[OK] Final web-optimized video normalized: {out_web_mp4}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Multimodal ML lip movement tracking for UGC videos.")
    parser.add_argument("--config", type=Path, required=True, help="Path to UGC engine config JSON.")
    parser.add_argument("--work-dir", type=Path, default=None, help="Render working directory (optional).")
    parser.add_argument(
        "--model",
        type=Path,
        default=PROJECT_DIR / "models/face_landmarker.task",
        help="Path to face_landmarker.task model.",
    )
    parser.add_argument("--out-bounds", type=Path, default=None, help="Output path for clause_bounds.json.")
    parser.add_argument("--render", action="store_true", default=False, help="Synthesize audio and mux final MP4.")
    args = parser.parse_args()

    _, cfg, persona_dir = resolve_persona_config(args.config)
    slug = cfg["slug"]
    work_dir = args.work_dir or (persona_dir / cfg.get("work_dir", f"renders/{slug}"))
    out_bounds = args.out_bounds or (work_dir / "clause_bounds.json")
    align_path = work_dir / "tts_v3_alignment.json"
    raw_mp3 = work_dir / "tts_v3_raw.mp3"
    scene_videos = [work_dir / f"scene{i + 1}_raw.mp4" for i in range(len(cfg["scenes"]))]

    bounds, total_dur = compute_ml_lip_synced_bounds(cfg, scene_videos, raw_mp3, align_path, args.model)
    out_bounds.write_text(json.dumps([list(b) for b in bounds], indent=2), encoding="utf-8")
    print(f"\n[OK] {len(bounds)}-utterance clause bounds saved to: {out_bounds}")

    if args.render:
        out_wav = work_dir / "tts_v3_ml_lip_synced.wav"
        build_lip_synced_audio(raw_mp3, scene_videos[0], bounds, out_wav, total_dur=total_dur, audio_mix_cfg=cfg.get("audio_mix"))
        out_raw_mp4 = work_dir / f"{slug}_raw_muxed.mp4"
        out_web_mp4 = (
            persona_dir / cfg["output_path"]
            if "output_path" in cfg
            else work_dir / f"{slug}_web_optimized.mp4"
        )
        mux_final_video(
            scene_videos,
            out_wav,
            out_raw_mp4,
            out_web_mp4,
            SCRIPT_DIR / "normalize_video.py",
            args.model,
            cfg.get("lighting"),
        )


if __name__ == "__main__":
    main()
