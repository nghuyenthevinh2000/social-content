"""Language-aware prompt builders (EN / VI) for Keyword Research."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional


def resolve_language(language: Optional[str] = None) -> str:
    """Normalize user default language to 'en' or 'vi' (default 'vi')."""
    norm = str(language or "vi").strip().lower()
    if norm in ("en", "eng", "english") or norm.startswith("en-"):
        return "en"
    return "vi"


def build_expand_keyword_prompt(keyword: str, language: Optional[str] = None) -> str:
    """Return EN or VI prompt for expanding a search keyword into 2 related terms."""
    if resolve_language(language) == "en":
        return (
            f'Expand the search keyword "{keyword}" into JSON with two short search terms:\n'
            '{"abbreviation": "<medical/slang full form or acronym, or empty>", '
            '"vi": "<natural Vietnamese translation, or empty>"}\n'
            "Return ONLY valid JSON."
        )
    return (
        f'Mở rộng từ khoá tìm kiếm "{keyword}" thành JSON gồm hai cụm từ tìm kiếm ngắn:\n'
        '{"abbreviation": "<dạng đầy đủ hoặc từ viết tắt chuyên ngành/slang, hoặc rỗng>", '
        '"vi": "<bản dịch tiếng Việt tự nhiên, hoặc rỗng>"}\n'
        "CHỈ trả về JSON hợp lệ."
    )


def build_creator_relevance_prompt(
    keyword: str,
    items: List[Dict[str, Any]],
    language: Optional[str] = None,
) -> str:
    """Return EN or VI prompt for assessing creator relevance to the search keyword."""
    payload = json.dumps(items, ensure_ascii=False)
    if resolve_language(language) == "en":
        return (
            f'Assess how each creator relates to the search keyword "{keyword}" based on their profile and matched video titles.\n'
            "Return ONLY a JSON object mapping each `key` to "
            '{"relevance": "direct|adjacent|tangential|off_topic", "why_relevant": "<1 concise English sentence explaining why relevant>"}.\n'
            f"Creators:\n{payload}"
        )
    return (
        f'Đánh giá mức độ liên quan của từng creator với từ khoá tìm kiếm "{keyword}" dựa trên hồ sơ và các tiêu đề video khớp.\n'
        "CHỈ trả về một JSON object ánh xạ mỗi `key` tới "
        '{"relevance": "direct|adjacent|tangential|off_topic", "why_relevant": "<1 câu ngắn gọn bằng tiếng Việt giải thích vì sao liên quan>"}.\n'
        f"Creators:\n{payload}"
    )
