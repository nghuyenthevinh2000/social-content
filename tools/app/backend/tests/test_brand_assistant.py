import pytest

from tools.app.backend import brand_assistant
from tools.app.backend.user_profile import normalize_brand_profile


def test_normalize_brand_profile_keywords():
    norm = normalize_brand_profile({
        "identity": "  Skincare coach  ",
        "keywords": ["Acne", "acne", "  Minimal Routine  ", "", "SPF"],
    })
    assert norm["identity"] == "Skincare coach"
    assert norm["keywords"] == ["Acne", "Minimal Routine", "SPF"]

    norm_str = normalize_brand_profile({"keywords": "skincare, Skincare, retinol , "})
    assert norm_str["keywords"] == ["skincare", "retinol"]

    assert normalize_brand_profile(None)["keywords"] == []


def test_brand_assistant_rejects_invalid_mode():
    with pytest.raises(ValueError, match="Unsupported mode"):
        brand_assistant.build_brand_assistant_prompt("invalid_mode", [{"role": "user", "content": "hi"}])

    with pytest.raises(ValueError, match="Unsupported mode"):
        brand_assistant.run_brand_assistant_chat("other", [{"role": "user", "content": "hi"}])


def test_parse_assistant_response_enforces_mode_boundaries():
    raw_fenced = (
        '```json\n'
        '{"reply": "Try these angles", '
        '"brand_draft": {"identity": "Should be stripped", "tone": "Direct"}, '
        '"keywords": ["viral skincare", "Viral Skincare", "morning routine"], '
        '"ready": true}\n'
        '```'
    )
    explore = brand_assistant.parse_assistant_response(raw_fenced, "keyword_explore")
    assert explore["reply"] == "Try these angles"
    assert explore["brand_draft"] == {}
    assert explore["ready"] is False
    assert explore["keywords"] == ["viral skincare", "morning routine"]

    setup = brand_assistant.parse_assistant_response(raw_fenced, "brand_setup")
    assert setup["brand_draft"] == {"identity": "Should be stripped", "tone": "Direct"}
    assert setup["ready"] is True
    assert setup["keywords"] == ["viral skincare", "morning routine"]

    fallback = brand_assistant.parse_assistant_response("Plain text reply", "brand_setup")
    assert fallback == {"reply": "Plain text reply", "brand_draft": {}, "keywords": [], "ready": False}

    capped = brand_assistant.parse_assistant_response(
        '{"reply": "ok", "keywords": ["k1", "k2", "k3", "k4", "k5"]}',
        "keyword_explore",
    )
    assert capped["keywords"] == ["k1", "k2", "k3"]


def test_run_brand_assistant_chat_uses_acp_client(monkeypatch):
    calls = []

    class FakeACPClient:
        def __init__(self, command, cwd, timeout_sec=90.0):
            calls.append(("init_client", command, timeout_sec))

        def initialize(self):
            calls.append(("initialize",))
            return {}

        def new_session(self):
            calls.append(("new_session",))
            return "sess-1"

        def prompt(self, session_id, text):
            calls.append(("prompt", session_id, "Brand Setup Assistant" in text))
            return '{"reply": "Got it!", "brand_draft": {"identity": "Home baker"}, "keywords": ["sourdough"], "ready": true}'

        def close(self):
            calls.append(("close",))

    monkeypatch.setattr(brand_assistant, "configured_agent", lambda: {"id": "agy", "command": ["agy", "acp"]})
    monkeypatch.setattr(brand_assistant, "ACPClient", FakeACPClient)

    res = brand_assistant.run_brand_assistant_chat(
        mode="brand_setup",
        messages=[{"role": "user", "content": "I bake sourdough at home"}],
        brand_profile={"identity": ""},
        language="en",
    )

    assert res["mode"] == "brand_setup"
    assert res["reply"] == "Got it!"
    assert res["brand_draft"] == {"identity": "Home baker"}
    assert res["keywords"] == ["sourdough"]
    assert res["ready"] is True
    assert calls[0][1] == ["agy", "acp"]
    assert ("initialize",) in calls
    assert ("new_session",) in calls
    assert ("prompt", "sess-1", True) in calls
    assert calls[-1] == ("close",)


def test_run_viral_video_search_uses_pre_expanded_queries(tmp_path):
    from tools.loop.viral_analyzer import runtime
    from tools.loop.viral_analyzer.keyword_research import pipeline

    def fail_expand(*_args, **_kwargs):
        raise AssertionError("expand_keyword should not run when pre-expanded queries are provided")

    def fake_glasser(_provider, _endpoint, _version, _payload, _cache_dir, **_kwargs):
        return {}, "empty", None

    ctx = runtime.EngineContext(agent_runner=lambda _p: "{}")
    orig_expand = pipeline.expand_keyword
    orig_glasser = pipeline._glasser_run_json
    pipeline.expand_keyword = fail_expand
    pipeline._glasser_run_json = fake_glasser
    try:
        res = pipeline.run_viral_video_search(
            "kw1",
            tmp_path,
            options={"platforms": ("youtube",)},
            ctx=ctx,
            queries=[{"kind": "original", "text": "kw1"}, {"kind": "expanded", "text": "kw2"}],
        )
    finally:
        pipeline.expand_keyword = orig_expand
        pipeline._glasser_run_json = orig_glasser

    assert [q["text"] for q in res["queries"]] == ["kw1", "kw2"]
