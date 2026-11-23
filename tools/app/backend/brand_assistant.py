"""ACP-powered Brand Assistant chat for brand profile setup (v1) and free keyword discovery."""

from __future__ import annotations

import atexit
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import re
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from tools.app.backend.acp import ACPClient, ACPError
from tools.app.backend.research_engine.research import WORKSPACE, configured_agent
from tools.app.backend.user_profile import BRAND_FIELDS, normalize_brand_keywords, normalize_language
from tools.loop.viral_analyzer.keyword_research.prompt import resolve_language

ALLOWED_MODES = ("brand_setup",)
MAX_HISTORY_MESSAGES = 12
MAX_MESSAGE_CHARS = 2000
MAX_RESPONSE_KEYWORDS = 3
DEFAULT_SESSION_TTL_SEC = 600.0
MAX_CACHED_SESSIONS = 16


@dataclass
class _CachedSession:
    client: ACPClient
    session_id: str
    command: List[str]
    last_used: float
    lock: threading.Lock = field(default_factory=threading.Lock)


_SESSIONS: Dict[Tuple[str, str], _CachedSession] = {}
_SESSIONS_LOCK = threading.Lock()


def _session_ttl_sec() -> float:
    try:
        return max(30.0, float(os.environ.get("BRAND_ASSISTANT_SESSION_TTL", str(DEFAULT_SESSION_TTL_SEC))))
    except ValueError:
        return DEFAULT_SESSION_TTL_SEC


def _close_quietly(client: ACPClient) -> None:
    try:
        client.close()
    except Exception:
        pass


def _evict_expired_locked(now: float) -> None:
    ttl = _session_ttl_sec()
    expired = [k for k, entry in _SESSIONS.items() if (now - entry.last_used) > ttl or not getattr(entry.client, "is_alive", True)]
    for k in expired:
        entry = _SESSIONS.pop(k, None)
        if entry:
            _close_quietly(entry.client)
    while len(_SESSIONS) >= MAX_CACHED_SESSIONS:
        oldest_key = min(_SESSIONS, key=lambda k: _SESSIONS[k].last_used)
        entry = _SESSIONS.pop(oldest_key, None)
        if entry:
            _close_quietly(entry.client)


def evict_brand_assistant_session(user_id: str, mode: Optional[str] = None) -> None:
    with _SESSIONS_LOCK:
        keys = [(user_id, mode)] if mode else [k for k in _SESSIONS if k[0] == user_id]
        for k in keys:
            entry = _SESSIONS.pop(k, None)
            if entry:
                _close_quietly(entry.client)


def close_all_brand_assistant_sessions() -> None:
    with _SESSIONS_LOCK:
        entries = list(_SESSIONS.values())
        _SESSIONS.clear()
    for entry in entries:
        _close_quietly(entry.client)


atexit.register(close_all_brand_assistant_sessions)


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
        "STRICT SCOPE: Your ONLY purpose is to continuously build and refine a workable brand profile through an iterative loop:\n"
        "  determine a workable brand version -> learn from user feedback -> determine a sharper brand version.\n"
        "Brand profile fields (keep every field concise and grounded ONLY in what the user said — NEVER invent, pad, or embellish extra claims):\n"
        "1. identity: Short, punchy, and easy to say aloud (3-8 words, max ~60 chars; e.g. 'Nike = athletic performance' or 'Chin-su = nước tương').\n"
        "2. audience: One concise, concrete phrase for the target customer group.\n"
        "3. differentiator: One short phrase for why viewers remember and choose them.\n"
        "4. tone: 2-4 words describing how the brand speaks.\n"
        "5. keywords: 3 focused on-brand search keywords for viral content research.\n"
        "If the user asks for anything outside building or refining this brand profile and its on-brand keywords, politely refuse and redirect back to the brand profile loop.\n"
        "How the loop works:\n"
        "- If details are missing, ask 1-2 concise, practical questions first. As soon as there is enough signal (or an existing saved brand profile), propose a concrete, workable `brand_draft` + 3 focused `keywords` and set `ready` to true.\n"
        "- Treat every user reply, critique, or market/audience observation as feedback: preserve what already works, revise what feels off, explain briefly what changed in this version, and ask 1-2 targeted feedback questions to guide the next iteration.\n\n"
        f"Current saved brand profile:\n{json.dumps(current_brand, ensure_ascii=False)}\n\n"
        f"Conversation so far:\n{transcript}\n\n"
        "Reply ONLY with a valid JSON object matching this exact schema (no markdown outside the JSON):\n"
        '{"reply": "your conversational response", '
        '"brand_draft": {"identity": "...", "audience": "...", "differentiator": "...", "tone": "..."}, '
        '"keywords": ["kw1", "kw2", "kw3"], '
        '"ready": false}'
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


def build_brand_assistant_followup_prompt(
    mode: str,
    latest_user_message: str,
    brand_profile: Optional[Dict[str, Any]] = None,
    language: str = "vi",
) -> str:
    if mode not in ALLOWED_MODES:
        raise ValueError(f"Unsupported mode: {mode}. Allowed modes: {', '.join(ALLOWED_MODES)}")
    lang = resolve_language(language)
    lang_instruction = "Respond in Vietnamese." if lang == "vi" else "Respond in English."
    brand = brand_profile if isinstance(brand_profile, dict) else {}

    current_brand = {
        "identity": str(brand.get("identity") or ""),
        "audience": str(brand.get("audience") or ""),
        "differentiator": str(brand.get("differentiator") or ""),
        "tone": str(brand.get("tone") or ""),
        "keywords": normalize_brand_keywords(brand.get("keywords")),
    }
    return (
        f"{lang_instruction}\n"
        f"Current saved brand profile:\n{json.dumps(current_brand, ensure_ascii=False)}\n\n"
        f"User: {latest_user_message}\n\n"
        "Stay strictly in Brand Setup Assistant scope (short, grounded fields; never invent claims). "
        "Reply ONLY with valid JSON:\n"
        '{"reply": "...", "brand_draft": {"identity": "...", "audience": "...", "differentiator": "...", "tone": "..."}, '
        '"keywords": ["kw1", "kw2", "kw3"], "ready": false}'
    )


def run_brand_assistant_chat(
    mode: str,
    messages: List[Dict[str, str]],
    brand_profile: Optional[Dict[str, Any]] = None,
    language: str = "vi",
    timeout_sec: Optional[float] = None,
    user_id: Optional[str] = None,
) -> Dict[str, Any]:
    if mode not in ALLOWED_MODES:
        raise ValueError(f"Unsupported mode: {mode}. Allowed modes: {', '.join(ALLOWED_MODES)}")
    sanitized_messages = _sanitize_messages(messages)
    full_prompt = build_brand_assistant_prompt(
        mode=mode,
        messages=sanitized_messages,
        brand_profile=brand_profile,
        language=language,
    )

    agent = configured_agent()
    effective_timeout = timeout_sec if timeout_sec is not None else float(os.environ.get("BRAND_ASSISTANT_ACP_TIMEOUT", "90"))

    if not user_id:
        client = ACPClient(agent["command"], cwd=Path(WORKSPACE), timeout_sec=effective_timeout)
        try:
            client.initialize()
            session_id = client.new_session()
            raw_text = client.prompt(session_id, full_prompt)
        finally:
            client.close()
        return {"mode": mode, **parse_assistant_response(raw_text, mode)}

    if len(sanitized_messages) == 1:
        evict_brand_assistant_session(user_id, mode)

    cache_key = (user_id, mode)
    cached: Optional[_CachedSession] = None
    with _SESSIONS_LOCK:
        _evict_expired_locked(time.monotonic())
        candidate = _SESSIONS.get(cache_key)
        if candidate and candidate.command == agent["command"] and getattr(candidate.client, "is_alive", True):
            cached = candidate

    if cached is not None:
        followup_prompt = build_brand_assistant_followup_prompt(
            mode=mode,
            latest_user_message=sanitized_messages[-1]["content"],
            brand_profile=brand_profile,
            language=language,
        )
        try:
            with cached.lock:
                raw_text = cached.client.prompt(cached.session_id, followup_prompt)
                cached.last_used = time.monotonic()
            return {"mode": mode, **parse_assistant_response(raw_text, mode)}
        except ACPError:
            evict_brand_assistant_session(user_id, mode)

    client = ACPClient(agent["command"], cwd=Path(WORKSPACE), timeout_sec=effective_timeout)
    try:
        client.initialize()
        session_id = client.new_session()
        raw_text = client.prompt(session_id, full_prompt)
    except Exception:
        _close_quietly(client)
        raise

    entry = _CachedSession(
        client=client,
        session_id=session_id,
        command=list(agent["command"]),
        last_used=time.monotonic(),
    )
    with _SESSIONS_LOCK:
        _evict_expired_locked(time.monotonic())
        old = _SESSIONS.pop(cache_key, None)
        if old:
            _close_quietly(old.client)
        _SESSIONS[cache_key] = entry

    return {"mode": mode, **parse_assistant_response(raw_text, mode)}
