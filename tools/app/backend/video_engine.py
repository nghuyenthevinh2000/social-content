"""Lite video generation engine: 10-second reference_to_video Omni call with normalization."""

from __future__ import annotations

import base64
import datetime
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_MODEL = "gemini-omni-1.2-flash"


def get_video_duration(*_args: Any) -> int:
    """Return video duration enforced by VIDEO_GENERATION_DURATION (default 15)."""
    _load_env()
    try:
        return int(os.environ.get("VIDEO_GENERATION_DURATION", 15))
    except (ValueError, TypeError):
        return 15


def _load_env() -> None:
    env_file = Path(__file__).resolve().parent / ".env"
    if not env_file.is_file():
        return
    for line in env_file.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip("'\""))


def _get_agent_platform_credentials() -> Optional[Any]:
    """Resolve credentials for Gemini Agent Platform: standard ADC or Antigravity OAuth fallback."""
    if os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        return None

    gcloud_adc = Path(os.environ.get("CLOUDSDK_CONFIG", Path.home() / ".config/gcloud")) / "application_default_credentials.json"
    if gcloud_adc.is_file():
        return None

    token_candidates = [
        Path.home() / ".gemini/antigravity-cli/antigravity-oauth-token",
        Path("/home/app/.gemini/antigravity-cli/antigravity-oauth-token"),
        Path("/home/vinh/.gemini/antigravity-cli/antigravity-oauth-token"),
    ]
    for candidate in token_candidates:
        if candidate.is_file():
            try:
                from google.oauth2.credentials import Credentials

                raw = json.loads(candidate.read_text(encoding="utf-8"))
                tok = raw.get("token", {})
                expiry_str = tok.get("expiry")
                needs_refresh = False
                if expiry_str:
                    try:
                        exp_dt = datetime.datetime.fromisoformat(expiry_str)
                        if exp_dt.tzinfo is None:
                            exp_dt = exp_dt.replace(tzinfo=datetime.timezone.utc)
                        if datetime.datetime.now(exp_dt.tzinfo) >= exp_dt - datetime.timedelta(seconds=60):
                            needs_refresh = True
                    except Exception:
                        pass
                if needs_refresh and shutil.which("agy"):
                    subprocess.run(["agy", "-p", "ping"], capture_output=True, timeout=15)
                    raw = json.loads(candidate.read_text(encoding="utf-8"))
                    tok = raw.get("token", {})

                access_token = tok.get("access_token")
                if access_token:
                    return Credentials(token=access_token)
            except Exception:
                pass

    return None


def _detect_mime(data: bytes) -> str:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return "image/jpeg"


def _format_actor_cue(actor_profile: Optional[Dict[str, Any]]) -> Tuple[str, str]:
    from tools.app.backend.user_profile import normalize_actor_profile

    norm = normalize_actor_profile(actor_profile)
    gender = norm["gender"]
    age = norm["age"]
    tone = norm["voice_tone"]
    if tone.lower() in ("bắc", "bac", "north", "northern"):
        tone_desc = "chất giọng Bắc"
    elif tone.lower() in ("nam", "south", "southern"):
        tone_desc = "chất giọng Nam"
    elif tone.lower() in ("trung", "central"):
        tone_desc = "chất giọng Trung"
    else:
        tone_desc = f"tông giọng {tone}"

    gender_noun = "người dẫn nam" if gender == "male" else "người dẫn nữ"
    gender_voice = "nam" if gender == "male" else "nữ"

    actor_cue = f"Ngoại hình nhất quán của {gender_noun} ({age} tuổi) đồng bộ chính xác với ảnh chân dung mẫu <IMAGE_REF_0>, biểu cảm thân thiện kết nối trực tiếp với ống kính."
    voice_cue = (
        f"Giọng {gender_voice} chuẩn tiếng Việt ({age} tuổi) với {tone_desc}, âm thanh rõ nét chuẩn phòng thu. "
        f"Giọng đọc khớp hoàn toàn với khẩu hình và biểu cảm của {gender_noun} trên màn hình."
    )
    return actor_cue, voice_cue


def _apply_actor_profile_to_structured_prompt(prompt: str, actor_profile: Optional[Dict[str, Any]]) -> str:
    actor_cue, voice_cue = _format_actor_cue(actor_profile)
    from tools.app.backend.user_profile import normalize_actor_profile

    norm = normalize_actor_profile(actor_profile)
    gender = norm["gender"]
    gender_vn = "nam" if gender == "male" else "nữ"
    opposite_vn = "nữ" if gender == "male" else "nam"
    age = norm["age"]

    res = prompt

    # 1. Align [SUBJECT & CONTINUITY]
    if "[SUBJECT & CONTINUITY]" in res:
        subject_pattern = r"(\[SUBJECT & CONTINUITY\]\s*)([\s\S]*?)(?=\n\n\[|\Z)"
        match = re.search(subject_pattern, res)
        if match:
            content = match.group(2).strip()
            # Replace conflicting gender/age mentions
            content = re.sub(
                r"(\b(?:người dẫn|presenter|diễn viên)\s+)" + opposite_vn,
                r"\g<1>" + gender_vn,
                content,
                flags=re.IGNORECASE,
            )
            content = re.sub(
                r"(\b(?:người dẫn|presenter|diễn viên)\s+(?:nam|nữ)?\s*)\d+\s*tuổi",
                f"\\g<1>{age} tuổi",
                content,
                flags=re.IGNORECASE,
            )
            # Ensure reference image is cited
            if "<IMAGE_REF_0>" not in content:
                content += " (<IMAGE_REF_0>)"
            # Ensure actor cue is explicitly added/updated in Vietnamese
            if re.search(r"(?:Đặc tả diễn viên|Actor specification):", content, flags=re.IGNORECASE):
                content = re.sub(
                    r"(?:Đặc tả diễn viên|Actor specification):[^\n]*",
                    f"Đặc tả diễn viên: {actor_cue}",
                    content,
                    flags=re.IGNORECASE,
                )
            else:
                content = f"{content}\nĐặc tả diễn viên: {actor_cue}"
            res = res[:match.start(2)] + content + res[match.end(2):]
    else:
        res += f"\n\n[SUBJECT & CONTINUITY]\nNgười dẫn {gender_vn} ({age} tuổi) nhìn thẳng ống kính camera (<IMAGE_REF_0>).\nĐặc tả diễn viên: {actor_cue}"

    # 2. Align [AUDIO & DIALOGUE]
    if "[AUDIO & DIALOGUE]" in res:
        audio_pattern = r"(\[AUDIO & DIALOGUE\]\s*)([\s\S]*?)(?=\n\n\[|\Z)"
        match = re.search(audio_pattern, res)
        if match:
            content = match.group(2).strip()
            # Replace conflicting gender in voice mentions
            content = re.sub(
                r"(\bgiọng\s+)" + opposite_vn,
                r"\g<1>" + gender_vn,
                content,
                flags=re.IGNORECASE,
            )
            content = re.sub(
                r"(\bgiọng\s+(?:nam|nữ)?\s*\(?)\d+(\s*tuổi\b)",
                f"\\g<1>{age}\\g<2>",
                content,
                flags=re.IGNORECASE,
            )
            # Ensure voice cue is explicitly added/updated in Vietnamese
            if re.search(r"(?:Đặc tả giọng đọc|Voice specification):", content, flags=re.IGNORECASE):
                content = re.sub(
                    r"(?:Đặc tả giọng đọc|Voice specification):[^\n]*",
                    f"Đặc tả giọng đọc: {voice_cue}",
                    content,
                    flags=re.IGNORECASE,
                )
            else:
                content = f"{content}\nĐặc tả giọng đọc: {voice_cue}"
            res = res[:match.start(2)] + content + res[match.end(2):]
    else:
        res += f"\n\n[AUDIO & DIALOGUE]\nĐặc tả giọng đọc: {voice_cue}"

    return res.strip()


def build_prompt(
    prompt: str,
    safe_fallback: bool = False,
    actor_profile: Optional[Dict[str, Any]] = None,
    *_args: Any,
    **_kwargs: Any,
) -> str:
    dur = get_video_duration()
    hook_end = "03"
    cta_start = f"{max(4, dur - 4):02d}"
    actor_cue, voice_cue = _format_actor_cue(actor_profile)

    if safe_fallback:
        spoken = "Xin chào các bạn, hôm nay chúng ta cùng chia sẻ những điều hữu ích và tích cực."
        action = (
            f"00:00 - 00:{hook_end}: Người dẫn nhìn thẳng ống kính camera với nụ cười thân thiện, thu hút sự chú ý.\n"
            f"00:{hook_end} - 00:{cta_start}: Người dẫn chia sẻ lời khuyên hữu ích với cử chỉ tay nhẹ nhàng, tự nhiên.\n"
            f"00:{cta_start} - 00:{dur:02d}: Người dẫn mỉm cười thân thiện và mời người xem lưu lại và áp dụng mẹo hay."
        )
        return (
            f"[CAMERA & COMPOSITION]\n"
            f"Khung hình dọc 9:16 góc nhìn điện thoại (POV), máy cầm tay ngang tầm mắt, góc quay cận cảnh tự nhiên theo dõi người dẫn và thao tác, phong cách đời thường chân thực (BTS), video sạch sẽ, không watermark, logo hay chữ chèn đè.\n\n"
            f"[ENVIRONMENT & ATMOSPHERE]\n"
            f"Không gian làm việc chân thực, gọn gàng với ánh sáng tự nhiên phù hợp chủ đề.\n\n"
            f"[SUBJECT & CONTINUITY]\n"
            f"Đặc tả diễn viên: {actor_cue}\n\n"
            f"[ACTION & TIMECODE]\n"
            f"{action}\n\n"
            f"[AUDIO & DIALOGUE]\n"
            f"Lời thoại tiếng Việt: \"{spoken}\"\n"
            f"Đặc tả giọng đọc: {voice_cue}"
        )

    if "[CAMERA & COMPOSITION]" in prompt or "[ACTION & TIMECODE]" in prompt:
        if actor_profile is not None:
            return _apply_actor_profile_to_structured_prompt(prompt.strip(), actor_profile)
        return prompt.strip()

    spoken = prompt.strip()
    action = (
        f"00:00 - 00:{hook_end}: Người dẫn nhìn thẳng ống kính camera với nụ cười tự tin, mở đầu lôi cuốn.\n"
        f"00:{hook_end} - 00:{cta_start}: Người dẫn truyền tải thông điệp chính với cử chỉ tay và biểu cảm gương mặt tự nhiên.\n"
        f"00:{cta_start} - 00:{dur:02d}: Người dẫn mỉm cười thân thiện, ra hiệu chào và kêu gọi người xem tương tác."
    )

    return (
        f"[CAMERA & COMPOSITION]\n"
        f"Khung hình dọc 9:16 góc nhìn điện thoại (POV), máy cầm tay ngang tầm mắt, góc quay cận cảnh tự nhiên theo dõi người dẫn và thao tác, phong cách đời thường chân thực (BTS), video sạch sẽ, không watermark, logo hay chữ chèn đè.\n\n"
        f"[ENVIRONMENT & ATMOSPHERE]\n"
        f"Không gian làm việc chân thực, gọn gàng với ánh sáng tự nhiên phù hợp chủ đề.\n\n"
        f"[SUBJECT & CONTINUITY]\n"
        f"Đặc tả diễn viên: {actor_cue}\n\n"
        f"[ACTION & TIMECODE]\n"
        f"{action}\n\n"
        f"[AUDIO & DIALOGUE]\n"
        f"Lời thoại tiếng Việt: \"{spoken}\"\n"
        f"Đặc tả giọng đọc: {voice_cue}"
    )


def normalize_video(input_path: Path, output_path: Path) -> Path:
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
        "-vf",
        "colorspace=all=bt709:fast=1",
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        "-color_primaries",
        "bt709",
        "-color_trc",
        "bt709",
        "-colorspace",
        "bt709",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-ar",
        "44100",
        "-ac",
        "2",
        "-af",
        "loudnorm=I=-16:TP=-1.5:LRA=11",
        "-movflags",
        "+faststart",
        str(output_path),
    ]

    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        # Fallback if audio track is missing or loudnorm failed
        fallback_cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(input_path),
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(output_path),
        ]
        fallback_res = subprocess.run(fallback_cmd, capture_output=True, text=True)
        if fallback_res.returncode != 0:
            raise RuntimeError(f"FFmpeg normalization failed: {res.stderr}\nFallback: {fallback_res.stderr}")

    return output_path


def generate_video(
    prompt: str,
    profile_image_bytes: bytes,
    context_images_bytes: Optional[List[bytes]] = None,
    output_path: Optional[Path] = None,
    client: Optional[Any] = None,
    duration_sec: Optional[int] = None,
    actor_profile: Optional[Dict[str, Any]] = None,
) -> Path:
    if not prompt or not prompt.strip():
        raise ValueError("Prompt must not be empty.")
    if not profile_image_bytes:
        raise ValueError("Profile image bytes required.")

    dur = get_video_duration()

    if output_path is None:
        fd, temp_out = tempfile.mkstemp(suffix=".mp4")
        os.close(fd)
        output_path = Path(temp_out)

    inputs: List[Dict[str, Any]] = [
        {
            "type": "image",
            "data": base64.b64encode(profile_image_bytes).decode("utf-8"),
            "mime_type": _detect_mime(profile_image_bytes),
        }
    ]

    if context_images_bytes:
        for ctx_bytes in context_images_bytes:
            if ctx_bytes:
                inputs.append(
                    {
                        "type": "image",
                        "data": base64.b64encode(ctx_bytes).decode("utf-8"),
                        "mime_type": _detect_mime(ctx_bytes),
                    }
                )

    inputs.append({"type": "text", "text": build_prompt(prompt, safe_fallback=False, actor_profile=actor_profile)})

    _load_env()
    if client is None:
        from google import genai

        project = (
            os.environ.get("AGENT_PLATFORM_PROJECT")
            or os.environ.get("GOOGLE_CLOUD_PROJECT")
            or "gen-lang-client-0582170752"
        )
        location = (
            os.environ.get("AGENT_PLATFORM_LOCATION")
            or os.environ.get("GOOGLE_CLOUD_LOCATION")
            or "global"
        )

        creds = _get_agent_platform_credentials()
        if creds is not None:
            client = genai.Client(enterprise=True, project=project, location=location, credentials=creds)
        else:
            client = genai.Client(enterprise=True, project=project, location=location)

    model = os.environ.get("AGENT_PLATFORM_MODEL", DEFAULT_MODEL)
    kwargs = {
        "model": model,
        "input": inputs,
        "response_format": {
            "type": "video",
            "aspect_ratio": "9:16",
            "duration": f"{dur}s",
            "resolution": "360p",
        },
        "store": True,
    }

    try:
        interaction = client.interactions.create(**kwargs)
    except Exception as exc:
        err_msg = str(exc).lower()
        if "safety" in err_msg or "harmful" in err_msg:
            inputs[-1] = {"type": "text", "text": build_prompt(prompt, safe_fallback=True, actor_profile=actor_profile)}
            interaction = client.interactions.create(**kwargs)
        else:
            raise

    video_b64 = None
    out_vid = getattr(interaction, "output_video", None)
    if out_vid:
        video_b64 = getattr(out_vid, "data", None) or (out_vid.get("data") if isinstance(out_vid, dict) else None)

    if not video_b64:
        for item in getattr(interaction, "outputs", None) or []:
            item_type = getattr(item, "type", None) or (item.get("type") if isinstance(item, dict) else None)
            if item_type == "video":
                video_b64 = getattr(item, "data", None) or (item.get("data") if isinstance(item, dict) else None)
                break

    if not video_b64:
        raise RuntimeError(f"Omni call returned no video data: {interaction}")

    raw_mp4_bytes = base64.b64decode(video_b64)

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as raw_file:
        raw_path = Path(raw_file.name)
        raw_path.write_bytes(raw_mp4_bytes)

    try:
        normalize_video(raw_path, output_path)
    finally:
        try:
            raw_path.unlink()
        except OSError:
            pass

    return output_path
