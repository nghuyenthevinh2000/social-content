"""Minimal checks for Excel parsing and topic parsing (run: python3 -m unittest tools.app.backend.test_backend)."""

import json
from pathlib import Path
import sys
import tempfile
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


class BackendTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
