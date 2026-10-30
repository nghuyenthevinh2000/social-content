#!/usr/bin/env python3
"""Unified Multi-Scene UGC Video Engine (Gemini Omni 1.1 Flash I2V Chaining + ElevenLabs eleven_v3 Auto-Sync + Seamless Seam Editor)."""

import argparse
import base64
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from normalize_video import normalize_video

REPO_ROOT = Path(__file__).resolve().parents[4]
PROJECT_DIR = Path(__file__).resolve().parents[2]
SEAM_OVERLAP_SEC = 1.0 / 24.0  # 1-frame (0.0417s) blend merges duplicate anchor [s1_end, s2_frame0] without ghosting


def load_env() -> None:
    for env_path in (REPO_ROOT / ".env", PROJECT_DIR / ".env"):
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip("'\""))


def resolve_path(rel_or_abs: str) -> Path:
    p = Path(rel_or_abs)
    if p.is_absolute() and p.exists():
        return p
    for base in (PROJECT_DIR, REPO_ROOT):
        cand = (base / p).resolve()
        if cand.exists():
            return cand
    return (PROJECT_DIR / p).resolve()


def build_prompt(cfg: dict, scene: dict, is_first_scene: bool) -> str:
    cam = cfg["camera"]
    env = scene.get("environment") or cfg["environment"]
    subj = (
        cfg["subject_first_scene"]
        if is_first_scene
        else "Exact continuation from the starting frame. " + cfg["subject_continuation"]
    )
    actions = "\n".join(scene["actions"])
    dialogue = " ".join(c["text"] if isinstance(c, dict) else c for c in scene["clauses"])
    return (
        f"[CAMERA & COMPOSITION]\n{cam}\n\n"
        f"[ENVIRONMENT & ATMOSPHERE]\n{env}\n\n"
        f"[SUBJECT & CONTINUITY]\n{subj}\n\n"
        f"[ACTION & TIMECODE]\n{actions}\n\n"
        f"[AUDIO & DIALOGUE]\n"
        f'Clear spoken Vietnamese dialogue with natural northern artisan cadence: "{dialogue}". Ambient workshop room tone.'
    )


def render_scene(cfg: dict, scene: dict, idx: int, prev_video: Path | None, work_dir: Path) -> Path:
    for candidate in (work_dir / f"scene{idx}_raw.mp4", work_dir / f"scene{idx}_omni11_raw.mp4"):
        if candidate.exists() and candidate.stat().st_size > 0:
            print(f"  [Scene {idx}] Reusing cached raw video: {candidate.name}")
            return candidate
    out_video = work_dir / f"scene{idx}_raw.mp4"
    try:
        from google import genai
    except ModuleNotFoundError:
        venv_py = REPO_ROOT / "projects/OpenMontage/.venv/bin/python"
        if venv_py.exists() and Path(sys.executable) != venv_py:
            os.execv(str(venv_py), [str(venv_py), *sys.argv])
        raise

    client = genai.Client(vertexai=True, project=cfg.get("gcp_project", "gen-lang-client-0582170752"), location="global")
    model = cfg.get("video_model", "gemini-omni-1.1-flash-preview")
    prompt = build_prompt(cfg, scene, is_first_scene=(idx == 1))

    if idx == 1:
        face_b64 = base64.b64encode(resolve_path(cfg["face_image"]).read_bytes()).decode("utf-8")
        clothes_b64 = base64.b64encode(resolve_path(cfg["clothes_image"]).read_bytes()).decode("utf-8")
        inputs = [
            {"type": "image", "data": face_b64, "mime_type": "image/jpeg"},
            {"type": "image", "data": clothes_b64, "mime_type": "image/jpeg"},
        ]
        if cfg.get("product_image"):
            prod_path = resolve_path(cfg["product_image"])
            prod_b64 = base64.b64encode(prod_path.read_bytes()).decode("utf-8")
            inputs.append({"type": "image", "data": prod_b64, "mime_type": "image/jpeg"})
            print(f"  [Scene 1] Anchoring face + clothes + product image ({prod_path.name} as <IMAGE_REF_2>)...")
        inputs.append({"type": "text", "text": prompt})
        gen_cfg = None
    else:
        assert prev_video is not None and prev_video.exists(), f"Missing previous scene video for Scene {idx}"
        last_frame_jpg = work_dir / f"scene{idx - 1}_end.jpg"
        subprocess.run(
            ["ffmpeg", "-y", "-sseof", "-0.1", "-i", str(prev_video), "-update", "1", "-q:v", "2", str(last_frame_jpg), "-loglevel", "error"],
            check=True,
        )
        frame_b64 = base64.b64encode(last_frame_jpg.read_bytes()).decode("utf-8")
        inputs = [
            {"type": "image", "data": frame_b64, "mime_type": "image/jpeg"},
            {"type": "text", "text": prompt},
        ]
        gen_cfg = {"video_config": {"task": "image_to_video"}}

    print(f"  [Scene {idx}] Generating 10s clip on {model} (task={'reference_to_video' if idx == 1 else 'image_to_video'})...")
    kwargs = {
        "model": model,
        "input": inputs,
        "response_format": {"type": "video", "aspect_ratio": "9:16", "duration": "10s", "resolution": "720p"},
        "store": True,
    }
    if gen_cfg:
        kwargs["generation_config"] = gen_cfg

    interaction = client.interactions.create(**kwargs)
    out_vid = getattr(interaction, "output_video", None)
    video_b64 = getattr(out_vid, "data", None) or (out_vid.get("data") if isinstance(out_vid, dict) else None)
    if not video_b64:
        video_b64 = next(
            (getattr(item, "data", None) for item in (getattr(interaction, "outputs", None) or []) if getattr(item, "type", None) == "video"),
            None,
        )
    if not video_b64:
        raise RuntimeError(f"Scene {idx} returned no video data: {interaction}")

    out_video.write_bytes(base64.b64decode(video_b64))
    return out_video


def synthesize_eleven_v3(voice_id: str, clauses: list[str], work_dir: Path) -> tuple[Path, Path]:
    raw_mp3 = work_dir / "tts_v3_raw.mp3"
    align_json = work_dir / "tts_v3_alignment.json"
    full_text = " ".join(clauses)

    if raw_mp3.exists() and align_json.exists():
        cached_str = "".join(json.loads(align_json.read_text(encoding="utf-8")).get("characters", []))
        if cached_str.strip() == full_text.strip():
            print(f"  [Voice] Reusing cached eleven_v3 track: {raw_mp3.name}")
            return raw_mp3, align_json

    load_env()
    print(f"  [Voice] Synthesizing single-pass eleven_v3 TTS for {len(clauses)} clauses (Voice ID: {voice_id})...")
    node_script = (
        "import { ElevenLabsClient } from '@elevenlabs/elevenlabs-js';"
        "import { writeFileSync } from 'fs';"
        "const client = new ElevenLabsClient({ apiKey: process.env.ELEVENLABS_API_KEY });"
        "const res = await client.textToSpeech.convertWithTimestamps(process.env.VOICE_ID, {"
        "  text: process.env.TTS_TEXT, modelId: 'eleven_v3', outputFormat: 'mp3_44100_192',"
        "  voiceSettings: { stability: 0.5, similarityBoost: 0.85, style: 0.0, useSpeakerBoost: true }"
        "});"
        "writeFileSync(process.env.OUT_MP3, Buffer.from(res.audioBase64, 'base64'));"
        "writeFileSync(process.env.OUT_JSON, JSON.stringify(res.alignment, null, 2));"
    )
    env = {**os.environ, "VOICE_ID": voice_id, "TTS_TEXT": full_text, "OUT_MP3": str(raw_mp3), "OUT_JSON": str(align_json)}
    subprocess.run(["node", "--input-type=module", "-e", node_script], cwd=str(REPO_ROOT), env=env, check=True)
    return raw_mp3, align_json


def get_video_duration(video_path: Path) -> float:
    res = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(video_path)],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(res.stdout.strip() or 10.0)


def expand_scene_clauses(raw_clauses: list, detected_count: int) -> list:
    """Auto-split long sentences at comma/semicolon boundaries when video has more speech segments than JSON clauses."""
    if len(raw_clauses) >= detected_count or any(isinstance(c, dict) for c in raw_clauses):
        return raw_clauses
    expanded = []
    for c in raw_clauses:
        if len(expanded) + (len(raw_clauses) - raw_clauses.index(c)) < detected_count and "," in c:
            parts = [p.strip() for p in re.split(r"(?<=[,;])\s+", c) if p.strip()]
            expanded.extend(parts)
        else:
            expanded.append(c)
    return expanded


def merge_closest_windows(windows: list[tuple[float, float]], target_count: int) -> list[tuple[float, float]]:
    """Greedily merge adjacent speech windows with the smallest silence gap until count == target_count."""
    w = list(windows)
    while len(w) > target_count and len(w) > 1:
        gaps = [(w[i + 1][0] - w[i][1], i) for i in range(len(w) - 1)]
        _, idx = min(gaps)
        w[idx : idx + 2] = [(w[idx][0], w[idx + 1][1])]
    return w


def detect_scene_speech_windows(video_path: Path, is_last_scene: bool) -> list[tuple[float, float]]:
    dur = get_video_duration(video_path)
    max_end = round(dur - 0.08, 2)
    res = subprocess.run(
        ["ffmpeg", "-i", str(video_path), "-af", "silencedetect=noise=-30dB:d=0.18", "-f", "null", "-"],
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )
    starts = [float(x) for x in re.findall(r"silence_start:\s*([0-9.]+)", res.stderr)]
    ends = [float(x) for x in re.findall(r"silence_end:\s*([0-9.]+)", res.stderr)]
    speech = []
    cur = 0.0
    for s_start, s_end in zip(starts, ends + [dur]):
        # Drop only spurious false-start syllables that begin in the last 0.65s of non-final scenes
        if s_start - cur >= 0.30 and (is_last_scene or cur < dur - 0.65):
            speech.append((round(max(cur, 0.15), 2), round(min(s_start, max_end), 2)))
        cur = s_end
    if dur - cur >= 0.30 and (is_last_scene or cur < dur - 0.65):
        speech.append((round(max(cur, 0.15), 2), max_end))
    return speech or [(0.18, max_end)]


def resolve_clause_windows(
    scenes: list[dict], scene_videos: list[Path], align_path: Path
) -> list[tuple[float, float, float, float]]:
    resolved = []
    num_scenes = len(scenes)
    scene_offset = 0.0
    expanded_scenes = []
    detected_per_scene = []

    for s_idx, (scene, video_path) in enumerate(zip(scenes, scene_videos)):
        detected = detect_scene_speech_windows(video_path, is_last_scene=(s_idx == num_scenes - 1))
        detected_per_scene.append(detected)
        expanded_scenes.append(expand_scene_clauses(scene["clauses"], len(detected)))

    all_texts = [(c["text"] if isinstance(c, dict) else c) for sc in expanded_scenes for c in sc]
    src_bounds = parse_tts_clause_bounds(align_path, all_texts)
    clause_cursor = 0

    for s_idx, (raw_clauses, video_path, detected) in enumerate(zip(expanded_scenes, scene_videos, detected_per_scene)):
        n_c = len(raw_clauses)
        scene_src = src_bounds[clause_cursor : clause_cursor + n_c]

        if all(isinstance(c, dict) and "window" in c for c in raw_clauses):
            local_windows = [(float(c["window"][0]), float(c["window"][1])) for c in raw_clauses]
        elif len(detected) >= n_c:
            local_windows = merge_closest_windows(detected, n_c)
        else:
            span_start, span_end = detected[0][0], detected[-1][1]
            gap = 0.18
            usable = max(1.0, (span_end - span_start) - gap * (n_c - 1))
            weights = [s_e - s_s for s_s, s_e in scene_src]
            total_w = sum(weights) or 1.0
            local_windows = []
            t_cur = span_start
            for w in weights:
                dur = usable * (w / total_w)
                local_windows.append((round(t_cur, 2), round(t_cur + dur, 2)))
                t_cur += dur + gap

        for (s_s, s_e), (loc_s, loc_e) in zip(scene_src, local_windows):
            resolved.append((s_s, s_e, round(scene_offset + loc_s, 2), round(scene_offset + loc_e, 2)))
        clause_cursor += n_c
        scene_offset += get_video_duration(video_path) - SEAM_OVERLAP_SEC

    return resolved


def parse_tts_clause_bounds(align_path: Path, clauses: list[str]) -> list[tuple[float, float]]:
    align = json.loads(align_path.read_text(encoding="utf-8"))
    full_str = "".join(align["characters"])
    starts = align["characterStartTimesSeconds"]
    ends = align["characterEndTimesSeconds"]
    bounds = []
    search_from = 0
    for text in clauses:
        idx = full_str.find(text, search_from)
        assert idx != -1, f"Clause not found in alignment JSON: {text}"
        end_idx = idx + len(text) - 1
        bounds.append((starts[idx], ends[end_idx]))
        search_from = end_idx + 1
    return bounds


def compute_rgb_lut_filter(prev_video: Path, next_video: Path, work_dir: Path, idx: int) -> str:
    """Compute per-channel affine RGB LUT matching next_video Frame 0 to prev_video Last Frame."""
    f_prev = work_dir / f"_seam_prev_{idx}.ppm"
    f_next = work_dir / f"_seam_next_{idx}.ppm"
    subprocess.run(["ffmpeg", "-y", "-sseof", "-0.08", "-i", str(prev_video), "-update", "1", str(f_prev), "-loglevel", "error"], check=True)
    subprocess.run(["ffmpeg", "-y", "-i", str(next_video), "-vframes", "1", str(f_next), "-loglevel", "error"], check=True)

    def read_ppm_stats(p: Path) -> tuple[list[float], list[float]]:
        data = p.read_bytes()
        # Skip 3 header lines (P6, W H, 255)
        offset = 0
        for _ in range(3):
            offset = data.index(b"\n", offset) + 1
        rgb = memoryview(data)[offset:]
        n_px = len(rgb) // 3
        means, stds = [], []
        for c in range(3):
            ch = rgb[c::3]
            m = sum(ch) / n_px
            v = sum((x - m) ** 2 for x in ch) / n_px
            means.append(m)
            stds.append(max(v ** 0.5, 1e-6))
        return means, stds

    m1, s1 = read_ppm_stats(f_prev)
    m2, s2 = read_ppm_stats(f_next)
    f_prev.unlink(missing_ok=True)
    f_next.unlink(missing_ok=True)

    exprs = []
    for c_name, mu1, sd1, mu2, sd2 in zip(("r", "g", "b"), m1, s1, m2, s2):
        gain = sd1 / sd2
        bias = mu1 - mu2 * gain
        exprs.append(f"{c_name}='clip(val*{gain:.4f}+{bias:.2f},0,255)'")
    return "lutrgb=" + ":".join(exprs)


def build_seamless_video_filter(scene_videos: list[Path], work_dir: Path) -> str:
    """Build FFmpeg filtergraph with per-seam RGB color equalization + 1-frame duplicate-eliminating xfade."""
    if len(scene_videos) == 1:
        return "[0:v]fps=24,settb=AVTB[vout]"

    parts = ["[0:v]fps=24,settb=AVTB[v0]"]
    prev_label = "[v0]"
    cum_offset = get_video_duration(scene_videos[0]) - SEAM_OVERLAP_SEC

    for i in range(1, len(scene_videos)):
        lut_str = compute_rgb_lut_filter(scene_videos[i - 1], scene_videos[i], work_dir, i)
        col_label = f"[v{i}c]"
        out_label = "[vout]" if i == len(scene_videos) - 1 else f"[vx{i}]"
        parts.append(f"[{i}:v]fps=24,settb=AVTB,{lut_str}{col_label}")
        parts.append(
            f"{prev_label}{col_label}xfade=transition=fade:duration={SEAM_OVERLAP_SEC:.4f}:offset={cum_offset:.4f}{out_label}"
        )
        prev_label = out_label
        cum_offset += get_video_duration(scene_videos[i]) - SEAM_OVERLAP_SEC

    return ";".join(parts)


def run_pipeline(config_path: Path) -> Path:
    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    slug = cfg["slug"]
    work_dir = PROJECT_DIR / cfg.get("work_dir", f"renders/{slug}")
    work_dir.mkdir(parents=True, exist_ok=True)
    scenes = cfg["scenes"]

    scene_videos: list[Path] = []
    prev_video: Path | None = None
    for idx, scene in enumerate(scenes, start=1):
        prev_video = render_scene(cfg, scene, idx, prev_video, work_dir)
        scene_videos.append(prev_video)

    total_dur = sum(get_video_duration(v) for v in scene_videos) - max(0, len(scenes) - 1) * SEAM_OVERLAP_SEC
    print(f"=== Running Multi-Scene UGC Engine for '{slug}' ({len(scenes)} scenes, {total_dur:.2f}s) ===")

    all_clause_texts = [
        (c["text"] if isinstance(c, dict) else c) for s in scenes for c in s["clauses"]
    ]
    voice_id = cfg.get("voice_id", "FXJGVNPXC71BGT9PjlMX")
    raw_mp3, align_json = synthesize_eleven_v3(voice_id, all_clause_texts, work_dir)

    mapped_bounds = resolve_clause_windows(scenes, scene_videos, align_json)

    aligned_wav = work_dir / f"tts_v3_{len(scenes)*10}s_aligned.wav"
    filter_parts, mix_inputs = [], []
    for i, (s_start, s_end, t_start, t_end) in enumerate(mapped_bounds):
        src_dur = s_end - s_start
        tgt_dur = t_end - t_start
        tempo = max(0.5, min(2.0, src_dur / tgt_dur))
        delay_ms = int(round(t_start * 1000))
        fade_out_st = max(0.0, tgt_dur - 0.025)
        print(f"  [Clause {i+1}] TTS {s_start:.2f}-{s_end:.2f}s -> Video {t_start:.2f}-{t_end:.2f}s (atempo={tempo:.3f}x)")
        filter_parts.append(
            f"[0:a]atrim=start={s_start:.3f}:end={s_end:.3f},asetpts=PTS-STARTPTS,"
            f"atempo={tempo:.4f},afade=t=in:st=0:d=0.020,afade=t=out:st={fade_out_st:.3f}:d=0.025,"
            f"adelay={delay_ms}|{delay_ms}[c{i}]"
        )
        mix_inputs.append(f"[c{i}]")

    # Extract subtle continuous workshop room tone from first 0.18s of Scene 1 so pauses never drop to dead digital zero
    filter_parts.append(
        f"[1:a]atrim=0.02:0.18,asetpts=PTS-STARTPTS,aloop=loop=-1:size=8000,atrim=0:{total_dur:.2f},volume=0.06[amb]"
    )
    mix_inputs.append("[amb]")

    filter_parts.append(
        f"{''.join(mix_inputs)}amix=inputs={len(mix_inputs)}:normalize=0,"
        f"loudnorm=I=-16:TP=-1.5:LRA=11,apad=whole_dur={total_dur:.2f},atrim=0:{total_dur:.2f}[aout]"
    )
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(raw_mp3), "-i", str(scene_videos[0]),
            "-filter_complex", ";".join(filter_parts),
            "-map", "[aout]", "-ar", "44100", "-ac", "2", str(aligned_wav), "-loglevel", "error",
        ],
        check=True,
    )

    print("  [Seam Editor] Applying per-channel RGB equalization + 1-frame duplicate-anchor fusion...")
    raw_muxed = work_dir / f"{slug}_raw_muxed.mp4"
    v_inputs = [arg for v in scene_videos for arg in ("-i", str(v))]
    v_filter = build_seamless_video_filter(scene_videos, work_dir)
    subprocess.run(
        [
            "ffmpeg", "-y", *v_inputs, "-i", str(aligned_wav),
            "-filter_complex", v_filter, "-map", "[vout]", "-map", f"{len(scene_videos)}:a:0",
            "-c:v", "libx264", "-crf", "18", "-preset", "fast", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2", "-shortest", str(raw_muxed), "-loglevel", "error",
        ],
        check=True,
    )

    final_out = PROJECT_DIR / cfg.get("output_path", f"renders/{slug}_web_optimized.mp4")
    normalize_video(raw_muxed, final_out)
    raw_muxed.unlink(missing_ok=True)
    for copy_target in cfg.get("mirror_outputs", []):
        dst = PROJECT_DIR / copy_target
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(final_out, dst)
    print(f"=== Completed: {final_out} ===")
    return final_out


def main() -> None:
    parser = argparse.ArgumentParser(description="Multi-Scene UGC Video Engine")
    parser.add_argument("config", type=Path, help="Path to scene config JSON")
    args = parser.parse_args()
    out = run_pipeline(args.config)
    assert out.exists() and out.stat().st_size > 100_000, f"Output check failed: {out}"


if __name__ == "__main__":
    main()
