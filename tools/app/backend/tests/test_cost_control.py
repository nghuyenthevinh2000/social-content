"""Tests for cost_control, transcript leak remediation, and /api/costs/summary."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from tools.app.backend import cost_control
from tools.app.backend.db import init_schema, ro, tx
from tools.app.backend.research_engine import reel_research
from tools.loop.viral_analyzer.cache import NO_TRANSCRIPT_SENTINEL, get_cached_transcript
from tools.loop.viral_analyzer.transcriber import glasser as tr_glasser


def test_parse_glasser_stdout_exact_decimal_and_wasted():
    sample = (
        "Run ID:   23f84c7a-394a-4f7d-a8f1-1565ef3460be\n"
        "Run URL:  https://app.glasser.ai/runs/23f84c7a-394a-4f7d-a8f1-1565ef3460be\n"
        "Response: HTTP 404\n"
        "Charge:   $0.00188 (NO_RESULT)\n"
    )
    parsed = cost_control.parse_glasser_stdout(sample)
    assert parsed["run_id"] == "23f84c7a-394a-4f7d-a8f1-1565ef3460be"
    assert parsed["run_url"] == "https://app.glasser.ai/runs/23f84c7a-394a-4f7d-a8f1-1565ef3460be"
    assert parsed["http_status"] == 404
    assert parsed["cost_micro"] == 1880
    assert parsed["charge_usd"] == "0.001880"
    assert parsed["charge_clause"] == "NO_RESULT"
    assert parsed["wasted"] is True

    ok_sample = "Run ID: abc\nRun URL: https://app.glasser.ai/runs/abc\nResponse: HTTP 200\nCharge: $0.005\n"
    ok_parsed = cost_control.parse_glasser_stdout(ok_sample)
    assert ok_parsed["cost_micro"] == 5000
    assert ok_parsed["wasted"] is False


def test_cost_scope_propagates_across_threadpool():
    seen = []

    def worker(idx: int) -> str:
        scope = cost_control.current_cost_scope()
        assert scope is not None
        seen.append((idx, scope.user_id, scope.action, scope.job_id))
        cost_control.record_cost_event(
            provider="scrapecreators",
            endpoint="/v1/youtube/search",
            cost_micro=1000,
            sub_action="test_worker",
        )
        return scope.user_id

    with cost_control.cost_scope("u_thread", "keyword_search", job_id="job_t1") as scope:
        with ThreadPoolExecutor(max_workers=3) as pool:
            futs = [cost_control.submit_with_context(pool, worker, i) for i in range(4)]
            results = [f.result() for f in futs]

    assert results == ["u_thread"] * 4
    assert len(seen) == 4
    assert scope.api_calls == 4
    assert scope.cost_micro == 4000


def test_policy_guards_and_budget_circuit_breakers():
    # 1. Non-Facebook URL blocked for Facebook transcript endpoint & mismatched URLs blocked for YT/TT/IG
    with cost_control.cost_scope("u1", "reel_research", job_id="j1"):
        for bad_url in (
            "https://www.youtube.com/watch?v=LYxSPJPO4vE",
            "https://www.tiktok.com/@creator/video/123",
            "https://www.instagram.com/reel/abc/",
        ):
            with pytest.raises(cost_control.CostPolicyError):
                cost_control.check_call_allowed(
                    "scrapecreators",
                    "/v1/facebook/post/transcript",
                    payload={"url": bad_url},
                )
        for endpoint, bad_url, good_url in (
            ("/v1/youtube/video/transcript", "https://www.tiktok.com/@creator/video/123", "https://www.youtube.com/watch?v=LYxSPJPO4vE"),
            ("/v1/tiktok/video/transcript", "https://www.youtube.com/watch?v=LYxSPJPO4vE", "https://www.tiktok.com/@creator/video/123"),
            ("/v2/instagram/media/transcript", "https://www.facebook.com/reel/123456", "https://www.instagram.com/reel/DOq6eV6iIgD/"),
        ):
            with pytest.raises(cost_control.CostPolicyError):
                cost_control.check_call_allowed("scrapecreators", endpoint, payload={"url": bad_url})
            assert cost_control.check_call_allowed("scrapecreators", endpoint, payload={"url": good_url})[0] is True

    # 2. keyword_search blocks transcript endpoint
    with cost_control.cost_scope("u1", "keyword_search", job_id="j2"):
        assert cost_control.check_call_allowed("scrapecreators", "/v1/youtube/search")[0] is True
        with pytest.raises(cost_control.CostPolicyError):
            cost_control.check_call_allowed(
                "scrapecreators",
                "/v1/facebook/post/transcript",
                payload={"url": "https://www.facebook.com/reel/123456"},
            )

    # 3. profile_research caps transcript calls at 3
    with cost_control.cost_scope("u1", "profile_research", job_id="j3"):
        for i in range(3):
            cost_control.check_call_allowed(
                "scrapecreators",
                "/v1/facebook/post/transcript",
                payload={"url": f"https://www.facebook.com/reel/{100 + i}"},
            )
            cost_control.record_cost_event(
                "scrapecreators",
                "/v1/facebook/post/transcript",
                cost_micro=1880,
            )
        with pytest.raises(cost_control.CostPolicyError):
            cost_control.check_call_allowed(
                "scrapecreators",
                "/v1/facebook/post/transcript",
                payload={"url": "https://www.facebook.com/reel/999"},
            )


def test_transcriber_blocks_non_fb_and_negative_caches_404():
    init_schema()
    # 1. Mismatched URLs blocked at policy boundary; unsupported web URLs skipped without subprocess
    with cost_control.cost_scope("u_tr", "reel_research", job_id="j_bad"):
        for endpoint, bad_url in (
            ("/v1/facebook/post/transcript", "https://www.youtube.com/watch?v=LYxSPJPO4vE"),
            ("/v1/youtube/video/transcript", "https://www.facebook.com/reel/123456"),
            ("/v1/tiktok/video/transcript", "https://www.instagram.com/reel/DOq6eV6iIgD/"),
            ("/v2/instagram/media/transcript", "https://www.tiktok.com/@creator/video/123"),
        ):
            with pytest.raises(cost_control.CostPolicyError):
                cost_control.check_call_allowed("scrapecreators", endpoint, payload={"url": bad_url})

    with patch("tools.app.backend.cost_control.subprocess.run") as mock_run:
        with cost_control.cost_scope("u_tr", "reel_research", job_id="j_web"):
            assert tr_glasser.fetch_reel_transcript("https://example.com/video/123") is None
        mock_run.assert_not_called()

    # 2. YouTube, TikTok, and Instagram URLs route to their ScrapeCreators transcript endpoints
    yt_vid = "LYxSPJPO4vE"
    tt_vid = "7499229683859426602"
    ig_vid = "DOq6eV6iIgD"
    with tx() as conn:
        conn.execute(
            "DELETE FROM videos WHERE id = ANY(%s)",
            ([f"youtube:{yt_vid}", f"tiktok:{tt_vid}", f"instagram:{ig_vid}"],),
        )

    called_endpoints = []

    def fake_multi_run(cmd, *args, **kwargs):
        ep = cmd[cmd.index("-e") + 1]
        out_path = Path(cmd[cmd.index("-o") + 1])
        called_endpoints.append(ep)
        if ep == "/v1/youtube/video/transcript":
            out_path.write_text(json.dumps({"transcript_only_text": "YouTube hello world"}), encoding="utf-8")
        elif ep == "/v1/tiktok/video/transcript":
            out_path.write_text(
                json.dumps({"transcript": "WEBVTT\n\n00:00:00.120 --> 00:00:01.840\nTikTok line one\n\n00:00:01.850 --> 00:00:03.000\nline two"}),
                encoding="utf-8",
            )
        elif ep == "/v2/instagram/media/transcript":
            out_path.write_text(
                json.dumps({"transcripts": [{"shortcode": ig_vid, "text": "Instagram speech"}]}),
                encoding="utf-8",
            )

        class OkProc:
            returncode = 0
            stdout = "Run ID: r_ok\nRun URL: https://app.glasser.ai/runs/r_ok\nResponse: HTTP 200\nCharge: $0.00188\n"
            stderr = ""

        return OkProc()

    with patch("tools.app.backend.cost_control.shutil.which", return_value="/usr/local/bin/glasser"):
        with patch("tools.app.backend.cost_control.subprocess.run", side_effect=fake_multi_run):
            with cost_control.cost_scope("u_tr", "profile_research", job_id="j_multi"):
                assert tr_glasser.fetch_reel_transcript(f"https://www.youtube.com/watch?v={yt_vid}") == "YouTube hello world"
                assert tr_glasser.fetch_reel_transcript(f"https://www.tiktok.com/@creator/video/{tt_vid}") == "TikTok line one line two"
                assert tr_glasser.fetch_reel_transcript(f"https://www.instagram.com/reel/{ig_vid}/") == "Instagram speech"

    assert called_endpoints == [
        "/v1/youtube/video/transcript",
        "/v1/tiktok/video/transcript",
        "/v2/instagram/media/transcript",
    ]

    # 3. HTTP 404 on a Facebook reel caches __NO_TRANSCRIPT__ and prevents repeat billing
    fb_vid = "999888777666"
    fb_url = f"https://www.facebook.com/reel/{fb_vid}"
    with tx() as conn:
        conn.execute("DELETE FROM videos WHERE id = %s", (f"facebook:{fb_vid}",))

    class FakeProc:
        returncode = 0
        stdout = (
            "Run ID: 44dda52b-0000-0000-0000-000000000001\n"
            "Run URL: https://app.glasser.ai/runs/44dda52b\n"
            "Response: HTTP 404\n"
            "Charge: $0.00188 (NO_RESULT)\n"
        )
        stderr = ""

    with patch("tools.app.backend.cost_control.shutil.which", return_value="/usr/local/bin/glasser"):
        with patch("tools.app.backend.cost_control.subprocess.run", return_value=FakeProc()) as mock_run:
            with cost_control.cost_scope("u_tr", "profile_research", job_id="j_404") as scope:
                first = tr_glasser.fetch_reel_transcript(fb_url, video_id=fb_vid)
                second = tr_glasser.fetch_reel_transcript(fb_url, video_id=fb_vid)

    assert first is None
    assert second is None
    assert mock_run.call_count == 1
    assert scope.cache_hits == 1
    assert get_cached_transcript(fb_vid) is None
    assert get_cached_transcript(fb_vid, include_negative=True) == NO_TRANSCRIPT_SENTINEL


def test_suggest_topics_fetches_transcripts_once_for_top_3(tmp_path: Path):
    reels = [
        {
            "url": f"https://www.facebook.com/reel/{1000 + i}",
            "video_id": str(1000 + i),
            "views": 10000 - i * 100,
            "velocity_per_hour": 500,
            "current_pool": 2,
            "author_handle": f"creator_{i}",
            "title": f"Reel {i}",
        }
        for i in range(8)
    ]

    class FakeACP:
        def __init__(self, *args, **kwargs):
            self.stderr_tail = ""

        def initialize(self):
            return {}

        def new_session(self):
            return "sess-1"

        def prompt(self, _sid, _prompt):
            return json.dumps([
                {
                    "title": f"Topic {i}",
                    "hook": "Hook",
                    "angle": "Angle",
                    "why_viral": "Why",
                    "outline": ["1", "2", "3"],
                    "format": "Reels 30s UGC",
                    "source_urls": [reels[i]["url"]],
                }
                for i in range(5)
            ])

        def close(self):
            pass

    fetch_calls = []

    def fake_fetch(items, **_kwargs):
        fetch_calls.append(len(items))

    with patch.object(reel_research, "ACPClient", FakeACP):
        with patch.object(reel_research, "fetch_top_reels_transcripts", side_effect=fake_fetch):
            topics, err = reel_research.suggest_topics(
                agent_id="agy",
                sheet_name="Test Sheet",
                targets=[{"name": "t", "url": "https://www.facebook.com/test"}],
                reels=reels,
                cwd=tmp_path,
                timeout_sec=10.0,
                log=lambda _m: None,
            )

    assert err is None
    assert len(topics) >= 3
    assert fetch_calls == [3]


def test_cost_store_summaries_and_cli_report():
    init_schema()
    uid = "u_cost_test"
    with tx() as conn:
        conn.execute("DELETE FROM cost_events WHERE user_id = %s", (uid,))
        conn.execute(
            "INSERT INTO user_profiles (user_id, gender, age, name, updated_at) VALUES (%s, 'female', 25, 'Alice', '2026-11-16T00:00:00Z') "
            "ON CONFLICT (user_id) DO UPDATE SET name = EXCLUDED.name",
            (uid,),
        )

    with cost_control.cost_scope(uid, "profile_research", job_id="job_sum_1", sheet_slug="s1"):
        cost_control.record_cost_event(
            provider="scrapecreators",
            endpoint="/v1/facebook/post/transcript",
            cost_micro=1880,
            run_id="r1",
            run_url="https://app.glasser.ai/runs/r1",
            http_status=200,
        )
        cost_control.record_cost_event(
            provider="scrapecreators",
            endpoint="/v1/facebook/post/transcript",
            cost_micro=0,
            cache_hit=True,
        )

    summary = cost_control.COST_STORE.get_user_summary(uid, days=7)
    assert summary["user_profile"]["name"] == "Alice"
    assert len(summary["by_action"]) == 1
    assert summary["by_action"][0]["cost_micro"] == 1880
    assert summary["by_action"][0]["cache_hits"] == 1
    assert any(r["run_url"] == "https://app.glasser.ai/runs/r1" for r in summary["recent_runs"])

    job_sum = cost_control.COST_STORE.get_job_summary("job_sum_1")
    assert job_sum["api_calls"] == 1
    assert job_sum["cache_hits"] == 1
    assert job_sum["cost_micro"] == 1880

    report = cost_control.format_cost_report(days=7, user_id=uid)
    assert "Spend per User Profile" in report
    assert "Alice" in report
    assert "Wasted / Blocked Call Audit" in report
