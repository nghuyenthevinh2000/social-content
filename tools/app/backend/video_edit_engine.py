"""ACP + rea-video video edit engine."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
from typing import Optional
import uuid

from tools.app.backend.acp import ACPClient

WORKSPACE = Path(__file__).resolve().parents[3]
DEFAULT_REA_VIDEO_BIN = WORKSPACE / "local/aibrand/rea-video/.venv/bin/rea-video"
DOCKER_REA_VIDEO_BIN = WORKSPACE / "local/aibrand/rea-video/.venv-docker/bin/rea-video"
JSON_VIDEO_EDITOR = WORKSPACE / ".agents/skills/video-editing/scripts/video_engine/json_video_editor.py"
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


def _run_rea_decompose(video_path: Path, out_dir: Path, rea_bin: Path, timeout_sec: int = 240) -> bool:
    """Run fast rea-video decompose (--no-stems --no-speakers --no-vlm) and return True if VIDEO.md exists."""
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
) -> str:
    """Build the ACP prompt instructing the agent to use rea-video decompositions and apply edits."""
    rea_cmd = str(rea_video_bin or resolve_rea_video_bin() or "rea-video")
    lines = [
        "You are a fast, focused video editing agent.",
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
                f'  "{rea_cmd}" decompose "{ref_clip}" -o "{ref_out}" --lang en --no-stems --no-speakers --no-vlm',
                f"Read `{ref_out}/VIDEO.md` and `{ref_out}/breakdown.json` to extract the edit style.",
                "",
            ])

    user_out = work_dir / "user" / "out"
    if user_out_ready:
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

    rea_bin = rea_video_bin or resolve_rea_video_bin()
    editor_py = str(rea_bin.parent / "python") if rea_bin else "python3"
    edit_plan_path = work_dir / "edit_plan.json"
    lines.extend([
        "Step 3 — Apply the requested edits via `json_video_editor.py` (do NOT write custom Python rendering/PIL/SFX scripts from scratch):",
        f"User edit request: {prompt.strip()}",
        "",
        f"Write `{edit_plan_path}` with keys: `input_video` (`{source_video_path}`), `output_video` (`{output_path}`), `color_grade` (`contrast`, `saturation`, `brightness`, `gamma`), `punch_zooms` (`[{{start, end, scale}}]`), `cards` (`[{{type: 'hook'|'info'|'table', start, end, y, bg_color, text_color, lines/title+body+tag/headers+rows}}]`), `captions` (`{{style: {{color, outline_color, font_size, margin_v, uppercase, pop_in}}, items: [{{start, end, text}}]}}`), `sfx` (`[{{time, type: 'pop'|'ding'|'whoosh', volume}}]`).",
        f'Then run: `"{editor_py}" "{JSON_VIDEO_EDITOR}" "{edit_plan_path}"`',
        f"Do not overwrite `{source_video_path}`. Verify `{output_path}` exists with `ffprobe` and finish.",
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
    """Pre-decompose in parallel, then run ACP to apply requested edits to source_video_path."""
    from tools.app.backend.research_engine.research import configured_agent

    resolved_ref = extract_reference_url(prompt, reference_video_url)
    run_dir = work_dir or (REA_RUNS_ROOT / f"edit_{uuid.uuid4().hex[:10]}")
    run_dir.mkdir(parents=True, exist_ok=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    rea_bin = resolve_rea_video_bin()
    user_out_ready = False
    ref_out_dir: Optional[Path] = None

    if pre_decompose and rea_bin is not None:
        user_out = run_dir / "user" / "out"
        with ThreadPoolExecutor(max_workers=2) as pool:
            user_fut = pool.submit(_run_rea_decompose, source_video_path, user_out, rea_bin)
            ref_fut = pool.submit(_prepare_reference_decompose, resolved_ref, rea_bin) if resolved_ref else None
            try:
                user_out_ready = bool(user_fut.result())
            except Exception:
                user_out_ready = False
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
        user_out_ready=user_out_ready,
        ref_out_dir=ref_out_dir,
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
