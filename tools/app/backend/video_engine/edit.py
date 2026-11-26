"""ACP + rea-video video edit engine."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Optional
import uuid

from tools.app.backend.acp import ACPClient

WORKSPACE = Path(__file__).resolve().parents[4]
DEFAULT_REA_VIDEO_BIN = WORKSPACE / "local/aibrand/rea-video/.venv/bin/rea-video"
DOCKER_REA_VIDEO_BIN = WORKSPACE / "local/aibrand/rea-video/.venv-docker/bin/rea-video"
DEFAULT_VENV_PYTHON = WORKSPACE / ".venv/bin/python"
EFFECT_EDITOR = WORKSPACE / ".agents/skills/video-editing/scripts/video_engine/effect_editor.py"
REFERENCE_EDIT_WORKFLOW = WORKSPACE / ".agents/skills/video-editing/workflows/reference-edit-replication.md"
REA_RUNS_ROOT = WORKSPACE / "local/aibrand/rea-video-runs"
REF_CACHE_ROOT = REA_RUNS_ROOT / "ref-cache"
_URL_RE = re.compile(r"https?://[^\s<>\"']+")


def extract_reference_url(prompt: str, explicit_url: Optional[str] = None) -> Optional[str]:
    """Return explicit reference URL or the first HTTP(S) URL in the prompt."""
    if explicit_url and explicit_url.strip():
        return explicit_url.strip()
    match = _URL_RE.search(prompt or "")
    return match.group(0).rstrip(".,);]") if match else None


def resolve_rea_video_bin() -> Optional[Path]:
    """Locate the rea-video CLI binary in local/aibrand/rea-video/.venv-docker (in Docker), .venv, or PATH."""
    if Path("/.dockerenv").exists() and DOCKER_REA_VIDEO_BIN.exists():
        return DOCKER_REA_VIDEO_BIN
    if DEFAULT_REA_VIDEO_BIN.exists():
        return DEFAULT_REA_VIDEO_BIN
    found = shutil.which("rea-video")
    return Path(found) if found else None


def ref_cache_dir(url: str, cache_root: Path = REF_CACHE_ROOT) -> Path:
    """Return deterministic cache directory for a reference video URL."""
    digest = hashlib.sha1(url.strip().encode("utf-8")).hexdigest()[:16]
    return cache_root / digest


def _resolve_editor_python(rea_video_bin: Optional[Path] = None) -> str:
    """Resolve the Python interpreter for effect_editor.py and faster_whisper."""
    if rea_video_bin is not None:
        cand = rea_video_bin.parent / "python"
        if cand.exists():
            return str(cand)
    if DEFAULT_VENV_PYTHON.exists():
        return str(DEFAULT_VENV_PYTHON)
    return sys.executable


def _prepare_user_source(
    source_video_path: Path,
    work_dir: Path,
    py_bin: Optional[str] = None,
) -> Optional[dict]:
    """Fast-probe user video, extract 3 JPG keyframes, and transcribe speech with faster_whisper."""
    ffprobe_bin = shutil.which("ffprobe") or "ffprobe"
    try:
        probe_res = subprocess.run(
            [
                ffprobe_bin,
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                "-show_streams",
                str(source_video_path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
        raw_probe = json.loads(probe_res.stdout)
    except Exception:
        return None

    streams = raw_probe.get("streams", [])
    v_stream = next((s for s in streams if s.get("codec_type") == "video"), {})
    has_audio = any(s.get("codec_type") == "audio" for s in streams)
    duration = float(raw_probe.get("format", {}).get("duration") or v_stream.get("duration") or 0.0)
    fps_raw = str(v_stream.get("r_frame_rate") or "24/1")
    if "/" in fps_raw:
        num, den = fps_raw.split("/", 1)
        fps = round(float(num) / max(1.0, float(den)), 2)
    else:
        fps = float(fps_raw)

    probe_summary = {
        "width": int(v_stream.get("width", 720)),
        "height": int(v_stream.get("height", 1280)),
        "duration": round(duration, 2),
        "fps": fps,
        "has_audio": has_audio,
    }
    work_dir.mkdir(parents=True, exist_ok=True)
    probe_path = work_dir / "user_probe.json"
    probe_path.write_text(json.dumps(probe_summary, indent=2), encoding="utf-8")

    frames_dir = work_dir / "user_frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    ffmpeg_bin = shutil.which("ffmpeg") or "ffmpeg"
    for idx, frac in enumerate((0.15, 0.50, 0.85)):
        ts = max(0.0, round(duration * frac, 2))
        subprocess.run(
            [
                ffmpeg_bin, "-y", "-v", "error",
                "-ss", f"{ts:.2f}",
                "-i", str(source_video_path),
                "-vframes", "1",
                str(frames_dir / f"f_{idx}.jpg"),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

    transcript_path: Optional[Path] = None
    if has_audio and py_bin:
        cand_transcript = work_dir / "user_transcript.json"
        whisper_script = (
            "import json, sys\n"
            "from faster_whisper import WhisperModel\n"
            "m = WhisperModel('small', device='cpu', compute_type='int8')\n"
            "segs, info = m.transcribe(sys.argv[1], word_timestamps=True)\n"
            "out = {'language': info.language, 'segments': [\n"
            "  {'start': round(s.start, 2), 'end': round(s.end, 2), 'text': s.text.strip(),\n"
            "   'words': [{'start': round(w.start, 2), 'end': round(w.end, 2), 'word': w.word} for w in (s.words or [])]}\n"
            "  for s in segs\n"
            "]}\n"
            "open(sys.argv[2], 'w', encoding='utf-8').write(json.dumps(out, ensure_ascii=False, indent=2))\n"
        )
        try:
            res = subprocess.run(
                [py_bin, "-c", whisper_script, str(source_video_path), str(cand_transcript)],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if res.returncode == 0 and cand_transcript.exists():
                transcript_path = cand_transcript
        except Exception:
            transcript_path = None

    return {
        "probe_path": probe_path,
        "probe": probe_summary,
        "frames_dir": frames_dir,
        "transcript_path": transcript_path,
    }


def _run_rea_decompose(video_path: Path, out_dir: Path, rea_bin: Path, timeout_sec: int = 240) -> bool:
    """Run fast rea-video decompose (--no-stems --no-speakers --no-vlm --no-asr) and return True if VIDEO.md exists."""
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        str(rea_bin),
        "decompose",
        str(video_path),
        "-o",
        str(out_dir),
        "--lang",
        "en",
        "--no-stems",
        "--no-speakers",
        "--no-vlm",
        "--no-asr",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_sec)
    return res.returncode == 0 and (out_dir / "VIDEO.md").exists()


def _prepare_reference_decompose(
    reference_video_url: str,
    rea_bin: Path,
    cache_root: Path = REF_CACHE_ROOT,
) -> Optional[Path]:
    """Download, trim to 25s, and decompose reference video with URL-hash caching."""
    cache_dir = ref_cache_dir(reference_video_url, cache_root)
    out_dir = cache_dir / "out"
    if (out_dir / "VIDEO.md").exists() and (out_dir / "breakdown.json").exists():
        return out_dir

    cache_dir.mkdir(parents=True, exist_ok=True)
    ref_mp4 = cache_dir / "source.mp4"
    ref_clip = cache_dir / "clip_25s.mp4"

    yt_dlp_bin = shutil.which("yt-dlp") or "yt-dlp"
    dl = subprocess.run(
        [
            yt_dlp_bin,
            "-o",
            str(ref_mp4),
            "-f",
            "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "--merge-output-format",
            "mp4",
            reference_video_url,
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if dl.returncode != 0 or not ref_mp4.exists():
        try:
            from tools.loop.viral_analyzer.video_research.collect import download_video_stream

            if not download_video_stream(reference_video_url, ref_mp4, is_reel_page=True):
                return None
        except Exception:
            return None

    ffmpeg_bin = shutil.which("ffmpeg") or "ffmpeg"
    trim = subprocess.run(
        [ffmpeg_bin, "-y", "-i", str(ref_mp4), "-t", "25", "-c", "copy", str(ref_clip)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    target = ref_clip if trim.returncode == 0 and ref_clip.exists() else ref_mp4
    if _run_rea_decompose(target, out_dir, rea_bin):
        return out_dir
    return None


def build_video_edit_acp_prompt(
    source_video_path: Path,
    output_path: Path,
    prompt: str,
    work_dir: Path,
    reference_video_url: Optional[str] = None,
    rea_video_bin: Optional[Path] = None,
    user_out_ready: bool = False,
    ref_out_dir: Optional[Path] = None,
    user_prep: Optional[dict] = None,
) -> str:
    """Build the ACP prompt instructing the agent to use pre-computed metadata and apply edits."""
    rea_cmd = str(rea_video_bin or resolve_rea_video_bin() or "rea-video")
    lines = [
        "You are a fast, focused video editing agent.",
        f"Read and follow the workflow at `{REFERENCE_EDIT_WORKFLOW}` end-to-end.",
        "",
        f"User source video: `{source_video_path}`",
        f"Target output MP4: `{output_path}`",
        f"Working directory: `{work_dir}`",
        "",
    ]

    if reference_video_url:
        if ref_out_dir is not None:
            lines.extend([
                f"Reference video ({reference_video_url}) is ALREADY decomposed at `{ref_out_dir}`.",
                f"Step 1 — Read `{ref_out_dir}/VIDEO.md` and `{ref_out_dir}/breakdown.json` (and `{ref_out_dir}/packaging/` if present) to extract the edit style (cuts, pacing, captions, hook card, zoom, color grade). Do NOT re-download or re-run `rea-video` on the reference video.",
                "",
            ])
        else:
            cache_dir = ref_cache_dir(reference_video_url)
            ref_mp4 = cache_dir / "source.mp4"
            ref_clip = cache_dir / "clip_25s.mp4"
            ref_out = cache_dir / "out"
            lines.extend([
                f"Reference video to copy edit style from: {reference_video_url}",
                "Step 1 — Download, trim to 25s, and reverse-engineer the reference video into the shared cache (fast mode):",
                f'  yt-dlp -o "{ref_mp4}" -f "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best" --merge-output-format mp4 "{reference_video_url}"',
                f'  ffmpeg -y -i "{ref_mp4}" -t 25 -c copy "{ref_clip}"',
                f'  "{rea_cmd}" decompose "{ref_clip}" -o "{ref_out}" --lang en --no-stems --no-speakers --no-vlm --no-asr',
                f"Read `{ref_out}/VIDEO.md` and `{ref_out}/breakdown.json` to extract the edit style.",
                "",
            ])

    user_out = work_dir / "user" / "out"
    if user_prep is not None:
        probe = user_prep.get("probe") or {}
        frames_dir = user_prep.get("frames_dir")
        transcript_path = user_prep.get("transcript_path")
        lines.extend([
            "User source video is ALREADY pre-analyzed:",
            f"  - Dimensions: {probe.get('width')}x{probe.get('height')}, {probe.get('fps')} fps, {probe.get('duration')}s, has_audio={probe.get('has_audio')}",
            f"  - Sample keyframes: `{frames_dir}` (`f_0.jpg`, `f_1.jpg`, `f_2.jpg`)",
            f"  - Speech transcript: `{transcript_path}`" if transcript_path else "  - Speech transcript: none (no audio or skipped)",
            "Step 2 — Inspect the sample keyframes and read the transcript JSON to align edits with speech and safe zones. Do NOT re-run `rea-video`, `ffprobe`, WAV extraction, or `faster_whisper` on the user source video.",
            "",
        ])
    elif user_out_ready:
        lines.extend([
            f"User source video is ALREADY decomposed at `{user_out}`.",
            f"Step 2 — Read `{user_out}/VIDEO.md` and `{user_out}/breakdown.json` to align edits with speech/shot boundaries. Do NOT re-run `rea-video` or extract extra inspection frames.",
            "",
        ])
    else:
        lines.extend([
            "Step 2 — Decompose the user's source video to determine exact timestamps and placement for edits:",
            f'  "{rea_cmd}" decompose "{source_video_path}" -o "{user_out}" --lang en --no-stems --no-speakers --no-vlm',
            f"Inspect `{user_out}/VIDEO.md` and `{user_out}/breakdown.json` to align edits cleanly with speech/shot boundaries. Do not run extra manual frame-extraction loops.",
            "",
        ])

    editor_py = _resolve_editor_python(rea_video_bin or resolve_rea_video_bin())
    edit_config_path = work_dir / "edit_config.json"
    effects_dir = EFFECT_EDITOR.parent / "effects"
    lines.extend([
        "Step 3 — Follow the JSON-first workflow in `reference-edit-replication.md` (do NOT write one-off render scripts):",
        f"User edit request: {prompt.strip()}",
        "",
        "Compact `EFFECT_REGISTRY` schema (only read `effects/*.py` if a requested effect is not covered below):",
        '- `punch_zoom`: `{"type": "punch_zoom", "windows": [{"start", "end", "scale", "y_focus"}]}`',
        '- `transition`: `{"type": "transition", "kind": "fade_in"|"fade_out"|"flash", "start"|"time", "duration", "color"}`',
        '- `color_grade`: `{"type": "color_grade", "contrast", "saturation", "brightness", "gamma"}`',
        '- `text_box`: `{"type": "text_box", "variant": "hook"|"box"|"highlight_lines"|"info"|"table", "x", "y", "width", "height", "start", "end", "fade_in", "fade_out", "bg_color", "bg_alpha", "text_color", "font", "font_size", "stroke_width", "stroke_color", "outer_stroke_width", "outer_stroke_color", "glow_radius", "brackets", "accent_bar_color", "align", "radius", "lines"}`',
        '- `subtitles`: `{"type": "subtitles", "items": [{"start", "end", "text"}], "font_size", "margin_v", "pop_in"}`',
        '- `sfx` / `bgm`: `{"type": "sfx", "time", "sound": "pop"|"ding"|"whoosh"}`, `{"type": "bgm", "path", "volume"}`',
        "",
        "1-pass safe-zone & verification guardrails:",
        "- Portrait `720x1280` safe zones: top overlays `y=110..220`, lower-third captions/cards `y=780..1040` (strictly above `y=1100` platform UI), lateral margins `x>=52`, `max_width<=620`.",
        f'- Only if an effect or option is missing above, extend `{effects_dir}/*.py` and run `"{editor_py}" "{EFFECT_EDITOR}" --check`.',
        f"- Write `{edit_config_path}` with `input_video` (`{source_video_path}`), `output_video` (`{output_path}`), `width: 720`, `height: 1280`, `fps: 24`, `loudnorm: true`, and `effects`.",
        f'- Render, probe, and extract 3–4 representative JPG keyframes in ONE chained command: `"{editor_py}" "{EFFECT_EDITOR}" "{edit_config_path}" && ffprobe ... "{output_path}" && ffmpeg ...`',
        f"- Inspect those 3–4 keyframes; aim for 1-pass completion and only re-render if a keyframe shows clipping, face/hand overlap, or broken diacritics. Never overwrite `{source_video_path}`.",
    ])
    return "\n".join(lines)


def edit_video(
    source_video_path: Path,
    prompt: str,
    output_path: Path,
    reference_video_url: Optional[str] = None,
    work_dir: Optional[Path] = None,
    timeout_sec: Optional[float] = None,
    pre_decompose: bool = True,
) -> Path:
    """Fast-prepare user source and reference in parallel, then run ACP to apply edits."""
    from tools.app.backend.research_engine.research import configured_agent

    resolved_ref = extract_reference_url(prompt, reference_video_url)
    run_dir = work_dir or (REA_RUNS_ROOT / f"edit_{uuid.uuid4().hex[:10]}")
    run_dir.mkdir(parents=True, exist_ok=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    rea_bin = resolve_rea_video_bin()
    editor_py = _resolve_editor_python(rea_bin)
    user_prep: Optional[dict] = None
    ref_out_dir: Optional[Path] = None

    if pre_decompose:
        with ThreadPoolExecutor(max_workers=2) as pool:
            user_fut = pool.submit(_prepare_user_source, source_video_path, run_dir, editor_py)
            ref_fut = (
                pool.submit(_prepare_reference_decompose, resolved_ref, rea_bin)
                if (resolved_ref and rea_bin is not None)
                else None
            )
            try:
                user_prep = user_fut.result()
            except Exception:
                user_prep = None
            if ref_fut is not None:
                try:
                    ref_out_dir = ref_fut.result()
                except Exception:
                    ref_out_dir = None

    acp_prompt = build_video_edit_acp_prompt(
        source_video_path=source_video_path,
        output_path=output_path,
        prompt=prompt,
        work_dir=run_dir,
        reference_video_url=resolved_ref,
        rea_video_bin=rea_bin,
        user_out_ready=False,
        ref_out_dir=ref_out_dir,
        user_prep=user_prep,
    )

    agent = configured_agent()
    effective_timeout = timeout_sec if timeout_sec is not None else float(os.environ.get("VIDEO_EDIT_ACP_TIMEOUT", "600"))
    client = ACPClient(agent["command"], cwd=WORKSPACE, timeout_sec=effective_timeout)
    try:
        client.initialize()
        session_id = client.new_session()
        client.prompt(session_id, acp_prompt)
    finally:
        client.close()

    if not output_path.exists() or output_path.stat().st_size == 0:
        raise RuntimeError(f"Video edit did not produce output file at {output_path}")
    return output_path
