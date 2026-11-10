import base64
from pathlib import Path
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

import pytest
from tools.app.backend.video_engine import build_prompt, generate_video, normalize_video


def test_build_prompt():
    prompt = "Chia sẻ kinh nghiệm làm bánh mì giòn tan"
    p = build_prompt(prompt, safe_fallback=False)
    assert prompt in p
    assert "Vertical 9:16" in p
    assert "Spoken Vietnamese" in p

    p_safe = build_prompt(prompt, safe_fallback=True)
    assert "Xin chào các bạn" in p_safe


def test_normalize_video():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        raw_mp4 = tmp_path / "raw.mp4"
        norm_mp4 = tmp_path / "norm.mp4"

        # Generate a 1-second synthetic video using ffmpeg
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-f",
                "lavfi",
                "-i",
                "color=c=blue:s=360x640:d=1",
                "-f",
                "lavfi",
                "-i",
                "sine=f=1000:d=1",
                "-c:v",
                "libx264",
                "-c:a",
                "aac",
                str(raw_mp4),
            ],
            check=True,
            capture_output=True,
        )

        res = normalize_video(raw_mp4, norm_mp4)
        assert res.exists()
        assert res.stat().st_size > 0


class StubInteraction:
    def __init__(self, video_data_b64: str):
        self.output_video = {"data": video_data_b64}


class StubClient:
    def __init__(self, video_bytes: bytes, fail_safety_first: bool = False):
        self.video_bytes = video_bytes
        self.fail_safety_first = fail_safety_first
        self.calls = []

        class Interactions:
            def __init__(self, outer):
                self.outer = outer

            def create(self, **kwargs):
                self.outer.calls.append(kwargs)
                if self.outer.fail_safety_first and len(self.outer.calls) == 1:
                    raise RuntimeError("Request triggered safety harmful content filter")
                b64 = base64.b64encode(self.outer.video_bytes).decode("utf-8")
                return StubInteraction(b64)

        self.interactions = Interactions(self)


def test_generate_video_stubbed_and_safety_retry():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        synth_mp4 = tmp_path / "synth.mp4"
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-f",
                "lavfi",
                "-i",
                "color=c=red:s=360x640:d=1",
                "-f",
                "lavfi",
                "-i",
                "sine=f=440:d=1",
                "-c:v",
                "libx264",
                "-c:a",
                "aac",
                str(synth_mp4),
            ],
            check=True,
            capture_output=True,
        )
        sample_video_bytes = synth_mp4.read_bytes()

        # 1. Normal call with 15s duration
        client = StubClient(sample_video_bytes, fail_safety_first=False)
        out1 = tmp_path / "out1.mp4"
        generate_video(
            prompt="Hướng dẫn làm mứt dừa",
            profile_image_bytes=b"fakejpeg",
            context_images_bytes=[b"fakectx1"],
            output_path=out1,
            client=client,
            duration_sec=15,
        )
        assert out1.exists()
        assert len(client.calls) == 1
        assert client.calls[0]["model"] == "gemini-omni-1.2-flash"
        assert client.calls[0]["response_format"]["duration"] == "15s"
        # 1 profile + 1 context + 1 prompt text
        assert len(client.calls[0]["input"]) == 3

        # 2. Safety retry call
        client_safety = StubClient(sample_video_bytes, fail_safety_first=True)
        out2 = tmp_path / "out2.mp4"
        generate_video(
            prompt="Nội dung nhạy cảm",
            profile_image_bytes=b"fakejpeg",
            output_path=out2,
            client=client_safety,
        )
        assert out2.exists()
        assert len(client_safety.calls) == 2
        # The second call prompt should use safe fallback
        assert "Xin chào các bạn" in client_safety.calls[1]["input"][-1]["text"]
