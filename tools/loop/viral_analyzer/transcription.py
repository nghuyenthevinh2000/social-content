"""Unified AI Transcription engine for viral reels.

Integrates Qwen3-ASR via Apple Silicon MLX Metal acceleration (fastest, high-fidelity
Vietnamese tone recognition) with a fallback to faster-whisper.
"""

from pathlib import Path
import subprocess
from typing import Any, Dict, List, Optional

FFMPEG_BIN = "/opt/homebrew/bin/ffmpeg"


def extract_audio_ffmpeg(
    video_path: Path,
    audio_path: Path,
    max_duration_sec: int = 180,
    sample_rate: int = 16000,
) -> bool:
    """Extract lightweight mono WAV audio capped at max_duration_sec."""
    ffmpeg_cmd = FFMPEG_BIN if Path(FFMPEG_BIN).exists() else "ffmpeg"
    cmd = [
        ffmpeg_cmd,
        "-y",
        "-i", str(video_path),
        "-vn",
        "-ar", str(sample_rate),
        "-ac", "1",
        "-t", str(max_duration_sec),
        str(audio_path),
    ]
    proc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return proc.returncode == 0 and audio_path.exists() and audio_path.stat().st_size > 100


class UnifiedTranscriber:
    """AI Speech-to-Text Transcriber supporting Qwen3-ASR (MLX Metal) and Whisper."""

    def __init__(
        self,
        engine: str = "qwen3",
        model_name: str = "Qwen/Qwen3-ASR-0.6B",
        language: Optional[str] = None,
    ):
        self.engine = engine
        self.model_name = model_name
        self.language = language
        self._model = None
        self._load_engine()

    def _load_engine(self) -> None:
        if self.engine == "qwen3":
            try:
                import mlx_qwen3_asr
                self._model, _ = mlx_qwen3_asr.load_model(self.model_name)
                return
            except Exception as e:
                print(f"[!] Warning: failed to load mlx_qwen3_asr ({e}); falling back to faster-whisper.")
                self.engine = "whisper"
                self.model_name = "base"

        from faster_whisper import WhisperModel
        self._model = WhisperModel(self.model_name or "base", device="cpu", compute_type="int8")

    def transcribe_audio(self, audio_path: Path) -> Dict[str, Any]:
        """Transcribe an audio file and return text with segment timestamps."""
        if self.engine == "qwen3":
            import mlx_qwen3_asr
            res = mlx_qwen3_asr.transcribe(
                str(audio_path),
                model=self._model,
                language=self.language,
                return_chunks=True,
            )
            segments: List[Dict[str, Any]] = []
            if hasattr(res, "chunks") and res.chunks:
                for c in res.chunks:
                    segments.append({
                        "start": round(getattr(c, "start", 0.0), 2),
                        "end": round(getattr(c, "end", 0.0), 2),
                        "text": getattr(c, "text", "").strip(),
                    })
            elif hasattr(res, "segments") and res.segments:
                for s in res.segments:
                    segments.append({
                        "start": round(getattr(s, "start", 0.0), 2),
                        "end": round(getattr(s, "end", 0.0), 2),
                        "text": getattr(s, "text", "").strip(),
                    })

            return {
                "engine": f"qwen3-asr ({self.model_name})",
                "language": getattr(res, "language", self.language or "Vietnamese"),
                "transcript": getattr(res, "text", "").strip(),
                "segments": segments,
            }
        else:
            segments_iter, info = self._model.transcribe(
                str(audio_path),
                language="vi" if not self.language else self.language,
                beam_size=3,
                vad_filter=True,
            )
            seg_list = []
            parts = []
            for s in segments_iter:
                text = s.text.strip()
                if text:
                    parts.append(text)
                    seg_list.append({
                        "start": round(s.start, 2),
                        "end": round(s.end, 2),
                        "text": text,
                    })

            return {
                "engine": f"faster-whisper ({self.model_name})",
                "language": info.language,
                "transcript": " ".join(parts),
                "segments": seg_list,
            }
