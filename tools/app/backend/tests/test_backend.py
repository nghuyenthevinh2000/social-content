"""Minimal checks for Excel parsing and topic parsing (run: python3 -m unittest tools.app.backend.test_backend)."""

import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

import openpyxl

from tools.app.backend.profiles import (
    SocialProfileStore,
    facebook_handle,
    is_facebook_url,
    parse_workbook,
    resolve_xlsx_bytes,
    slugify,
)
from tools.app.backend.research_engine.research import (
    create_job,
    heuristic_video_analyses,
    normalize_video_analyses,
    parse_video_analyses,
)
from tools.app.backend.store import JobStore
from tools.loop.viral_analyzer.profile_research.config import load_config
from tools.loop.viral_analyzer.profile_research.pipeline import run_analyzer_pipeline
import unittest.mock as mock


class BackendTests(unittest.TestCase):
    def setUp(self):
        self._cache_tmp = tempfile.TemporaryDirectory()
        self._env_patch = mock.patch.dict(os.environ, {"VIRAL_APP_CACHE_DIR": self._cache_tmp.name})
        self._env_patch.start()
        self._runs_root = Path(self._cache_tmp.name) / "runs"
        self._store = JobStore()
        self._runs_patch = mock.patch("tools.app.backend.research_engine.research.RUNS_ROOT", self._runs_root)
        self._store_patch = mock.patch("tools.app.backend.research_engine.research.STORE", self._store)
        self._runs_patch.start()
        self._store_patch.start()

    def tearDown(self):
        self._store_patch.stop()
        self._runs_patch.stop()
        self._env_patch.stop()
        self._cache_tmp.cleanup()

    def test_parse_workbook(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "spy.xlsx"
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "mẹ chồng - nàng dâu"
            ws.append([None, "tên kênh", "mô tả"])
            ws.append(["https://www.facebook.com/profile.php?id=123&sk=reels_tab", "Mẹ chồng vào bếp"])
            ws.append(["https://www.facebook.com/bepongbay/reels/", "Bếp ông Bảy"])
            ws.append(["https://www.facebook.com/bepongbay/reels/", "Trùng lặp"])
            ws.append([None, "không phải link"])
            empty = wb.create_sheet("mẹ bé")
            empty.append([None])
            wb.save(path)

            sheets = parse_workbook(path)
            self.assertEqual([sheet["name"] for sheet in sheets], ["mẹ chồng - nàng dâu", "mẹ bé"])
            first = sheets[0]
            self.assertEqual(len(first["targets"]), 2)
            self.assertEqual(first["targets"][0]["url"], "https://www.facebook.com/profile.php?id=123")
            self.assertEqual(first["targets"][0]["handle"], "profile_123")
            self.assertEqual(first["targets"][0]["name"], "Mẹ chồng vào bếp")
            self.assertEqual(first["targets"][1]["handle"], "bepongbay")
            self.assertEqual(sheets[1]["targets"], [])

    def test_parse_workbook_preserves_saved_reel_urls(self):
        payload = {
            "sheets": [
                {
                    "name": "Reel đã lưu",
                    "targets": [{"name": "Saved", "url": "https://www.facebook.com/reel/1963371435020478"}],
                }
            ]
        }
        raw, _ = resolve_xlsx_bytes(json.dumps(payload).encode("utf-8"), "saved-reels")
        targets = parse_workbook(raw)[0]["targets"]
        self.assertEqual([t["url"] for t in targets], ["https://www.facebook.com/reel/1963371435020478"])

    def test_resolve_xlsx_bytes_sanitizes_url_sheet_title(self):
        reel_url = "https://www.facebook.com/reel/3002422696778809"
        payload = {
            "sheets": [
                {
                    "name": reel_url,
                    "targets": [{"name": "Saved", "url": reel_url}],
                }
            ]
        }
        raw, fn = resolve_xlsx_bytes(json.dumps(payload).encode("utf-8"), reel_url)
        self.assertTrue(raw.startswith(b"PK\x03\x04"))
        self.assertTrue(fn.endswith(".xlsx"))
        targets = parse_workbook(raw)[0]["targets"]
        self.assertEqual([t["url"] for t in targets], [reel_url])

    def test_slugify(self):
        self.assertEqual(slugify("tổng hợp"), "tong-hop")
        self.assertEqual(slugify("mẹ chồng - nàng dâu"), "me-chong-nang-dau")

    def test_parse_video_analyses_from_fenced_json(self):
        fallback = heuristic_video_analyses("thực phẩm bẩn", [{"url": "https://x", "title": "Sample"}])
        answer = "```json\n" + json.dumps(
            [
                {"title": "A", "hook": "H", "angle": "G", "why_viral": "W", "outline": ["1", "2"], "source_urls": ["https://x"]},
                {"title": "B"},
                {"title": "C"},
            ],
            ensure_ascii=False,
        ) + "\n```"
        analyses = parse_video_analyses(answer, fallback)
        self.assertEqual(len(analyses), 3)
        self.assertEqual(analyses[0]["title"], "A")
        self.assertEqual(analyses[0]["generated_by"], "agent")
        self.assertEqual(analyses[1]["generated_by"], "agent")

    def test_invalid_agent_output_falls_back(self):
        fallback = heuristic_video_analyses("mẹ bé", [{"url": "https://www.facebook.com/reel/1", "title": "Reel 1"}])
        analyses = parse_video_analyses("xin lỗi, tôi không trả JSON", fallback)
        self.assertEqual(len(analyses), 1)
        self.assertEqual(analyses[0]["generated_by"], "heuristic")

    def test_normalize_does_not_pad_to_three(self):
        fallback = heuristic_video_analyses("mẹ bé", [{"url": "https://www.facebook.com/reel/1", "title": "Reel 1"}])
        analyses = normalize_video_analyses([{"title": "Chỉ một"}], fallback)
        self.assertEqual(len(analyses), 1)

    def test_heuristic_and_normalize_video_analyses_sorted_by_views_up_to_10(self):
        reels = [
            {"video_id": f"v_{i}", "url": f"https://www.facebook.com/reel/v_{i}", "views": i * 1000, "velocity_per_hour": i * 100}
            for i in range(1, 15)
        ]
        fallback = heuristic_video_analyses("test sheet", reels, limit=10)
        self.assertEqual(len(fallback), 10)
        self.assertEqual(fallback[0]["views"], 14000)
        self.assertEqual(fallback[-1]["views"], 5000)
        views_list = [t["views"] for t in fallback]
        self.assertEqual(views_list, sorted(views_list, reverse=True))

        agent_data = [{"title": "Hot video", "source_urls": ["https://www.facebook.com/reel/v_14"]}]
        normalized = normalize_video_analyses(agent_data, fallback, reels=reels, limit=10)
        self.assertEqual(len(normalized), 10)
        self.assertEqual(normalized[0]["views"], 14000)

    def test_normalize_video_analyses_resolves_page_url_to_reel_url(self):
        fallback = heuristic_video_analyses("kênh", [])
        reels = [
            {"author_handle": "my_page", "video_id": "123456", "url": "https://www.facebook.com/reel/123456"},
            {"author_handle": "another_page", "video_id": "789101", "url": "https://www.facebook.com/reel/789101"},
        ]
        agent_data = [
            {"title": "T1", "source_urls": ["https://www.facebook.com/my_page"]},
            {"title": "T2", "source_urls": ["https://www.facebook.com/reel/789101"]},
        ]
        analyses = normalize_video_analyses(agent_data, fallback, reels=reels)
        self.assertEqual(analyses[0]["source_urls"], ["https://www.facebook.com/reel/123456"])
        self.assertEqual(analyses[1]["source_urls"], ["https://www.facebook.com/reel/789101"])

    def test_normalize_video_analyses_cross_checks_actor_profile(self):
        fallback = heuristic_video_analyses("hôn nhân", [])
        agent_data = [
            {
                "title": "Cấu trúc video hôn nhân",
                "prompt": (
                    "[CAMERA & COMPOSITION]\nVertical 9:16\n\n"
                    "[ENVIRONMENT & ATMOSPHERE]\nPhòng khách\n\n"
                    "[SUBJECT & CONTINUITY]\nNgười dẫn nữ 35 tuổi, áo sơ mi, nhìn thẳng ống kính (<IMAGE_REF_0>).\n\n"
                    "[ACTION & TIMECODE]\n00:00 - 00:15: Chia sẻ\n\n"
                    "[AUDIO & DIALOGUE]\nGiọng nữ (35 tuổi), lời thoại tiếng Việt: \"Xin chào\"."
                ),
            }
        ]
        actor_prof = {"gender": "male", "age": 28, "voice_tone": "Bắc"}
        analyses = normalize_video_analyses(agent_data, fallback, actor_profile=actor_prof)
        prompt = analyses[0]["prompt"]
        self.assertIn("Người dẫn nam 28 tuổi", prompt)
        self.assertIn("Giọng nam (28 tuổi)", prompt)
        self.assertIn("Ngoại hình nhất quán của người dẫn nam (28 tuổi)", prompt)
        self.assertIn("chất giọng Bắc", prompt)
        self.assertIn("<IMAGE_REF_0>", prompt)

    def test_pipeline_reads_job_cache_without_network(self):
        from datetime import datetime, timezone

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cache = root / "cache"
            cache.mkdir()
            now = datetime.now(timezone.utc).isoformat()
            (cache / "temp_testhandle.json").write_text(
                json.dumps(
                    {
                        "reels": [
                            {"video_id": "1", "url": "https://facebook.com/reel/1", "creation_time": now, "view_count": 120000, "description": "Mẹo nấu ăn"},
                            {"video_id": "2", "url": "https://facebook.com/reel/2", "creation_time": now, "view_count": 900, "description": "Chuyện nhà"},
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            config = load_config(
                {
                    "storage": {
                        "video_dir": str(root / "videos"),
                        "output_file": str(root / "out.json"),
                    },
                    "targets": [{"handle": "testhandle", "url": "https://facebook.com/testhandle", "name": "Test"}],
                }
            )
            payload = run_analyzer_pipeline(config, cache_dir=cache, transcribe=False, legacy_cache=False)
            self.assertEqual(len(payload["all_reels"]), 2)
            self.assertEqual(payload["all_reels"][0]["current_pool"], 4)
            self.assertTrue((root / "out.json").exists())

    def test_job_store_queue(self):
        from tools.app.backend.store import JobStore

        store = JobStore()
        for job_id, created in (("b", "2026-01-02"), ("a", "2026-01-01")):
            store.put({"id": job_id, "status": "queued", "created_at": created, "sheets": [{"slug": "s", "status": "pending"}], "logs": []})
        self.assertEqual(store.claim(2)["id"], "a")
        self.assertEqual(store.snapshot("a")["status"], "running")
        store.patch_sheet("a", "s", status="completed")
        store.log("a", "hello", "s")
        self.assertTrue(store.cancel("b"))
        self.assertFalse(store.cancel("missing"))
        snap = JobStore().snapshot("a")  # survives a new process/store
        self.assertEqual(snap["sheets"][0]["status"], "completed")
        self.assertEqual(snap["logs"][0]["message"], "hello")
        self.assertTrue(store.snapshot("b")["cancel_requested"])
        self.assertEqual(store.claim(2)["id"], "b")
        self.assertIsNone(store.claim(2))

    def test_claim_is_fair_across_clients(self):
        from tools.app.backend.store import JobStore

        store = JobStore()
        for job_id, client, created in (("a1", "A", "1"), ("a2", "A", "2"), ("b1", "B", "3")):
            store.put({"id": job_id, "client_id": client, "status": "queued", "created_at": created, "sheets": []})
        self.assertEqual(store.claim(1)["id"], "a1")
        self.assertEqual(store.claim(1)["id"], "b1")  # A is at its limit, so B jumps ahead of a2
        self.assertIsNone(store.claim(1))
        store.update("a1", status="completed")
        self.assertEqual(store.claim(1)["id"], "a2")
        self.assertEqual(store.stale_running(60), [])
        self.assertEqual(sorted(store.stale_running(-1)), ["a2", "b1"])  # no recent heartbeat => worker lost

    def test_log_collection(self):
        from tools.app.backend.server import _log_line, LOG_PATH
        import uuid
        marker = f"TEST_LOG_{uuid.uuid4().hex}"
        _log_line(marker)
        self.assertTrue(LOG_PATH.exists())
        content = LOG_PATH.read_text(encoding="utf-8")
        self.assertIn(marker, content)

    def test_resolve_xlsx_bytes_passthrough(self):
        from tools.app.backend.research_engine.research import resolve_xlsx_bytes
        raw = b"PK\x03\x04test"
        res, name = resolve_xlsx_bytes(raw, "file.xlsx")
        self.assertEqual(res, raw)
        self.assertEqual(name, "file.xlsx")

    def test_resolve_xlsx_bytes_gsheet_json(self):
        from unittest.mock import MagicMock, patch
        from tools.app.backend.research_engine.research import resolve_xlsx_bytes

        gsheet_json = json.dumps({
            "url": "https://docs.google.com/spreadsheets/d/test12345/edit",
            "doc_id": "test12345",
        }).encode("utf-8")

        mock_resp = MagicMock()
        mock_resp.read.return_value = b"PK\x03\x04mock_xlsx_bytes"
        mock_resp.__enter__.return_value = mock_resp

        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
            res, name = resolve_xlsx_bytes(gsheet_json, "Competitors.gsheet")
            self.assertEqual(res, b"PK\x03\x04mock_xlsx_bytes")
            self.assertEqual(name, "Competitors.xlsx")
            self.assertIn("test12345/export?format=xlsx", mock_urlopen.call_args[0][0].full_url)

    def test_resolve_xlsx_bytes_json_sheets(self):
        from tools.app.backend.research_engine.research import resolve_xlsx_bytes, parse_workbook
        import tempfile
        payload = json.dumps({
            "sheets": [
                {"name": "Topic A", "targets": [{"url": "https://facebook.com/ch1", "name": "Kênh 1"}]},
                {"name": "Topic B", "targets": [{"url": "https://facebook.com/ch2", "name": "Kênh 2"}]}
            ]
        }).encode("utf-8")
        res, name = resolve_xlsx_bytes(payload, "custom.json")
        self.assertTrue(res.startswith(b"PK\x03\x04"))
        self.assertEqual(name, "custom.xlsx")
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            f.write(res)
            f.flush()
            parsed = parse_workbook(Path(f.name))
            self.assertEqual(len(parsed), 2)
            self.assertEqual(parsed[0]["name"], "Topic A")
            self.assertEqual(len(parsed[0]["targets"]), 1)

    def test_create_job_includes_target_list(self):
        payload = {
            "sheets": [
                {
                    "name": "Topic Test",
                    "targets": [
                        {"url": "https://facebook.com/testpage", "name": "Test Page"}
                    ]
                }
            ]
        }
        job = create_job(
            json.dumps(payload).encode("utf-8"),
            "test.json",
            {"agent": "test-agent", "max_videos": 1, "transcribe": False},
            "client-1",
        )
        self.assertEqual(len(job["sheets"]), 1)
        self.assertEqual(job["sheets"][0]["name"], "Topic Test")
        self.assertEqual(job["sheets"][0]["targets"], 1)
        self.assertEqual(job["sheets"][0]["target_list"][0]["name"], "Test Page")
        self.assertEqual(job["sheets"][0]["target_list"][0]["url"], "https://www.facebook.com/testpage")

    def test_create_job_json_skips_excel_roundtrip(self):
        reel_url = "https://www.facebook.com/reel/3002422696778809"
        payload = {
            "sheets": [
                {
                    "name": reel_url,
                    "targets": [{"url": reel_url, "name": "Saved Reel"}],
                }
            ]
        }
        with mock.patch("openpyxl.load_workbook", side_effect=AssertionError("should not parse Excel")):
            job = create_job(
                json.dumps(payload).encode("utf-8"),
                reel_url,
                {"agent": "test-agent", "max_videos": 1, "transcribe": False},
                "client-1",
                job_kind="reel",
            )
        self.assertEqual(job["filename"], reel_url)
        self.assertEqual(job["sheets"][0]["name"], reel_url)
        self.assertEqual(job["sheets"][0]["target_list"][0]["url"], reel_url)

    def test_social_profile_store_crud(self):
        store = SocialProfileStore()

        # Test initial seed
        topics = store.list_topics()
        self.assertEqual(len(topics), 4)
        first = store.get_topic("me-chong-nang-dau")
        self.assertIsNotNone(first)
        self.assertEqual(len(first["targets"]), 3)

        # Test search query
        filtered = store.list_topics(query="nàng dâu")
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["slug"], "me-chong-nang-dau")

        # Test add profile to existing topic
        updated = store.add_profile("Mẹ chồng - nàng dâu", "https://facebook.com/newchannel", "Kênh Mới")
        self.assertEqual(len(updated["targets"]), 4)

        # Test add profile creating new topic
        new_topic = store.add_profile("Thời trang", "https://facebook.com/thoitrang123", "Shop Xinh")
        self.assertEqual(new_topic["name"], "Thời trang")
        self.assertEqual(len(new_topic["targets"]), 1)
        self.assertEqual(len(store.list_topics()), 5)

        # Test delete profile
        self.assertTrue(store.delete_profile("thoi-trang", "https://facebook.com/thoitrang123"))
        after_del = store.get_topic("thoi-trang")
        self.assertEqual(len(after_del["targets"]), 0)

        # Test delete topic
        self.assertTrue(store.delete_topic("thoi-trang"))
        self.assertIsNone(store.get_topic("thoi-trang"))
        self.assertEqual(len(store.list_topics()), 4)

        # Test multi-user isolation: new accounts start empty, no leakage
        user_a = "user_alpha_123"
        user_b = "user_beta_456"
        self.assertEqual(len(store.list_topics(user_id=user_a)), 0)
        self.assertEqual(len(store.list_topics(user_id=user_b)), 0)
        store.add_profile("Nấu ăn A", "https://facebook.com/nauan123", "Bếp A", user_id=user_a)
        self.assertEqual(len(store.list_topics(user_id=user_a)), 1)
        self.assertEqual(len(store.list_topics(user_id=user_b)), 0)
        self.assertIsNone(store.get_topic("nau-an-a", user_id=user_b))

    def test_job_store_user_isolation(self):
        from tools.app.backend.store import JobStore
        store = JobStore()
        job_a = {"id": "job_a1", "status": "completed", "created_at": "2026-11-08T00:00:00Z", "user_id": "user_a"}
        store.put(job_a)

        # user_a can read job_a
        self.assertIsNotNone(store.snapshot("job_a1", user_id="user_a"))
        # user_b cannot read job_a
        self.assertIsNone(store.snapshot("job_a1", user_id="user_b"))
        # unassigned user cannot cancel job_a
        self.assertFalse(store.cancel("job_a1", user_id="user_b"))

        # list_jobs isolation
        jobs_a = store.list_jobs(user_id="user_a")
        self.assertEqual(len(jobs_a), 1)
        self.assertEqual(jobs_a[0]["id"], "job_a1")
        self.assertEqual(len(store.list_jobs(user_id="user_b")), 0)

        # delete job
        self.assertFalse(store.delete("job_a1", user_id="user_b"))
        self.assertTrue(store.delete("job_a1", user_id="user_a"))
        self.assertEqual(len(store.list_jobs(user_id="user_a")), 0)

    def test_max_videos_env_fallback(self):
        from tools.app.backend.server import _int
        # Default when unset
        env_val = os.environ.get("VIRAL_APP_MAX_VIDEOS_NONEXISTENT")
        self.assertEqual(_int(env_val, 5, minimum=0, maximum=500), 5)
        # Custom setting from environment
        with unittest.mock.patch.dict(os.environ, {"VIRAL_APP_MAX_VIDEOS": "12"}):
            env_val = os.environ.get("VIRAL_APP_MAX_VIDEOS")
            self.assertEqual(_int(env_val, 5, minimum=0, maximum=500), 12)
        # Zero cap
        with unittest.mock.patch.dict(os.environ, {"VIRAL_APP_MAX_VIDEOS": "0"}):
            env_val = os.environ.get("VIRAL_APP_MAX_VIDEOS")
            self.assertEqual(_int(env_val, 5, minimum=0, maximum=500), 0)

    def test_fetch_target_reels_cache_hit_and_fallback(self):
        from tools.loop.viral_analyzer.cache import write_cached_reels
        from tools.loop.viral_analyzer.profile_research.collect import fetch_target_reels
        import subprocess
        with tempfile.TemporaryDirectory() as tmp:
            fake_reels = [{"video_id": "99", "url": "https://facebook.com/reel/99", "view_count": 1000}]
            write_cached_reels("testhandle", fake_reels)

            config = load_config({
                "storage": {
                    "video_dir": str(Path(tmp) / "videos"),
                    "output_file": str(Path(tmp) / "out.json"),
                },
                "targets": [{"handle": "testhandle", "url": "https://facebook.com/testhandle"}],
            })

            logs = []
            reels = fetch_target_reels(
                {"handle": "testhandle", "url": "https://facebook.com/testhandle"},
                config,
                progress_cb=logs.append,
            )
            # Must read directly from Postgres cache without subprocess/network call
            self.assertEqual(len(reels), 1)
            self.assertEqual(reels[0]["video_id"], "99")
            self.assertTrue(any("[cache]" in line for line in logs))

            # Test TTL expiration fallback on error
            write_cached_reels("testhandle", fake_reels, fetched_at=time.time() - 100000)
            logs_expired = []
            with mock.patch("subprocess.run", return_value=subprocess.CompletedProcess([], 1, stdout="err", stderr="err")):
                reels_expired = fetch_target_reels(
                    {"handle": "testhandle", "url": "https://facebook.com/testhandle"},
                    config,
                    progress_cb=logs_expired.append,
                )
            self.assertEqual(len(reels_expired), 1)
            self.assertTrue(any("dùng lại cache cũ" in line for line in logs_expired))

    def test_duplicate_target_uses_cache(self):
        from tools.loop.viral_analyzer.cache import read_cached_reels
        from tools.loop.viral_analyzer.profile_research.collect import fetch_target_reels
        import subprocess
        import unittest.mock as mock

        with tempfile.TemporaryDirectory() as tmp:
            config = load_config({
                "storage": {
                    "video_dir": str(Path(tmp) / "videos"),
                    "output_file": str(Path(tmp) / "out.json"),
                },
                "targets": [{"handle": "my_channel", "url": "https://facebook.com/my_channel"}],
            })

            target = {"handle": "my_channel", "url": "https://facebook.com/my_channel"}
            glasser_call_count = 0

            def fake_subprocess_run(cmd, *args, **kwargs):
                nonlocal glasser_call_count
                glasser_call_count += 1
                out_idx = cmd.index("-o") + 1
                out_path = Path(cmd[out_idx])
                fake_payload = {
                    "reels": [
                        {"video_id": "vid_1", "url": "https://facebook.com/reel/1", "view_count": 5000}
                    ]
                }
                out_path.write_text(json.dumps(fake_payload), encoding="utf-8")
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

            with mock.patch("subprocess.run", side_effect=fake_subprocess_run):
                # 1st call: cache is empty, Glasser must be called
                logs_1 = []
                reels_1 = fetch_target_reels(target, config, legacy_cache=False, progress_cb=logs_1.append)
                self.assertEqual(glasser_call_count, 1)
                self.assertEqual(len(reels_1), 1)
                self.assertEqual(reels_1[0]["video_id"], "vid_1")
                self.assertTrue(any("[api] Gọi Glasser" in log for log in logs_1))
                # Entry must have been persisted into centralized Postgres profile_cache
                cached_entry = read_cached_reels("my_channel")
                self.assertIsNotNone(cached_entry)
                self.assertEqual(len(cached_entry[0]), 1)

                # 2nd call: duplicate query, Glasser must NOT be called again
                logs_2 = []
                reels_2 = fetch_target_reels(target, config, legacy_cache=False, progress_cb=logs_2.append)
                self.assertEqual(glasser_call_count, 1, "Glasser was called again on duplicate query instead of hitting cache!")
                self.assertEqual(len(reels_2), 1)
                self.assertEqual(reels_2[0]["video_id"], "vid_1")
                self.assertTrue(any("[cache] Dùng cache" in log for log in logs_2))

    def test_pipeline_duplicate_targets_hit_cache(self):
        from tools.loop.viral_analyzer.profile_research.pipeline import run_analyzer_pipeline
        import subprocess
        import unittest.mock as mock

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cache = root / "cache"
            cache.mkdir()

            config = load_config({
                "storage": {
                    "video_dir": str(root / "videos"),
                    "output_file": str(root / "out.json"),
                },
                "targets": [
                    {"handle": "dup_channel", "url": "https://facebook.com/dup_channel"},
                    {"handle": "dup_channel", "url": "https://facebook.com/dup_channel"},
                ],
            })

            glasser_calls = 0
            def fake_run(cmd, *args, **kwargs):
                nonlocal glasser_calls
                glasser_calls += 1
                out_path = Path(cmd[cmd.index("-o") + 1])
                out_path.write_text(json.dumps({
                    "reels": [{"video_id": "v1", "url": "https://facebook.com/reel/v1", "view_count": 2000}]
                }), encoding="utf-8")
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

            logs = []
            with mock.patch("subprocess.run", side_effect=fake_run):
                payload = run_analyzer_pipeline(config, cache_dir=cache, transcribe=False, legacy_cache=False, progress_cb=logs.append)
                # Across 2 duplicate targets in targets list, Glasser should only be queried ONCE
                self.assertEqual(glasser_calls, 1, f"Expected 1 Glasser call for duplicate targets, got {glasser_calls}")
                self.assertTrue(any("[cache]" in log for log in logs))
                self.assertIn("dup_channel", payload["source_breakdown"]["glasser_api"])
                self.assertIn("dup_channel", payload["source_breakdown"]["cache"])
                self.assertTrue(any("Thống kê nguồn cào:" in log for log in logs))

    def test_analyze_video_structure_empty_reels_returns_empty(self):
        from tools.app.backend.research_engine.research import analyze_video_structure
        logs = []
        topics, err = analyze_video_structure(
            "agy",
            "test_sheet",
            [{"name": "chan", "url": "https://facebook.com/chan"}],
            [],
            Path("/tmp"),
            10.0,
            logs.append,
        )
        self.assertEqual(topics, [])
        self.assertIsNone(err)
        self.assertTrue(any("Không có reel nào" in m for m in logs))

    def test_process_sheet_zero_reels_notifies_and_produces_no_topics(self):
        from tools.app.backend.research_engine.research import _process_sheet
        import uuid
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            job_id = uuid.uuid4().hex[:12]
            sheet = {
                "name": "Chủ đề vắng",
                "slug": "chu-de-vang",
                "targets": [{"name": "k1", "url": "https://facebook.com/k1", "handle": "k1"}],
            }
            job = {
                "id": job_id,
                "status": "running",
                "created_at": "2026-01-01",
                "sheets": [{
                    "name": sheet["name"],
                    "slug": sheet["slug"],
                    "status": "pending",
                    "targets": 1,
                    "reels": 0,
                    "topics": [],
                    "error": None,
                    "notice": None,
                }],
                "logs": [],
            }
            self._store.put(job)
            with mock.patch("tools.app.backend.research_engine.research.run_analyzer_pipeline", return_value={"all_reels": [], "metadata": {}}):
                _process_sheet(job_id, 1, 1, sheet, run_dir, {"agent": "agy", "window_hours": 48})
            snap = self._store.snapshot(job_id)
            target_sheet = snap["sheets"][0]
            self.assertEqual(target_sheet["status"], "completed")
            self.assertEqual(target_sheet["reels"], 0)
            self.assertEqual(target_sheet["topics"], [])
            self.assertIn("Không tìm thấy reel mới nào trong 48 giờ qua", target_sheet["notice"])
            self.assertIn("cập nhật thêm danh sách", target_sheet["notice"])

    def test_process_sheet_no_targets_notifies_and_produces_no_topics(self):
        from tools.app.backend.research_engine.research import _process_sheet
        import uuid
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            job_id = uuid.uuid4().hex[:12]
            sheet = {
                "name": "Chủ đề rỗng",
                "slug": "chu-de-rong",
                "targets": [],
            }
            job = {
                "id": job_id,
                "status": "running",
                "created_at": "2026-01-01",
                "sheets": [{
                    "name": sheet["name"],
                    "slug": sheet["slug"],
                    "status": "pending",
                    "targets": 0,
                    "reels": 0,
                    "topics": [],
                    "error": None,
                    "notice": None,
                }],
                "logs": [],
            }
            self._store.put(job)
            _process_sheet(job_id, 1, 1, sheet, run_dir, {"agent": "agy", "window_hours": 48})
            snap = self._store.snapshot(job_id)
            target_sheet = snap["sheets"][0]
            self.assertEqual(target_sheet["status"], "completed")
            self.assertEqual(target_sheet["reels"], 0)
            self.assertEqual(target_sheet["topics"], [])
            self.assertIn("Chưa có kênh đối thủ nào", target_sheet["notice"])

    def test_process_sheet_profile_surfaces_48h_reels_without_auto_research(self):
        from tools.app.backend.research_engine.research import _process_sheet
        import uuid

        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            job_id = uuid.uuid4().hex[:12]
            sheet = {
                "name": "Ẩm thực",
                "slug": "am-thuc",
                "targets": [{"name": "k1", "url": "https://facebook.com/k1", "handle": "k1"}],
            }
            self._store.put({
                "id": job_id,
                "job_kind": "profile",
                "status": "running",
                "created_at": "2026-01-01",
                "sheets": [{
                    "name": sheet["name"],
                    "slug": sheet["slug"],
                    "status": "pending",
                    "targets": 1,
                    "reels": 0,
                    "topics": [],
                    "error": None,
                    "notice": None,
                }],
                "logs": [],
            })
            harvested = [
                {
                    "video_id": "v1",
                    "url": "https://www.facebook.com/reel/111",
                    "title": "Low views reel",
                    "views": 1000,
                    "velocity_per_hour": 50.0,
                    "current_pool": 1,
                    "pool_name": "P1",
                    "author_handle": "chef_a",
                    "platform": "facebook",
                },
                {
                    "video_id": "v2",
                    "url": "https://www.facebook.com/reel/222",
                    "title": "High views reel",
                    "views": 50000,
                    "velocity_per_hour": 2500.0,
                    "current_pool": 3,
                    "pool_name": "P3",
                    "author_handle": "chef_b",
                    "platform": "facebook",
                },
            ]
            with mock.patch(
                "tools.app.backend.research_engine.research.run_analyzer_pipeline",
                return_value={"all_reels": harvested, "metadata": {"pool_distribution": {"pool_1": 1, "pool_3": 1}}},
            ) as mock_pipeline, mock.patch(
                "tools.app.backend.research_engine.research.analyze_video_structure",
            ) as mock_analyze:
                _process_sheet(job_id, 1, 1, sheet, run_dir, {"agent": "agy", "window_hours": 48}, job_kind="profile")

            mock_analyze.assert_not_called()
            self.assertFalse(mock_pipeline.call_args.kwargs.get("transcribe"))
            snap = self._store.snapshot(job_id)
            target_sheet = snap["sheets"][0]
            self.assertEqual(target_sheet["status"], "completed")
            self.assertEqual(target_sheet["reels"], 2)
            self.assertEqual([t["video_id"] for t in target_sheet["topics"]], ["v2", "v1"])
            self.assertTrue(all(t["generated_by"] == "profile" and t["transcript"] == "" for t in target_sheet["topics"]))

    def test_install_binaries_script_content(self):
        script_path = Path(__file__).resolve().parents[1] / "install_binaries.sh"
        self.assertTrue(script_path.exists())
        content = script_path.read_text(encoding="utf-8")
        self.assertIn("https://opencode.ai/v2/install", content)
        self.assertIn("https://antigravity.google/cli/install.sh", content)
        self.assertIn("command -v opencode", content)
        self.assertIn("command -v agy", content)

    def test_agy_agent_model_resolution(self):
        from tools.app.backend.research_engine.research import resolve_agent
        with mock.patch("shutil.which", return_value="/usr/local/bin/agy"):
            # Unset env: no hard-coded model, defaults to base agy command
            with mock.patch.dict(os.environ, {}, clear=False):
                os.environ.pop("VIRAL_APP_AGY_MODEL", None)
                agent = resolve_agent("agy")
                self.assertNotIn("model", agent)
                self.assertEqual(agent["command"], ["agy", "acp"])

            # Env override: uses the env config
            with mock.patch.dict(os.environ, {"VIRAL_APP_AGY_MODEL": "gemini-3.8-flash-low"}):
                agent = resolve_agent("agy")
                self.assertEqual(agent["model"], "gemini-3.8-flash-low")
                self.assertEqual(agent["command"], ["agy", "--model", "gemini-3.8-flash-low", "acp"])

            # Parameter override
            agent = resolve_agent("agy", model="param-model")
            self.assertEqual(agent["model"], "param-model")
            self.assertEqual(agent["command"], ["agy", "--model", "param-model", "acp"])

    def test_agent_binary_format_mismatch_and_fallback(self):
        from tools.app.backend.acp import ACPError
        from tools.app.backend.errors import handle_acp_error
        from tools.app.backend.research_engine import research

        with tempfile.TemporaryDirectory() as tmp:
            macho_bin = Path(tmp) / "agy-macho"
            macho_bin.write_bytes(b"\xcf\xfa\xed\xfe" + b"\x00" * 16)
            elf_bin = Path(tmp) / "agy-elf"
            elf_bin.write_bytes(b"\x7fELF" + b"\x00" * 16)

            def which_linux_mismatch(name: str):
                if name == "agy":
                    return str(macho_bin)
                if name == "opencode":
                    return "/mock/opencode"
                return None

            with mock.patch.object(research.sys, "platform", "linux"):
                with mock.patch("shutil.which", side_effect=which_linux_mismatch):
                    with self.assertRaises(ACPError) as ctx:
                        research.resolve_agent("agy")
                    self.assertIn("Mach-O", str(ctx.exception))

                    with mock.patch.dict(os.environ, {"VIRAL_APP_AGENT": "agy"}):
                        chosen = research.configured_agent()
                        self.assertEqual(chosen["id"], "opencode")

            with mock.patch.object(research.sys, "platform", "darwin"):
                with mock.patch("shutil.which", return_value=str(elf_bin)):
                    with self.assertRaises(ACPError) as ctx:
                        research.resolve_agent("agy")
                    self.assertIn("ELF", str(ctx.exception))

        err = handle_acp_error("[Errno 8] Exec format error: 'agy'", agent_id="agy")
        self.assertEqual(err.code, "ACP_BINARY_FORMAT_ERROR")

    def test_glasser_module_and_error_classification(self):
        import subprocess
        from tools.loop.viral_analyzer.glasser import (
            ensure_glasser_env,
            check_glasser_key,
            check_glasser_status,
            execute_glasser_query,
            GlasserMissingKeyError,
            GlasserNotFoundError,
            GlasserExecutionError,
        )

        # 1. Truly missing key (no env, no .env file, no CLI stored key)
        with mock.patch("tools.loop.viral_analyzer.glasser.ensure_glasser_env", return_value=None):
            with mock.patch.dict(os.environ, {}, clear=False):
                os.environ.pop("GLASSER_API_KEY", None)
                with mock.patch("subprocess.run", return_value=subprocess.CompletedProcess([], 0, stdout="No Keys stored.", stderr="")):
                    has_key, err = check_glasser_key()
                    self.assertFalse(has_key)
                    self.assertIn("Thiếu", err)

                    with mock.patch("shutil.which", return_value="/usr/bin/glasser"):
                        status = check_glasser_status()
                        self.assertFalse(status["ok"])
                        self.assertFalse(status["has_key"])
                        self.assertTrue(status["installed"])

                        with mock.patch("subprocess.run", return_value=subprocess.CompletedProcess([], 2, stdout="", stderr="Error: No Key configured.")):
                            ok, msg, exc = execute_glasser_query(
                                profile_url="https://facebook.com/test",
                                provider="scrapecreators",
                                endpoint="/v1/facebook/profile/reels",
                                endpoint_version=2,
                                idempotency_key="k1",
                                temp_out=Path("/tmp/out.json"),
                            )
                            self.assertFalse(ok)
                            self.assertIsInstance(exc, GlasserMissingKeyError)

        # 2. Missing binary
        with mock.patch.dict(os.environ, {"GLASSER_API_KEY": "gl_valid_test_key_12345"}):
            with mock.patch("shutil.which", return_value=None):
                status = check_glasser_status()
                self.assertFalse(status["ok"])
                self.assertFalse(status["installed"])
                ok, msg, exc = execute_glasser_query(
                    profile_url="https://facebook.com/test",
                    provider="scrapecreators",
                    endpoint="/v1/facebook/profile/reels",
                    endpoint_version=2,
                    idempotency_key="k1",
                    temp_out=Path("/tmp/out.json"),
                )
                self.assertFalse(ok)
                self.assertIsInstance(exc, GlasserNotFoundError)

        # 3. HTTP 404 / Facebook not found handling (code 0, empty temp_out)
        with mock.patch.dict(os.environ, {"GLASSER_API_KEY": "gl_valid_test_key_12345"}):
            with mock.patch("shutil.which", return_value="/usr/bin/glasser"):
                with tempfile.TemporaryDirectory() as tmp_dir:
                    t_out = Path(tmp_dir) / "out.json"
                    stdout_404 = (
                        "Idempotency-Key: viral-loop-chan-20765\n"
                        "Response: HTTP 404\n"
                        '{"error": "not_found", "message": "Shoot it looks like this Facebook profile doesn\'t exist or is private"}\n'
                        "Nothing written to out.json: only a COMPLETED Run with output is saved."
                    )
                    with mock.patch("subprocess.run", return_value=subprocess.CompletedProcess([], 0, stdout=stdout_404, stderr="")):
                        ok, msg, exc = execute_glasser_query(
                            profile_url="https://facebook.com/404chan",
                            provider="scrapecreators",
                            endpoint="/v1/facebook/profile/reels",
                            endpoint_version=2,
                            idempotency_key="k404",
                            temp_out=t_out,
                            handle="404chan",
                        )
                        self.assertTrue(ok)
                        self.assertIsNone(exc)
                        self.assertTrue(t_out.exists())
                        data = json.loads(t_out.read_text(encoding="utf-8"))
                        self.assertEqual(data["reels"], [])
                        self.assertEqual(data["status"], "not_found")

                    # 4. Split-stream 404 test (stderr has "Nothing written", stdout has HTTP 404 response)
                    t_out_split = Path(tmp_dir) / "out_split.json"
                    real_stdout = (
                        "Run ID:   e52c2889-27c5-4c5f-b246-9ad1bd97c410\n"
                        "Status:   COMPLETED\n"
                        "Response: HTTP 404\n"
                        "Charge:   $0.00188 (NO_RESULT)\n"
                        '{"error": "not_found", "message": "Shoot it looks like this Facebook profile doesn\'t exist or is private :( Or they don\'t have a reels tab", "success": true, "errorStatus": 404}'
                    )
                    real_stderr = (
                        "Nothing written to out_split.json: only a COMPLETED Run with output is saved.\n"
                        "Update available: glasser v0.1.88 -> v0.1.125\n"
                    )
                    with mock.patch("subprocess.run", return_value=subprocess.CompletedProcess([], 0, stdout=real_stdout, stderr=real_stderr)):
                        ok, msg, exc = execute_glasser_query(
                            profile_url="https://facebook.com/testpage",
                            provider="scrapecreators",
                            endpoint="/v1/facebook/profile/reels",
                            endpoint_version=2,
                            idempotency_key="k_split",
                            temp_out=t_out_split,
                            handle="testpage",
                        )
                        self.assertTrue(ok)
                        self.assertIsNone(exc)
                        self.assertTrue(t_out_split.exists())
                        data_split = json.loads(t_out_split.read_text(encoding="utf-8"))
                        self.assertEqual(data_split["reels"], [])
                        self.assertEqual(data_split["status"], "not_found")

    def test_backend_errors_module_and_aggregation(self):
        from tools.app.backend.errors import (
            AppError,
            ErrorAggregator,
            ErrorCategory,
            ErrorSeverity,
            handle_glasser_error,
            handle_acp_error,
        )

        agg = ErrorAggregator(job_id="job123")
        self.assertFalse(agg.has_errors())

        # Test Glasser missing key handling
        g_err = handle_glasser_error("Error: No Key configured. Run glasser keys add", handle="test_handle")
        self.assertEqual(g_err.code, "GLASSER_MISSING_API_KEY")
        self.assertEqual(g_err.severity, ErrorSeverity.CRITICAL.value)
        self.assertIn("GLASSER_API_KEY", g_err.suggestion)
        agg.add(g_err)

        # Ensure general execution error is not misclassified as missing key
        exec_err = handle_glasser_error(
            {"error_type": "GlasserExecutionError", "message": "Failed query", "returncode": 0, "suggestion": "Kiểm tra cấu hình Glasser CLI và GLASSER_API_KEY."},
            handle="some_chan",
        )
        self.assertEqual(exec_err.code, "GLASSER_EXECUTION_ERROR")
        self.assertNotEqual(exec_err.code, "GLASSER_MISSING_API_KEY")

        # Test ACP auth handling
        a_err = handle_acp_error("ACP: auth required to proceed", agent_id="agy")
        self.assertEqual(a_err.code, "ACP_AUTH_REQUIRED")
        agg.add(a_err)

        self.assertTrue(agg.has_errors())
        self.assertTrue(agg.has_category(ErrorCategory.GLASSER))
        self.assertTrue(agg.has_category(ErrorCategory.ACP))
        summary = agg.summary()
        self.assertEqual(summary["total"], 2)
        self.assertEqual(summary["by_category"]["glasser"], 1)
        self.assertEqual(summary["by_category"]["acp"], 1)
        self.assertEqual(len(agg.notices()), 2)

    def test_process_sheet_reports_glasser_error_when_no_reels(self):
        from tools.app.backend.research_engine.research import _process_sheet
        import uuid
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            job_id = uuid.uuid4().hex[:12]
            sheet = {
                "name": "Kênh lỗi Glasser",
                "slug": "kenh-loi-glasser",
                "targets": [{"name": "fail_chan", "url": "https://facebook.com/fail_chan", "handle": "fail_chan"}],
            }
            job = {
                "id": job_id,
                "status": "running",
                "created_at": "2026-01-01",
                "sheets": [{
                    "name": sheet["name"],
                    "slug": sheet["slug"],
                    "status": "pending",
                    "targets": 1,
                    "reels": 0,
                    "topics": [],
                    "error": None,
                    "notice": None,
                }],
                "logs": [],
            }
            self._store.put(job)

            glasser_mock_error = {
                "error_type": "GlasserMissingKeyError",
                "message": "Chưa cấu hình GLASSER_API_KEY cho Glasser CLI.",
                "handle": "fail_chan",
                "suggestion": "Thêm GLASSER_API_KEY vào .env",
            }
            with mock.patch("tools.app.backend.research_engine.research.run_analyzer_pipeline", return_value={"all_reels": [], "errors": [glasser_mock_error], "metadata": {}}):
                _process_sheet(job_id, 1, 1, sheet, run_dir, {"agent": "agy", "window_hours": 48})

            snap = self._store.snapshot(job_id)
            target_sheet = snap["sheets"][0]
            self.assertEqual(target_sheet["status"], "failed")
            self.assertIn("Chưa cấu hình hoặc thiếu GLASSER_API_KEY", target_sheet["notice"])
            self.assertIn("GLASSER_API_KEY", target_sheet["error"])

    def test_process_sheet_with_single_reel_url(self):
        from tools.app.backend.research_engine.research import _process_sheet
        import uuid
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            job_id = uuid.uuid4().hex[:12]
            sheet = {
                "name": "Reel Đã Lưu Test",
                "slug": "reel-da-luu-test",
                "targets": [{"name": "Reel 1963371435020478", "url": "https://www.facebook.com/reel/1963371435020478"}],
            }
            job = {
                "id": job_id,
                "status": "running",
                "created_at": "2026-01-01",
                "sheets": [{
                    "name": sheet["name"],
                    "slug": sheet["slug"],
                    "status": "pending",
                    "targets": 1,
                    "reels": 0,
                    "topics": [],
                    "error": None,
                    "notice": None,
                }],
                "logs": [],
            }
            self._store.put(job)
            mock_topic = {
                "title": "Chủ đề thử nghiệm từ Reel",
                "hook": "Hook 3 giây mở đầu",
                "prompt": "[CAMERA & COMPOSITION]\nKhung hình 9:16",
                "source_urls": ["https://www.facebook.com/reel/1963371435020478"],
            }
            with mock.patch("tools.loop.viral_analyzer.video_research.pipeline.fetch_reel_transcript", return_value="Nội dung transcript mẫu"):
                with mock.patch("tools.loop.viral_analyzer.video_research.pipeline._download_reel_video", return_value=None):
                    with mock.patch("tools.loop.viral_analyzer.video_research.pipeline.analyze_video_structure", return_value=([mock_topic], None)):
                        _process_sheet(job_id, 1, 1, sheet, run_dir, {"agent": "agy", "window_hours": 48}, job_kind="reel")

            snap = self._store.snapshot(job_id)
            target_sheet = snap["sheets"][0]
            self.assertEqual(target_sheet["status"], "completed")
            self.assertEqual(target_sheet["reels"], 1)
            self.assertEqual(len(target_sheet["topics"]), 1)
            self.assertIsNone(target_sheet["error"])
            self.assertIn("https://www.facebook.com/reel/1963371435020478", target_sheet["topics"][0]["source_urls"])
            self.assertTrue(bool(target_sheet["topics"][0].get("prompt")))

    def test_research_single_reel_returns_one_prompt(self):
        from tools.loop.viral_analyzer.video_research import pipeline as reel_research

        url = "https://www.facebook.com/reel/1963371435020478"
        fake_topics = [{"title": f"T{i}", "prompt": "p", "source_urls": [url]} for i in range(3)]
        with mock.patch.object(reel_research, "fetch_reel_transcript", return_value="Nội dung"):
            with mock.patch.object(reel_research, "fetch_top_reels_transcripts", return_value=None):
                with mock.patch.object(reel_research, "_download_reel_video", return_value=None):
                    with mock.patch.object(reel_research, "analyze_video_structure", return_value=(fake_topics, None)):
                        agent_res = reel_research.research_single_reel(url, agent_id="agy", cwd=Path("."))
                    heuristic_res = reel_research.research_single_reel(url, agent_id=None)

        self.assertEqual(len(agent_res["topics"]), 1)
        self.assertEqual(len(heuristic_res["topics"]), 1)
        self.assertTrue(agent_res["topics"][0]["prompt"])

    def test_agy_host_bridge_validation_and_resolve_agent(self):
        from tools.app import agy_host_bridge
        from tools.app.backend.research_engine import research as research_mod

        self.assertEqual(agy_host_bridge._validate_agy_command(["agy", "acp"]), ["agy", "acp"])
        self.assertEqual(
            agy_host_bridge._validate_agy_command(["agy", "--model", "gemini-4-hydrogen-low", "acp"]),
            ["agy", "--model", "gemini-4-hydrogen-low", "acp"],
        )
        with self.assertRaises(ValueError):
            agy_host_bridge._validate_agy_command(["bash", "-c", "id"])

        with mock.patch.dict(os.environ, {"AGY_HOST_BRIDGE": "host.docker.internal:8766"}, clear=False):
            with mock.patch("tools.app.backend.research_engine.research.shutil.which", return_value=None):
                resolved = research_mod.resolve_agent("agy", model="gemini-4-hydrogen-low")
        self.assertEqual(resolved["command"], ["agy", "--model", "gemini-4-hydrogen-low", "acp"])

    def test_analyze_video_structure_without_3_topics(self):
        from tools.loop.viral_analyzer.video_research import pipeline as reel_research

        url = "https://www.instagram.com/reel/Dcxb-meiex7/"
        captured_prompts = []
        agent_json = json.dumps(
            [{"title": "Phân tích video", "why_viral": "Hook mạnh", "outline": ["Hook", "Thân", "CTA"], "source_urls": [url]}],
            ensure_ascii=False,
        )
        ctx = reel_research.runtime.EngineContext(agent_runner=lambda p: (captured_prompts.append(p), agent_json)[1])
        with mock.patch.object(reel_research, "fetch_top_reels_transcripts", return_value=None):
            topics, err = reel_research.analyze_video_structure(
                agent_id="agy",
                sheet_name="Reel đã lưu",
                targets=[{"name": "Reel đã lưu", "url": url}],
                reels=[{"url": url, "reel_url": url, "video_id": "Dcxb-meiex7", "platform": "instagram"}],
                cwd=Path("."),
                timeout_sec=10,
                log=lambda _m: None,
                ctx=ctx,
                limit=1,
            )

        self.assertIsNone(err)
        self.assertEqual(len(topics), 1)
        self.assertIn("why_viral", captured_prompts[0])
        self.assertNotIn("Đề xuất ĐÚNG 3 chủ đề", captured_prompts[0])

    def test_research_single_reel_analyzes_and_deletes_video(self):
        from tools.loop.viral_analyzer.video_research import pipeline as reel_research

        url = "https://www.facebook.com/reel/1963371435020478"
        with tempfile.TemporaryDirectory() as tmp:
            video = Path(tmp) / "reel_1963371435020478.mp4"
            video.write_bytes(b"video-bytes")
            with mock.patch.object(reel_research, "fetch_reel_transcript", return_value="Nội dung"):
                with mock.patch.object(reel_research, "fetch_top_reels_transcripts", return_value=None):
                    with mock.patch.object(reel_research, "_download_reel_video", return_value=video):
                        with mock.patch.object(
                            reel_research,
                            "analyze_video_visuals",
                            return_value="Bối cảnh bếp sáng, góc máy cận cảnh, có chữ overlay.",
                        ):
                            with mock.patch.object(reel_research, "analyze_video_structure", return_value=([], None)):
                                res = reel_research.research_single_reel(
                                    url, agent_id="agy", cwd=Path(".")
                                )

        self.assertFalse(video.exists())
        self.assertIn("bếp", res["visual"])
        self.assertIn("bếp", res["topics"][0]["prompt"])

    def test_acp_prompt_sends_image_blocks(self):
        from tools.app.backend.acp import ACPClient

        client = object.__new__(ACPClient)
        client.timeout_sec = 1
        sent = {}
        client.request = lambda method, params, timeout=None: sent.update(params) or {}

        client.prompt("session-1", "mô tả video", images=[(b"frame-bytes", "image/jpeg")])

        self.assertEqual(sent["prompt"][0], {"type": "text", "text": "mô tả video"})
        self.assertEqual(sent["prompt"][1]["type"], "image")
        self.assertEqual(sent["prompt"][1]["mimeType"], "image/jpeg")
        self.assertTrue(sent["prompt"][1]["data"])

    def test_centralized_cache(self):
        from tools.loop.viral_analyzer.cache import (
            connect_db,
            get_cached_transcript,
            persist_to_database,
            read_cached_reels,
            write_cached_reels,
        )

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            # 1. Negative cache for 404 channels (empty reels, status='not_found') must hit cache
            write_cached_reels("dead_channel_test", [], status="not_found")
            hit = read_cached_reels("dead_channel_test")
            self.assertIsNotNone(hit)
            self.assertEqual(hit[0], [])
            self.assertEqual(hit[1], "not_found")

            # 2. Cross-run persistence preserves transcript & computes acceleration
            reel_run_1 = [{
                "video_id": "v100_test",
                "url": "https://facebook.com/reel/v100_test",
                "author_handle": "chef_test",
                "title": "Món ngon",
                "views": 1000,
                "likes": 50,
                "comments": 5,
                "shares": 2,
                "published_at": "2026-11-08T00:00:00+00:00",
                "current_pool": 2,
                "velocity_per_hour": 100.0,
                "comment_ratio": 0.1,
                "transcript": "Xin chào các bạn",
            }]
            persist_to_database(reel_run_1)
            self.assertEqual(get_cached_transcript("v100_test"), "Xin chào các bạn")

            reel_run_2 = [{
                **reel_run_1[0],
                "views": 5000,
                "current_pool": 3,
                "velocity_per_hour": 250.0,
                "transcript": None,  # Must not overwrite existing transcript with None
            }]
            persist_to_database(reel_run_2)
            self.assertEqual(get_cached_transcript("v100_test"), "Xin chào các bạn")

            with connect_db() as conn:
                snaps = conn.execute(
                    "SELECT velocity_per_hour, acceleration FROM metric_snapshots WHERE video_id = 'facebook:v100_test' ORDER BY id ASC"
                ).fetchall()
                self.assertEqual(len(snaps), 2)
                self.assertEqual(snaps[0], (100.0, 0.0))
                self.assertEqual(snaps[1], (250.0, 150.0))

            # 3. Legacy JSON auto-import into PostgreSQL cache
            legacy_file = root / "glasser_legacy_chan_test.json"
            legacy_file.write_text(
                json.dumps({"reels": [{"video_id": "v300_test"}], "status": "ok"}), encoding="utf-8"
            )
            hit_legacy = read_cached_reels("legacy_chan_test", cache_dir=root)
            self.assertIsNotNone(hit_legacy)
            self.assertEqual(len(hit_legacy[0]), 1)
            self.assertEqual(hit_legacy[0][0]["video_id"], "v300_test")

    def test_run_job_and_purge_and_bounded_server(self):
        import concurrent.futures
        import threading
        import urllib.request
        from tools.app.backend import blobs, db, handler, server
        from tools.app.backend.video_engine import jobs as video_jobs
        from tools.app.backend.research_engine import research

        # Phase 5: schema applies twice cleanly
        db.init_schema()
        db.init_schema()

        # Phase 4: run_job completes with RUNS_ROOT unused and uploads result.json
        payload = {"sheets": [{"name": "Sheet 1", "targets": []}]}
        job = create_job(
            json.dumps(payload).encode("utf-8"),
            "test.json",
            {"agent": "agy", "window_hours": 48},
            "client-1",
            user_id="u_run",
        )
        research.run_job(job)
        snap = self._store.snapshot(job["id"], user_id="u_run")
        self.assertEqual(snap["status"], "completed")
        self.assertFalse(self._runs_root.exists())
        res_blob = json.loads(blobs.get(f"runs/{job['id']}/result.json"))
        self.assertEqual(res_blob["sheet"], "Sheet 1")

        # Phase 9: purge_expired removes expired jobs and video_jobs from DB and bucket
        old_ts = "2020-01-01T00:00:00+00:00"
        self._store.put({"id": "exp_job", "status": "completed", "created_at": old_ts, "user_id": "u_run", "sheets": []})
        blobs.put("runs/exp_job/result.json", b"{}")
        with db.tx() as conn:
            conn.execute(
                "INSERT INTO video_jobs (id, user_id, prompt, profile_media_id, cost, status, blob_key, created_at) "
                "VALUES ('exp_vjob', 'u_run', 'p', 'm1', 100, 'completed', 'videos/u_run/exp_vjob/output.mp4', %s)",
                (old_ts,),
            )
        blobs.put("videos/u_run/exp_vjob/output.mp4", b"mp4")
        handler.purge_expired()
        self.assertIsNone(self._store.snapshot("exp_job"))
        self.assertIsNone(video_jobs.VIDEO_STORE.get_job("u_run", "exp_vjob"))
        with self.assertRaises(FileNotFoundError):
            blobs.get("runs/exp_job/result.json")
        with self.assertRaises(FileNotFoundError):
            blobs.get("videos/u_run/exp_vjob/output.mp4")

        # Phase 8: BoundedHTTPServer caps concurrent request threads at max_workers
        active, max_active = 0, 0
        lock = threading.Lock()

        class SlowHandler(server.BaseHTTPRequestHandler):
            def do_GET(self_h):
                nonlocal active, max_active
                with lock:
                    active += 1
                    max_active = max(max_active, active)
                time.sleep(0.02)
                with lock:
                    active -= 1
                self_h.send_response(200)
                self_h.end_headers()
                self_h.wfile.write(b"ok")

            def log_message(self_h, *args):
                pass

        httpd = server.BoundedHTTPServer(("127.0.0.1", 0), SlowHandler, max_workers=16)
        port = httpd.server_address[1]
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=200) as ex:
                statuses = list(ex.map(lambda _: urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=30).status, range(200)))
            self.assertEqual(len(statuses), 200)
            self.assertLessEqual(max_active, 16)
        finally:
            httpd.server_close()

    def test_post_jobs_job_kind_validation_and_default(self):
        import io
        from tools.app.backend import server

        class FakeHandler(server.Handler):
            def __init__(self, path: str, body: bytes):
                self.command = "POST"
                self.path = path
                self.headers = {
                    "X-User-Id": "u_kind",
                    "Content-Type": "application/json",
                    "Content-Length": str(len(body)),
                }
                self.rfile = io.BytesIO(body)
                self.wfile = io.BytesIO()
                self.client_address = ("127.0.0.1", 12345)
                self.response_status = None
                self.response_headers = {}

            def send_response(self, code, message=None):
                self.response_status = code

            def send_header(self, keyword, value):
                self.response_headers[keyword.lower()] = value

            def end_headers(self):
                pass

        body = json.dumps({
            "sheets": [{"name": "Test", "targets": [{"name": "A", "url": "https://facebook.com/a"}]}]
        }).encode("utf-8")

        with mock.patch("tools.app.backend.server.configured_agent", return_value={"id": "agy"}):
            # Invalid job_kind -> 400
            h_bad = FakeHandler("/api/jobs?job_kind=bogus", body)
            h_bad.do_POST()
            self.assertEqual(h_bad.response_status, 400)

            # Missing job_kind -> defaults to profile, transcribe=False
            h_default = FakeHandler("/api/jobs", body)
            h_default.do_POST()
            self.assertEqual(h_default.response_status, 202)
            job_default = json.loads(h_default.wfile.getvalue().decode())
            self.assertEqual(job_default["job_kind"], "profile")
            self.assertFalse(job_default["options"]["transcribe"])

            # Explicit job_kind=reel&transcribe=1
            h_reel = FakeHandler("/api/jobs?job_kind=reel&transcribe=1", body)
            h_reel.do_POST()
            self.assertEqual(h_reel.response_status, 202)
            job_reel = json.loads(h_reel.wfile.getvalue().decode())
            self.assertEqual(job_reel["job_kind"], "reel")
            self.assertTrue(job_reel["options"]["transcribe"])

    def test_reel_job_routes_to_research_single_reel(self):
        from tools.app.backend.research_engine.research import _process_sheet

        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir)
            job_id = "job_route_reel"
            sheet = {
                "name": "Reel đã lưu",
                "slug": "reel-da-luu",
                "targets": [{"name": "R1", "url": "https://www.facebook.com/reel/123456"}],
            }
            self._store.put({
                "id": job_id,
                "job_kind": "reel",
                "status": "running",
                "created_at": "2026-01-01",
                "sheets": [{
                    "name": sheet["name"],
                    "slug": sheet["slug"],
                    "status": "pending",
                    "targets": 1,
                    "reels": 0,
                    "topics": [],
                    "error": None,
                    "notice": None,
                }],
                "logs": [],
            })
            with mock.patch("tools.app.backend.research_engine.research.research_single_reel", return_value={"topics": [{"title": "T1", "source_urls": ["https://www.facebook.com/reel/123456"]}], "reel_url": "https://www.facebook.com/reel/123456", "video_id": "123456"}) as mock_reel, \
                 mock.patch("tools.app.backend.research_engine.research.run_profile_research") as mock_profile:
                _process_sheet(job_id, 1, 1, sheet, run_dir, {"agent": "agy"}, job_kind="reel")
            mock_reel.assert_called_once()
            mock_profile.assert_not_called()

    def test_reel_job_limits_to_single_video_and_five_concurrent_claims_per_user(self):
        from tools.app.backend.research_engine.research import _process_sheet, create_job
        from tools.app.backend.store import JobStore

        payload = json.dumps({
            "sheets": [{
                "name": "Multi reel",
                "targets": [
                    {"name": "R1", "url": "https://www.facebook.com/reel/111"},
                    {"name": "R2", "url": "https://www.facebook.com/reel/222"},
                    {"name": "R3", "url": "https://www.facebook.com/reel/333"},
                ],
            }],
        }).encode("utf-8")
        created = create_job(payload, "multi.json", {"agent": "agy"}, "c1", user_id="u_five", job_kind="reel")
        self.assertEqual(created["sheets"][0]["targets"], 1)
        self.assertEqual(len(created["sheets"][0]["target_list"]), 1)

        with tempfile.TemporaryDirectory() as tmpdir:
            sheet = {
                "name": "Multi reel",
                "slug": "multi-reel",
                "targets": [
                    {"name": "R1", "url": "https://www.facebook.com/reel/111"},
                    {"name": "R2", "url": "https://www.facebook.com/reel/222"},
                ],
            }
            with mock.patch(
                "tools.app.backend.research_engine.research.research_single_reel",
                return_value={"topics": [{"title": "T1", "source_urls": ["https://www.facebook.com/reel/111"]}], "reel_url": "https://www.facebook.com/reel/111", "video_id": "111"},
            ) as mock_reel:
                _process_sheet(created["id"], 1, 1, sheet, Path(tmpdir), {"agent": "agy"}, job_kind="reel")
            mock_reel.assert_called_once()

        store = JobStore()
        for i in range(6):
            store.put({
                "id": f"u5_job_{i}",
                "client_id": f"c_{i}",
                "user_id": "u_five",
                "status": "queued",
                "created_at": f"2026-01-01T00:00:0{i}Z",
                "sheets": [],
            })
        claimed = [store.claim(5) for _ in range(5)]
        self.assertTrue(all(c is not None for c in claimed))
        self.assertIsNone(store.claim(5))
        store.update("u5_job_0", status="completed")
        self.assertEqual(store.claim(5)["id"], "u5_job_5")

    def test_persist_to_database_handles_existing_url_with_different_id(self):
        from tools.app.backend.db import tx
        from tools.loop.viral_analyzer.cache import persist_to_database

        dup_url = "https://www.facebook.com/reel/1638767047082365"
        with tx() as conn:
            conn.execute("DELETE FROM videos WHERE url = %s OR id IN ('legacy:1638767047082365', 'facebook:1638767047082365')", (dup_url,))
            conn.execute(
                "INSERT INTO videos (id, platform, video_id, url, author_handle, title) "
                "VALUES ('legacy:1638767047082365', 'facebook', 'legacy_id', %s, 'chef', 'Old')",
                (dup_url,),
            )

        reel = {
            "platform": "facebook",
            "video_id": "1638767047082365",
            "url": dup_url,
            "author_handle": "chef",
            "title": "Updated",
            "current_pool": 2,
            "published_at": "2026-11-24T00:00:00Z",
            "views": 1000,
            "likes": 10,
            "comments": 2,
            "shares": 1,
            "velocity_per_hour": 50.0,
        }
        persist_to_database([reel, reel])

        with tx() as conn:
            row = conn.execute("SELECT title, current_pool FROM videos WHERE url = %s", (dup_url,)).fetchone()
        self.assertEqual(row[0], "Updated")
        self.assertEqual(row[1], 2)

    def test_run_job_marks_job_failed_when_all_sheets_fail_and_list_jobs_reflects_it(self):
        from tools.app.backend.research_engine.research import create_job, run_job
        from tools.app.backend.store import JobStore

        payload = json.dumps({
            "sheets": [{"name": "Fail Sheet", "targets": [{"name": "A", "url": "https://facebook.com/a"}]}],
        }).encode("utf-8")
        created = create_job(payload, "fail.json", {"agent": "agy"}, "c_fail", user_id="u_fail_status", job_kind="profile")

        with mock.patch(
            "tools.app.backend.research_engine.research.run_analyzer_pipeline",
            return_value={
                "all_reels": [],
                "errors": [{"error_type": "GlasserMissingKeyError", "message": "Missing key", "handle": "a"}],
                "metadata": {},
            },
        ):
            run_job(created)

        store = JobStore()
        snap = store.snapshot(created["id"])
        self.assertEqual(snap["status"], "failed")
        self.assertEqual(snap["sheets"][0]["status"], "failed")

        # Legacy completed job whose sheets all failed should also show as failed in list_jobs
        store.update(created["id"], status="completed")
        listed = [j for j in store.list_jobs(user_id="u_fail_status") if j["id"] == created["id"]]
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]["status"], "failed")

    def test_research_single_reel_resolves_real_author_handle(self):
        from tools.loop.viral_analyzer.video_research import pipeline as reel_research

        with mock.patch.object(reel_research, "fetch_reel_transcript", return_value="Transcript"):
            res_explicit = reel_research.research_single_reel(
                "https://www.facebook.com/reel/123",
                author_handle="chef_nam",
                author_name="Chef Nam",
            )
            res_tiktok = reel_research.research_single_reel("https://www.tiktok.com/@doc_yt/video/999")
            res_unknown = reel_research.research_single_reel("https://www.facebook.com/reel/999888777")

        self.assertEqual(res_explicit["topics"][0]["author_handle"], "chef_nam")
        self.assertEqual(res_explicit["topics"][0]["author_name"], "Chef Nam")
        self.assertEqual(res_tiktok["topics"][0]["author_handle"], "doc_yt")
        self.assertEqual(res_unknown["topics"][0]["author_handle"], "")

    def test_research_single_reel_falls_back_to_local_asr_when_glasser_returns_none(self):
        from tools.loop.viral_analyzer.video_research import pipeline as reel_research

        with tempfile.TemporaryDirectory() as tmpdir:
            video_path = Path(tmpdir) / "reel_999.mp4"
            video_path.write_bytes(b"fake-mp4")
            url = "https://www.facebook.com/reel/999"
            with mock.patch.object(reel_research, "fetch_reel_transcript", return_value=None), \
                 mock.patch.object(reel_research, "_download_reel_video", return_value=video_path), \
                 mock.patch.object(reel_research, "_transcribe_local_fallback", return_value="Local ASR text") as mock_local, \
                 mock.patch.object(reel_research, "analyze_video_visuals", return_value="Visuals"), \
                 mock.patch.object(reel_research, "analyze_video_structure", return_value=([{"title": "T1", "source_urls": [url]}], None)) as mock_suggest:
                res = reel_research.research_single_reel(url, agent_id="agy", cwd=Path(tmpdir))
            mock_local.assert_called_once()
            self.assertEqual(res["transcript"], "Local ASR text")
            self.assertEqual(mock_suggest.call_args.kwargs["reels"][0]["transcript"], "Local ASR text")

    def test_expand_keyword_and_viral_video_search(self):
        from tools.loop.viral_analyzer.keyword_research import (
            expand_keyword,
            pipeline as keyword_search,
            run_viral_video_search,
        )

        queries = expand_keyword("gyno conditions")
        self.assertEqual([q["text"] for q in queries], ["gyno conditions", "gynecomastia", "nữ hóa tuyến vú"])
        self.assertEqual([q["kind"] for q in queries], ["original", "abbreviation", "vi"])

        calls = []

        def fake_glasser(provider, endpoint, version, payload, cache_dir, task_id=None, timeout=45.0):
            calls.append((provider, endpoint, payload))
            if provider == "scrapecreators" and endpoint == "/v1/youtube/search":
                return {"videos": [{"id": "yt1", "title": "YT Gyno", "url": "https://www.youtube.com/watch?v=yt1", "viewCountInt": 12000, "channel": {"title": "Dr YT", "url": "https://www.youtube.com/@dryt"}}]}, "glasser_api", None
            if provider == "serper" and endpoint == "/videos" and "site:facebook.com" in str(payload.get("q", "")):
                return {"videos": [{"title": "FB Gyno", "link": "https://www.facebook.com/reel/999", "channel": "FB Page"}]}, "glasser_api", None
            if provider == "serper" and endpoint == "/search" and "site:facebook.com" in str(payload.get("q", "")):
                return {"organic": [{"title": "FB Page Gyno Post", "link": "https://www.facebook.com/fbpage/posts/12345"}]}, "glasser_api", None
            if provider == "scrapecreators" and endpoint == "/v1/facebook/adLibrary/search/ads":
                return {"results": [{"ad_archive_id": "ad1", "page_name": "FB Ad Page", "snapshot": {"page_name": "FB Ad Page", "page_profile_uri": "https://www.facebook.com/fbadpage", "body": {"text": "Gyno post"}}}]}, "glasser_api", None
            if provider == "serper" and endpoint == "/videos":
                return {"videos": [{"title": "Google Gyno", "link": "https://www.youtube.com/watch?v=yt1", "channel": "Dr YT"}]}, "glasser_api", None
            if provider == "scrapecreators" and endpoint == "/v1/tiktok/search/keyword":
                return {"search_item_list": [{"aweme_info": {"aweme_id": "tt1", "desc": "TT Gyno", "statistics": {"play_count": 50000, "digg_count": 1200}, "author": {"unique_id": "ttdoc", "nickname": "TT Doc"}}}]}, "glasser_api", None
            if provider == "scrapecreators" and endpoint == "/v2/instagram/reels/search":
                return {"reels": [{"code": "ig1", "caption": {"text": "IG Gyno"}, "play_count": 30000, "user": {"username": "igdoc", "full_name": "IG Doc"}}]}, "glasser_api", None
            return {}, "glasser_api", None

        def fake_enrich(creators):
            for c in creators:
                if c.get("url"):
                    c["followers"] = 1234

        def fake_agent(prompt):
            return json.dumps({
                "https://www.youtube.com/@dryt": {"relevance": "direct", "why_relevant": "Covers gyno directly"},
                "https://www.tiktok.com/@ttdoc": {"relevance": "direct", "why_relevant": "TikTok gyno video"},
                "https://www.instagram.com/igdoc/": {"relevance": "adjacent", "why_relevant": "IG health clip"},
                "https://www.facebook.com/fbpage": {"relevance": "direct", "why_relevant": "FB page post"},
                "https://www.facebook.com/fbadpage": {"relevance": "adjacent", "why_relevant": "FB ad page"},
            })

        from tools.loop.viral_analyzer import runtime

        ctx = runtime.EngineContext(agent_runner=fake_agent)
        with tempfile.TemporaryDirectory() as tmpdir, \
             mock.patch.object(keyword_search, "_glasser_run_json", side_effect=fake_glasser), \
             mock.patch.object(keyword_search, "_enrich_creator_followers", side_effect=fake_enrich):
            res = run_viral_video_search("gyno conditions", Path(tmpdir), ctx=ctx)

        self.assertLessEqual(len(calls), 28)
        self.assertEqual(len(res["queries"]), 3)
        # yt1 appears in both YouTube and Google results -> deduplicated
        urls = [r["url"] for r in res["reels"]]
        self.assertEqual(len(urls), len(set(urls)))
        self.assertEqual(res["reels"][0]["platform"], "tiktok")
        self.assertEqual(res["reels"][0]["views"], 50000)
        creator_platforms = {c["platform"] for c in res["creators"]}
        self.assertEqual(creator_platforms, {"youtube", "tiktok", "instagram", "facebook"})
        for c in res["creators"]:
            self.assertTrue(c["url"].startswith("http"))
            self.assertGreater(c["followers"], 0)
            self.assertIn(c.get("relevance"), {"direct", "adjacent"})
            self.assertTrue(c.get("why_relevant"))

    def test_social_handle_and_saved_reels_post(self):
        import io
        from contextlib import contextmanager
        from tools.app.backend import server
        from tools.app.backend.profiles import detect_platform, social_handle

        self.assertEqual(detect_platform("https://www.youtube.com/@drericberg"), "youtube")
        self.assertEqual(social_handle("https://www.youtube.com/@drericberg"), ("drericberg", "https://www.youtube.com/@drericberg"))
        self.assertEqual(social_handle("https://www.tiktok.com/@ttdoc"), ("ttdoc", "https://www.tiktok.com/@ttdoc"))
        self.assertEqual(social_handle("https://www.instagram.com/igdoc/"), ("igdoc", "https://www.instagram.com/igdoc/"))
        self.assertEqual(social_handle("https://www.facebook.com/bepongbay"), ("bepongbay", "https://www.facebook.com/bepongbay"))

        executed = []

        class FakeConn:
            def execute(self, sql, params=None):
                executed.append((sql, params))
                return mock.MagicMock()

        @contextmanager
        def fake_tx():
            yield FakeConn()

        class FakePostHandler(server.Handler):
            def __init__(self, path: str, body: bytes):
                self.command = "POST"
                self.path = path
                self.headers = {"X-User-Id": "u_kw", "Content-Type": "application/json", "Content-Length": str(len(body))}
                self.rfile = io.BytesIO(body)
                self.wfile = io.BytesIO()
                self.client_address = ("127.0.0.1", 12345)
                self.response_status = None

            def send_response(self, code, message=None):
                self.response_status = code

            def send_header(self, keyword, value):
                pass

            def end_headers(self):
                pass

        save_body = json.dumps({"reel_url": "https://www.tiktok.com/@ttdoc/video/123", "title": "TT Gyno", "sender_name": "ttdoc"}).encode("utf-8")
        with mock.patch("tools.app.backend.db.tx", fake_tx), \
             mock.patch.object(server, "tx", fake_tx, create=True):
            h = FakePostHandler("/api/saved-reels", save_body)
            h.do_POST()
        self.assertEqual(h.response_status, 200)
        resp = json.loads(h.wfile.getvalue().decode())
        self.assertEqual(resp["reel"]["platform"], "tiktok")
        self.assertTrue(any("INSERT INTO saved_reels" in sql for sql, _ in executed))

    def test_multi_platform_url_helpers_and_workbook(self):
        from tools.app.backend.profiles import _normalize_target, is_social_url
        from tools.loop.viral_analyzer.video_research.pipeline import (
            canonicalize_reel_url,
            extract_video_id,
            is_reel_url,
        )

        cases = [
            ("https://www.youtube.com/watch?feature=share&v=abc123XYZ", "https://www.youtube.com/watch?v=abc123XYZ", "youtube", "abc123XYZ"),
            ("https://www.youtube.com/shorts/short999?si=1", "https://www.youtube.com/shorts/short999", "youtube", "short999"),
            ("https://youtu.be/youtu1234?t=5", "https://www.youtube.com/watch?v=youtu1234", "youtube", "youtu1234"),
            ("https://www.tiktok.com/@creator/video/7499229683859426602?is_from_webapp=1", "https://www.tiktok.com/@creator/video/7499229683859426602", "tiktok", "7499229683859426602"),
            ("https://www.instagram.com/reel/DOq6eV6iIgD/?igsh=1", "https://www.instagram.com/reel/DOq6eV6iIgD", "instagram", "DOq6eV6iIgD"),
            ("https://www.instagram.com/p/PostCode99/?igsh=1", "https://www.instagram.com/p/PostCode99", "instagram", "PostCode99"),
            (
                "https://www.facebook.com/61552426085742/posts/kh%E1%BB%91i-u-v%C3%BA-c%C3%B3-th%E1%BB%83-bi%E1%BA%BFn-m%E1%BA%A5t-ch%E1%BB%89-nh%E1%BB%9D-thu%E1%BB%91c-nam-vi%E1%BB%87n-gi%C3%A1p-v%C3%BA-gan-bs-l%C3%AA-l%C3%BD-tr%E1%BB%8Dng-h%C6%B0ng/122353337234080869/",
                "https://www.facebook.com/61552426085742/posts/kh%E1%BB%91i-u-v%C3%BA-c%C3%B3-th%E1%BB%83-bi%E1%BA%BFn-m%E1%BA%A5t-ch%E1%BB%89-nh%E1%BB%9D-thu%E1%BB%91c-nam-vi%E1%BB%87n-gi%C3%A1p-v%C3%BA-gan-bs-l%C3%AA-l%C3%BD-tr%E1%BB%8Dng-h%C6%B0ng/122353337234080869",
                "facebook",
                "122353337234080869",
            ),
            (
                "https://www.facebook.com/61552426085742/posts/pfbid02AbC123xyz/?mibextid=abc",
                "https://www.facebook.com/61552426085742/posts/pfbid02AbC123xyz",
                "facebook",
                "pfbid02AbC123xyz",
            ),
            (
                "https://www.facebook.com/somepage/videos/some-title-slug/9876543210/?ref=share",
                "https://www.facebook.com/somepage/videos/some-title-slug/9876543210",
                "facebook",
                "9876543210",
            ),
            (
                "https://www.facebook.com/permalink.php?id=61552426085742&story_fbid=pfbid02xyz&mibextid=1",
                "https://www.facebook.com/permalink.php?story_fbid=pfbid02xyz&id=61552426085742",
                "facebook",
                "pfbid02xyz",
            ),
        ]
        for raw, expected_url, expected_platform, expected_vid in cases:
            self.assertTrue(is_reel_url(raw), raw)
            self.assertEqual(canonicalize_reel_url(raw, resolve_redirects=False), (expected_url, expected_platform))
            self.assertEqual(extract_video_id(expected_url), expected_vid)
            norm = _normalize_target(raw, name="Video")
            self.assertEqual(norm["url"], expected_url)
            self.assertEqual(norm["platform"], expected_platform)

        for non_reel in (
            "https://www.facebook.com/61552426085742",
            "https://www.facebook.com/61552426085742/posts/",
            "https://www.facebook.com/61552426085742/posts/10-meo-hay/",
            "https://www.facebook.com/61552426085742/videos/",
        ):
            self.assertFalse(is_reel_url(non_reel), non_reel)

        self.assertTrue(is_social_url("https://www.youtube.com/@drericberg"))
        self.assertTrue(is_social_url("https://www.tiktok.com/@ttdoc"))
        self.assertTrue(is_social_url("https://www.instagram.com/igdoc/"))
        self.assertFalse(is_social_url("https://example.com/profile"))

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "multi.xlsx"
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Multi"
            ws.append(["url", "name"])
            ws.append(["https://www.youtube.com/@drericberg", "Dr Eric Berg"])
            ws.append(["https://www.tiktok.com/@ttdoc", "TT Doc"])
            ws.append(["https://www.instagram.com/igdoc/", "IG Doc"])
            ws.append(["https://www.facebook.com/fbpage", "FB Page"])
            wb.save(path)

            sheets = parse_workbook(path)
            targets = sheets[0]["targets"]
            self.assertEqual(len(targets), 4)
            self.assertEqual([t["platform"] for t in targets], ["youtube", "tiktok", "instagram", "facebook"])
            self.assertEqual([t["handle"] for t in targets], ["drericberg", "ttdoc", "igdoc", "fbpage"])

    def test_fetch_target_reels_and_pipeline_multi_platform(self):
        from datetime import datetime, timedelta, timezone
        import subprocess
        from tools.loop.viral_analyzer import glasser as va_glasser

        now_utc = datetime.now(timezone.utc)
        fresh_iso = (now_utc - timedelta(hours=6)).isoformat()
        old_iso = (now_utc - timedelta(days=7)).isoformat()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = load_config({
                "window_hours": 48,
                "storage": {
                    "video_dir": str(root / "videos"),
                    "output_file": str(root / "out.json"),
                },
                "targets": [
                    {"handle": "drericberg", "url": "https://www.youtube.com/@drericberg", "name": "Dr Eric", "platform": "youtube"},
                    {"handle": "ttdoc", "url": "https://www.tiktok.com/@ttdoc", "name": "TT Doc", "platform": "tiktok"},
                    {"handle": "igdoc", "url": "https://www.instagram.com/igdoc/", "name": "IG Doc", "platform": "instagram"},
                ],
            })

            seen_calls = []

            def fake_run(cmd, *args, **kwargs):
                ep = cmd[cmd.index("-e") + 1]
                payload = json.loads(cmd[cmd.index("-i") + 1])
                out_path = Path(cmd[cmd.index("-o") + 1])
                seen_calls.append((ep, payload))
                if ep == "/v1/youtube/channel-videos":
                    out_path.write_text(json.dumps({
                        "videos": [
                            {
                                "id": "yt_v1",
                                "url": "https://www.youtube.com/watch?v=yt_v1",
                                "title": "YT Channel Video",
                                "viewCountInt": 15000,
                                "publishDate": fresh_iso,
                            },
                            {
                                "id": "yt_old",
                                "url": "https://www.youtube.com/watch?v=yt_old",
                                "title": "YT Old Video",
                                "viewCountInt": 99000,
                                "publishedTimeText": "1 week ago",
                            },
                        ]
                    }), encoding="utf-8")
                elif ep == "/v3/tiktok/profile/videos":
                    out_path.write_text(json.dumps({
                        "aweme_list": [
                            {
                                "aweme_id": "7499229683859426602",
                                "desc": "TikTok Profile Video",
                                "create_time": int(time.time()) - 3600,
                                "author": {"unique_id": "ttdoc"},
                                "statistics": {"play_count": 25000, "digg_count": 300, "comment_count": 20, "share_count": 10},
                                "video": {"play_addr": {"url_list": ["https://cdn.tiktok.local/v.mp4"]}},
                            },
                            {
                                "aweme_id": "7499229683859420000",
                                "desc": "TikTok Old Video",
                                "create_time": int(time.time()) - 7 * 86400,
                                "author": {"unique_id": "ttdoc"},
                                "statistics": {"play_count": 90000},
                            },
                        ]
                    }), encoding="utf-8")
                elif ep == "/v1/instagram/user/reels":
                    out_path.write_text(json.dumps({
                        "items": [
                            {
                                "media": {
                                    "pk": "3540614075954356349",
                                    "code": "DEiyb48AeB9",
                                    "taken_at": int(time.time()) - 7200,
                                    "play_count": 8000,
                                    "like_count": 120,
                                    "comment_count": 15,
                                    "caption": {"text": "IG User Reel"},
                                    "video_versions": [{"url": "https://cdn.ig.local/r.mp4"}],
                                }
                            },
                            {
                                "media": {
                                    "pk": "3540614075954350000",
                                    "code": "IGold1week",
                                    "created_at": old_iso,
                                    "taken_at": int(time.time()) - 7 * 86400,
                                    "play_count": 50000,
                                    "caption": {"text": "IG Old Reel"},
                                }
                            },
                        ]
                    }), encoding="utf-8")
                return subprocess.CompletedProcess(cmd, 0, stdout="Run ID: r1\nResponse: HTTP 200\nCharge: $0.00188\n", stderr="")

            with mock.patch("tools.loop.viral_analyzer.profile_research.collect.read_cached_reels", return_value=None), \
                 mock.patch("tools.loop.viral_analyzer.profile_research.collect.write_cached_reels") as mock_write_cache, \
                 mock.patch("tools.loop.viral_analyzer.glasser.check_glasser_key", return_value=(True, None)), \
                 mock.patch("tools.loop.viral_analyzer.profile_research.pipeline.persist_to_database"), \
                 mock.patch("tools.app.backend.telemetry.cost_control.record_cost_event"), \
                 mock.patch("tools.app.backend.telemetry.cost_control.shutil.which", return_value="/usr/local/bin/glasser"), \
                 mock.patch("tools.app.backend.telemetry.cost_control.subprocess.run", side_effect=fake_run):
                res = run_analyzer_pipeline(config, cache_dir=root / "cache", transcribe=False, legacy_cache=False)

            seen_by_ep = dict(seen_calls)
            self.assertEqual(set(seen_by_ep.keys()), {
                "/v1/youtube/channel-videos",
                "/v3/tiktok/profile/videos",
                "/v1/instagram/user/reels",
            })
            self.assertEqual(seen_by_ep["/v1/youtube/channel-videos"], {"handle": "drericberg", "sort": "latest"})
            self.assertEqual(seen_by_ep["/v3/tiktok/profile/videos"], {"handle": "ttdoc", "sort_by": "latest"})
            self.assertEqual(seen_by_ep["/v1/instagram/user/reels"], {"handle": "igdoc"})
            self.assertEqual({call.kwargs["handle"] for call in mock_write_cache.call_args_list}, {
                "youtube:drericberg",
                "tiktok:ttdoc",
                "instagram:igdoc",
            })

            reels = res["all_reels"]
            self.assertEqual(len(reels), 3)
            self.assertEqual({r["video_id"] for r in reels}, {"yt_v1", "7499229683859426602", "3540614075954356349"})
            by_plat = {r["platform"]: r for r in reels}
            self.assertEqual(by_plat["youtube"]["url"], "https://www.youtube.com/watch?v=yt_v1")
            self.assertEqual(by_plat["youtube"]["views"], 15000)
            self.assertEqual(by_plat["tiktok"]["likes"], 300)
            self.assertEqual(by_plat["tiktok"]["comments"], 20)
            self.assertEqual(by_plat["tiktok"]["shares"], 10)
            self.assertEqual(by_plat["instagram"]["url"], "https://www.instagram.com/reel/DEiyb48AeB9/")
            self.assertEqual(by_plat["instagram"]["likes"], 120)

    def test_research_single_reel_and_process_sheet_multi_platform(self):
        from tools.loop.viral_analyzer.video_research import pipeline as reel_research
        from tools.app.backend.research_engine.research import _process_sheet

        for url, expected_plat, expected_vid in (
            ("https://www.youtube.com/watch?v=LYxSPJPO4vE", "youtube", "LYxSPJPO4vE"),
            ("https://www.tiktok.com/@ttdoc/video/7499229683859426602", "tiktok", "7499229683859426602"),
            ("https://www.instagram.com/reel/DOq6eV6iIgD/", "instagram", "DOq6eV6iIgD"),
        ):
            with mock.patch.object(reel_research, "fetch_reel_transcript", return_value="Sample transcript") as mock_tr, \
                 mock.patch.object(reel_research, "fetch_top_reels_transcripts"), \
                 mock.patch.object(reel_research, "_download_reel_video", return_value=None):
                res = reel_research.research_single_reel(url, agent_id=None)
            mock_tr.assert_called_once_with(url.rstrip("/") if expected_plat == "instagram" else url, video_id=expected_vid)
            self.assertEqual(res["platform"], expected_plat)
            self.assertEqual(res["transcript"], "Sample transcript")
            self.assertEqual(res["topics"][0]["platform"], expected_plat)

        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = Path(tmpdir)
            job_id = "job_yt_reel"
            yt_url = "https://www.youtube.com/watch?v=LYxSPJPO4vE"
            sheet = {
                "name": "YT Saved Reel",
                "slug": "yt-saved-reel",
                "targets": [{"name": "YT Video", "url": yt_url}],
            }
            self._store.put({
                "id": job_id,
                "job_kind": "reel",
                "status": "running",
                "created_at": "2026-01-01",
                "sheets": [{
                    "name": sheet["name"],
                    "slug": sheet["slug"],
                    "status": "pending",
                    "targets": 1,
                    "reels": 0,
                    "topics": [],
                    "error": None,
                    "notice": None,
                }],
                "logs": [],
            })
            with mock.patch("tools.loop.viral_analyzer.video_research.pipeline.fetch_reel_transcript", return_value="YT tr"), \
                 mock.patch("tools.loop.viral_analyzer.video_research.pipeline._download_reel_video", return_value=None), \
                 mock.patch("tools.loop.viral_analyzer.video_research.pipeline.analyze_video_structure", return_value=([{"title": "T1", "source_urls": [yt_url], "platform": "youtube"}], None)):
                _process_sheet(job_id, 1, 1, sheet, run_dir, {"agent": "agy"}, job_kind="reel")
            snap = self._store.snapshot(job_id)
            self.assertEqual(snap["sheets"][0]["status"], "completed")
            self.assertEqual(snap["sheets"][0]["reels"], 1)
            self.assertEqual(snap["sheets"][0]["topics"][0]["platform"], "youtube")


if __name__ == "__main__":
    unittest.main()
