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
from match_lighting import compute_ml_scene_luts
from normalize_video import normalize_video
from synthesize_eleven_v3 import load_env, synthesize_eleven_v3

REPO_ROOT = Path(__file__).resolve().parents[4]
PROJECT_DIR = Path(__file__).resolve().parents[2]
SEAM_OVERLAP_SEC = 1.0 / 24.0  # 1-frame (0.0417s) blend merges duplicate anchor [s1_end, s2_frame0] without ghosting


def resolve_config_path(path_or_persona: str | Path) -> Path:
    p = Path(path_or_persona)
    for cand in (
        p,
        p / "config.json",
        PROJECT_DIR / p,
        PROJECT_DIR / p / "config.json",
        REPO_ROOT / p,
        REPO_ROOT / p / "config.json",
    ):
        if cand.is_file():
            return cand.resolve()
    return p.resolve()


def resolve_path(rel_or_abs: str | Path, persona_dir: Path | None = None) -> Path:
    p = Path(rel_or_abs)
    if p.is_absolute() and p.exists():
        return p
    bases = ([persona_dir] if persona_dir else []) + [PROJECT_DIR, REPO_ROOT]
    for base in bases:
        cand = (base / p).resolve()
        if cand.exists():
            return cand
    return ((persona_dir or PROJECT_DIR) / p).resolve()


def resolve_creator_defaults(cfg: dict, config_path: Path | None = None) -> dict:
    creator = cfg.get("creator")
    if not creator and config_path is not None:
        for parent in [config_path.resolve().parent, *config_path.resolve().parents]:
            if parent.parent == PROJECT_DIR and (PROJECT_DIR / parent.name).is_dir():
                creator = parent.name
                break
    persona_dir = (
        (PROJECT_DIR / creator).resolve()
        if creator and (PROJECT_DIR / creator).is_dir()
        else (config_path.resolve().parent if config_path else PROJECT_DIR)
    )
    persona_cfg_path = persona_dir / "config.json"
    if persona_cfg_path.is_file():
        persona_cfg = json.loads(persona_cfg_path.read_text(encoding="utf-8"))
        cfg = {**persona_cfg, **cfg}
    cfg["_persona_dir"] = str(persona_dir)
    if creator:
        cfg["creator"] = creator
        cfg.setdefault("face_image", "assets/images/face.jpg")
        cfg.setdefault("clothes_image", "assets/images/clothes.jpg")
        for meta_cand in (
            persona_dir / "assets/audio/voice_meta.json",
            PROJECT_DIR / creator / "assets/audio/voice_meta.json",
        ):
            if "voice_id" not in cfg and meta_cand.exists():
                meta = json.loads(meta_cand.read_text(encoding="utf-8"))
                if meta.get("voice_id"):
                    cfg["voice_id"] = meta["voice_id"]
                break
    return cfg


def build_prompt(cfg: dict, scene: dict, is_first_scene: bool, safe_fallback: bool = False) -> str:
    cam = scene.get("camera") or cfg["camera"]
    env = scene.get("environment") or cfg["environment"]
    subj = (
        cfg["subject_first_scene"]
        if is_first_scene
        else "Exact continuation from the starting frame. " + cfg["subject_continuation"]
    )
    if safe_fallback:
        fb = cfg["safe_fallback"]
        actions = "\n".join(fb["actions"])
        dialogue = fb["dialogue"]
    else:
        actions = "\n".join(scene.get("visual_actions") or scene["actions"])
        dialogue = scene.get("visual_dialogue") or " ".join(c["text"] if isinstance(c, dict) else c for c in scene["clauses"])
    tmpl = cfg.get("audio_description_template", "{dialogue}")
    audio_desc = scene.get("audio_description") or cfg.get("audio_description") or tmpl.format(dialogue=dialogue)
    return (
        f"[CAMERA & COMPOSITION]\n{cam}\n\n"
        f"[ENVIRONMENT & ATMOSPHERE]\n{env}\n\n"
        f"[SUBJECT & CONTINUITY]\n{subj}\n\n"
        f"[ACTION & TIMECODE]\n{actions}\n\n"
        f"[AUDIO & DIALOGUE]\n{audio_desc}"
    )


def resolve_resolution(val: str | int | None = None) -> str:
    s = str(val or "360p").strip().lower().removesuffix("p")
    if s not in ("360", "720"):
        raise ValueError(f"Unsupported quality/resolution '{val}'. Allowed: 360p, 720p.")
    return f"{s}p"


def render_scene(
    cfg: dict, scene: dict, idx: int, prev_video: Path | None, work_dir: Path, quality: str | None = None
) -> Path:
    for candidate in (work_dir / f"scene{idx}_raw.mp4", work_dir / f"scene{idx}_omni11_raw.mp4"):
        if candidate.exists() and candidate.stat().st_size > 0:
            print(f"  [Scene {idx}] Reusing cached raw video: {candidate.name}")
            return candidate
    out_video = work_dir / f"scene{idx}_raw.mp4"
    try:
        from google import genai
    except ModuleNotFoundError:
        venv_py = REPO_ROOT / ".venv/bin/python"
        if venv_py.exists() and Path(sys.executable) != venv_py:
            os.execv(str(venv_py), [str(venv_py), *sys.argv])
        raise

    load_env()
    gcp_project = cfg.get("gcp_project") or os.environ.get("GOOGLE_CLOUD_PROJECT")
    gcp_location = cfg.get("gcp_location", "global")
    client = genai.Client(vertexai=True, project=gcp_project, location=gcp_location)
    model = cfg["video_model"]
    aspect_ratio = scene.get("aspect_ratio") or cfg.get("aspect_ratio", "9:16")
    scene_duration = scene.get("duration") or cfg.get("scene_duration", "10s")
    resolution = resolve_resolution(
        quality or scene.get("quality") or scene.get("resolution") or cfg.get("quality") or cfg.get("resolution") or "360p"
    )
    prompt = build_prompt(cfg, scene, is_first_scene=(idx == 1))

    persona_dir = Path(cfg.get("_persona_dir", PROJECT_DIR))
    if idx == 1:
        face_b64 = base64.b64encode(resolve_path(cfg["face_image"], persona_dir).read_bytes()).decode("utf-8")
        clothes_b64 = base64.b64encode(resolve_path(cfg["clothes_image"], persona_dir).read_bytes()).decode("utf-8")
        inputs = [
            {"type": "image", "data": face_b64, "mime_type": "image/jpeg"},
            {"type": "image", "data": clothes_b64, "mime_type": "image/jpeg"},
        ]
        if cfg.get("product_image"):
            prod_path = resolve_path(cfg["product_image"], persona_dir)
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

    print(f"  [Scene {idx}] Generating {scene_duration} clip on {model} ({resolution}, task={'reference_to_video' if idx == 1 else 'image_to_video'})...")
    kwargs = {
        "model": model,
        "input": inputs,
        "response_format": {"type": "video", "aspect_ratio": aspect_ratio, "duration": scene_duration, "resolution": resolution},
        "store": True,
    }
    if gen_cfg:
        kwargs["generation_config"] = gen_cfg

    try:
        interaction = client.interactions.create(**kwargs)
    except Exception as e:
        if "safety" in str(e).lower() or "harmful" in str(e).lower():
            print(f"  [Scene {idx}] Safety filter triggered on raw prompt; retrying automatically with neutral visual dialogue...")
            inputs[-1] = {"type": "text", "text": build_prompt(cfg, scene, is_first_scene=(idx == 1), safe_fallback=True)}
            interaction = client.interactions.create(**kwargs)
        else:
            raise
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


def get_video_duration(video_path: Path) -> float:
    res = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(video_path)],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(res.stdout.strip() or 10.0)


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


def extract_scene_words(align: dict, start_char: int, end_char: int) -> list[tuple[str, float, float]]:
    chars = align["characters"]
    starts = align["characterStartTimesSeconds"]
    ends = align["characterEndTimesSeconds"]
    words, cur_w, w_s, w_e = [], [], None, None
    for idx in range(start_char, end_char):
        ch = chars[idx]
        if not ch.isspace():
            if w_s is None:
                w_s = starts[idx]
            w_e = ends[idx]
            cur_w.append(ch)
        elif cur_w and w_s is not None and w_e is not None:
            words.append(("".join(cur_w), float(w_s), float(w_e)))
            cur_w, w_s = [], None
    if cur_w and w_s is not None and w_e is not None:
        words.append(("".join(cur_w), float(w_s), float(w_e)))
    return words


def partition_words_to_windows_dp(
    words: list[tuple[str, float, float]], windows: list[tuple[float, float]]
) -> list[tuple[float, float, float, float]]:
    """Map TTS words strictly into detected mouth-open windows via DP so zero audio plays while lips are closed."""
    n_w = len(words)
    wins = merge_closest_windows(windows, min(len(windows), n_w))
    m_win = len(wins)
    if m_win == 1:
        return [(words[0][1], words[-1][2], wins[0][0], wins[0][1])]

    win_durs = [max(0.15, e - s) for s, e in wins]
    win_gaps = [wins[j + 1][0] - wins[j][1] for j in range(m_win - 1)] + [0.0]
    total_tts = sum(e - s for _, s, e in words)
    avg_tempo = total_tts / max(0.2, sum(win_durs))
    dp = [[(1e9, -1)] * n_w for _ in range(m_win)]

    def seg_cost(i: int, k: int, j: int) -> float:
        tts_dur = max(0.08, words[k][2] - words[i][1])
        tempo = tts_dur / win_durs[j]
        cost = ((tempo - avg_tempo) / max(0.5, avg_tempo)) ** 2 * 4.0
        if tempo > 1.45:
            cost += (tempo - 1.45) ** 2 * 25.0
        elif tempo < 0.72:
            cost += (0.72 - tempo) ** 2 * 20.0
        if j < m_win - 1:
            last_ch = words[k][0][-1]
            tts_gap = max(0.0, words[k + 1][1] - words[k][2])
            gap_weight = 1.5 if win_gaps[j] >= 0.5 else 1.0
            if last_ch in ".?!":
                cost -= 1.4 * gap_weight
            elif last_ch in ",;:":
                cost -= 0.95 * gap_weight
            else:
                cost += 0.85 * gap_weight
            cost -= min(0.6, tts_gap * 2.5) * gap_weight
        return cost

    for k in range(0, n_w - (m_win - 1)):
        dp[0][k] = (seg_cost(0, k, 0), -1)
    for j in range(1, m_win):
        for k in range(j, n_w - (m_win - 1 - j)):
            best = (1e9, -1)
            for prev_k in range(j - 1, k):
                cand = dp[j - 1][prev_k][0] + seg_cost(prev_k + 1, k, j)
                if cand < best[0]:
                    best = (cand, prev_k)
            dp[j][k] = best

    res = []
    cur_k = n_w - 1
    for j in range(m_win - 1, -1, -1):
        prev_k = dp[j][cur_k][1]
        start_i = prev_k + 1
        res.append((words[start_i][1], words[cur_k][2], wins[j][0], wins[j][1]))
        cur_k = prev_k
    res.reverse()
    return res


def resolve_clause_windows(
    scenes: list[dict], scene_videos: list[Path], align_path: Path
) -> list[tuple[float, float, float, float]]:
    resolved = []
    num_scenes = len(scenes)
    scene_offset = 0.0
    align = json.loads(align_path.read_text(encoding="utf-8"))
    full_str = "".join(align["characters"])
    search_from = 0

    for s_idx, (scene, video_path) in enumerate(zip(scenes, scene_videos)):
        raw_clauses = scene["clauses"]
        clause_texts = [c["text"] if isinstance(c, dict) else c for c in raw_clauses]
        scene_text = " ".join(clause_texts)
        idx = full_str.find(scene_text, search_from)
        assert idx != -1, f"Scene text not found in alignment JSON: {scene_text}"
        end_idx = idx + len(scene_text)
        search_from = end_idx

        if all(isinstance(c, dict) and "window" in c for c in raw_clauses):
            src_bounds = parse_tts_clause_bounds(align_path, clause_texts)
            local_windows = [(float(c["window"][0]), float(c["window"][1])) for c in raw_clauses]
            scene_pairs = [
                (s_s, s_e, loc_s, loc_e) for (s_s, s_e), (loc_s, loc_e) in zip(src_bounds, local_windows)
            ]
        else:
            detected = detect_scene_speech_windows(video_path, is_last_scene=(s_idx == num_scenes - 1))
            words = extract_scene_words(align, idx, end_idx)
            scene_pairs = partition_words_to_windows_dp(words, detected)

        for s_s, s_e, loc_s, loc_e in scene_pairs:
            resolved.append((round(s_s, 3), round(s_e, 3), round(scene_offset + loc_s, 2), round(scene_offset + loc_e, 2)))
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


def build_seamless_video_filter(scene_videos: list[Path], lighting_cfg: dict | None = None) -> str:
    """Build FFmpeg filtergraph with ML Face+BG RGB color harmonization across N scenes."""
    luts = compute_ml_scene_luts(scene_videos, lighting_cfg=lighting_cfg)
    chains = [f"[{i}:v]fps=24,settb=AVTB,setpts=PTS-STARTPTS{lut}[v{i}]" for i, lut in enumerate(luts)]
    labels = "".join(f"[v{i}]" for i in range(len(scene_videos)))
    return f"{';'.join(chains)};{labels}concat=n={len(scene_videos)}:v=1:a=0[vout]"


def run_pipeline(config_path: Path, quality: str | None = None) -> Path:
    config_path = resolve_config_path(config_path)
    cfg = resolve_creator_defaults(json.loads(config_path.read_text(encoding="utf-8")), config_path)
    persona_dir = Path(cfg["_persona_dir"])
    slug = cfg["slug"]
    work_dir = resolve_path(cfg.get("work_dir", f"renders/{slug}"), persona_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    scenes = cfg["scenes"]

    scene_videos: list[Path] = []
    prev_video: Path | None = None
    for idx, scene in enumerate(scenes, start=1):
        prev_video = render_scene(cfg, scene, idx, prev_video, work_dir, quality=quality)
        scene_videos.append(prev_video)

    total_dur = sum(get_video_duration(v) for v in scene_videos) - max(0, len(scenes) - 1) * SEAM_OVERLAP_SEC
    print(f"=== Running Multi-Scene UGC Engine for '{slug}' ({len(scenes)} scenes, {total_dur:.2f}s) ===")

    all_clause_texts = [
        (c["text"] if isinstance(c, dict) else c) for s in scenes for c in s["clauses"]
    ]
    voice_id = cfg["voice_id"]
    raw_mp3, align_json = synthesize_eleven_v3(voice_id, all_clause_texts, work_dir, cfg=cfg)

    mapped_bounds = resolve_clause_windows(scenes, scene_videos, align_json)
    (work_dir / "clause_bounds.json").write_text(
        json.dumps([list(b) for b in mapped_bounds], indent=2), encoding="utf-8"
    )

    am = cfg.get("audio_mix", {})
    rt_s = float(am.get("room_tone_start", 0.02))
    rt_e = float(am.get("room_tone_end", 0.18))
    rt_vol = float(am.get("room_tone_volume", 0.05))
    lufs = float(am.get("target_lufs", -16.0))
    tp = float(am.get("true_peak", -1.5))
    lra = float(am.get("lra", 11.0))

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
            "ffmpeg", "-y", "-i", str(raw_mp3), "-i", str(scene_videos[0]),
            "-filter_complex", ";".join(filter_parts),
            "-map", "[aout]", "-ar", "44100", "-ac", "2", str(aligned_wav), "-loglevel", "error",
        ],
        check=True,
    )

    print("  [Seam Editor] Applying ML per-channel RGB equalization...")
    raw_muxed = work_dir / f"{slug}_raw_muxed.mp4"
    v_inputs = [arg for v in scene_videos for arg in ("-i", str(v))]
    v_filter = build_seamless_video_filter(scene_videos, cfg.get("lighting"))
    subprocess.run(
        [
            "ffmpeg", "-y", *v_inputs, "-i", str(aligned_wav),
            "-filter_complex", v_filter, "-map", "[vout]", "-map", f"{len(scene_videos)}:a:0",
            "-c:v", "libx264", "-crf", "18", "-preset", "fast", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2", "-shortest", str(raw_muxed), "-loglevel", "error",
        ],
        check=True,
    )

    final_out = resolve_path(cfg.get("output_path", f"renders/{slug}/{slug}_web_optimized.mp4"), persona_dir)
    normalize_video(raw_muxed, final_out)
    raw_muxed.unlink(missing_ok=True)
    for copy_target in cfg.get("mirror_outputs", []):
        dst = resolve_path(copy_target, persona_dir)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(final_out, dst)
    print(f"=== Completed: {final_out} ===")
    return final_out


def analyze_reference_reel(url_or_path: str, config_path: Path | None = None) -> str:
    try:
        from google import genai
        from google.genai import types
    except ModuleNotFoundError:
        venv_py = REPO_ROOT / ".venv/bin/python"
        if venv_py.exists() and Path(sys.executable) != venv_py:
            os.execv(str(venv_py), [str(venv_py), *sys.argv])
        raise

    load_env()
    cfg = resolve_creator_defaults({}, resolve_config_path(config_path)) if config_path else {}
    gcp_project = cfg.get("gcp_project") or os.environ.get("GOOGLE_CLOUD_PROJECT")
    gcp_location = cfg.get("gcp_location", "global")
    analysis_model = cfg.get("analysis_model", "gemini-3.8-flash")

    local_dir = PROJECT_DIR / "local"
    local_dir.mkdir(parents=True, exist_ok=True)
    p = Path(url_or_path)
    if p.exists():
        video_path = p
    else:
        reel_id = re.sub(r"[^a-zA-Z0-9_-]", "", url_or_path.rstrip("/").split("/")[-1]) or "sample"
        video_path = local_dir / f"ref_reel_{reel_id}.mp4"
        if not video_path.exists():
            subprocess.run(
                ["uv", "run", "yt-dlp", "-o", str(video_path), "--merge-output-format", "mp4", url_or_path],
                cwd=str(REPO_ROOT),
                check=True,
            )

    audio_mp3 = local_dir / f"{video_path.stem}_16k.mp3"
    if not audio_mp3.exists():
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(video_path), "-vn", "-ar", "16000", "-ac", "1", "-b:a", "64k", str(audio_mp3), "-loglevel", "error"],
            check=True,
        )

    client = genai.Client(enterprise=True, project=gcp_project, location=gcp_location)
    part = types.Part.from_bytes(data=audio_mp3.read_bytes(), mime_type="audio/mp3")
    prompt = (
        "Phân tích video/audio này để clone sang kịch bản UGC ngắn:\n"
        "1. Chép lại transcript chính xác.\n"
        "2. Tóm tắt chủ đề, nỗi đau (pain point), cấu trúc Hook - Body - Kết.\n"
        "3. Đề xuất các phân cảnh 10s (mỗi cảnh tổng 18-24 chữ tiếng Việt để tốc độ đọc 1.0x-1.15x)."
    )
    res = client.models.generate_content(model=analysis_model, contents=[part, prompt])
    print(res.text)
    return res.text


def run_self_check() -> None:
    cfg = resolve_creator_defaults({"slug": "test", "creator": "ngat", "camera": "cam", "environment": "env", "subject_first_scene": "s1", "subject_continuation": "s2"})
    assert cfg["face_image"] == "assets/images/face.jpg", cfg
    assert cfg["voice_id"] == "a95xm5oG7Gvnxoyv5jeJ", cfg
    assert resolve_config_path("ngat") == (PROJECT_DIR / "ngat/config.json").resolve()
    assert resolve_config_path("diep") == (PROJECT_DIR / "diep/config.json").resolve()
    sc = {"actions": ["act"], "clauses": ["sensitive text"]}
    p_safe = build_prompt(cfg, sc, is_first_scene=True, safe_fallback=True)
    assert "sensitive text" not in p_safe and "sự bình yên" in p_safe
    words = [("Câu", 0.0, 0.5), ("một.", 0.6, 1.2), ("Câu", 1.5, 2.0), ("hai.", 2.1, 2.8)]
    wins = partition_words_to_windows_dp(words, [(0.5, 1.8), (2.5, 4.0)])
    assert wins == [(0.0, 1.2, 0.5, 1.8), (1.5, 2.8, 2.5, 4.0)], wins
    assert resolve_resolution() == "360p"
    assert resolve_resolution("360") == "360p" and resolve_resolution("360p") == "360p"
    assert resolve_resolution("720") == "720p" and resolve_resolution("720p") == "720p"
    print("engine.py self_check passed.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Multi-Scene UGC Video Engine")
    parser.add_argument("config", nargs="?", type=Path, help="Path to scene config JSON")
    parser.add_argument(
        "--quality",
        "--resolution",
        dest="quality",
        choices=["360", "360p", "720", "720p"],
        default=None,
        help="Video generation quality for gemini-omni-1.1-flash-preview: 360p (default) or 720p",
    )
    parser.add_argument("--analyze-reel", type=str, help="Download and analyze reference reel URL or local MP4")
    parser.add_argument("--check", action="store_true", help="Run fast self-check")
    args = parser.parse_args()
    if args.check:
        run_self_check()
        return
    if args.analyze_reel:
        analyze_reference_reel(args.analyze_reel)
        return
    if not args.config:
        parser.error("Provide a config JSON path, --analyze-reel <URL>, or --check")
    out = run_pipeline(args.config, quality=args.quality)
    assert out.exists() and out.stat().st_size > 100_000, f"Output check failed: {out}"


if __name__ == "__main__":
    main()
