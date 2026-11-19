"""Configuration, prompts, and topic prompt builders for Video Research."""

from __future__ import annotations

import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional

from tools.app.backend.video_engine import get_video_duration
from tools.loop.viral_analyzer.platforms import fallback_video_url

# Temporary videos live under the repo's local data dir and are deleted after analysis.
TEMP_DIR = Path(os.environ.get("VIRAL_APP_TEMP", Path(__file__).resolve().parents[4] / "local" / "aibrand" / "temp"))

VISUAL_PROMPT = """Bạn nhận được các khung hình trích từ một video Reel. Phân tích và mô tả NGẮN GỌN bằng tiếng Việt, chỉ dựa trên những gì nhìn thấy:
- Bối cảnh/không gian, ánh sáng, tông màu
- Góc máy, khung hình, chuyển động camera (nếu suy ra được từ các khung hình)
- Người xuất hiện (giới tính, độ tuổi ước lượng, trang phục), hành động chính
- Đạo cụ, sản phẩm, chữ/overlay trên màn hình
- Nhịp cắt cảnh và phong cách hình ảnh tổng thể
Trả về một đoạn văn 4-6 câu, không markdown, không nhận xét ngoài nội dung video."""


def _fallback_reel_url(reel: Dict[str, Any]) -> str:
    """Build a platform-appropriate fallback video URL when only video_id is present."""
    vid = str(reel.get("video_id") or "").strip()
    if not vid:
        return ""
    return fallback_video_url(
        str(reel.get("platform") or "facebook"),
        vid,
        str(reel.get("author_handle") or ""),
    )


def _reel_digest(reels: List[Dict[str, Any]], limit: int = 12) -> str:
    ranked = sorted(
        reels,
        key=lambda r: (
            int(r.get("current_pool") or 0),
            float(r.get("velocity_per_hour") or 0),
            int(r.get("views") or 0),
        ),
        reverse=True,
    )[:limit]
    lines = []
    for index, reel in enumerate(ranked, 1):
        title = str(reel.get("title") or "").strip() or "(không có tiêu đề)"
        transcript = str(reel.get("transcript") or "").strip().replace("\n", " ")
        if transcript:
            transcript = f" | transcript: {transcript[:400]}"
        reel_url = str(reel.get("url") or reel.get("reel_url") or "").strip()
        if not reel_url and reel.get("video_id"):
            reel_url = _fallback_reel_url(reel)
        url_part = f" | reel_url: {reel_url}" if reel_url else ""
        visual = str(reel.get("visual") or "").strip().replace("\n", " ")
        visual_part = f" | hình ảnh: {visual[:600]}" if visual else ""
        lines.append(
            f"{index}. [P{reel.get('current_pool', 0)} | {int(reel.get('views') or 0):,} views | "
            f"{float(reel.get('velocity_per_hour') or 0):,.0f} views/h | @{reel.get('author_handle', 'reel')}{url_part}] "
            f"{title}{transcript}{visual_part}"
        )
    return "\n".join(lines)


def _normalize_actor(actor_profile: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    try:
        from tools.app.backend.user_profile import normalize_actor_profile

        return normalize_actor_profile(actor_profile)
    except ImportError:
        raw = dict(actor_profile or {})
        raw_gender = str(raw.get("gender") or "male").strip().lower()
        return {
            "gender": "female" if raw_gender in ("female", "nữ", "nu", "woman") else "male",
            "age": int(raw.get("age", 28)) if str(raw.get("age", 28)).isdigit() else 28,
            "name": str(raw.get("name") or "").strip()[:100],
            "voice_tone": str(raw.get("voice_tone") or "Bắc").strip() or "Bắc",
        }


def format_director_prompt(
    item: Dict[str, Any],
    sheet_name: str = "",
    actor_profile: Optional[Dict[str, Any]] = None,
    *_args: Any,
    **_kwargs: Any,
) -> str:
    norm = _normalize_actor(actor_profile)
    gender_vn = "nam" if norm["gender"] == "male" else "nữ"
    age = norm["age"]

    dur = get_video_duration()
    hook_end = "03"
    cta_start = f"{max(4, dur - 4):02d}"

    title = str(item.get("title") or "").strip()
    hook = str(item.get("hook") or "").strip().strip("\"'")
    angle = str(item.get("angle") or "").strip()
    outline = item.get("outline") or []
    if isinstance(outline, list):
        clean_outline = [re.sub(r"^\d+[\.\)]\s*", "", str(x)).strip() for x in outline if str(x).strip()]
    else:
        clean_outline = [str(outline).strip()]
    outline_summary = ". ".join(clean_outline[:2])

    dialogue_parts = []
    if hook:
        dialogue_parts.append(hook)
    if outline_summary:
        dialogue_parts.append(outline_summary)
    dialogue_parts.append("Mọi người cùng lưu lại và áp dụng ngay nhé!")
    dialogue_text = ". ".join(dialogue_parts).replace("..", ".")

    env_text = f"Không gian làm việc chân thực phù hợp chủ đề '{sheet_name or title}'. Ánh sáng tự nhiên rõ nét, bố cục gọn gàng, tự nhiên."
    visual = str(item.get("visual") or "").strip()
    if visual:
        env_text = f"{env_text} Tham chiếu hình ảnh thật từ video gốc: {visual}"
    action_hook = f"Presenter nhìn thẳng ống kính camera cười tươi, mở đầu lôi cuốn: \"{hook or title}\"."
    action_body = f"Presenter thao tác tự nhiên, diễn giải các ý chính: {outline_summary or angle or title}."
    action_cta = "Presenter cười thân thiện, gật đầu và ra hiệu kêu gọi người xem lưu lại và tương tác."

    actions = (
        f"00:00 - 00:{hook_end}: {action_hook}\n"
        f"00:{hook_end} - 00:{cta_start}: {action_body}\n"
        f"00:{cta_start} - 00:{dur:02d}: {action_cta}"
    )

    tone = norm.get("voice_tone") or "Bắc"
    if tone.lower() in ("bắc", "bac", "north", "northern"):
        tone_desc = "chất giọng Bắc"
    elif tone.lower() in ("nam", "south", "southern"):
        tone_desc = "chất giọng Nam"
    elif tone.lower() in ("trung", "central"):
        tone_desc = "chất giọng Trung"
    else:
        tone_desc = f"tông giọng {tone}"

    return (
        f"[CAMERA & COMPOSITION]\n"
        f"Khung hình dọc 9:16 góc nhìn điện thoại (POV), máy cầm tay ngang tầm mắt, góc quay cận cảnh tự nhiên theo dõi người dẫn và thao tác, phong cách đời thường chân thực (BTS), video sạch sẽ, không watermark, logo hay chữ chèn đè.\n\n"
        f"[ENVIRONMENT & ATMOSPHERE]\n"
        f"{env_text}\n\n"
        f"[SUBJECT & CONTINUITY]\n"
        f"Người dẫn ({gender_vn}, {age} tuổi) nhìn thẳng ống kính, cử chỉ tự nhiên, kết nối trực tiếp với người xem đồng bộ với ảnh mẫu <IMAGE_REF_0>.\n\n"
        f"[ACTION & TIMECODE]\n"
        f"{actions}\n\n"
        f"[AUDIO & DIALOGUE]\n"
        f"Giọng {gender_vn} ({age} tuổi), {tone_desc}, lời thoại tiếng Việt tự nhiên, chuẩn nhịp điệu: \"{dialogue_text}\". Âm thanh nền chân thực."
    )


def build_topic_prompt(
    sheet_name: str,
    targets: List[Dict[str, Any]],
    reels: List[Dict[str, Any]],
    actor_profile: Optional[Dict[str, Any]] = None,
) -> str:
    norm = _normalize_actor(actor_profile)
    gender_vn = "nam" if norm["gender"] == "male" else "nữ"
    age = norm["age"]
    tone_str = norm.get("voice_tone") or "Bắc"
    name_str = f", tên: {norm['name']}" if norm.get("name") else ""

    channels = ", ".join(target.get("name") or target.get("handle", "") for target in targets[:20]) or "(chưa có kênh)"
    pools: Dict[str, int] = {}
    for reel in reels:
        key = f"P{reel.get('current_pool', 0)}"
        pools[key] = pools.get(key, 0) + 1
    pool_text = ", ".join(f"{key}: {count}" for key, count in sorted(pools.items())) or "không có dữ liệu"
    digest = _reel_digest(reels) or "(không có reel nào trong 48 giờ)"
    dur = get_video_duration()
    hook_end = "03"
    cta_start = f"{max(4, dur - 4):02d}"

    return f"""Bạn là chiến lược gia nội dung viral cho Facebook Reels & video ngắn tiếng Việt.

NHÓM CHỦ ĐỀ: {sheet_name}
KÊNH / NGUỒN REEL: {channels}
PHÂN BỔ POOL: {pool_text}
DỮ LIỆU REEL:
{digest}

NHIỆM VỤ: Đề xuất ĐÚNG 3 chủ đề video có khả năng viral cao nhất cho nội dung này.
Mỗi chủ đề phải đi kèm trường "prompt" chứa kịch bản đạo diễn (director prompt) hoàn chỉnh, chuẩn bị sẵn cho AI tạo video (tỷ lệ 9:16 dọc, thời lượng {dur} giây).

CẤU TRÚC PROMPT ĐẠO DIỄN (bắt buộc đúng 5 phần theo chuẩn UGC):
[CAMERA & COMPOSITION]
Khung hình dọc 9:16 góc nhìn điện thoại (POV), máy cầm tay ngang tầm mắt, góc quay cận cảnh tự nhiên theo dõi người dẫn và thao tác, phong cách đời thường chân thực (BTS), không watermark, logo hay chữ chèn đè.

[ENVIRONMENT & ATMOSPHERE]
Bối cảnh thực tế phù hợp chủ đề (xưởng, văn phòng, nhà bếp, studio...), ánh sáng tự nhiên, chân thực.

[SUBJECT & CONTINUITY]
Người dẫn ({gender_vn}, {age} tuổi{name_str}) nhìn thẳng ống kính, biểu cảm thân thiện kết nối trực tiếp với người xem (<IMAGE_REF_0>).

[ACTION & TIMECODE]
Phân chia nhịp thời gian chính xác trong đúng {dur} giây:
- 00:00 - 00:{hook_end}: Hành động mở đầu và hook gây tò mò
- 00:{hook_end} - 00:{cta_start}: Thao tác và diễn giải nội dung chính
- 00:{cta_start} - 00:{dur:02d}: Kết luận và kêu gọi hành động (CTA)

[AUDIO & DIALOGUE]
Giọng {gender_vn} ({age} tuổi), giọng {tone_str}, lời thoại tiếng Việt tự nhiên, súc tích, nhịp điệu nhanh vừa khớp thời lượng {dur} giây.

Yêu cầu:
- 3 chủ đề phải khác nhau rõ rệt về góc khai thác, không trùng ý.
- Dựa trên bằng chứng thật từ dữ liệu trên (view, velocity, pool, transcript, tên kênh, reel_url).
- Nếu có mô tả hình ảnh, bám sát bối cảnh, góc máy, ánh sáng, đạo cụ và chữ trên màn hình thật của video.
- Cụ thể, có thể bấm máy quay làm ngay; không viết chung chung.
- Viết tiếng Việt.
- Trả về DUY NHẤT một JSON array, không markdown, không giải thích ngoài JSON.

Schema mỗi phần tử:
[
  {{
    "title": "tên chủ đề ngắn gọn, gây tò mò",
    "hook": "câu mở đầu 3 giây",
    "angle": "góc khai thác khác biệt so với đối thủ",
    "why_viral": "vì sao chủ đề này có khả năng viral, dẫn số liệu hoặc tâm lý người xem",
    "outline": ["ý 1", "ý 2", "ý 3"],
    "format": "Reels {dur}s UGC",
    "source_urls": ["url reel bằng chứng (bắt đầu bằng https://www.facebook.com/reel/...)"],
    "prompt": "[CAMERA & COMPOSITION]\\n...\\n\\n[ENVIRONMENT & ATMOSPHERE]\\n...\\n\\n[SUBJECT & CONTINUITY]\\n...\\n\\n[ACTION & TIMECODE]\\n...\\n\\n[AUDIO & DIALOGUE]\\n..."
  }}
]"""
