"""
effects/audio_mix.py
────────────────────
Multi-track audio sound design module.
Handles BGM ducking, fade in/out, timed SFX cue placement, and
broadcast loudness normalization (EBU R128 / -16 LUFS target).
"""

import math
from pathlib import Path
import random
import struct
from typing import Callable
import wave


def synthesize_sfx_wav(kind: str, out_path: Path, sample_rate: int = 44100) -> Path:
    """Synthesize a clean UI SFX WAV (pop, ding, or whoosh) using Python stdlib."""
    kind = kind.lower().strip()
    if kind == "ding":
        dur = 0.28
        n = int(sample_rate * dur)
        samples = [
            (0.55 * math.sin(2 * math.pi * 1046.5 * (i / sample_rate)) + 0.25 * math.sin(2 * math.pi * 1568.0 * (i / sample_rate)))
            * math.exp(-(i / sample_rate) * 11.0)
            for i in range(n)
        ]
    elif kind == "whoosh":
        dur = 0.22
        n = int(sample_rate * dur)
        rng = random.Random(42)
        samples = [
            rng.gauss(0.0, 0.25) * (math.sin(math.pi * (i / sample_rate) / dur) ** 1.5)
            for i in range(n)
        ]
    else:  # pop
        dur = 0.09
        n = int(sample_rate * dur)
        samples = []
        for i in range(n):
            t = i / sample_rate
            freq = 520.0 * math.exp(-t * 22.0) + 140.0
            samples.append(0.65 * math.sin(2 * math.pi * freq * t) * math.exp(-t * 32.0))

    pcm = b"".join(struct.pack("<h", max(-32768, min(32767, int(s * 32767.0)))) for s in samples)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm)
    return out_path


def apply_bgm(cfg: dict, ctx) -> None:
    """Add a background music bed with fade-in/fade-out to the audio mix."""
    bgm_file = ctx.resolve_path(cfg.get("file", "assets/zephiramusic-lofi-focus-606303.mp3"))
    if not bgm_file.exists():
        print(f"  [Warning] BGM file not found: {bgm_file}")
        return
    bgm_vol = float(cfg.get("volume", 0.08))
    fade_in = float(cfg.get("fade_in", 0.5))
    fade_out = float(cfg.get("fade_out", 1.5))
    in_idx = ctx.add_input(["-i", str(bgm_file)])
    lbl = ctx.next_a_label("bgm")
    ctx.a_filters.append(
        f"[{in_idx}:a]atrim=0:{ctx.duration:.3f},asetpts=PTS-STARTPTS,volume={bgm_vol:.3f},"
        f"afade=t=in:st=0:d={fade_in:.2f},afade=t=out:st={max(0.0, ctx.duration - fade_out):.2f}:d={fade_out:.2f}{lbl}"
    )
    ctx.a_mix_labels.append(lbl)


def apply_sfx(cfg: dict, ctx) -> None:
    """Add one or more timed SFX cues (file-based or synthesized pop/ding/whoosh) to the audio mix."""
    events = cfg.get("events") if "events" in cfg else [cfg]
    for ev in events:
        if "file" in ev:
            sfx_path = ctx.sfx_dir / ev["file"]
            if not sfx_path.exists():
                sfx_path = ctx.resolve_path(ev["file"])
            if not sfx_path.exists():
                print(f"  [Warning] SFX not found: {sfx_path}")
                continue
        else:
            kind = str(ev.get("sound", ev.get("kind", "pop"))).lower()
            if kind not in ctx.sfx_cache:
                ctx.sfx_cache[kind] = synthesize_sfx_wav(kind, ctx.work_dir / f"sfx_{kind}.wav")
            sfx_path = ctx.sfx_cache[kind]

        in_idx = ctx.add_input(["-i", str(sfx_path)])
        delay_ms = max(0, int(round(float(ev.get("time", 0.0)) * 1000)))
        vol = float(ev.get("volume", 0.35 if "file" not in ev else 0.5))
        lbl = ctx.next_a_label("sfx")
        ctx.a_filters.append(f"[{in_idx}:a]adelay={delay_ms}|{delay_ms},volume={vol:.3f}{lbl}")
        ctx.a_mix_labels.append(lbl)


def finalize_audio_graph(ctx, loudnorm: bool = True) -> str:
    """Assemble the complete FFmpeg audio filtergraph string ending at [aout]."""
    parts: list[str] = []
    if ctx.has_audio:
        parts.append("[0:a]aresample=44100[a_main]")
    else:
        parts.append(f"anullsrc=channel_layout=stereo:sample_rate=44100,atrim=0:{max(0.1, ctx.duration):.3f}[a_main]")

    parts.extend(ctx.a_filters)
    mix_sources = ["[a_main]", *ctx.a_mix_labels]

    if len(mix_sources) > 1:
        amix_out = "[a_mix]" if loudnorm else "[aout]"
        parts.append(f"{''.join(mix_sources)}amix=inputs={len(mix_sources)}:duration=first:normalize=0{amix_out}")
        a_cur = amix_out
    else:
        a_cur = "[a_main]"

    if loudnorm:
        parts.append(f"{a_cur}loudnorm=I=-16:TP=-1.5:LRA=11[aout]")
    elif a_cur != "[aout]":
        parts.append(f"{a_cur}anull[aout]")

    return ";".join(parts)


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
