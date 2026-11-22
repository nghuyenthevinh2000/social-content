"""ACP-powered Brand Assistant chat for brand profile setup (v1) and free keyword discovery."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional

from tools.app.backend.acp import ACPClient
from tools.app.backend.research_engine.research import WORKSPACE, configured_agent
from tools.app.backend.user_profile import BRAND_FIELDS, normalize_brand_keywords, normalize_language
from tools.loop.viral_analyzer.keyword_research.prompt import resolve_language

ALLOWED_MODES = ("brand_setup", "keyword_explore")
MAX_HISTORY_MESSAGES = 12
MAX_MESSAGE_CHARS = 2000
MAX_RESPONSE_KEYWORDS = 3


def _sanitize_messages(messages: Any) -> List[Dict[str, str]]:
    if not isinstance(messages, list):
        raise ValueError("messages must be a non-empty list.")
    cleaned: List[Dict[str, str]] = []
    for item in messages:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "").strip().lower()
        if role not in ("user", "assistant"):
            continue
        content = str(item.get("content") or "").strip()[:MAX_MESSAGE_CHARS]
        if not content:
            continue
        cleaned.append({"role": role, "content": content})
    if not cleaned:
        raise ValueError("messages must contain at least one non-empty message.")
    return cleaned[-MAX_HISTORY_MESSAGES:]


def build_brand_assistant_prompt(
    mode: str,
    messages: List[Dict[str, str]],
    brand_profile: Optional[Dict[str, Any]] = None,
    language: str = "vi",
) -> str:
    if mode not in ALLOWED_MODES:
        raise ValueError(f"Unsupported mode: {mode}. Allowed modes: {', '.join(ALLOWED_MODES)}")

    lang = resolve_language(language)
    lang_instruction = "Respond in Vietnamese." if lang == "vi" else "Respond in English."
    brand = brand_profile if isinstance(brand_profile, dict) else {}

    history_lines = []
    for msg in messages:
        speaker = "User" if msg["role"] == "user" else "Assistant"
        history_lines.append(f"{speaker}: {msg['content']}")
    transcript = "\n".join(history_lines)

    if mode == "brand_setup":
        current_brand = {
            "identity": str(brand.get("identity") or ""),
            "audience": str(brand.get("audience") or ""),
            "differentiator": str(brand.get("differentiator") or ""),
            "tone": str(brand.get("tone") or ""),
            "keywords": normalize_brand_keywords(brand.get("keywords")),
        }
        return (
            "You are a focused Brand Setup Assistant.\n"
            f"{lang_instruction}\n"
            "STRICT SCOPE: Your ONLY purpose is to interview the user and help them determine a workable first version (v1, can be refined later) of their #brand-profile:\n"
            "1. identity: When people think of the user/brand, what should they remember?\n"
            "2. audience: Who is the target audience / customer group?\n"
            "3. differentiator: What makes viewers remember and choose them over other channels?\n"
            "4. tone: If the brand were a person, how would they speak (style & tone)?\n"
            "5. keywords: On-brand search keywords for viral content research.\n"
            "If the user asks for anything outside setting up or refining this brand profile and its on-brand keywords, politely refuse and redirect back to these 4 questions and on-brand keywords.\n"
            "Ask 1-2 concise, practical questions at a time when details are missing. Once you have enough context (even if rough), propose a concrete v1 draft in `brand_draft` plus 3 focused on-brand `keywords` and set `ready` to true.\n\n"
            f"Current saved #brand-profile:\n{json.dumps(current_brand, ensure_ascii=False)}\n\n"
            f"Conversation so far:\n{transcript}\n\n"
            "Reply ONLY with a valid JSON object matching this exact schema (no markdown outside the JSON):\n"
            '{"reply": "your conversational response", '
            '"brand_draft": {"identity": "...", "audience": "...", "differentiator": "...", "tone": "..."}, '
            '"keywords": ["kw1", "kw2"], '
            '"ready": false}'
        )

    return (
        "You are a focused Brand Keyword Explorer.\n"
        f"{lang_instruction}\n"
        "STRICT SCOPE: Your ONLY purpose is to act as the keyword-expansion step before cross-platform brand/competitor research—expanding the user's query into concrete search keywords so they can launch the search directly from the chat.\n"
        "Allow free-range exploration — the user may freely explore niches or angles even if they are off-brand. Do NOT edit or draft a brand profile.\n"
        "Include helpful expansions such as abbreviations/full forms (e.g. medical or slang terms) and natural Vietnamese/English equivalents alongside specific 2-5 word search queries.\n"
        "If the user asks for anything unrelated to keyword discovery or exploring topics/brands, politely refuse and redirect back to keyword exploration.\n"
        "Provide 3 specific, actionable search keywords in `keywords`.\n\n"
        f"Conversation so far:\n{transcript}\n\n"
        "Reply ONLY with a valid JSON object matching this exact schema (no markdown outside the JSON):\n"
        '{"reply": "your concise explanation of the keyword angles", "keywords": ["kw1", "kw2", "kw3"]}'
    )


def _extract_json_object(raw_text: str) -> Optional[Dict[str, Any]]:
    text = (raw_text or "").strip()
    if not text:
        return None
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    candidates = [fenced.group(1)] if fenced else []
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace > first_brace:
        candidates.append(text[first_brace : last_brace + 1])
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except (ValueError, TypeError):
            continue
    return None


def parse_assistant_response(raw_text: str, mode: str) -> Dict[str, Any]:
    if mode not in ALLOWED_MODES:
        raise ValueError(f"Unsupported mode: {mode}. Allowed modes: {', '.join(ALLOWED_MODES)}")

    parsed = _extract_json_object(raw_text)
    if not parsed:
        return {
            "reply": (raw_text or "").strip(),
            "brand_draft": {},
            "keywords": [],
            "ready": False,
        }

    reply = str(parsed.get("reply") or "").strip() or (raw_text or "").strip()
    keywords = normalize_brand_keywords(parsed.get("keywords"), limit=MAX_RESPONSE_KEYWORDS)

    if mode == "keyword_explore":
        return {
            "reply": reply,
            "brand_draft": {},
            "keywords": keywords,
            "ready": False,
        }

    raw_draft = parsed.get("brand_draft")
    brand_draft: Dict[str, str] = {}
    if isinstance(raw_draft, dict):
        for field in BRAND_FIELDS:
            val = str(raw_draft.get(field) or "").strip()[:500]
            if val:
                brand_draft[field] = val

    return {
        "reply": reply,
        "brand_draft": brand_draft,
        "keywords": keywords,
        "ready": bool(parsed.get("ready")),
    }


def run_brand_assistant_chat(
    mode: str,
    messages: List[Dict[str, str]],
    brand_profile: Optional[Dict[str, Any]] = None,
    language: str = "vi",
    timeout_sec: Optional[float] = None,
) -> Dict[str, Any]:
    if mode not in ALLOWED_MODES:
        raise ValueError(f"Unsupported mode: {mode}. Allowed modes: {', '.join(ALLOWED_MODES)}")
    sanitized_messages = _sanitize_messages(messages)
    prompt = build_brand_assistant_prompt(
        mode=mode,
        messages=sanitized_messages,
        brand_profile=brand_profile,
        language=language,
    )

    agent = configured_agent()
    effective_timeout = timeout_sec if timeout_sec is not None else float(os.environ.get("BRAND_ASSISTANT_ACP_TIMEOUT", "90"))
    # ponytail: stateless per-turn ACP replay avoids persistent subprocess leaks/deadlocks; upgrade to pooled sessions if turn latency matters.
    client = ACPClient(agent["command"], cwd=Path(WORKSPACE), timeout_sec=effective_timeout)
    try:
        client.initialize()
        session_id = client.new_session()
        raw_text = client.prompt(session_id, prompt)
    finally:
        client.close()

    parsed = parse_assistant_response(raw_text, mode)
    return {"mode": mode, **parsed}
