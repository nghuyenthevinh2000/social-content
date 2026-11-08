"""Minimal checks for Excel parsing and topic parsing (run: python3 -m unittest tools.app.backend.test_backend)."""

import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import openpyxl

from tools.app.backend.profiles import (
    SocialProfileStore,
    facebook_handle,
    is_facebook_url,
    parse_workbook,
    resolve_xlsx_bytes,
    slugify,
)
from tools.app.backend.research import (
    create_job,
    heuristic_topics,
    normalize_topics,
    parse_topics,
)
from tools.loop.viral_analyzer.config import load_config
from tools.loop.viral_analyzer.pipeline import run_analyzer_pipeline
import unittest.mock as mock


class BackendTests(unittest.TestCase):
    def setUp(self):
        self._cache_tmp = tempfile.TemporaryDirectory()
        self._env_patch = mock.patch.dict(os.environ, {"VIRAL_APP_CACHE_DIR": self._cache_tmp.name})
        self._env_patch.start()

    def tearDown(self):
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
                        "db_path": str(root / "db.sqlite"),
                        "video_dir": str(root / "videos"),
                        "output_file": str(root / "out.json"),
                    },
                    "targets": [{"handle": "testhandle", "url": "https://facebook.com/testhandle", "name": "Test"}],
                }
            )
            payload = run_analyzer_pipeline(config, cache_dir=cache, media=False, legacy_cache=False)
            self.assertEqual(len(payload["all_reels"]), 2)
            self.assertEqual(payload["all_reels"][0]["current_pool"], 4)
            self.assertTrue((root / "out.json").exists())

    def test_job_store_queue(self):
        from tools.app.backend.store import JobStore

        with tempfile.TemporaryDirectory() as tmp:
            store = JobStore(Path(tmp) / "jobs.db")
            for job_id, created in (("b", "2026-01-02"), ("a", "2026-01-01")):
                store.put({"id": job_id, "status": "queued", "created_at": created, "sheets": [{"slug": "s", "status": "pending"}], "logs": []})
            self.assertEqual(store.claim(2)["id"], "a")
            self.assertEqual(store.snapshot("a")["status"], "running")
            store.patch_sheet("a", "s", status="completed")
            store.log("a", "hello", "s")
            self.assertTrue(store.cancel("b"))
            self.assertFalse(store.cancel("missing"))
            snap = JobStore(Path(tmp) / "jobs.db").snapshot("a")  # survives a new process/store
            self.assertEqual(snap["sheets"][0]["status"], "completed")
            self.assertEqual(snap["logs"][0]["message"], "hello")
            self.assertTrue(store.snapshot("b")["cancel_requested"])
            self.assertEqual(store.claim(2)["id"], "b")
            self.assertIsNone(store.claim(2))

    def test_claim_is_fair_across_clients(self):
        from tools.app.backend.store import JobStore

        with tempfile.TemporaryDirectory() as tmp:
            store = JobStore(Path(tmp) / "jobs.db")
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

    def test_download_models_snapshot(self):
        from unittest.mock import MagicMock, patch
        from tools.app.backend.download_models import download_model

        mock_hub = MagicMock()
        mock_hub.snapshot_download.return_value = "/tmp/fake_model"
        with patch.dict("sys.modules", {"huggingface_hub": mock_hub}):
            res = download_model("test/repo-model", cache_dir=Path("/tmp/cache"))
            self.assertEqual(res, Path("/tmp/fake_model"))
            mock_hub.snapshot_download.assert_called_once_with(repo_id="test/repo-model", cache_dir="/tmp/cache")

    def test_resolve_xlsx_bytes_passthrough(self):
        from tools.app.backend.research import resolve_xlsx_bytes
        raw = b"PK\x03\x04test"
        res, name = resolve_xlsx_bytes(raw, "file.xlsx")
        self.assertEqual(res, raw)
        self.assertEqual(name, "file.xlsx")

    def test_resolve_xlsx_bytes_gsheet_json(self):
        from unittest.mock import MagicMock, patch
        from tools.app.backend.research import resolve_xlsx_bytes

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
        from tools.app.backend.research import resolve_xlsx_bytes, parse_workbook
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
            {"agent": "test-agent", "max_videos": 1, "media": False},
            "client-1",
        )
        self.assertEqual(len(job["sheets"]), 1)
        self.assertEqual(job["sheets"][0]["name"], "Topic Test")
        self.assertEqual(job["sheets"][0]["targets"], 1)
        self.assertEqual(job["sheets"][0]["target_list"][0]["name"], "Test Page")
        self.assertEqual(job["sheets"][0]["target_list"][0]["url"], "https://www.facebook.com/testpage")

    def test_social_profile_store_crud(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "profiles.db"
            store = SocialProfileStore(db_path)

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
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "jobs.db"
            store = JobStore(db_path)
            job_a = {"id": "job_a1", "status": "completed", "created_at": "2026-11-08T00:00:00Z", "user_id": "user_a"}
            store.put(job_a)

            # user_a can read job_a
            self.assertIsNotNone(store.snapshot("job_a1", user_id="user_a"))
            # user_b cannot read job_a
            self.assertIsNone(store.snapshot("job_a1", user_id="user_b"))
            # unassigned user cannot cancel job_a
            self.assertFalse(store.cancel("job_a1", user_id="user_b"))

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
        from tools.loop.viral_analyzer.pipeline import fetch_target_reels
        with tempfile.TemporaryDirectory() as tmp:
            cache_dir = Path(tmp) / "cache"
            cache_dir.mkdir()
            fake_reels = [{"video_id": "99", "url": "https://facebook.com/reel/99", "view_count": 1000}]
            cache_file = cache_dir / "glasser_testhandle.json"
            cache_file.write_text(json.dumps({"reels": fake_reels}), encoding="utf-8")

            config = load_config({
                "storage": {
                    "db_path": str(Path(tmp) / "db.sqlite"),
                    "video_dir": str(Path(tmp) / "videos"),
                    "output_file": str(Path(tmp) / "out.json"),
                },
                "targets": [{"handle": "testhandle", "url": "https://facebook.com/testhandle"}],
            })

            logs = []
            reels = fetch_target_reels(
                {"handle": "testhandle", "url": "https://facebook.com/testhandle"},
                config,
                cache_dir=cache_dir,
                progress_cb=logs.append,
            )
            # Must read directly from cache without subprocess/network call
            self.assertEqual(len(reels), 1)
            self.assertEqual(reels[0]["video_id"], "99")
            self.assertTrue(any("[cache]" in line for line in logs))

            # Test TTL expiration fallback on error
            os.utime(cache_file, (time.time() - 100000, time.time() - 100000))
            logs_expired = []
            reels_expired = fetch_target_reels(
                {"handle": "testhandle", "url": "https://facebook.com/testhandle"},
                config,
                cache_dir=cache_dir,
                progress_cb=logs_expired.append,
            )
            # Since Glasser is not mocked and will fail or exit, it falls back to the expired cache
            self.assertEqual(len(reels_expired), 1)
            self.assertTrue(any("dùng lại cache cũ" in line for line in logs_expired))

    def test_duplicate_target_uses_cache(self):
        from tools.loop.viral_analyzer.pipeline import fetch_target_reels
        import subprocess
        import unittest.mock as mock

        with tempfile.TemporaryDirectory() as tmp:
            cache_dir = Path(tmp) / "cache"
            cache_dir.mkdir()
            config = load_config({
                "storage": {
                    "db_path": str(Path(tmp) / "db.sqlite"),
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
                reels_1 = fetch_target_reels(target, config, cache_dir=cache_dir, legacy_cache=False, progress_cb=logs_1.append)
                self.assertEqual(glasser_call_count, 1)
                self.assertEqual(len(reels_1), 1)
                self.assertEqual(reels_1[0]["video_id"], "vid_1")
                self.assertTrue(any("[api] Gọi Glasser" in log for log in logs_1))
                # Cache file must have been written
                cache_file = cache_dir / "glasser_my_channel.json"
                self.assertTrue(cache_file.exists())

                # 2nd call: duplicate query, Glasser must NOT be called again
                logs_2 = []
                reels_2 = fetch_target_reels(target, config, cache_dir=cache_dir, legacy_cache=False, progress_cb=logs_2.append)
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
                    "db_path": str(root / "db.sqlite"),
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
                payload = run_analyzer_pipeline(config, cache_dir=cache, media=False, legacy_cache=False, progress_cb=logs.append)
                # Across 2 duplicate targets in targets list, Glasser should only be queried ONCE
                self.assertEqual(glasser_calls, 1, f"Expected 1 Glasser call for duplicate targets, got {glasser_calls}")
                self.assertTrue(any("[cache]" in log for log in logs))

    def test_suggest_topics_empty_reels_returns_empty(self):
        from tools.app.backend.research import suggest_topics
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
        from tools.app.backend.research import STORE, _process_sheet
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
            STORE.put(job)
            with mock.patch("tools.app.backend.research.run_analyzer_pipeline", return_value={"all_reels": [], "metadata": {}}):
                _process_sheet(job_id, 1, 1, sheet, run_dir, {"agent": "agy", "window_hours": 48})
            snap = STORE.snapshot(job_id)
            target_sheet = snap["sheets"][0]
            self.assertEqual(target_sheet["status"], "completed")
            self.assertEqual(target_sheet["reels"], 0)
            self.assertEqual(target_sheet["topics"], [])
            self.assertIn("Không tìm thấy reel mới nào trong 48 giờ qua", target_sheet["notice"])
            self.assertIn("cập nhật thêm danh sách", target_sheet["notice"])

    def test_process_sheet_no_targets_notifies_and_produces_no_topics(self):
        from tools.app.backend.research import STORE, _process_sheet
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
            STORE.put(job)
            _process_sheet(job_id, 1, 1, sheet, run_dir, {"agent": "agy", "window_hours": 48})
            snap = STORE.snapshot(job_id)
            target_sheet = snap["sheets"][0]
            self.assertEqual(target_sheet["status"], "completed")
            self.assertEqual(target_sheet["reels"], 0)
            self.assertEqual(target_sheet["topics"], [])
            self.assertIn("Chưa có kênh đối thủ nào", target_sheet["notice"])


if __name__ == "__main__":
    unittest.main()
