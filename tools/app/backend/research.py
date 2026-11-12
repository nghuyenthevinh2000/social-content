"""Excel ingestion, per-sheet pipeline orchestration and ACP topic suggestions."""

from __future__ import annotations

from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
import unicodedata
import urllib.error
import urllib.request
import uuid
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlparse

import openpyxl

from tools.app.backend import blobs
from tools.app.backend.acp import ACPClient, ACPError
from tools.app.backend.errors import (
    AppError,
    ErrorAggregator,
    ErrorCategory,
    ErrorSeverity,
    handle_acp_error,
    handle_glasser_error,
)
from tools.app.backend.profiles import (
    clean_name,
    facebook_handle,
    is_facebook_url,
    parse_workbook,
    resolve_xlsx_bytes,
    slugify,
    SocialProfileStore,
    PROFILE_STORE,
    RUNS_ROOT,
)
from tools.app.backend.store import JobStore, now_iso
from tools.app.backend.video_engine import get_video_duration
from tools.loop.viral_analyzer.config import load_config
from tools.loop.viral_analyzer.glasser import ensure_glasser_env
from tools.loop.viral_analyzer.pipeline import run_analyzer_pipeline

ensure_glasser_env()

_facebook_handle = facebook_handle
_is_facebook_url = is_facebook_url
_clean_name = clean_name

WORKSPACE = Path(__file__).resolve().parents[3]

AGENT_PRESETS: List[Dict[str, Any]] = [
    {
        "id": "agy",
        "label": "Antigravity (agy)",
        "command": ["agy", "acp"],
        "detect": "agy",
        "login_hint": "agy",
        "note": "Gemini/Antigravity CLI ở chế độ ACP.",
    },
    {
        "id": "opencode",
        "label": "OpenCode",
        "command": ["opencode", "acp"],
        "detect": "opencode",
        "login_hint": "opencode auth login",
        "note": "Agent mặc định trong repo.",
    },
    {
        "id": "claude",
        "label": "Claude Code",
        "command": ["npx", "-y", "@zed-industries/claude-code-acp"],
        "detect": "npx",
        "login_hint": "claude",
        "note": "Lần đầu sẽ tải ACP adapter qua npx.",
    },
    {
        "id": "codex",
        "label": "Codex",
        "command": ["npx", "-y", "@zed-industries/codex-acp"],
        "detect": "npx",
        "login_hint": "codex login",
        "note": "Lần đầu sẽ tải ACP adapter qua npx.",
    },
]


def configured_agent() -> Dict[str, Any]:
    """Harness from VIRAL_APP_AGENT, else the first installed preset."""
    agent_id = os.environ.get("VIRAL_APP_AGENT")
    if agent_id:
        try:
            return resolve_agent(agent_id)
        except ACPError:
            pass
    for preset in AGENT_PRESETS:
        if shutil.which(preset["detect"]):
            return resolve_agent(preset["id"])
    raise ACPError("Không tìm thấy harness nào trên máy (agy, opencode, claude, codex).")


def resolve_agent(agent_id: str, model: Optional[str] = None) -> Dict[str, Any]:
    for preset in AGENT_PRESETS:
        if preset["id"] == agent_id:
            if shutil.which(preset["detect"]) is None:
                raise ACPError(
                    f"Không tìm thấy harness '{preset['label']}' trên máy. "
                    f"Cài đặt rồi thử lại (gợi ý đăng nhập: {preset['login_hint']})."
                )
            result = dict(preset)
            if agent_id == "agy":
                selected_model = (model or os.environ.get("VIRAL_APP_AGY_MODEL", "")).strip()
                if selected_model:
                    result["model"] = selected_model
                    result["command"] = ["agy", "--model", selected_model, "acp"]
            return result
    raise ACPError(f"Harness không hợp lệ: {agent_id}")


# -- Topic generation --------------------------------------------------------
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
        reel_url = str(reel.get("url") or "").strip()
        if not reel_url and reel.get("video_id"):
            reel_url = f"https://www.facebook.com/reel/{reel['video_id']}"
        url_part = f" | reel_url: {reel_url}" if reel_url else ""
        lines.append(
            f"{index}. [P{reel.get('current_pool')} | {int(reel.get('views') or 0):,} views | "
            f"{float(reel.get('velocity_per_hour') or 0):,.0f} views/h | @{reel.get('author_handle')}{url_part}] "
            f"{title}{transcript}"
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
        key = f"P{reel.get('current_pool')}"
        pools[key] = pools.get(key, 0) + 1
    pool_text = ", ".join(f"{key}: {count}" for key, count in sorted(pools.items())) or "không có dữ liệu"
    digest = _reel_digest(reels) or "(không có reel nào trong 48 giờ)"
    dur = get_video_duration()
    hook_end = "03"
    cta_start = f"{max(4, dur - 4):02d}"

    return f"""Bạn là chiến lược gia nội dung viral cho Facebook Reels & video ngắn tiếng Việt.

NHÓM CHỦ ĐỀ: {sheet_name}
KÊNH ĐỐI THỦ: {channels}
PHÂN BỔ POOL: {pool_text}
DỮ LIỆU REEL 48 GIỜ:
{digest}

NHIỆM VỤ: Đề xuất ĐÚNG 3 chủ đề video có khả năng viral cao nhất cho nhóm chủ đề này.
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
- Cụ thể, có thể bấm máy quay làm ngay; không viết chung chung.
- Viết tiếng Việt.
- Trả về DUY NHẤT một JSON array, không markdown, không giải thích ngoài JSON.

Schema mỗi phần tử:
[
  {{
    "title": "tên chủ đề ngắn gọn, gây tò mò",
    "hook": "câu mở đầu 3 giây",
    "angle": "góc khai thác khác biệt so với đối thủ",
    "why_viral": "vì sao chủ đề này có khả năng viral, dẫn số liệu",
    "outline": ["ý 1", "ý 2", "ý 3"],
    "format": "Reels {dur}s UGC",
    "source_urls": ["url reel bằng chứng (chính xác giá trị reel_url ở trên, bắt đầu bằng https://www.facebook.com/reel/...)"],
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

    # Find the top matching reel by author handle
    for r in reels:
        r_handle = str(r.get("author_handle") or "").strip().lower()
        if r_handle and (r_handle == target_handle or target_handle in r_handle or r_handle in target_handle):
            if r.get("url"):
                return str(r["url"]).strip()
            if r.get("video_id"):
                return f"https://www.facebook.com/reel/{r['video_id']}"

    # If it is a facebook page/profile URL, route to the /reels/ tab
    if "facebook.com" in clean and not clean.endswith("/reels"):
        return f"{clean}/reels/"

    return url


def normalize_topics(
    data: Any,
    fallback: List[Dict[str, Any]],
    reels: Optional[List[Dict[str, Any]]] = None,
    sheet_name: str = "",
    actor_profile: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    if isinstance(data, dict):
        data = data.get("topics") or data.get("ideas") or [data]
    if not isinstance(data, list):
        return fallback
    topics = []
    dur = get_video_duration()
    for index, item in enumerate(data):
        if not isinstance(item, dict):
            continue
        raw_sources = _normalize_sources(item.get("source_urls") or item.get("sources"))
        sources = [_resolve_to_reel_url(u, reels or []) for u in raw_sources if u]
        if not sources and index < len(fallback):
            sources = fallback[index].get("source_urls", [])
        if not sources and reels and index < len(reels):
            top_url = reels[index].get("url") or (f"https://www.facebook.com/reel/{reels[index]['video_id']}" if reels[index].get("video_id") else None)
            if top_url:
                sources = [top_url]
        prompt_val = str(item.get("prompt") or item.get("director_prompt") or "").strip()
        if not prompt_val:
            prompt_val = format_director_prompt(item, sheet_name=sheet_name, actor_profile=actor_profile)
        elif actor_profile:
            from tools.app.backend.video_engine import _apply_actor_profile_to_structured_prompt
            prompt_val = _apply_actor_profile_to_structured_prompt(prompt_val, actor_profile)
        topics.append(
            {
                "title": str(item.get("title") or "").strip() or (fallback[index]["title"] if index < len(fallback) else "Chủ đề mới"),
                "hook": str(item.get("hook") or "").strip(),
                "angle": str(item.get("angle") or "").strip(),
                "why_viral": str(item.get("why_viral") or item.get("why") or "").strip(),
                "outline": _normalize_outline(item.get("outline")),
                "format": str(item.get("format") or f"Reels {dur}s UGC").strip(),
                "source_urls": sources,
                "prompt": prompt_val,
                "generated_by": "agent",
            }
        )
    while len(topics) < 3:
        topics.append(fallback[len(topics)])
    return topics[:3]


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
) -> List[Dict[str, Any]]:
    dur = get_video_duration()
    ranked = sorted(
        reels,
        key=lambda r: (
            int(r.get("current_pool") or 0),
            float(r.get("velocity_per_hour") or 0),
            int(r.get("views") or 0),
        ),
        reverse=True,
    )
    topics: List[Dict[str, Any]] = []
    for reel in ranked[:3]:
        title = str(reel.get("title") or "").strip() or f"Câu chuyện từ @{reel.get('author_handle')}"
        views = int(reel.get("views") or 0)
        velocity = float(reel.get("velocity_per_hour") or 0)
        t = {
            "title": f"Kể lại: {title[:90]}",
            "hook": f"Vì sao chuyện này đạt {views:,} lượt xem trong 48 giờ?",
            "angle": f"Phân tích góc P{reel.get('current_pool')} - {reel.get('pool_name', '')}, tập trung vào cảm xúc và bình luận.",
            "why_viral": f"{views:,} views, {velocity:,.0f} views/giờ, pool P{reel.get('current_pool')}.",
            "outline": [
                f"Mở bằng chi tiết gây tò mò từ video gốc của @{reel.get('author_handle')}",
                "Kể lại câu chuyện bằng hình ảnh/điện thoại, giữ nhịp nhanh",
                "Kết bằng câu hỏi mở để kéo bình luận",
            ],
            "format": f"Reels {dur}s UGC",
            "source_urls": [reel.get("url")] if reel.get("url") else [],
            "generated_by": "heuristic",
        }
        t["prompt"] = format_director_prompt(t, sheet_name=sheet_name, actor_profile=actor_profile)
        topics.append(t)

    generic = [
        {
            "title": f"'{sheet_name}': điều 90% người xem hiểu sai",
            "hook": f"Bạn đang làm sai điều cơ bản nhất về {sheet_name}?",
            "angle": "Myth-busting: nêu hiểu lầm phổ biến rồi sửa bằng ví dụ đời thường.",
            "why_viral": "Chủ đề dựa trên tên nhóm; chưa có reel 48 giờ để đối chiếu.",
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
    return topics[:3]


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
        log(f"Không có reel nào trong 48 giờ cho '{sheet_name}'; bỏ qua gợi ý chủ đề.")
        return [], None
    fallback = heuristic_topics(sheet_name, reels, actor_profile=actor_profile)
    prompt = build_topic_prompt(sheet_name, targets, reels, actor_profile=actor_profile)
    client = None
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


@contextmanager
def _harness_lock(log: Callable[[str], None]):
    """One harness session across all workers: serialized via Postgres advisory lock."""
    import psycopg
    from tools.app.backend.db import get_dsn

    with psycopg.connect(get_dsn(), autocommit=True) as conn:
        cur = conn.execute("SELECT pg_try_advisory_lock(hashtext('harness_lock'))")
        got_lock = cur.fetchone()[0]
        if not got_lock:
            log("Harness đang bận với job khác; chờ tới lượt...")
            conn.execute("SELECT pg_advisory_lock(hashtext('harness_lock'))")
        try:
            yield
        finally:
            try:
                conn.execute("SELECT pg_advisory_unlock(hashtext('harness_lock'))")
            except Exception:
                pass


# -- Jobs --------------------------------------------------------------------
STORE = JobStore()


def create_job(
    xlsx_bytes: bytes,
    filename: str,
    options: Dict[str, Any],
    client_id: str,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    xlsx_bytes, filename = resolve_xlsx_bytes(xlsx_bytes, filename)
    job_id = uuid.uuid4().hex[:12]
    blobs.put(
        f"runs/{job_id}/input.xlsx",
        xlsx_bytes,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    sheets = parse_workbook(xlsx_bytes)
    if len(sheets) == 1 and sheets[0].get("name"):
        filename = sheets[0]["name"]
    elif filename:
        filename = filename.removesuffix(".json").removesuffix(".xlsx")
    actor_prof = options.get("actor_profile")
    if not actor_prof and user_id:
        try:
            from tools.app.backend.user_profile import USER_PROFILE_STORE
            actor_prof = USER_PROFILE_STORE.get_profile(user_id)
        except Exception:
            actor_prof = None
    job = {
        "id": job_id,
        "client_id": client_id,
        "user_id": user_id,
        "actor_profile": actor_prof,
        "status": "queued",
        "filename": filename,
        "agent": options.get("agent"),
        "options": options,
        "created_at": now_iso(),
        "finished_at": None,
        "current_sheet": None,
        "cancel_requested": False,
        "sheets": [
            {
                "name": sheet["name"],
                "slug": sheet["slug"],
                "status": "pending",
                "targets": len(sheet["targets"]),
                "target_list": [
                    {"name": t.get("name") or t.get("handle") or "", "url": t.get("url") or ""}
                    for t in sheet["targets"]
                ],
                "reels": 0,
                "pool_distribution": {},
                "topics": [],
                "error": None,
                "notice": None,
                "started_at": None,
                "finished_at": None,
            }
            for sheet in sheets
        ],
        "logs": [],
    }
    STORE.put(job)
    STORE.log(job_id, f"Đã đọc {len(sheets)} sheet từ {filename}.")
    return STORE.snapshot(job_id) or job


def run_job(job: Dict[str, Any]) -> None:
    job_id, options = job["id"], job["options"]
    actor_profile = job.get("actor_profile") or options.get("actor_profile")
    if not actor_profile and job.get("user_id"):
        try:
            from tools.app.backend.user_profile import USER_PROFILE_STORE
            actor_profile = USER_PROFILE_STORE.get_profile(job["user_id"])
        except Exception:
            actor_profile = None
    with tempfile.TemporaryDirectory(prefix=f"job-{job_id}-") as tmpdir:
        run_dir = Path(tmpdir)
        try:
            input_path = run_dir / "input.xlsx"
            blobs.download(f"runs/{job_id}/input.xlsx", input_path)
            sheets = parse_workbook(input_path)
            for index, sheet in enumerate(sheets, 1):
                cur_job = STORE.snapshot(job_id)
                if not cur_job or cur_job.get("cancel_requested"):
                    STORE.update(job_id, status="cancelled", finished_at=now_iso())
                    STORE.log(job_id, "Đã dừng theo yêu cầu.")
                    return
                _process_sheet(job_id, index, len(sheets), sheet, run_dir, options, actor_profile=actor_profile)
            STORE.update(job_id, status="completed", current_sheet=None, finished_at=now_iso())
            STORE.log(job_id, "Hoàn tất toàn bộ sheet.")
        except Exception as exc:  # keep the job inspectable on unexpected failure
            STORE.update(job_id, status="failed", finished_at=now_iso(), current_sheet=None)
            STORE.log(job_id, f"Lỗi job: {exc}")


def _process_sheet(
    job_id: str,
    index: int,
    total: int,
    sheet: Dict[str, Any],
    run_dir: Path,
    options: Dict[str, Any],
    actor_profile: Optional[Dict[str, Any]] = None,
) -> None:
    sheet_name = sheet["name"]
    STORE.update(job_id, current_sheet=sheet_name)
    STORE.patch_sheet(job_id, sheet["slug"], status="running", started_at=now_iso())
    STORE.log(job_id, f"[{index}/{total}] Bắt đầu sheet '{sheet_name}' ({len(sheet['targets'])} kênh).", sheet_name)

    def log(message: str) -> None:
        STORE.log(job_id, message, sheet_name)

    reels: List[Dict[str, Any]] = []
    error: Optional[str] = None
    notice: Optional[str] = None
    payload: Dict[str, Any] = {}
    if sheet["targets"]:
        sheet_dir = run_dir / "sheets" / sheet["slug"]
        sheet_dir.mkdir(parents=True, exist_ok=True)
        shared_cache = run_dir / "cache"
        shared_cache.mkdir(parents=True, exist_ok=True)
        aggregator = ErrorAggregator(job_id=job_id)
        config = load_config(
            {
                "window_hours": options.get("window_hours", 48),
                "retention_days": 7,
                "max_videos": options.get("max_videos"),
                "storage": {
                    "video_dir": str(shared_cache / "videos"),
                    "output_file": str(sheet_dir / "viral_reels_48h.json"),
                },
                "transcription": {"engine": "qwen3", "model": "Qwen/Qwen3-ASR-0.6B", "language": None},
                "targets": sheet["targets"],
            }
        )
        try:
            payload = run_analyzer_pipeline(
                config,
                max_videos=options.get("max_videos"),
                cache_dir=shared_cache,
                media=bool(options.get("media")),
                legacy_cache=False,
                progress_cb=log,
            )
            reels = payload.get("all_reels", [])
            for err_item in payload.get("errors", []):
                handle_name = err_item.get("handle") if isinstance(err_item, dict) else None
                app_err = handle_glasser_error(err_item, handle=handle_name, log=log)
                aggregator.add(app_err)

            STORE.patch_sheet(
                job_id,
                sheet["slug"],
                reels=len(reels),
                pool_distribution=payload.get("metadata", {}).get("pool_distribution", {}),
                source_breakdown=payload.get("source_breakdown") or payload.get("metadata", {}).get("source_breakdown", {}),
            )
        except Exception as exc:
            app_err = handle_glasser_error(exc, log=log)
            aggregator.add(app_err)
            error = app_err.message
    else:
        aggregator = ErrorAggregator(job_id=job_id)
        log("Sheet không có link Facebook.")

    window_hours = options.get("window_hours", 48)
    if not reels:
        topics = []
        if not error:
            glasser_errs = aggregator.filter(category=ErrorCategory.GLASSER.value)
            if glasser_errs:
                critical = next(
                    (e for e in glasser_errs if e.severity == ErrorSeverity.CRITICAL.value),
                    glasser_errs[0],
                )
                notice = critical.format_notice()
                error = critical.message
                log(f"[Cảnh báo API] {notice}")
            elif not sheet["targets"]:
                notice = "Chưa có kênh đối thủ nào. Vui lòng cập nhật thêm danh sách kênh."
                log(notice)
            else:
                notice = f"Không tìm thấy reel mới nào trong {window_hours} giờ qua. Vui lòng cập nhật thêm danh sách kênh."
                log(notice)
    else:
        agent_choice = options.get("agent") or os.environ.get("VIRAL_APP_AGENT") or "agy"
        try:
            resolve_agent(agent_choice)
        except ACPError:
            for preset in AGENT_PRESETS:
                if shutil.which(preset["detect"]):
                    agent_choice = preset["id"]
                    break
        topics, topic_error = suggest_topics(
            agent_choice,
            sheet_name,
            sheet["targets"],
            reels,
            cwd=run_dir,
            timeout_sec=float(options.get("acp_timeout", 240)),
            log=log,
            model=options.get("agy_model") or options.get("model"),
            actor_profile=actor_profile,
        )
        if topic_error and not error:
            acp_err = handle_acp_error(topic_error, agent_id=agent_choice, log=log)
            aggregator.add(acp_err)
            error = acp_err.message

    result = {
        "sheet": sheet_name,
        "targets": sheet["targets"],
        "reels": reels,
        "source_breakdown": payload.get("source_breakdown", {}),
        "topics": topics,
        "error": error,
        "notice": notice,
        "errors": [e.to_dict() for e in aggregator.all_errors()],
    }
    result_path = run_dir / "sheets" / sheet["slug"] / "result.json"
    result_path.parent.mkdir(parents=True, exist_ok=True)
    res_bytes = json.dumps(result, ensure_ascii=False, indent=2).encode("utf-8")
    result_path.write_bytes(res_bytes)
    blobs.put(f"runs/{job_id}/result.json", res_bytes, content_type="application/json")

    STORE.patch_sheet(
        job_id,
        sheet["slug"],
        status="failed" if error else "completed",
        error=error,
        notice=notice,
        topics=topics,
        source_breakdown=payload.get("source_breakdown", {}),
        finished_at=now_iso(),
    )
    if topics:
        STORE.log(job_id, f"Xong sheet '{sheet_name}': {len(reels)} reel, {len(topics)} chủ đề.", sheet_name)
    else:
        STORE.log(job_id, f"Xong sheet '{sheet_name}': 0 reel. {notice or error or ''}".strip(), sheet_name)
