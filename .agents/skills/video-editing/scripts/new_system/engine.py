#!/usr/bin/env python3
"""Unified Multi-Scene UGC Video Engine (Gemini Omni I2V Chaining + ElevenLabs eleven_v3 Auto-Sync + Seamless Seam Editor)."""

import argparse
import base64
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from match_lighting import DEFAULT_MODEL, compute_ml_scene_luts
from normalize_video import normalize_video
from synthesize_eleven_v3 import load_env, synthesize_eleven_v3
from track_lip_movement import compute_ml_lip_synced_bounds

_HERE = Path(__file__).resolve()
REPO_ROOT = next((p for p in _HERE.parents if (p / "projects/ugc-video").is_dir()), _HERE.parents[4])
PROJECT_DIR = REPO_ROOT / "projects/ugc-video"
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


def build_prompt(
    cfg: dict,
    scene: dict,
    is_first_scene: bool,
    safe_fallback: bool = False,
    ref_roles: list[str] | None = None,
) -> str:
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

    realism_keys = ("skin_texture", "lighting_prompt", "scale", "physics", "imperfection", "camera_look")
    realism_lines = [val for k in realism_keys if (val := scene.get(k) or cfg.get(k))]

    sections = []
    if ref_roles:
        sections.append("[REFERENCE MAPPING]\n" + "\n".join(ref_roles))
    sections.extend([
        f"[CAMERA & COMPOSITION]\n{cam}",
        f"[ENVIRONMENT & ATMOSPHERE]\n{env}",
        f"[SUBJECT & CONTINUITY]\n{subj}",
    ])
    if realism_lines:
        sections.append("[REALISM & PHYSICS]\n" + "\n".join(realism_lines))
    sections.extend([
        f"[ACTION & TIMECODE]\n{actions}",
        f"[AUDIO & DIALOGUE]\n{audio_desc}",
    ])
    return "\n\n".join(sections)


def resolve_resolution(val: str | int | None = None) -> str:
    s = str(val or "360p").strip().lower().removesuffix("p")
    if s not in ("360", "720"):
        raise ValueError(f"Unsupported quality/resolution '{val}'. Allowed: 360p, 720p.")
    return f"{s}p"


FIRST_SCENE_REF_SPECS = (
    ("face_image", "character face (identity only)"),
    ("clothes_image", "character clothing/outfit"),
    ("background_image", "empty location/background (keep scene layout and anchors)"),
    ("product_image", "product prop"),
    ("storyboard_frame", "approved storyboard frame (copy composition and subject scale in frame)"),
)


def resolve_scene_refs(cfg: dict, scene: dict, is_first_scene: bool, persona_dir: Path) -> tuple[list[Path], list[str]]:
    if not is_first_scene:
        return [], ["<IMAGE_REF_0> = exact ending frame of previous scene"]
    ref_paths, ref_roles = [], []
    for key, desc in FIRST_SCENE_REF_SPECS:
        val = scene.get(key) or cfg.get(key)
        if not val:
            continue
        ref_path = resolve_path(val, persona_dir)
        ref_roles.append(f"<IMAGE_REF_{len(ref_paths)}> = {desc} ({ref_path.name})")
        ref_paths.append(ref_path)
    return ref_paths, ref_roles


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
    client = genai.Client(enterprise=True, project=gcp_project, location=gcp_location)
    model = scene.get("video_model") or cfg["video_model"]
    aspect_ratio = scene.get("aspect_ratio") or cfg.get("aspect_ratio", "9:16")
    scene_duration = scene.get("duration") or cfg.get("scene_duration", "10s")
    resolution = resolve_resolution(
        quality or scene.get("quality") or scene.get("resolution") or cfg.get("quality") or cfg.get("resolution") or "360p"
    )
    persona_dir = Path(cfg.get("_persona_dir", PROJECT_DIR))
    ref_paths, ref_roles = resolve_scene_refs(cfg, scene, is_first_scene=(idx == 1), persona_dir=persona_dir)
    if idx == 1:
        inputs = [
            {
                "type": "image",
                "data": base64.b64encode(p.read_bytes()).decode("utf-8"),
                "mime_type": "image/png" if p.suffix.lower() == ".png" else "image/jpeg",
            }
            for p in ref_paths
        ]
        prompt = build_prompt(cfg, scene, is_first_scene=True, ref_roles=ref_roles)
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
        prompt = build_prompt(cfg, scene, is_first_scene=False, ref_roles=ref_roles)
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
            inputs[-1] = {
                "type": "text",
                "text": build_prompt(cfg, scene, is_first_scene=(idx == 1), safe_fallback=True, ref_roles=ref_roles),
            }
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


def resolve_clause_windows(
    scenes: list[dict], scene_videos: list[Path], align_path: Path
) -> list[tuple[float, float, float, float]]:
    resolved = []
    scene_offset = 0.0
    for scene, video_path in zip(scenes, scene_videos):
        raw_clauses = scene["clauses"]
        clause_texts = [c["text"] if isinstance(c, dict) else c for c in raw_clauses]
        assert all(isinstance(c, dict) and "window" in c for c in raw_clauses), (
            "resolve_clause_windows requires explicit 'window' on all clauses; use compute_ml_lip_synced_bounds()."
        )
        src_bounds = parse_tts_clause_bounds(align_path, clause_texts)
        local_windows = [(float(c["window"][0]), float(c["window"][1])) for c in raw_clauses]
        for (s_s, s_e), (loc_s, loc_e) in zip(src_bounds, local_windows):
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

    if any(isinstance(c, dict) and "window" in c for s in scenes for c in s["clauses"]):
        mapped_bounds = resolve_clause_windows(scenes, scene_videos, align_json)
    else:
        assert DEFAULT_MODEL.exists(), f"Missing MediaPipe face landmarker model: {DEFAULT_MODEL}"
        mapped_bounds, _ = compute_ml_lip_synced_bounds(cfg, scene_videos, raw_mp3, align_json, DEFAULT_MODEL)
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
        "2. Trả lời 4 câu hỏi cốt lõi của câu chuyện:\n"
        "   - Nhân vật muốn gì?\n"
        "   - Vì sao phải làm điều đó ngay bây giờ?\n"
        "   - Điều gì cản đường họ?\n"
        "   - Cái kết có trả lời được câu 'để làm gì?' không?\n"
        "3. Tóm tắt chủ đề, nỗi đau (pain point), cấu trúc Hook - Body - Kết.\n"
        "4. Đề xuất các phân cảnh 10s (mỗi cảnh tổng 18-24 chữ tiếng Việt để tốc độ đọc 1.0x-1.15x)."
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
    sc = {"actions": ["act"], "clauses": ["sensitive text"], "scale": "one quarter of frame height", "skin_texture": "visible pores"}
    p_safe = build_prompt(cfg, sc, is_first_scene=True, safe_fallback=True, ref_roles=["<IMAGE_REF_0> = character face"])
    assert "sensitive text" not in p_safe and "sự bình yên" in p_safe
    assert "[REFERENCE MAPPING]" in p_safe and "<IMAGE_REF_0> = character face" in p_safe
    assert "[REALISM & PHYSICS]" in p_safe and "visible pores" in p_safe
    assert "one quarter of frame height" in p_safe
    p_plain = build_prompt(cfg, {"actions": ["act"], "clauses": ["hi"]}, is_first_scene=True)
    assert "[REALISM & PHYSICS]" not in p_plain
    assert DEFAULT_MODEL.exists(), f"Missing MediaPipe model: {DEFAULT_MODEL}"
    assert callable(compute_ml_lip_synced_bounds)
    assert resolve_resolution() == "360p"
    assert resolve_resolution("360") == "360p" and resolve_resolution("360p") == "360p"
    assert resolve_resolution("720") == "720p" and resolve_resolution("720p") == "720p"
    print("engine.py self_check passed.")


def print_prompts(config_path: Path, quality: str | None = None) -> None:
    config_path = resolve_config_path(config_path)
    cfg = resolve_creator_defaults(json.loads(config_path.read_text(encoding="utf-8")), config_path)
    persona_dir = Path(cfg["_persona_dir"])
    for idx, scene in enumerate(cfg["scenes"], start=1):
        model = scene.get("video_model") or cfg["video_model"]
        dur = scene.get("duration") or cfg.get("scene_duration", "10s")
        res = resolve_resolution(quality or scene.get("quality") or cfg.get("quality") or "360p")
        _, ref_roles = resolve_scene_refs(cfg, scene, is_first_scene=(idx == 1), persona_dir=persona_dir)
        print(f"=== Scene {idx} ({model}, {dur}, {res}) ===")
        print(build_prompt(cfg, scene, is_first_scene=(idx == 1), ref_roles=ref_roles))
        print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Multi-Scene UGC Video Engine")
    parser.add_argument("config", nargs="?", type=Path, help="Path to scene config JSON")
    parser.add_argument(
        "--quality",
        "--resolution",
        dest="quality",
        choices=["360", "360p", "720", "720p"],
        default=None,
        help="Video generation quality/resolution: 360p (default) or 720p",
    )
    parser.add_argument("--analyze-reel", type=str, help="Download and analyze reference reel URL or local MP4")
    parser.add_argument("--print-prompt", "--dry-run", action="store_true", help="Print resolved scene prompts without generating video")
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
    if args.print_prompt:
        print_prompts(args.config, quality=args.quality)
        return
    out = run_pipeline(args.config, quality=args.quality)
    assert out.exists() and out.stat().st_size > 100_000, f"Output check failed: {out}"


if __name__ == "__main__":
    main()
