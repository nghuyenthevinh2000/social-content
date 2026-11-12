"""Local AI Speech-to-Text Transcriber for Viral Reels.

@deprecated [OBSOLETE]: Local video download + ASR transcription (Qwen3-ASR / faster-whisper)
is flagged obsolete compared to direct API transcription (e.g. Glasser.ai / ScrapeCreators).
Retained as a local offline solution; do not delete.

Qwen3-ASR backends:
- macOS Apple Silicon: mlx-qwen3-asr (Metal GPU, fastest).
- Windows/Linux: transformers Qwen3-ASR (CPU or CUDA).
- Last resort: faster-whisper when installed.
"""

from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Callable, Dict, List, Optional

from tools.loop.viral_analyzer.cache import get_cached_transcript
from tools.loop.viral_analyzer.config import ViralAnalyzerConfig
from tools.loop.viral_analyzer.retention import register_video
from tools.loop.viral_analyzer.video_download import download_video_stream

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
    """Local AI Speech-to-Text Transcriber."""

    def __init__(
        self,
        model_name: str = "Qwen/Qwen3-ASR-0.6B",
        language: Optional[str] = None,
    ):
        self.engine = "local"
        self._backend = "whisper"
        self.model_name = model_name
        self.language = language
        self._model = None
        self._processor = None
        self._load_engine()

    def _load_engine(self) -> None:
        if sys.platform == "darwin":
            try:
                import mlx_qwen3_asr

                self._model, _ = mlx_qwen3_asr.load_model(self.model_name)
                self._backend = "mlx"
                return
            except Exception as exc:
                print(f"[!] mlx-qwen3-asr unavailable ({exc}); trying transformers Qwen3-ASR.")

        try:
            self._load_qwen3_transformers()
            return
        except Exception as exc:
            print(f"[!] transformers Qwen3-ASR unavailable ({exc}); falling back to faster-whisper.")

        self.model_name = "base"
        from faster_whisper import WhisperModel

        self._model = WhisperModel(self.model_name, device="cpu", compute_type="int8")

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
        self._backend = "transformers"

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
            "engine": f"local ({self.model_name})",
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
            "engine": f"local ({self.model_name})",
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
            "engine": f"local ({self.model_name})",
            "language": info.language,
            "transcript": " ".join(parts),
            "segments": seg_list,
        }

    def transcribe_audio(self, audio_path: Path) -> Dict[str, Any]:
        """Transcribe an audio file and return text with segment timestamps."""
        if self._backend == "mlx":
            return self._transcribe_mlx(audio_path)
        if self._backend == "transformers":
            return self._transcribe_transformers(audio_path)
        return self._transcribe_whisper(audio_path)


LocalTranscriber = UnifiedTranscriber


def transcribe_reels_local(
    extracted_reels: List[Dict[str, Any]],
    config: ViralAnalyzerConfig,
    effective_max: Optional[int] = None,
    now: Optional[datetime] = None,
    progress_cb: Optional[Callable[[str], None]] = None,
) -> None:
    """Download video media and transcribe reels locally."""
    if not extracted_reels:
        return
    now = now or datetime.now(timezone.utc)
    try:
        transcriber = LocalTranscriber(
            model_name=config.transcription.model,
            language=config.transcription.language,
        )
    except Exception as exc:
        msg = f"[!] Local transcription unavailable ({exc}); continuing without transcripts."
        print(msg)
        if progress_cb:
            progress_cb(msg)
        return

    for idx, reel in enumerate(extracted_reels, 1):
        vid = reel["video_id"]
        v_cdn = reel.get("video_url")
        v_url = v_cdn if v_cdn else reel["url"]
        is_reel_page = not bool(v_cdn)

        video_path = config.storage.video_dir / f"reel_{vid}.mp4"
        temp_audio = Path(tempfile.gettempdir()) / f"audio_{vid}.wav"

        print(f"\n[{idx}/{len(extracted_reels)}] Pool {reel['current_pool']} ({reel['views']:,} views) - {reel['author_handle']}: {reel['title'][:50]}...")
        if progress_cb:
            progress_cb(f"[{idx}/{len(extracted_reels)}] Đang xử lý {reel['author_handle']}: {reel['title'][:60]}")

        if effective_max:
            total_cached = len(list(config.storage.video_dir.glob("*.mp4")))
            if total_cached >= effective_max and not video_path.exists():
                print(f"    [*] Target video quota reached ({total_cached}/{effective_max}); skipping additional downloads.")
                break

        if not video_path.exists():
            print(f"    [*] Downloading to persistent video cache: {video_path.name}...")
            dl_ok = download_video_stream(v_url, video_path, is_reel_page=is_reel_page)
            if not dl_ok:
                print(f"    [-] Download failed for {vid}")
                continue
            register_video(config.storage.video_dir, vid, video_path, retention_days=config.retention_days, now=now)
            print(f"    [+] Saved to cache (Expires in {config.retention_days} days).")
        else:
            print(f"    [*] Found in cache: {video_path.name}")

        existing_tr = get_cached_transcript(vid)
        if existing_tr:
            print(f"    [*] Transcript already present in DB ({len(existing_tr)} chars).")
            reel["transcript"] = existing_tr
            reel["segments"] = []
            reel["language"] = "vi"
            continue

        try:
            print("    [*] Extracting 16kHz mono audio via FFmpeg...")
            audio_ok = extract_audio_ffmpeg(
                video_path,
                temp_audio,
                max_duration_sec=config.transcription.max_audio_duration_sec,
            )
            if audio_ok:
                print(f"    [*] Transcribing with {transcriber.engine.upper()}...")
                tr_res = transcriber.transcribe_audio(temp_audio)
                reel["transcript"] = tr_res["transcript"]
                reel["segments"] = tr_res["segments"]
                reel["language"] = tr_res["language"]
                print(f"    [+] Transcribed ({len(tr_res['transcript'])} chars): {tr_res['transcript'][:70]}...")
            else:
                reel["transcript"] = ""
                reel["segments"] = []
        finally:
            if temp_audio.exists():
                try:
                    os.remove(temp_audio)
                except Exception:
                    pass
