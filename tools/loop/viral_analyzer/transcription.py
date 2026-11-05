"""Unified AI Transcription engine for viral reels.

Qwen3-ASR backends:
- macOS Apple Silicon: mlx-qwen3-asr (Metal GPU, fastest).
- Windows/Linux: transformers Qwen3-ASR (CPU or CUDA).
- Last resort: faster-whisper when installed.
"""

from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional

FFMPEG_BIN = "/opt/homebrew/bin/ffmpeg"


def ffmpeg_bin() -> str:
    if Path(FFMPEG_BIN).exists():
        return FFMPEG_BIN
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def extract_audio_ffmpeg(
    video_path: Path,
    audio_path: Path,
    max_duration_sec: int = 180,
    sample_rate: int = 16000,
) -> bool:
    """Extract lightweight mono WAV audio capped at max_duration_sec."""
    cmd = [
        ffmpeg_bin(),
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
    """AI Speech-to-Text Transcriber supporting Qwen3-ASR and Whisper fallback."""

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
        self._processor = None
        self._load_engine()

    def _load_engine(self) -> None:
        if self.engine == "qwen3":
            if sys.platform == "darwin":
                try:
                    import mlx_qwen3_asr

                    self._model, _ = mlx_qwen3_asr.load_model(self.model_name)
                    self.engine = "qwen3-mlx"
                    return
                except Exception as exc:
                    print(f"[!] mlx-qwen3-asr unavailable ({exc}); trying transformers Qwen3-ASR.")

            try:
                self._load_qwen3_transformers()
                return
            except Exception as exc:
                print(f"[!] transformers Qwen3-ASR unavailable ({exc}); falling back to faster-whisper.")

            self.engine = "whisper"
            self.model_name = "base"

        from faster_whisper import WhisperModel

        self._model = WhisperModel(self.model_name or "base", device="cpu", compute_type="int8")

    def _load_qwen3_transformers(self) -> None:
        import torch
        from transformers import AutoModelForMultimodalLM, AutoProcessor

        model_id = self.model_name
        if not model_id.endswith("-hf"):
            model_id = "Qwen/Qwen3-ASR-0.6B-hf"
        self._processor = AutoProcessor.from_pretrained(model_id)
        device = "cuda:0" if torch.cuda.is_available() else "cpu"
        dtype = torch.bfloat16 if device != "cpu" else torch.float32
        self._model = AutoModelForMultimodalLM.from_pretrained(
            model_id,
            device_map=device,
            dtype=dtype,
        )
        self.model_name = model_id
        self.engine = "qwen3-transformers"

    def _transcribe_mlx(self, audio_path: Path) -> Dict[str, Any]:
        import mlx_qwen3_asr

        res = mlx_qwen3_asr.transcribe(
            str(audio_path),
            model=self._model,
            language=self.language,
            return_chunks=True,
        )
        segments: List[Dict[str, Any]] = []
        if hasattr(res, "chunks") and res.chunks:
            for chunk in res.chunks:
                segments.append({
                    "start": round(getattr(chunk, "start", 0.0), 2),
                    "end": round(getattr(chunk, "end", 0.0), 2),
                    "text": getattr(chunk, "text", "").strip(),
                })
        elif hasattr(res, "segments") and res.segments:
            for segment in res.segments:
                segments.append({
                    "start": round(getattr(segment, "start", 0.0), 2),
                    "end": round(getattr(segment, "end", 0.0), 2),
                    "text": getattr(segment, "text", "").strip(),
                })

        return {
            "engine": f"qwen3-asr-mlx ({self.model_name})",
            "language": getattr(res, "language", self.language or "Vietnamese"),
            "transcript": getattr(res, "text", "").strip(),
            "segments": segments,
        }

    def _transcribe_transformers(self, audio_path: Path) -> Dict[str, Any]:
        inputs = self._processor.apply_transcription_request(audio=str(audio_path))
        inputs = inputs.to(self._model.device, self._model.dtype)
        output_ids = self._model.generate(**inputs, max_new_tokens=512)
        generated = output_ids[:, inputs["input_ids"].shape[1]:]
        parsed = self._processor.decode(generated, return_format="parsed")[0]
        if isinstance(parsed, dict):
            text = parsed.get("transcription", "")
            language = parsed.get("language", self.language or "Vietnamese")
        else:
            text = str(parsed)
            language = self.language or "Vietnamese"
        return {
            "engine": f"qwen3-asr-transformers ({self.model_name})",
            "language": language,
            "transcript": text.strip(),
            "segments": [],
        }

    def _transcribe_whisper(self, audio_path: Path) -> Dict[str, Any]:
        segments_iter, info = self._model.transcribe(
            str(audio_path),
            language="vi" if not self.language else self.language,
            beam_size=3,
            vad_filter=True,
        )
        seg_list = []
        parts = []
        for segment in segments_iter:
            text = segment.text.strip()
            if text:
                parts.append(text)
                seg_list.append({
                    "start": round(segment.start, 2),
                    "end": round(segment.end, 2),
                    "text": text,
                })
        return {
            "engine": f"faster-whisper ({self.model_name})",
            "language": info.language,
            "transcript": " ".join(parts),
            "segments": seg_list,
        }

    def transcribe_audio(self, audio_path: Path) -> Dict[str, Any]:
        """Transcribe an audio file and return text with segment timestamps."""
        if self.engine == "qwen3-mlx":
            return self._transcribe_mlx(audio_path)
        if self.engine == "qwen3-transformers":
            return self._transcribe_transformers(audio_path)
        return self._transcribe_whisper(audio_path)
