import base64
from pathlib import Path
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

import pytest
from tools.app.backend.video_engine import build_prompt, generate_video, get_video_duration, normalize_video


def test_get_video_duration(monkeypatch):
    monkeypatch.delenv("VIDEO_GENERATION_DURATION", raising=False)
    assert get_video_duration() == 15

    monkeypatch.setenv("VIDEO_GENERATION_DURATION", "10")
    assert get_video_duration() == 10

    monkeypatch.setenv("VIDEO_GENERATION_DURATION", "20")
    assert get_video_duration() == 20

    monkeypatch.setenv("VIDEO_GENERATION_DURATION", "invalid")
    assert get_video_duration() == 15


def test_build_prompt():
    prompt = "Chia sẻ kinh nghiệm làm bánh mì giòn tan"
    p = build_prompt(prompt, safe_fallback=False, duration_sec=15)
    assert prompt in p
    assert "[CAMERA & COMPOSITION]" in p
    assert "[ENVIRONMENT & ATMOSPHERE]" in p
    assert "[SUBJECT & CONTINUITY]" in p
    assert "[ACTION & TIMECODE]" in p
    assert "[AUDIO & DIALOGUE]" in p
    assert "00:00 - 00:03" in p
    assert "00:15" in p
    assert "Khung hình dọc 9:16" in p
    assert "Lời thoại tiếng Việt" in p

    # If prompt is already structured, build_prompt preserves it directly
    already_structured = "[CAMERA & COMPOSITION]\nPOV 9:16\n\n[ACTION & TIMECODE]\n00:00 - 00:15"
    assert build_prompt(already_structured) == already_structured

    p_safe = build_prompt(prompt, safe_fallback=True, duration_sec=15)
    assert "Xin chào các bạn" in p_safe
    assert "[ACTION & TIMECODE]" in p_safe


def test_build_prompt_with_actor_profile():
    raw_prompt = "Mẹo tiết kiệm chi phí sinh hoạt"
    male_prof = {"gender": "male", "age": 30, "voice_tone": "warm"}
    p_male = build_prompt(raw_prompt, actor_profile=male_prof)
    assert "người dẫn nam (30 tuổi)" in p_male
    assert "Giọng nam chuẩn tiếng Việt (30 tuổi)" in p_male
    assert "tông giọng warm" in p_male
    assert "<IMAGE_REF_0>" in p_male

    female_prof = {"gender": "female", "age": 24, "voice_tone": "energetic"}
    p_female = build_prompt(raw_prompt, actor_profile=female_prof)
    assert "người dẫn nữ (24 tuổi)" in p_female
    assert "Giọng nữ chuẩn tiếng Việt (24 tuổi)" in p_female
    assert "tông giọng energetic" in p_female
    assert "<IMAGE_REF_0>" in p_female

    structured = (
        "[CAMERA & COMPOSITION]\nVertical 9:16\n\n"
        "[ENVIRONMENT & ATMOSPHERE]\nStudio sáng\n\n"
        "[SUBJECT & CONTINUITY]\nNgười dẫn nhìn vào camera.\n\n"
        "[ACTION & TIMECODE]\n00:00 - 00:15: Chia sẻ mẹo hay\n\n"
        "[AUDIO & DIALOGUE]\nLời thoại tiếng Việt: \"Xin chào mọi người\"."
    )
    p_struct = build_prompt(structured, actor_profile=male_prof)
    assert "Ngoại hình nhất quán của người dẫn nam (30 tuổi)" in p_struct
    assert "Giọng nam chuẩn tiếng Việt (30 tuổi)" in p_struct
    assert "<IMAGE_REF_0>" in p_struct

    # Conflict resolution: prompt generated with female 35, actor profile is male 28
    conflict_structured = (
        "[CAMERA & COMPOSITION]\nVertical 9:16\n\n"
        "[ENVIRONMENT & ATMOSPHERE]\nPhòng khách\n\n"
        "[SUBJECT & CONTINUITY]\nNgười dẫn nữ 35 tuổi nhìn thẳng ống kính.\n\n"
        "[ACTION & TIMECODE]\n00:00 - 00:15: Chia sẻ\n\n"
        "[AUDIO & DIALOGUE]\nGiọng nữ (35 tuổi), lời thoại tiếng Việt: \"Xin chào\"."
    )
    p_resolved = build_prompt(conflict_structured, actor_profile={"gender": "male", "age": 28, "voice_tone": "Bắc"})
    assert "Người dẫn nam 28 tuổi" in p_resolved
    assert "Giọng nam (28 tuổi)" in p_resolved
    assert "Ngoại hình nhất quán của người dẫn nam (28 tuổi)" in p_resolved
    assert "Giọng nam chuẩn tiếng Việt (28 tuổi) với chất giọng Bắc" in p_resolved
    assert "<IMAGE_REF_0>" in p_resolved


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
        text_input = [x for x in client.calls[0]["input"] if x["type"] == "text"][0]["text"]
        assert "người dẫn nam" in text_input
        assert "Giọng nam chuẩn tiếng Việt" in text_input

        # Call with explicit female actor profile
        client_female = StubClient(sample_video_bytes)
        out_female = tmp_path / "out_female.mp4"
        generate_video(
            prompt="Hướng dẫn cắm hoa",
            profile_image_bytes=b"fakejpeg",
            output_path=out_female,
            client=client_female,
            actor_profile={"gender": "female", "age": 25},
        )
        female_text = [x for x in client_female.calls[0]["input"] if x["type"] == "text"][0]["text"]
        assert "người dẫn nữ" in female_text
        assert "Giọng nữ chuẩn tiếng Việt (25 tuổi)" in female_text

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


def test_get_agent_platform_credentials_antigravity_fallback(tmp_path, monkeypatch):
    import json
    from tools.app.backend.video_engine import _get_agent_platform_credentials

    # Clear env
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    monkeypatch.setenv("CLOUDSDK_CONFIG", str(tmp_path / "no-gcloud"))

    fake_token_file = tmp_path / "antigravity-oauth-token"
    fake_token_file.write_text(
        json.dumps({
            "token": {
                "access_token": "ya29.test_token_123",
                "expiry": "2099-01-01T00:00:00Z",
            }
        }),
        encoding="utf-8",
    )

    # Monkeypatch candidates
    monkeypatch.setattr(
        "tools.app.backend.video_engine.Path.home",
        lambda: tmp_path,
    )
    fake_gemini_dir = tmp_path / ".gemini/antigravity-cli"
    fake_gemini_dir.mkdir(parents=True, exist_ok=True)
    (fake_gemini_dir / "antigravity-oauth-token").write_text(fake_token_file.read_text())

    creds = _get_agent_platform_credentials()
    assert creds is not None
    assert creds.token == "ya29.test_token_123"
