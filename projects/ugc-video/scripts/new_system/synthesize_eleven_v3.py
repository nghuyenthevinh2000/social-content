#!/usr/bin/env python3
"""ElevenLabs eleven_v3 timestamp-aligned TTS synthesis using official elevenlabs-python SDK."""

import argparse
import base64
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
PROJECT_DIR = Path(__file__).resolve().parents[2]

try:
    from elevenlabs import VoiceSettings
    from elevenlabs.client import ElevenLabs
except ModuleNotFoundError:
    venv_py = REPO_ROOT / ".venv/bin/python"
    if venv_py.exists() and Path(sys.executable) != venv_py:
        os.execv(str(venv_py), [str(venv_py), *sys.argv])
    raise


def load_env() -> None:
    for env_path in (REPO_ROOT / ".env", PROJECT_DIR / ".env"):
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip("'\""))


def synthesize_eleven_v3(
    voice_id: str, clauses: list[str], work_dir: Path, cfg: dict | None = None
) -> tuple[Path, Path]:
    cfg = cfg or {}
    work_dir = Path(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    raw_mp3 = work_dir / "tts_v3_raw.mp3"
    align_json = work_dir / "tts_v3_alignment.json"
    full_text = " ".join(clauses).strip()

    if raw_mp3.exists() and align_json.exists():
        cached_str = "".join(json.loads(align_json.read_text(encoding="utf-8")).get("characters", []))
        if cached_str.strip() == full_text:
            print(f"  [Voice] Reusing cached eleven_v3 track: {raw_mp3.name}")
            return raw_mp3, align_json

    load_env()
    api_key = os.environ.get("ELEVENLABS_API_KEY")
    assert api_key, "Missing ELEVENLABS_API_KEY in environment or .env"

    vs = cfg.get("voice_settings", {})
    tts_model = cfg.get("tts_model", "eleven_v3")
    out_fmt = cfg.get("tts_output_format", "mp3_44100_128")
    print(f"  [Voice] Synthesizing single-pass {tts_model} TTS for {len(clauses)} clauses (Voice ID: {voice_id})...")
    client = ElevenLabs(api_key=api_key)
    res = client.text_to_speech.convert_with_timestamps(
        voice_id=voice_id,
        text=full_text,
        model_id=tts_model,
        output_format=out_fmt,
        voice_settings=VoiceSettings(
            stability=float(vs.get("stability", 0.5)),
            similarity_boost=float(vs.get("similarity_boost", 0.85)),
            style=float(vs.get("style", 0.0)),
            use_speaker_boost=bool(vs.get("use_speaker_boost", True)),
        ),
    )

    raw_mp3.write_bytes(base64.b64decode(res.audio_base_64))
    align = res.alignment or res.normalized_alignment
    assert align is not None, "ElevenLabs returned no character alignment data"
    alignment_payload = {
        "characters": list(align.characters),
        "characterStartTimesSeconds": list(align.character_start_times_seconds),
        "characterEndTimesSeconds": list(align.character_end_times_seconds),
    }
    align_json.write_text(json.dumps(alignment_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return raw_mp3, align_json


def run_self_check() -> None:
    load_env()
    client = ElevenLabs(api_key=os.environ.get("ELEVENLABS_API_KEY", "test_key"))
    assert hasattr(client.text_to_speech, "convert_with_timestamps")
    settings = VoiceSettings(stability=0.5, similarity_boost=0.85, style=0.0, use_speaker_boost=True)
    assert settings.stability == 0.5 and settings.similarity_boost == 0.85
    print("synthesize_eleven_v3.py self_check passed.")


def main() -> None:
    parser = argparse.ArgumentParser(description="ElevenLabs eleven_v3 TTS with timestamps")
    parser.add_argument("--config", type=Path, default=None, help="Path to persona/render config JSON")
    parser.add_argument("--voice-id", default=None, help="ElevenLabs Voice ID (overrides config)")
    parser.add_argument("--text", help="Text to synthesize")
    parser.add_argument("--work-dir", type=Path, default=Path("."), help="Output directory")
    parser.add_argument("--check", action="store_true", help="Run fast self-check")
    args = parser.parse_args()
    if args.check:
        run_self_check()
        return
    cfg = json.loads(args.config.read_text(encoding="utf-8")) if args.config else {}
    voice_id = args.voice_id or cfg.get("voice_id")
    if not args.text or not voice_id:
        parser.error("Provide --text and either --voice-id or --config <persona/config.json>, or --check")
    mp3_path, json_path = synthesize_eleven_v3(voice_id, [args.text], args.work_dir, cfg=cfg)
    print(f"Saved: {mp3_path} and {json_path}")


if __name__ == "__main__":
    main()
