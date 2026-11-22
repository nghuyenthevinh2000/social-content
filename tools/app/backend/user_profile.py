"""User actor profile storage and management for consistent video and voice generation."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any, Dict, List, Optional

from tools.app.backend.db import ro, tx


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

DEFAULT_PROFILE: Dict[str, Any] = {
    "gender": "male",
    "age": 28,
    "name": "",
    "voice_tone": "Bắc",
    "language": "vi",
}


def normalize_language(value: Any) -> str:
    raw = str(value or "vi").strip().lower()
    if raw in ("en", "eng", "english") or raw.startswith("en-"):
        return "en"
    return "vi"

BRAND_FIELDS = ("identity", "audience", "differentiator", "tone")
MAX_BRAND_KEYWORDS = 20
MAX_BRAND_KEYWORD_LEN = 80


def normalize_brand_keywords(value: Any, limit: int = MAX_BRAND_KEYWORDS) -> List[str]:
    if isinstance(value, str):
        items = [part.strip() for part in value.split(",")]
    elif isinstance(value, list):
        items = [str(part or "").strip() for part in value]
    else:
        return []
    seen: set[str] = set()
    result: List[str] = []
    for item in items:
        cleaned = item[:MAX_BRAND_KEYWORD_LEN].strip()
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(cleaned)
        if len(result) >= limit:
            break
    return result


def normalize_brand_profile(data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    raw = data if isinstance(data, dict) else {}
    normalized: Dict[str, Any] = {field: str(raw.get(field) or "").strip()[:500] for field in BRAND_FIELDS}
    normalized["keywords"] = normalize_brand_keywords(raw.get("keywords"))
    return normalized


def _parse_brand_json(raw: Any) -> Dict[str, Any]:
    if isinstance(raw, dict):
        return normalize_brand_profile(raw)
    if isinstance(raw, str) and raw.strip():
        try:
            return normalize_brand_profile(json.loads(raw))
        except (ValueError, TypeError):
            pass
    return normalize_brand_profile(None)


def normalize_actor_profile(data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    raw = dict(data or {})
    raw_gender = str(raw.get("gender") or "male").strip().lower()
    gender = "female" if raw_gender in ("female", "nữ", "nu", "woman") else "male"
    try:
        age = int(raw.get("age", 28))
    except (ValueError, TypeError):
        age = 28
    if age < 10 or age > 100:
        age = 28
    raw_tone = str(raw.get("voice_tone") or "Bắc").strip()
    tone_lower = raw_tone.lower()
    if tone_lower in ("bắc", "bac", "north", "northern"):
        tone = "Bắc"
    elif tone_lower in ("nam", "south", "southern"):
        tone = "Nam"
    elif tone_lower in ("trung", "central"):
        tone = "Trung"
    else:
        tone = "Bắc" if tone_lower in ("natural", "") else raw_tone[:50]
    name = str(raw.get("name") or "").strip()[:100]
    return {
        "gender": gender,
        "age": age,
        "name": name,
        "voice_tone": tone,
    }


class UserProfileStore:
    def __init__(self) -> None:
        self._memory_cache: Dict[str, Dict[str, Any]] = {}

    def get_profile(self, user_id: str) -> Dict[str, Any]:
        try:
            with ro() as conn:
                cur = conn.execute(
                    "SELECT gender, age, name, voice_tone, brand_json, language, updated_at FROM user_profiles WHERE user_id = %s",
                    (user_id,),
                )
                row = cur.fetchone()
                if row:
                    return {
                        "user_id": user_id,
                        "gender": row[0],
                        "age": row[1],
                        "name": row[2] or "",
                        "voice_tone": row[3] or "Bắc",
                        "brand": _parse_brand_json(row[4]),
                        "language": normalize_language(row[5]),
                        "updated_at": row[6],
                    }
        except Exception:
            pass

        cached = self._memory_cache.get(user_id)
        if cached:
            return dict(cached)

        return {
            "user_id": user_id,
            "gender": "male",
            "age": 28,
            "name": "",
            "voice_tone": "Bắc",
            "brand": normalize_brand_profile(None),
            "language": "vi",
            "updated_at": now_iso(),
        }

    def save_profile(self, user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        existing = self.get_profile(user_id)
        merged_actor = {
            "gender": data.get("gender", existing.get("gender")),
            "age": data.get("age", existing.get("age")),
            "name": data.get("name", existing.get("name")),
            "voice_tone": data.get("voice_tone", existing.get("voice_tone")),
        }
        norm = normalize_actor_profile(merged_actor)
        brand = (
            normalize_brand_profile({**(existing.get("brand") or {}), **data["brand"]})
            if isinstance(data.get("brand"), dict)
            else normalize_brand_profile(existing.get("brand"))
        )
        language = normalize_language(data.get("language", existing.get("language", "vi")))
        updated = now_iso()
        record = {
            "user_id": user_id,
            "gender": norm["gender"],
            "age": norm["age"],
            "name": norm["name"],
            "voice_tone": norm["voice_tone"],
            "brand": brand,
            "language": language,
            "updated_at": updated,
        }
        self._memory_cache[user_id] = record

        try:
            with tx() as conn:
                conn.execute(
                    """
                    INSERT INTO user_profiles (user_id, gender, age, name, voice_tone, brand_json, language, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (user_id) DO UPDATE SET
                        gender = EXCLUDED.gender,
                        age = EXCLUDED.age,
                        name = EXCLUDED.name,
                        voice_tone = EXCLUDED.voice_tone,
                        brand_json = EXCLUDED.brand_json,
                        language = EXCLUDED.language,
                        updated_at = EXCLUDED.updated_at
                    """,
                    (
                        record["user_id"],
                        record["gender"],
                        record["age"],
                        record["name"],
                        record["voice_tone"],
                        json.dumps(brand, ensure_ascii=False),
                        record["language"],
                        record["updated_at"],
                    ),
                )
        except Exception:
            pass

        return record


USER_PROFILE_STORE = UserProfileStore()
