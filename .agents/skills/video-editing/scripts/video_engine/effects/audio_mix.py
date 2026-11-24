"""
effects/audio_mix.py
────────────────────
Multi-track audio sound design module.
Handles BGM ducking, fade in/out, timed SFX cue placement, and
broadcast loudness normalization (EBU R128 / -16 LUFS target).
"""

from pathlib import Path
from typing import Callable


def build_audio_graph(
    bgm_cfg: dict | None,
    sfx_events: list[dict],
    sfx_dir: Path,
    total_dur: float,
    input_stream_start_idx: int,
    resolve_path_fn: Callable[[str | Path], Path],
) -> tuple[list[str], str, int]:
    """
    Build FFmpeg audio inputs and filtergraph.

    Returns:
        (extra_ffmpeg_inputs, full_a_filter_string, next_stream_idx)
    """
    extra_inputs: list[str] = []
    a_filters: list[str] = []
    mix_sources: list[str] = ["[0:a]"]
    stream_idx = input_stream_start_idx

    # 1. BGM bed
    if bgm_cfg and bgm_cfg.get("enabled", True):
        bgm_file = resolve_path_fn(bgm_cfg.get("file", "assets/zephiramusic-lofi-focus-606303.mp3"))
        if bgm_file.exists():
            bgm_vol = float(bgm_cfg.get("volume", 0.08))
            fade_in = float(bgm_cfg.get("fade_in", 0.5))
            fade_out = float(bgm_cfg.get("fade_out", 1.5))
            extra_inputs.extend(["-i", str(bgm_file)])
            a_filters.append(
                f"[{stream_idx}:a]atrim=0:{total_dur:.3f},asetpts=PTS-STARTPTS,volume={bgm_vol:.3f},"
                f"afade=t=in:st=0:d={fade_in:.2f},afade=t=out:st={total_dur - fade_out:.2f}:d={fade_out:.2f}[bgm]"
            )
            mix_sources.append("[bgm]")
            stream_idx += 1
        else:
            print(f"  [Warning] BGM file not found: {bgm_file}")

    # 2. SFX timed cues
    for ev in sfx_events:
        sfx_path = sfx_dir / ev["file"]
        if not sfx_path.exists():
            print(f"  [Warning] SFX not found: {sfx_path.name}")
            continue
        extra_inputs.extend(["-i", str(sfx_path)])
        lbl = f"[sfx_{stream_idx}]"
        delay_ms = int(round(float(ev["time"]) * 1000))
        vol = float(ev.get("volume", 0.5))
        a_filters.append(f"[{stream_idx}:a]volume={vol:.2f},adelay={delay_ms}|{delay_ms}{lbl}")
        mix_sources.append(lbl)
        stream_idx += 1

    total_mix = len(mix_sources)
    mix_in_str = "".join(mix_sources)
    a_filters.append(
        f"{mix_in_str}amix=inputs={total_mix}:duration=first:dropout_transition=0,"
        f"loudnorm=I=-16:TP=-1.5:LRA=11[aout]"
    )
    full_a_filter = ";".join(a_filters)
    return extra_inputs, full_a_filter, stream_idx
