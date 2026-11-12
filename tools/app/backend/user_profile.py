"""User actor profile storage and management for consistent video and voice generation."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from tools.app.backend.db import ro, tx


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

DEFAULT_PROFILE: Dict[str, Any] = {
    "gender": "male",
    "age": 28,
    "name": "",
    "voice_tone": "Bắc",
}


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
                    "SELECT gender, age, name, voice_tone, updated_at FROM user_profiles WHERE user_id = %s",
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
                        "updated_at": row[4],
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
            "updated_at": now_iso(),
        }

    def save_profile(self, user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        norm = normalize_actor_profile(data)
        updated = now_iso()
        record = {
            "user_id": user_id,
            "gender": norm["gender"],
            "age": norm["age"],
            "name": norm["name"],
            "voice_tone": norm["voice_tone"],
            "updated_at": updated,
        }
        self._memory_cache[user_id] = record

        try:
            with tx() as conn:
                conn.execute(
                    """
                    INSERT INTO user_profiles (user_id, gender, age, name, voice_tone, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (user_id) DO UPDATE SET
                        gender = EXCLUDED.gender,
                        age = EXCLUDED.age,
                        name = EXCLUDED.name,
                        voice_tone = EXCLUDED.voice_tone,
                        updated_at = EXCLUDED.updated_at
                    """,
                    (record["user_id"], record["gender"], record["age"], record["name"], record["voice_tone"], record["updated_at"]),
                )
        except Exception:
            pass

        return record


USER_PROFILE_STORE = UserProfileStore()
