"""Language-aware prompt builders (EN / VI) for Video Research."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from tools.app.backend.video_engine import get_video_duration
from tools.loop.viral_analyzer.platforms import fallback_video_url


def resolve_language(language: Optional[str] = None) -> str:
    """Normalize user default language to 'en' or 'vi' (default 'vi')."""
    norm = str(language or "vi").strip().lower()
    if norm in ("en", "eng", "english") or norm.startswith("en-"):
        return "en"
    return "vi"


VISUAL_PROMPTS: Dict[str, str] = {
    "vi": """Bạn nhận được các khung hình trích từ một video Reel. Phân tích và mô tả NGẮN GỌN bằng tiếng Việt, chỉ dựa trên những gì nhìn thấy:
- Bối cảnh/không gian, ánh sáng, tông màu
- Góc máy, khung hình, chuyển động camera (nếu suy ra được từ các khung hình)
- Người xuất hiện (giới tính, độ tuổi ước lượng, trang phục), hành động chính
- Đạo cụ, sản phẩm, chữ/overlay trên màn hình
- Nhịp cắt cảnh và phong cách hình ảnh tổng thể
Trả về một đoạn văn 4-6 câu, không markdown, không nhận xét ngoài nội dung video.""",
    "en": """You are given extracted frames from a Reel video. Analyze and describe CONCISELY in English, based strictly on what is visible:
- Setting/environment, lighting, color tone
- Camera angle, framing, camera movement (if inferable from frames)
- People appearing (gender, estimated age, outfit), main action
- Props, products, on-screen text/overlays
- Editing pace and overall visual style
Return a single 4-6 sentence paragraph, no markdown, no commentary outside the video content.""",
}

VISUAL_PROMPT = VISUAL_PROMPTS["vi"]


def get_visual_prompt(language: Optional[str] = None) -> str:
    """Return EN or VI visual frame-analysis prompt."""
    return VISUAL_PROMPTS[resolve_language(language)]


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


def _reel_digest(reels: List[Dict[str, Any]], limit: int = 12, language: Optional[str] = None) -> str:
    lang = resolve_language(language)
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
    no_title = "(no title)" if lang == "en" else "(không có tiêu đề)"
    visual_label = "visuals" if lang == "en" else "hình ảnh"
    for index, reel in enumerate(ranked, 1):
        title = str(reel.get("title") or "").strip() or no_title
        transcript = str(reel.get("transcript") or "").strip().replace("\n", " ")
        if transcript:
            transcript = f" | transcript: {transcript[:400]}"
        reel_url = str(reel.get("url") or reel.get("reel_url") or "").strip()
        if not reel_url and reel.get("video_id"):
            reel_url = _fallback_reel_url(reel)
        url_part = f" | reel_url: {reel_url}" if reel_url else ""
        visual = str(reel.get("visual") or "").strip().replace("\n", " ")
        visual_part = f" | {visual_label}: {visual[:600]}" if visual else ""
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
    language: Optional[str] = None,
    **_kwargs: Any,
) -> str:
    """Format a 5-section UGC director prompt in EN or VI."""
    lang = resolve_language(language)
    norm = _normalize_actor(actor_profile)
    is_male = norm["gender"] == "male"
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

    dialogue_parts = [p for p in (hook, outline_summary) if p]
    dialogue_parts.append(
        "Save this and try it right away!" if lang == "en" else "Mọi người cùng lưu lại và áp dụng ngay nhé!"
    )
    dialogue_text = ". ".join(dialogue_parts).replace("..", ".")
    visual = str(item.get("visual") or "").strip()
    tone = norm.get("voice_tone") or ("Natural" if lang == "en" else "Bắc")

    if lang == "en":
        gender_en = "male" if is_male else "female"
        env_text = f"Authentic workspace matching '{sheet_name or title}'. Clear natural lighting, clean and realistic framing."
        if visual:
            env_text = f"{env_text} Visual reference from original video: {visual}"
        actions = (
            f'00:00 - 00:{hook_end}: Presenter looks directly into the camera, smiling warmly, delivering an engaging hook: "{hook or title}".\n'
            f"00:{hook_end} - 00:{cta_start}: Presenter demonstrates naturally and explains key points: {outline_summary or angle or title}.\n"
            f"00:{cta_start} - 00:{dur:02d}: Presenter smiles warmly, nods, and gestures to viewers to save and engage."
        )
        return (
            "[CAMERA & COMPOSITION]\n"
            "Vertical 9:16 handheld phone POV at eye level, natural close-up tracking the presenter and hand actions, authentic BTS style, clean video with no watermarks, logos, or text overlays.\n\n"
            "[ENVIRONMENT & ATMOSPHERE]\n"
            f"{env_text}\n\n"
            "[SUBJECT & CONTINUITY]\n"
            f"Presenter ({gender_en}, {age} years old) looking directly into the lens with natural gestures, consistent with reference image <IMAGE_REF_0>.\n\n"
            "[ACTION & TIMECODE]\n"
            f"{actions}\n\n"
            "[AUDIO & DIALOGUE]\n"
            f'{gender_en.capitalize()} voice ({age} years old), {tone} tone, natural English delivery with crisp pacing: "{dialogue_text}". Authentic ambient audio.'
        )

    gender_vn = "nam" if is_male else "nữ"
    env_text = f"Không gian làm việc chân thực phù hợp chủ đề '{sheet_name or title}'. Ánh sáng tự nhiên rõ nét, bố cục gọn gàng, tự nhiên."
    if visual:
        env_text = f"{env_text} Tham chiếu hình ảnh thật từ video gốc: {visual}"
    actions = (
        f'00:00 - 00:{hook_end}: Presenter nhìn thẳng ống kính camera cười tươi, mở đầu lôi cuốn: "{hook or title}".\n'
        f"00:{hook_end} - 00:{cta_start}: Presenter thao tác tự nhiên, diễn giải các ý chính: {outline_summary or angle or title}.\n"
        f"00:{cta_start} - 00:{dur:02d}: Presenter cười thân thiện, gật đầu và ra hiệu kêu gọi người xem lưu lại và tương tác."
    )
    if tone.lower() in ("bắc", "bac", "north", "northern"):
        tone_desc = "chất giọng Bắc"
    elif tone.lower() in ("nam", "south", "southern"):
        tone_desc = "chất giọng Nam"
    elif tone.lower() in ("trung", "central"):
        tone_desc = "chất giọng Trung"
    else:
        tone_desc = f"tông giọng {tone}"

    return (
        "[CAMERA & COMPOSITION]\n"
        "Khung hình dọc 9:16 góc nhìn điện thoại (POV), máy cầm tay ngang tầm mắt, góc quay cận cảnh tự nhiên theo dõi người dẫn và thao tác, phong cách đời thường chân thực (BTS), video sạch sẽ, không watermark, logo hay chữ chèn đè.\n\n"
        "[ENVIRONMENT & ATMOSPHERE]\n"
        f"{env_text}\n\n"
        "[SUBJECT & CONTINUITY]\n"
        f"Người dẫn ({gender_vn}, {age} tuổi) nhìn thẳng ống kính, cử chỉ tự nhiên, kết nối trực tiếp với người xem đồng bộ với ảnh mẫu <IMAGE_REF_0>.\n\n"
        "[ACTION & TIMECODE]\n"
        f"{actions}\n\n"
        "[AUDIO & DIALOGUE]\n"
        f'Giọng {gender_vn} ({age} tuổi), {tone_desc}, lời thoại tiếng Việt tự nhiên, chuẩn nhịp điệu: "{dialogue_text}". Âm thanh nền chân thực.'
    )


def build_video_structure_prompt(
    sheet_name: str,
    targets: List[Dict[str, Any]],
    reels: List[Dict[str, Any]],
    actor_profile: Optional[Dict[str, Any]] = None,
    language: Optional[str] = None,
) -> str:
    """Build EN or VI video-structure analysis & director-prompt generation prompt."""
    lang = resolve_language(language)
    norm = _normalize_actor(actor_profile)
    is_male = norm["gender"] == "male"
    age = norm["age"]
    tone_str = norm.get("voice_tone") or ("Natural" if lang == "en" else "Bắc")
    dur = get_video_duration()
    hook_end = "03"
    cta_start = f"{max(4, dur - 4):02d}"

    pools: Dict[str, int] = {}
    for reel in reels:
        key = f"P{reel.get('current_pool', 0)}"
        pools[key] = pools.get(key, 0) + 1

    brand = (actor_profile or {}).get("brand") if isinstance(actor_profile, dict) else None

    if lang == "en":
        gender_en = "male" if is_male else "female"
        name_str = f", name: {norm['name']}" if norm.get("name") else ""
        channels = ", ".join(t.get("name") or t.get("handle", "") for t in targets[:20]) or "(no channels)"
        pool_text = ", ".join(f"{k}: {v}" for k, v in sorted(pools.items())) or "no data"
        digest = _reel_digest(reels, language="en") or "(no reels in the last 48 hours)"
        brand_lines = []
        if isinstance(brand, dict):
            for key, label in (
                ("identity", "Brand identity (what people remember)"),
                ("audience", "Target audience / customers"),
                ("differentiator", "Core value & differentiator"),
                ("tone", "Style & tone of voice"),
            ):
                val = str(brand.get(key) or "").strip()
                if val:
                    brand_lines.append(f"- {label}: {val}")
        brand_block = (
            "\n\nPERSONAL BRAND GUIDELINES (MUST FOLLOW STRICTLY):\n" + "\n".join(brand_lines)
            if brand_lines
            else ""
        )
        brand_rule = (
            '\n- Every angle ("angle"), hook, outline ("outline"), and script ("prompt") must stay consistent with the PERSONAL BRAND GUIDELINES above.'
            if brand_lines
            else ""
        )
        return f"""You are a viral short-form video strategist analyzing Reels and short videos in English.

TOPIC GROUP: {sheet_name}
CHANNELS / REEL SOURCES: {channels}
POOL DISTRIBUTION: {pool_text}
REEL DATA:
{digest}{brand_block}

TASK: Analyze the structure of the videos in the reel data above — explain why each video can go viral and break down its outline/structure so it can be replicated.
Each video analysis must include a "prompt" field containing a complete director prompt to recreate that viral structure for AI video generation (9:16 vertical, {dur}s duration).

DIRECTOR PROMPT STRUCTURE (strictly 5 UGC sections):
[CAMERA & COMPOSITION]
Vertical 9:16 handheld phone POV at eye level, natural close-up tracking presenter and actions, authentic BTS style, no watermarks, logos, or text overlays.

[ENVIRONMENT & ATMOSPHERE]
Realistic setting matching the topic (workshop, office, kitchen, studio...), natural authentic lighting.

[SUBJECT & CONTINUITY]
Presenter ({gender_en}, {age} years old{name_str}) looking straight into the lens, friendly expression connecting directly with viewers (<IMAGE_REF_0>).

[ACTION & TIMECODE]
Exact pacing within {dur} seconds:
- 00:00 - 00:{hook_end}: Opening action and curiosity hook
- 00:{hook_end} - 00:{cta_start}: Demonstration and core explanation
- 00:{cta_start} - 00:{dur:02d}: Conclusion and call to action (CTA)

[AUDIO & DIALOGUE]
{gender_en.capitalize()} voice ({age} years old), {tone_str} tone, natural concise English dialogue with brisk pacing fitting {dur} seconds.

Requirements:
- Analyze the real structure and viral drivers of the videos in the data (1 item per analyzed video; do not invent unrelated topics).
- "why_viral" must clearly explain why this video is viral (hook, viewer psychology, pacing, visuals/audio, citing metrics from the data).
- "outline" must break down the actual video structure section by section (opening/hook, body/development, closing/CTA) for viral replication.
- Ground every claim in real evidence from the data above (views, velocity, pool, transcript, channel name, reel_url).
- If visual descriptions are present, stay faithful to the real setting, camera angles, lighting, props, and on-screen text.
- Be concrete and ready to shoot; avoid generic advice.{brand_rule}
- Write in English.
- Return ONLY a single JSON array, no markdown, no extra explanation.

Item schema:
[
  {{
    "title": "concise, curiosity-driven topic title",
    "hook": "3-second opening hook line",
    "angle": "distinctive angle compared to competitors",
    "why_viral": "why this topic can go viral, citing metrics or viewer psychology",
    "outline": ["point 1", "point 2", "point 3"],
    "format": "Reels {dur}s UGC",
    "source_urls": ["evidence reel url (e.g. https://www.facebook.com/reel/...)"],
    "prompt": "[CAMERA & COMPOSITION]\\n...\\n\\n[ENVIRONMENT & ATMOSPHERE]\\n...\\n\\n[SUBJECT & CONTINUITY]\\n...\\n\\n[ACTION & TIMECODE]\\n...\\n\\n[AUDIO & DIALOGUE]\\n..."
  }}
]"""

    gender_vn = "nam" if is_male else "nữ"
    name_str = f", tên: {norm['name']}" if norm.get("name") else ""
    channels = ", ".join(target.get("name") or target.get("handle", "") for target in targets[:20]) or "(chưa có kênh)"
    pool_text = ", ".join(f"{key}: {count}" for key, count in sorted(pools.items())) or "không có dữ liệu"
    digest = _reel_digest(reels, language="vi") or "(không có reel nào trong 48 giờ)"

    brand_lines = []
    if isinstance(brand, dict):
        for key, label in (
            ("identity", "Nhân hiệu (điều mọi người nhớ tới)"),
            ("audience", "Khách hàng / Khán giả mục tiêu"),
            ("differentiator", "Giá trị cốt lõi & Điểm khác biệt"),
            ("tone", "Phong cách & Giọng điệu"),
        ):
            val = str(brand.get(key) or "").strip()
            if val:
                brand_lines.append(f"- {label}: {val}")
    brand_block = (
        "\n\nĐỊNH HƯỚNG NHÂN HIỆU (BẮT BUỘC BÁM SÁT):\n" + "\n".join(brand_lines)
        if brand_lines
        else ""
    )
    brand_rule = (
        '\n- Mọi góc khai thác ("angle"), hook, dàn ý ("outline") và kịch bản ("prompt") phải nhất quán với ĐỊNH HƯỚNG NHÂN HIỆU ở trên.'
        if brand_lines
        else ""
    )

    return f"""Bạn là chiến lược gia phân tích cấu trúc video viral cho Reels & video ngắn tiếng Việt.

NHÓM CHỦ ĐỀ: {sheet_name}
KÊNH / NGUỒN REEL: {channels}
PHÂN BỔ POOL: {pool_text}
DỮ LIỆU REEL:
{digest}{brand_block}

NHIỆM VỤ: Phân tích cấu trúc của video trong dữ liệu reel trên — giải thích vì sao video có khả năng viral và bóc tách dàn ý/cấu trúc để nhân bản lại độ viral.
Mỗi phân tích video phải đi kèm trường "prompt" chứa kịch bản đạo diễn (director prompt) hoàn chỉnh để tái tạo cấu trúc viral đó cho AI tạo video (tỷ lệ 9:16 dọc, thời lượng {dur} giây).

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
- Phân tích đúng cấu trúc và yếu tố viral của chính video trong dữ liệu (1 phần tử cho mỗi video cần phân tích; không bịa thêm chủ đề ngoài video).
- Trường "why_viral" giải thích rõ vì sao video này viral (hook, tâm lý người xem, nhịp độ, hình ảnh/âm thanh, dẫn số liệu từ dữ liệu).
- Trường "outline" bóc tách cấu trúc thực tế của video theo từng phần (mở đầu/hook, thân bài/triển khai, kết/CTA) để nhân bản độ viral.
- Dựa trên bằng chứng thật từ dữ liệu trên (view, velocity, pool, transcript, tên kênh, reel_url).
- Nếu có mô tả hình ảnh, bám sát bối cảnh, góc máy, ánh sáng, đạo cụ và chữ trên màn hình thật của video.
- Cụ thể, có thể bấm máy quay làm ngay; không viết chung chung.{brand_rule}
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
