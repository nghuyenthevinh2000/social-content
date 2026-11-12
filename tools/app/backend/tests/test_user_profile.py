from contextlib import contextmanager
import pytest
from tools.app.backend.user_profile import normalize_actor_profile, UserProfileStore
import tools.app.backend.user_profile as user_profile_mod


def test_normalize_actor_profile():
    # Defaults
    assert normalize_actor_profile(None) == {
        "gender": "male",
        "age": 28,
        "name": "",
        "voice_tone": "Bắc",
    }

    # Vietnamese aliases & lowercase
    assert normalize_actor_profile({"gender": "nam", "age": 32})["gender"] == "male"
    assert normalize_actor_profile({"gender": "nữ", "age": 22})["gender"] == "female"
    assert normalize_actor_profile({"gender": "nu", "age": 22})["gender"] == "female"
    assert normalize_actor_profile({"gender": "female", "age": "26"}) == {
        "gender": "female",
        "age": 26,
        "name": "",
        "voice_tone": "Bắc",
    }

    # Age boundary checks
    assert normalize_actor_profile({"age": 5})["age"] == 28
    assert normalize_actor_profile({"age": 120})["age"] == 28
    assert normalize_actor_profile({"age": "invalid"})["age"] == 28
    assert normalize_actor_profile({"age": 45})["age"] == 45


@contextmanager
def _failing_cm():
    raise RuntimeError("DB offline")
    yield


def test_user_profile_store_memory_fallback(monkeypatch):
    monkeypatch.setattr(user_profile_mod, "ro", _failing_cm)
    monkeypatch.setattr(user_profile_mod, "tx", _failing_cm)

    store = UserProfileStore()

    # Unseen user returns defaults
    p = store.get_profile("test-user-1")
    assert p["user_id"] == "test-user-1"
    assert p["gender"] == "male"
    assert p["age"] == 28

    # Save updates profile
    saved = store.save_profile("test-user-1", {
        "gender": "female",
        "age": 27,
        "name": "Linh",
        "voice_tone": "friendly",
    })
    assert saved["gender"] == "female"
    assert saved["age"] == 27
    assert saved["name"] == "Linh"
    assert saved["voice_tone"] == "friendly"

    # Fetch retrieved saved record
    retrieved = store.get_profile("test-user-1")
    assert retrieved["gender"] == "female"
    assert retrieved["age"] == 27
    assert retrieved["name"] == "Linh"
