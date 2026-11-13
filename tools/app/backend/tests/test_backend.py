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
    heuristic_topics,
    normalize_topics,
    parse_topics,
)
from tools.app.backend.store import JobStore
from tools.loop.viral_analyzer.config import load_config
from tools.loop.viral_analyzer.pipeline import run_analyzer_pipeline
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

    def test_parse_topics_from_fenced_json(self):
        fallback = heuristic_topics("thực phẩm bẩn", [])
        answer = "```json\n" + json.dumps(
            [
                {"title": "A", "hook": "H", "angle": "G", "why_viral": "W", "outline": ["1", "2"], "source_urls": ["https://x"]},
                {"title": "B"},
                {"title": "C"},
            ],
            ensure_ascii=False,
        ) + "\n```"
        topics = parse_topics(answer, fallback)
        self.assertEqual(len(topics), 3)
        self.assertEqual(topics[0]["title"], "A")
        self.assertEqual(topics[0]["generated_by"], "agent")
        self.assertEqual(topics[1]["generated_by"], "agent")

    def test_invalid_agent_output_falls_back(self):
        fallback = heuristic_topics("mẹ bé", [])
        topics = parse_topics("xin lỗi, tôi không trả JSON", fallback)
        self.assertEqual(len(topics), 3)
        self.assertEqual(topics[0]["generated_by"], "heuristic")

    def test_normalize_pads_to_three(self):
        fallback = heuristic_topics("mẹ bé", [])
        topics = normalize_topics([{"title": "Chỉ một"}], fallback)
        self.assertEqual(len(topics), 3)

    def test_heuristic_and_normalize_topics_sorted_by_views_up_to_10(self):
        reels = [
            {"video_id": f"v_{i}", "url": f"https://www.facebook.com/reel/v_{i}", "views": i * 1000, "velocity_per_hour": i * 100}
            for i in range(1, 15)
        ]
        fallback = heuristic_topics("test sheet", reels, limit=10)
        self.assertEqual(len(fallback), 10)
        self.assertEqual(fallback[0]["views"], 14000)
        self.assertEqual(fallback[-1]["views"], 5000)
        # Verify descending order
        views_list = [t["views"] for t in fallback]
        self.assertEqual(views_list, sorted(views_list, reverse=True))

        # Test normalize_topics also preserves max 10 and descending view sort
        agent_data = [{"title": "Hot video", "source_urls": ["https://www.facebook.com/reel/v_14"]}]
        normalized = normalize_topics(agent_data, fallback, reels=reels, limit=10)
        self.assertEqual(len(normalized), 10)
        self.assertEqual(normalized[0]["views"], 14000)

    def test_normalize_topics_resolves_page_url_to_reel_url(self):
        fallback = heuristic_topics("kênh", [])
        reels = [
            {"author_handle": "my_page", "video_id": "123456", "url": "https://www.facebook.com/reel/123456"},
            {"author_handle": "another_page", "video_id": "789101", "url": "https://www.facebook.com/reel/789101"},
        ]
        # Agent provided a page URL instead of reel URL
        agent_data = [
            {"title": "T1", "source_urls": ["https://www.facebook.com/my_page"]},
            {"title": "T2", "source_urls": ["https://www.facebook.com/reel/789101"]},
        ]
        topics = normalize_topics(agent_data, fallback, reels=reels)
        # Should resolve page URL to the actual reel URL
        self.assertEqual(topics[0]["source_urls"], ["https://www.facebook.com/reel/123456"])
        self.assertEqual(topics[1]["source_urls"], ["https://www.facebook.com/reel/789101"])

    def test_normalize_topics_cross_checks_actor_profile(self):
        fallback = heuristic_topics("hôn nhân", [])
        agent_data = [
            {
                "title": "Chủ đề hôn nhân",
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
        topics = normalize_topics(agent_data, fallback, actor_profile=actor_prof)
        prompt = topics[0]["prompt"]
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
        from tools.loop.viral_analyzer.pipeline import fetch_target_reels
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
        from tools.loop.viral_analyzer.pipeline import fetch_target_reels
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
        from tools.loop.viral_analyzer.pipeline import run_analyzer_pipeline
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

    def test_suggest_topics_empty_reels_returns_empty(self):
        from tools.app.backend.research_engine.research import suggest_topics
        logs = []
        topics, err = suggest_topics(
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
            with mock.patch("tools.app.backend.research_engine.reel_research.fetch_reel_transcript", return_value="Nội dung transcript mẫu"):
                with mock.patch("tools.app.backend.research_engine.reel_research._download_reel_video", return_value=None):
                    with mock.patch("tools.app.backend.research_engine.reel_research.suggest_topics", return_value=([mock_topic], None)):
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
        from tools.app.backend.research_engine import reel_research

        url = "https://www.facebook.com/reel/1963371435020478"
        fake_topics = [{"title": f"T{i}", "prompt": "p", "source_urls": [url]} for i in range(3)]
        with mock.patch.object(reel_research, "fetch_reel_transcript", return_value="Nội dung"):
            with mock.patch.object(reel_research, "fetch_top_reels_transcripts", return_value=None):
                with mock.patch.object(reel_research, "_download_reel_video", return_value=None):
                    with mock.patch.object(reel_research, "suggest_topics", return_value=(fake_topics, None)):
                        agent_res = reel_research.research_single_reel(url, agent_id="agy", cwd=Path("."))
                    heuristic_res = reel_research.research_single_reel(url, agent_id=None)

        self.assertEqual(len(agent_res["topics"]), 1)
        self.assertEqual(len(heuristic_res["topics"]), 1)
        self.assertTrue(agent_res["topics"][0]["prompt"])

    def test_research_single_reel_analyzes_and_deletes_video(self):
        from tools.app.backend.research_engine import reel_research

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
                            with mock.patch.object(reel_research, "suggest_topics", return_value=([], None)):
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
        from tools.app.backend import blobs, db, handler, server, video_jobs
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

    def test_research_single_reel_falls_back_to_local_asr_when_glasser_returns_none(self):
        from tools.app.backend.research_engine import reel_research

        with tempfile.TemporaryDirectory() as tmpdir:
            video_path = Path(tmpdir) / "reel_999.mp4"
            video_path.write_bytes(b"fake-mp4")
            url = "https://www.facebook.com/reel/999"
            with mock.patch.object(reel_research, "fetch_reel_transcript", return_value=None), \
                 mock.patch.object(reel_research, "_download_reel_video", return_value=video_path), \
                 mock.patch.object(reel_research, "_transcribe_local_fallback", return_value="Local ASR text") as mock_local, \
                 mock.patch.object(reel_research, "analyze_video_visuals", return_value="Visuals"), \
                 mock.patch.object(reel_research, "suggest_topics", return_value=([{"title": "T1", "source_urls": [url]}], None)) as mock_suggest:
                res = reel_research.research_single_reel(url, agent_id="agy", cwd=Path(tmpdir))
            mock_local.assert_called_once()
            self.assertEqual(res["transcript"], "Local ASR text")
            self.assertEqual(mock_suggest.call_args.kwargs["reels"][0]["transcript"], "Local ASR text")


if __name__ == "__main__":
    unittest.main()
