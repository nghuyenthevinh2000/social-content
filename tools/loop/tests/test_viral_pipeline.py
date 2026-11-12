"""Unit tests for the standardized viral analyzer pipeline and retention manager."""

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from tools.loop.viral_analyzer.config import (
    DEFAULT_POOLS,
    PoolDefinition,
    StorageConfig,
    ViralAnalyzerConfig,
    load_config,
)
from tools.loop.viral_analyzer.pipeline import classify_pool, run_analyzer_pipeline
from tools.loop.viral_analyzer.retention import (
    load_manifest,
    purge_expired_videos,
    register_video,
)


class TestViralAnalyzerPipeline(unittest.TestCase):

    def test_pool_classification(self):
        cfg = ViralAnalyzerConfig(pools=DEFAULT_POOLS)

        # Pool 1: 0 - 499
        self.assertEqual(classify_pool(0, cfg)[0], 1)
        self.assertEqual(classify_pool(499, cfg)[0], 1)

        # Pool 2: 500 - 4,999
        self.assertEqual(classify_pool(500, cfg)[0], 2)
        self.assertEqual(classify_pool(4999, cfg)[0], 2)

        # Pool 3: 5,000 - 49,999
        self.assertEqual(classify_pool(5000, cfg)[0], 3)
        self.assertEqual(classify_pool(49999, cfg)[0], 3)

        # Pool 4: 50,000 - 499,999
        self.assertEqual(classify_pool(50000, cfg)[0], 4)
        self.assertEqual(classify_pool(499999, cfg)[0], 4)

        # Pool 5: >= 500,000
        self.assertEqual(classify_pool(500000, cfg)[0], 5)
        self.assertEqual(classify_pool(3100000, cfg)[0], 5)

    def test_config_parsing(self):
        sample_dict = {
            "window_hours": 48,
            "retention_days": 7,
            "pools": {
                "1": {"name": "test_sandbox", "min_views": 0, "max_views": 100},
                "2": {"name": "test_breakout", "min_views": 100, "max_views": None},
            },
            "transcription": {
                "engine": "local",
                "model": "Qwen/Qwen3-ASR-0.6B",
            },
            "max_videos": 100,
        }
        cfg = load_config(sample_dict)
        self.assertEqual(cfg.window_hours, 48)
        self.assertEqual(cfg.retention_days, 7)
        self.assertEqual(cfg.max_videos, 100)
        self.assertEqual(cfg.pools[1].name, "test_sandbox")
        self.assertEqual(cfg.pools[2].name, "test_breakout")
        self.assertEqual(cfg.transcription.engine, "local")

    def test_one_week_retention_purge(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            vdir = Path(tmp_dir)
            t_now = datetime.now(timezone.utc)

            # Create video 1 (downloaded today, within 7 days)
            f1 = vdir / "reel_fresh.mp4"
            f1.write_bytes(b"dummy fresh video")
            register_video(vdir, "fresh_001", f1, retention_days=7, now=t_now)

            # Create video 2 (downloaded 8 days ago, expired)
            f2 = vdir / "reel_old.mp4"
            f2.write_bytes(b"dummy old video")
            t_old = t_now - timedelta(days=8)
            register_video(vdir, "old_002", f2, retention_days=7, now=t_old)

            self.assertTrue(f1.exists())
            self.assertTrue(f2.exists())

            # Run retention sweep
            purged, retained = purge_expired_videos(vdir, retention_days=7, now=t_now)

            self.assertEqual(purged, 1)
            self.assertEqual(retained, 1)
            self.assertTrue(f1.exists(), "Fresh video under 7 days must be retained")
            self.assertFalse(f2.exists(), "Expired video older than 7 days must be purged")

            # Check manifest updated
            manifest = load_manifest(vdir)
            self.assertIn("fresh_001", manifest)
            self.assertNotIn("old_002", manifest)

    def test_transcriber_engine_routing(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            cfg = ViralAnalyzerConfig(
                storage=StorageConfig(
                    video_dir=tmp_path / "videos",
                    output_file=tmp_path / "out.json",
                ),
                targets=[],
            )
            with (
                mock.patch("tools.loop.viral_analyzer.pipeline.persist_to_database"),
                mock.patch("tools.loop.viral_analyzer.pipeline.transcribe_reels_local") as mock_local,
                mock.patch("tools.loop.viral_analyzer.pipeline.transcribe_reels_glasser") as mock_glasser,
            ):
                run_analyzer_pipeline(cfg, transcriber_engine="local")
                mock_local.assert_called_once()
                mock_glasser.assert_not_called()

                mock_local.reset_mock()
                run_analyzer_pipeline(cfg, transcriber_engine="glasser")
                mock_glasser.assert_called_once()
                mock_local.assert_not_called()

                with self.assertRaises(ValueError):
                    run_analyzer_pipeline(cfg, transcriber_engine="qwen3")


if __name__ == "__main__":
    unittest.main()
