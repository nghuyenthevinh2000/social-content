"""Reel Research Engine: Deep content, transcript, style, and viral analysis on individual reels.

Focuses on:
- Fast transcript retrieval (Glasser ScrapeCreators / local ASR engine).
- Style, format, and pacing analysis (9:16 vertical, UGC framing, duration).
- "Why Viral" catalyst interrogation (hook, psychological angle, retention triggers).
- Topic suggestion and Director Prompt generation (ACP harness or heuristic engine).
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any, Callable, Dict, List, Optional, Tuple
import urllib.error
import urllib.parse
import urllib.request

from tools.app.backend.acp import ACPClient, ACPError
from tools.app.backend.video_engine import get_video_duration
from tools.loop.viral_analyzer.transcriber import fetch_reel_transcript, fetch_top_reels_transcripts

logger = logging.getLogger("reel_research")

# Temporary videos live under the repo's local data dir and are deleted after analysis.
TEMP_DIR = Path(os.environ.get("VIRAL_APP_TEMP", Path(__file__).resolve().parents[4] / "local" / "aibrand" / "temp"))

VISUAL_PROMPT = """Bạn nhận được các khung hình trích từ một video Reel. Phân tích và mô tả NGẮN GỌN bằng tiếng Việt, chỉ dựa trên những gì nhìn thấy:
- Bối cảnh/không gian, ánh sáng, tông màu
- Góc máy, khung hình, chuyển động camera (nếu suy ra được từ các khung hình)
- Người xuất hiện (giới tính, độ tuổi ước lượng, trang phục), hành động chính
- Đạo cụ, sản phẩm, chữ/overlay trên màn hình
- Nhịp cắt cảnh và phong cách hình ảnh tổng thể
Trả về một đoạn văn 4-6 câu, không markdown, không nhận xét ngoài nội dung video."""


# Supported Reel, Short-Form, and Video Share URL patterns
REEL_PATTERNS = [
    re.compile(r'https?://(?:www\.)?facebook\.com/reel/(\d+)', re.I),
    re.compile(r'https?://(?:www\.)?facebook\.com/share/[rvp]/([a-zA-Z0-9_-]+)', re.I),
    re.compile(r'https?://(?:www\.)?facebook\.com/watch/\?v=(\d+)', re.I),
    re.compile(r'https?://(?:www\.)?facebook\.com/[a-zA-Z0-9_.-]+/videos/(\d+)', re.I),
    re.compile(r'https?://fb\.watch/([a-zA-Z0-9_-]+)', re.I),
    re.compile(r'https?://(?:www\.)?instagram\.com/reel/([a-zA-Z0-9_-]+)', re.I),
    re.compile(r'https?://(?:www\.)?instagram\.com/p/([a-zA-Z0-9_-]+)', re.I),
    re.compile(r'https?://(?:www\.)?tiktok\.com/@[\w.-]+/video/(\d+)', re.I),
    re.compile(r'https?://(?:vm|vt)\.tiktok\.com/([a-zA-Z0-9_-]+)', re.I),
]


def resolve_short_url(url: str, timeout: float = 3.0) -> str:
    """Resolve short share URLs (fb.watch, facebook.com/share/*, vm.tiktok.com) to target URL."""
    if not url or not any(x in url for x in ('facebook.com/share/', 'fb.watch/', 'tiktok.com/')):
        return url
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
        )

        class _NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None

        opener = urllib.request.build_opener(_NoRedirect)
        try:
            resp = opener.open(req, timeout=timeout)
            loc = resp.headers.get("Location")
        except urllib.error.HTTPError as exc:
            loc = exc.headers.get("Location")
        if loc:
            return loc
    except Exception:
        pass
    return url


def canonicalize_reel_url(url: str, resolve_redirects: bool = True) -> Optional[Tuple[str, str]]:
    """Clean tracking params from Reel URL and detect platform."""
    if not url:
        return None
    target_url = resolve_short_url(url) if resolve_redirects else url
    for pattern in REEL_PATTERNS:
        match = pattern.search(target_url)
        if match:
            clean = match.group(0).rstrip('/')
            if 'facebook.com' in clean or 'fb.watch' in clean:
                return clean, 'facebook'
            if 'instagram.com' in clean:
                return clean, 'instagram'
            if 'tiktok.com' in clean:
                return clean, 'tiktok'
    return None


def is_reel_url(url: str) -> bool:
    """Return True if the URL points directly to an individual Reel or video."""
    if not url:
        return False
    return any(p.search(url) for p in REEL_PATTERNS)


def extract_video_id(url: str) -> Optional[str]:
    """Extract numeric or alphanumeric video ID from a reel/video URL."""
    if not url:
        return None
    for pattern in REEL_PATTERNS:
        m = pattern.search(url)
        if m and m.groups():
            return m.group(1)
    return None


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
            reel_url = f"https://www.facebook.com/reel/{reel['video_id']}"
        url_part = f" | reel_url: {reel_url}" if reel_url else ""
        visual = str(reel.get("visual") or "").strip().replace("\n", " ")
        visual_part = f" | hình ảnh: {visual[:600]}" if visual else ""
        lines.append(
            f"{index}. [P{reel.get('current_pool', 0)} | {int(reel.get('views') or 0):,} views | "
            f"{float(reel.get('velocity_per_hour') or 0):,.0f} views/h | @{reel.get('author_handle', 'reel')}{url_part}] "
            f"{title}{transcript}{visual_part}"
        )
    return "\n".join(lines)


def format_director_prompt(
    item: Dict[str, Any],
    sheet_name: str = "",
    actor_profile: Optional[Dict[str, Any]] = None,
    *_args: Any,
    **_kwargs: Any,
) -> str:
    from tools.app.backend.user_profile import normalize_actor_profile

    norm = normalize_actor_profile(actor_profile)
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
    from tools.app.backend.user_profile import normalize_actor_profile

    norm = normalize_actor_profile(actor_profile)
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


def _normalize_outline(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [part.strip() for part in re.split(r"[\n;•]+", value) if part.strip()]
    return []


def _normalize_sources(value: Any) -> List[str]:
    if isinstance(value, str):
        return [value] if value.startswith("http") else []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).startswith("http")]
    return []


def _resolve_to_reel_url(url: str, reels: List[Dict[str, Any]]) -> str:
    """Ensure URL points directly to a reel rather than a generic profile/page."""
    url = url.strip()
    if not url:
        return ""
    if "/reel/" in url or "/videos/" in url or "/watch/" in url:
        return url

    clean = url.rstrip("/")
    target_handle = clean.split("/")[-1].replace("@", "").lower()

    for r in reels:
        r_handle = str(r.get("author_handle") or "").strip().lower()
        if r_handle and (r_handle == target_handle or target_handle in r_handle or r_handle in target_handle):
            if r.get("url") or r.get("reel_url"):
                return str(r.get("url") or r.get("reel_url")).strip()
            if r.get("video_id"):
                return f"https://www.facebook.com/reel/{r['video_id']}"

    if "facebook.com" in clean and not clean.endswith("/reels"):
        return f"{clean}/reels/"

    return url


def normalize_topics(
    data: Any,
    fallback: List[Dict[str, Any]],
    reels: Optional[List[Dict[str, Any]]] = None,
    sheet_name: str = "",
    actor_profile: Optional[Dict[str, Any]] = None,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    if isinstance(data, dict):
        data = data.get("topics") or data.get("ideas") or [data]
    if not isinstance(data, list):
        return fallback
    topics = []
    dur = get_video_duration()
    ranked_reels = sorted(
        reels or [],
        key=lambda r: (int(r.get("views") or 0), float(r.get("velocity_per_hour") or 0)),
        reverse=True,
    )
    for index, item in enumerate(data):
        if not isinstance(item, dict):
            continue
        raw_sources = _normalize_sources(item.get("source_urls") or item.get("sources"))
        sources = [_resolve_to_reel_url(u, reels or []) for u in raw_sources if u]
        if not sources and index < len(fallback):
            sources = fallback[index].get("source_urls", [])
        if not sources and ranked_reels and index < len(ranked_reels):
            top_url = ranked_reels[index].get("url") or ranked_reels[index].get("reel_url") or (
                f"https://www.facebook.com/reel/{ranked_reels[index]['video_id']}" if ranked_reels[index].get("video_id") else None
            )
            if top_url:
                sources = [top_url]
        prompt_val = str(item.get("prompt") or item.get("director_prompt") or "").strip()
        if not prompt_val:
            prompt_val = format_director_prompt(item, sheet_name=sheet_name, actor_profile=actor_profile)
        elif actor_profile:
            from tools.app.backend.video_engine import _apply_actor_profile_to_structured_prompt
            prompt_val = _apply_actor_profile_to_structured_prompt(prompt_val, actor_profile)

        matched_reel = None
        if ranked_reels:
            for r in ranked_reels:
                r_url = r.get("url") or r.get("reel_url") or ""
                r_id = str(r.get("video_id") or "")
                if sources and any((r_url and r_url in s) or (r_id and r_id in s) for s in sources):
                    matched_reel = r
                    break
            if not matched_reel and index < len(ranked_reels):
                matched_reel = ranked_reels[index]

        fb_item = fallback[index] if index < len(fallback) else {}
        t_views = int((matched_reel.get("views") if matched_reel else fb_item.get("views")) or 0)
        t_vel = float((matched_reel.get("velocity_per_hour") if matched_reel else fb_item.get("velocity_per_hour")) or 0)
        t_pool = (matched_reel.get("current_pool") if matched_reel else fb_item.get("current_pool")) or 0
        t_pool_name = str((matched_reel.get("pool_name") if matched_reel else fb_item.get("pool_name")) or "")
        t_likes = int((matched_reel.get("likes") if matched_reel else fb_item.get("likes")) or 0)
        t_comments = int((matched_reel.get("comments") if matched_reel else fb_item.get("comments")) or 0)
        t_video_url = (matched_reel.get("video_url") if matched_reel else fb_item.get("video_url")) or None
        t_video_id = str((matched_reel.get("video_id") if matched_reel else fb_item.get("video_id")) or "")
        t_handle = str((matched_reel.get("author_handle") if matched_reel else fb_item.get("author_handle")) or "")
        t_name = str((matched_reel.get("author_name") if matched_reel else fb_item.get("author_name")) or "")
        t_transcript = str((matched_reel.get("transcript") if matched_reel else fb_item.get("transcript")) or "").strip()
        t_visual = str((matched_reel.get("visual") if matched_reel else fb_item.get("visual")) or "").strip()

        topics.append(
            {
                "title": str(item.get("title") or "").strip() or (fallback[index]["title"] if index < len(fallback) else "Chủ đề mới"),
                "hook": str(item.get("hook") or "").strip(),
                "angle": str(item.get("angle") or "").strip(),
                "why_viral": str(item.get("why_viral") or item.get("why") or "").strip(),
                "outline": _normalize_outline(item.get("outline")),
                "format": str(item.get("format") or f"Reels {dur}s UGC").strip(),
                "source_urls": sources,
                "reel_url": sources[0] if sources else (matched_reel.get("url") or matched_reel.get("reel_url") if matched_reel else ""),
                "video_url": t_video_url,
                "video_id": t_video_id,
                "views": t_views,
                "velocity_per_hour": t_vel,
                "current_pool": t_pool,
                "pool_name": t_pool_name,
                "likes": t_likes,
                "comments": t_comments,
                "author_handle": t_handle,
                "author_name": t_name,
                "transcript": t_transcript,
                "visual": t_visual,
                "prompt": prompt_val,
                "generated_by": "agent",
            }
        )
    while len(topics) < len(fallback) and len(topics) < limit:
        topics.append(fallback[len(topics)])
    while len(topics) < 3 and len(fallback) >= 3:
        topics.append(fallback[len(topics)])

    has_views = any((t.get("views") or 0) > 0 for t in topics)
    if has_views:
        topics.sort(
            key=lambda x: (
                int(x.get("views") or 0),
                float(x.get("velocity_per_hour") or 0),
            ),
            reverse=True,
        )
    selected = topics[:limit]
    fetch_top_reels_transcripts(selected)
    return selected


def _extract_json_candidates(text: str) -> List[str]:
    text = text.strip()
    candidates = [text]
    candidates.extend(re.findall(r"```(?:json)?\s*(.*?)```", text, re.S | re.I))
    start, end = text.find("["), text.rfind("]")
    if start != -1 and end > start:
        candidates.append(text[start : end + 1])
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        candidates.append(text[start : end + 1])
    return candidates


def parse_topics(
    text: str,
    fallback: List[Dict[str, Any]],
    reels: Optional[List[Dict[str, Any]]] = None,
    sheet_name: str = "",
    actor_profile: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    for candidate in _extract_json_candidates(text):
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        topics = normalize_topics(data, fallback, reels=reels, sheet_name=sheet_name, actor_profile=actor_profile)
        if topics:
            return topics
    return fallback


def heuristic_topics(
    sheet_name: str,
    reels: List[Dict[str, Any]],
    actor_profile: Optional[Dict[str, Any]] = None,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    dur = get_video_duration()
    ranked = sorted(
        reels,
        key=lambda r: (
            int(r.get("views") or 0),
            float(r.get("velocity_per_hour") or 0),
            int(r.get("current_pool") or 0),
        ),
        reverse=True,
    )
    topics: List[Dict[str, Any]] = []
    for reel in ranked[:limit]:
        title = str(reel.get("title") or "").strip() or f"Video từ @{reel.get('author_handle', 'reel')}"
        views = int(reel.get("views") or 0)
        velocity = float(reel.get("velocity_per_hour") or 0)
        reel_url = reel.get("url") or reel.get("reel_url") or (f"https://www.facebook.com/reel/{reel['video_id']}" if reel.get("video_id") else "")
        t = {
            "title": f"Kể lại: {title[:90]}",
            "hook": f"Vì sao chuyện này đạt {views:,} lượt xem trong 48 giờ?" if views else "Đây là điều bất ngờ nhất bạn từng nghe?",
            "angle": f"Phân tích góc P{reel.get('current_pool', 0)} - {reel.get('pool_name', '')}, tập trung vào cảm xúc và bình luận." if views else "Tập trung vào yếu tố cảm xúc và sự tò mò trong nội dung gốc.",
            "why_viral": f"{views:,} views, {velocity:,.0f} views/giờ, pool P{reel.get('current_pool', 0)}." if views else "Video thu hút sự chú ý mạnh mẽ nhờ yếu tố bất ngờ.",
            "outline": [
                f"Mở bằng chi tiết gây tò mò từ video gốc của @{reel.get('author_handle', 'creator')}",
                "Kể lại câu chuyện bằng hình ảnh/điện thoại, giữ nhịp nhanh",
                "Kết bằng câu hỏi mở để kéo bình luận",
            ],
            "format": f"Reels {dur}s UGC",
            "source_urls": [reel_url] if reel_url else [],
            "reel_url": reel_url,
            "video_url": reel.get("video_url"),
            "video_id": str(reel.get("video_id") or ""),
            "views": views,
            "velocity_per_hour": velocity,
            "current_pool": reel.get("current_pool", 0),
            "pool_name": str(reel.get("pool_name") or ""),
            "likes": int(reel.get("likes") or 0),
            "comments": int(reel.get("comments") or 0),
            "shares": int(reel.get("shares") or 0),
            "author_handle": str(reel.get("author_handle") or ""),
            "author_name": str(reel.get("author_name") or ""),
            "transcript": str(reel.get("transcript") or "").strip(),
            "visual": str(reel.get("visual") or "").strip(),
            "generated_by": "heuristic",
        }
        t["prompt"] = format_director_prompt(t, sheet_name=sheet_name, actor_profile=actor_profile)
        topics.append(t)

    generic = [
        {
            "title": f"'{sheet_name}': điều 90% người xem hiểu sai",
            "hook": f"Bạn đang làm sai điều cơ bản nhất về {sheet_name}?",
            "angle": "Myth-busting: nêu hiểu lầm phổ biến rồi sửa bằng ví dụ đời thường.",
            "why_viral": "Chủ đề dựa trên tên nhóm; khai thác điểm nghẽn nhận thức của số đông.",
            "outline": ["Nêu hiểu lầm", "Đưa bằng chứng trực quan", "Chốt bằng mẹo làm ngay"],
            "format": f"Reels {dur}s UGC",
            "source_urls": [],
            "generated_by": "heuristic",
        },
        {
            "title": f"Thử thách 7 ngày về {sheet_name}",
            "hook": "Tôi thử điều này 7 ngày và kết quả bất ngờ.",
            "angle": "Nhật ký trải nghiệm cá nhân, tạo chuỗi theo dõi nhiều tập.",
            "why_viral": "Chuỗi thử thách giữ chân người xem quay lại.",
            "outline": ["Ngày 1: mục tiêu", "Ngày 3-5: khó khăn", "Ngày 7: kết quả"],
            "format": f"Chuỗi Reels {dur}s UGC",
            "source_urls": [],
            "generated_by": "heuristic",
        },
        {
            "title": f"3 mẹo {sheet_name} cho người mới",
            "hook": "Đừng bắt đầu trước khi biết 3 điều này.",
            "angle": "Danh sách nhanh, dễ lưu và chia sẻ.",
            "why_viral": "Nội dung lưu/chia sẻ tốt, phù hợp người mới.",
            "outline": ["Mẹo 1", "Mẹo 2", "Mẹo 3 + lời mời lưu video"],
            "format": f"Reels {dur}s UGC",
            "source_urls": [],
            "generated_by": "heuristic",
        },
    ]
    for g in generic:
        g["prompt"] = format_director_prompt(g, sheet_name=sheet_name, actor_profile=actor_profile)
    while len(topics) < 3:
        topics.append(generic[len(topics)])
    selected = topics[:limit]
    fetch_top_reels_transcripts(selected)
    return selected


def suggest_topics(
    agent_id: str,
    sheet_name: str,
    targets: List[Dict[str, Any]],
    reels: List[Dict[str, Any]],
    cwd: Path,
    timeout_sec: float,
    log: Callable[[str], None],
    model: Optional[str] = None,
    actor_profile: Optional[Dict[str, Any]] = None,
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    if not reels:
        log(f"Không có reel nào cho '{sheet_name}'; bỏ qua gợi ý chủ đề.")
        return [], None
    fallback = heuristic_topics(sheet_name, reels, actor_profile=actor_profile)
    prompt = build_topic_prompt(sheet_name, targets, reels, actor_profile=actor_profile)
    client = None

    from tools.app.backend.research_engine.research import _harness_lock, resolve_agent

    with _harness_lock(log):
        try:
            preset = resolve_agent(agent_id, model=model)
            model_info = f" ({preset['model']})" if preset.get("model") else ""
            log(f"Gọi harness {preset['label']}{model_info} qua ACP...")
            client = ACPClient(preset["command"], cwd=cwd, timeout_sec=timeout_sec, log=log)
            client.initialize()
            session_id = client.new_session()
            text = client.prompt(session_id, prompt)
            if not text.strip():
                raise ACPError("Agent trả về nội dung rỗng.")
            topics = parse_topics(text, fallback, reels=reels, sheet_name=sheet_name, actor_profile=actor_profile)
            if topics and topics[0].get("generated_by") == "agent":
                log("Agent đã trả về 3 chủ đề.")
            else:
                log("Không parse được JSON từ agent; dùng gợi ý dự phòng.")
            return topics, None
        except Exception as exc:
            detail = str(exc)
            if client is not None and client.stderr_tail:
                detail = f"{detail} | stderr: {client.stderr_tail}"
            if "auth" in detail.lower():
                detail = f"{detail} | Gợi ý đăng nhập harness rồi thử lại."
            log(f"ACP thất bại: {detail}")
            return fallback, detail
        finally:
            if client is not None:
                client.close()


def _download_reel_video(
    reel_url: str,
    video_id: Optional[str],
    log: Callable[[str], None],
) -> Optional[Path]:
    from tools.loop.viral_analyzer.video_download import download_video_stream

    target = TEMP_DIR / f"reel_{video_id or 'saved'}.mp4"
    if target.exists() and target.stat().st_size > 1000:
        return target
    log(f"Tải video để phân tích hình ảnh: {target}")
    if download_video_stream(reel_url, target, is_reel_page=True):
        return target
    log("Không tải được video; bỏ qua phân tích hình ảnh.")
    return None


def _extract_video_frames(video_path: Path, frame_dir: Path, count: int = 4) -> List[Path]:
    """Sample up to `count` frames (one every 3s) from a local video with FFmpeg."""
    from tools.loop.viral_analyzer.transcriber.local import ffmpeg_bin

    frame_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg_bin(),
        "-y",
        "-i", str(video_path),
        "-vf", "fps=1/3,scale=720:-2",
        "-frames:v", str(count),
        str(frame_dir / "frame_%02d.jpg"),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return []
    return sorted(frame_dir.glob("frame_*.jpg"))


def analyze_video_visuals(
    video_path: Path,
    agent_id: str,
    cwd: Path,
    timeout_sec: float,
    log: Callable[[str], None],
    model: Optional[str] = None,
) -> str:
    """Describe the downloaded Reel's on-screen visuals with the local CLI harness."""
    from tools.app.backend.research_engine.research import _harness_lock, resolve_agent

    frame_dir = video_path.parent / f"{video_path.stem}_frames"
    frames = _extract_video_frames(video_path, frame_dir)
    if not frames:
        log("Không trích xuất được khung hình video.")
        return ""

    client = None
    try:
        with _harness_lock(log):
            preset = resolve_agent(agent_id, model=model)
            log(f"Phân tích hình ảnh bằng harness {preset['label']}...")
            client = ACPClient(preset["command"], cwd=cwd, timeout_sec=timeout_sec, log=log)
            client.initialize()
            session_id = client.new_session()
            images = [(frame.read_bytes(), "image/jpeg") for frame in frames]
            return client.prompt(session_id, VISUAL_PROMPT, images=images).strip()
    except Exception as exc:
        log(f"Phân tích hình ảnh bằng harness thất bại: {exc}")
        return ""
    finally:
        if client is not None:
            client.close()
        for frame in frames:
            try:
                frame.unlink()
            except OSError:
                pass
        try:
            frame_dir.rmdir()
        except OSError:
            pass


def _transcribe_local_fallback(
    video_path: Path,
    vid: Optional[str],
    clean_url: str,
    log: Callable[[str], None],
) -> Optional[str]:
    """Run local ASR on an already-downloaded reel video when Glasser transcript is unavailable."""
    audio_path = video_path.with_suffix(".wav")
    chunk_paths: List[Path] = []
    try:
        import subprocess
        from tools.loop.viral_analyzer.cache import save_cached_transcript
        from tools.loop.viral_analyzer.transcriber.local import UnifiedTranscriber, extract_audio_ffmpeg, ffmpeg_bin

        if not extract_audio_ffmpeg(video_path, audio_path, max_duration_sec=300):
            return None
        chunk_pattern = video_path.parent / f"{video_path.stem}_chunk_%03d.wav"
        proc = subprocess.run(
            [
                ffmpeg_bin(),
                "-y",
                "-i", str(audio_path),
                "-f", "segment",
                "-segment_time", "45",
                "-c", "copy",
                str(chunk_pattern),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        chunk_paths = sorted(video_path.parent.glob(f"{video_path.stem}_chunk_*.wav"))
        targets = chunk_paths if (proc.returncode == 0 and chunk_paths) else [audio_path]

        transcriber = UnifiedTranscriber()
        parts: List[str] = []
        for idx, part_path in enumerate(targets, 1):
            log(f"Đang chạy transcript local đoạn {idx}/{len(targets)}...")
            result = transcriber.transcribe_audio(part_path)
            chunk_text = str(result.get("transcript") or result.get("text") or "").strip()
            if chunk_text:
                parts.append(chunk_text)

        text = " ".join(parts).strip()
        if text:
            log(f"Đã trích xuất transcript local ({len(text)} ký tự).")
            if vid:
                save_cached_transcript(vid, text, url=clean_url)
            return text
    except Exception as exc:
        log(f"Không thể chạy transcript local: {exc}")
    finally:
        for p in [audio_path, *chunk_paths]:
            if p.exists():
                try:
                    p.unlink()
                except OSError:
                    pass
    return None


def research_single_reel(
    reel_url: str,
    sheet_name: str = "Reel đã lưu",
    actor_profile: Optional[Dict[str, Any]] = None,
    agent_id: Optional[str] = None,
    model: Optional[str] = None,
    log: Optional[Callable[[str], None]] = None,
    cwd: Optional[Path] = None,
    timeout_sec: float = 120.0,
) -> Dict[str, Any]:
    """Execute direct deep research on an individual Reel URL (e.g. from Saved Reels).

    Steps:
    1. Canonicalize the Reel URL (e.g. resolve /share/v/ redirects).
    2. Retrieve transcript via Glasser or local ASR engine.
    3. Download the video to the local temp dir and describe its visuals with the CLI harness.
    4. Analyze viral structure, hook, angle, outline, format, and generate Director Prompt.
    """
    _log = log or (lambda msg: logger.info(msg))
    canon_res = canonicalize_reel_url(reel_url)
    clean_url = canon_res[0] if canon_res else reel_url.strip()
    platform = canon_res[1] if canon_res else "facebook"
    vid = extract_video_id(clean_url)

    _log(f"Bắt đầu phân tích Reel: {clean_url}")

    # Fetch transcript
    transcript = fetch_reel_transcript(clean_url, video_id=vid)
    if transcript:
        _log(f"Đã trích xuất transcript ({len(transcript)} ký tự).")
    else:
        _log("Không tìm thấy transcript; tiến hành phân tích qua cấu trúc video và hook.")

    # Download the video for visual analysis (and local ASR fallback if Glasser had no transcript).
    visual = ""
    if agent_id and cwd:
        video_path = _download_reel_video(clean_url, vid, _log)
        if video_path:
            if not transcript:
                transcript = _transcribe_local_fallback(video_path, vid, clean_url, _log)
            visual = analyze_video_visuals(
                video_path, agent_id, cwd, timeout_sec, _log, model=model
            )
            if visual:
                _log(f"Đã phân tích hình ảnh video ({len(visual)} ký tự).")
                try:
                    video_path.unlink()
                    _log("Đã xoá video tạm sau khi phân tích.")
                except OSError:
                    pass
            else:
                _log(f"Chưa phân tích được hình ảnh; giữ video tạm để kiểm tra: {video_path}")
    else:
        _log("Không có harness để phân tích hình ảnh video; bỏ qua.")

    reel_obj: Dict[str, Any] = {
        "url": clean_url,
        "reel_url": clean_url,
        "video_id": vid or "",
        "platform": platform,
        "title": sheet_name or f"Reel {vid or ''}",
        "transcript": transcript or "",
        "visual": visual,
        "views": 0,
        "velocity_per_hour": 0,
        "current_pool": 0,
        "pool_name": "Direct Saved Reel",
        "author_handle": "saved_reel",
    }

    # A saved Reel maps to exactly one director prompt.
    topics: List[Dict[str, Any]] = []
    error: Optional[str] = None

    if agent_id and cwd:
        targets = [{"name": sheet_name, "url": clean_url}]
        topics, error = suggest_topics(
            agent_id=agent_id,
            sheet_name=sheet_name,
            targets=targets,
            reels=[reel_obj],
            cwd=cwd,
            timeout_sec=timeout_sec,
            log=_log,
            model=model,
            actor_profile=actor_profile,
        )
        topics = topics[:1]

    if not topics:
        topics = heuristic_topics(sheet_name, [reel_obj], actor_profile=actor_profile, limit=1)
        for t in topics:
            t["source_urls"] = [clean_url]
            t["reel_url"] = clean_url
            t["transcript"] = transcript or ""
            t["visual"] = visual

    return {
        "ok": True,
        "reel_url": clean_url,
        "video_id": vid,
        "platform": platform,
        "transcript": transcript,
        "visual": visual,
        "topics": topics,
        "error": error,
    }


def research_reels(
    reels: List[Dict[str, Any]],
    sheet_name: str,
    actor_profile: Optional[Dict[str, Any]] = None,
    agent_id: Optional[str] = None,
    model: Optional[str] = None,
    log: Optional[Callable[[str], None]] = None,
    cwd: Optional[Path] = None,
    timeout_sec: float = 180.0,
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """Generate viral topics and director prompts for a collection of reels."""
    _log = log or (lambda msg: logger.info(msg))
    if not reels:
        return [], None
    fetch_top_reels_transcripts(reels[:5])
    targets = [{"name": r.get("author_name") or r.get("author_handle", "Reel"), "url": r.get("url") or r.get("reel_url", "")} for r in reels]
    if agent_id and cwd:
        return suggest_topics(
            agent_id=agent_id,
            sheet_name=sheet_name,
            targets=targets,
            reels=reels,
            cwd=cwd,
            timeout_sec=timeout_sec,
            log=_log,
            model=model,
            actor_profile=actor_profile,
        )
    return heuristic_topics(sheet_name, reels, actor_profile=actor_profile, limit=3), None
