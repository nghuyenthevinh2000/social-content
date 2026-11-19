"""Unit tests for the standardized viral analyzer engine, concurrency, and extensibility."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

from tools.loop.viral_analyzer import platforms, runtime
from tools.loop.viral_analyzer.profile_research.config import (
    DEFAULT_POOLS,
    StorageConfig,
    ViralAnalyzerConfig,
    load_config,
)
from tools.loop.viral_analyzer.profile_research.pipeline import classify_pool, run_analyzer_pipeline
from tools.loop.viral_analyzer.video_research.collect import (
    load_manifest,
    purge_expired_videos,
    register_video,
)


class TestViralAnalyzerPipeline(unittest.TestCase):

    def test_pool_classification(self):
        cfg = ViralAnalyzerConfig(pools=DEFAULT_POOLS)

        self.assertEqual(classify_pool(0, cfg)[0], 1)
        self.assertEqual(classify_pool(499, cfg)[0], 1)
        self.assertEqual(classify_pool(500, cfg)[0], 2)
        self.assertEqual(classify_pool(4999, cfg)[0], 2)
        self.assertEqual(classify_pool(5000, cfg)[0], 3)
        self.assertEqual(classify_pool(49999, cfg)[0], 3)
        self.assertEqual(classify_pool(50000, cfg)[0], 4)
        self.assertEqual(classify_pool(499999, cfg)[0], 4)
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

            f1 = vdir / "reel_fresh.mp4"
            f1.write_bytes(b"dummy fresh video")
            register_video(vdir, "fresh_001", f1, retention_days=7, now=t_now)

            f2 = vdir / "reel_old.mp4"
            f2.write_bytes(b"dummy old video")
            t_old = t_now - timedelta(days=8)
            register_video(vdir, "old_002", f2, retention_days=7, now=t_old)

            self.assertTrue(f1.exists())
            self.assertTrue(f2.exists())

            purged, retained = purge_expired_videos(vdir, retention_days=7, now=t_now)

            self.assertEqual(purged, 1)
            self.assertEqual(retained, 1)
            self.assertTrue(f1.exists(), "Fresh video under 7 days must be retained")
            self.assertFalse(f2.exists(), "Expired video older than 7 days must be purged")

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
                mock.patch("tools.loop.viral_analyzer.profile_research.pipeline.persist_to_database"),
                mock.patch("tools.loop.viral_analyzer.profile_research.pipeline.transcribe_reels_local") as mock_local,
                mock.patch("tools.loop.viral_analyzer.profile_research.pipeline.transcribe_reels_glasser") as mock_glasser,
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

    def test_standardized_five_file_contract(self):
        pkg_root = Path(__file__).resolve().parents[1] / "viral_analyzer"
        standard_files = ("__init__.py", "__main__.py", "config.py", "collect.py", "pipeline.py")
        for domain in ("profile_research", "video_research", "keyword_research"):
            domain_dir = pkg_root / domain
            self.assertTrue(domain_dir.is_dir(), f"Missing domain package: {domain}")
            for fname in standard_files:
                self.assertTrue((domain_dir / fname).is_file(), f"Missing {domain}/{fname}")
        for legacy in ("config.py", "pipeline.py", "retention.py", "video_download.py", "hashtag_common.py", "viral_scrape.py"):
            self.assertFalse((pkg_root / legacy).exists(), f"Legacy flat file still present: {legacy}")
        import tools.loop.viral_analyzer as va
        self.assertTrue(hasattr(va, "run_profile_research"))
        self.assertTrue(hasattr(va, "research_single_reel"))
        self.assertTrue(hasattr(va, "run_viral_video_search"))

    def test_platform_registry_extensibility(self):
        spec = platforms.PlatformSpec(
            name="threads",
            domains=("threads.net",),
            reel_patterns=(re.compile(r"https?://(?:www\.)?threads\.net/@[\w.-]+/post/([A-Za-z0-9_-]+)", re.I),),
            handle_fn=lambda url: ("threads_user", url),
            fallback_url_fn=lambda vid, h="": f"https://www.threads.net/@{h or 'user'}/post/{vid}",
        )
        platforms.register_platform(spec)
        try:
            test_url = "https://www.threads.net/@creator/post/C9AbCd123"
            self.assertEqual(platforms.detect_platform(test_url), "threads")
            self.assertTrue(platforms.is_reel_url(test_url))
            self.assertEqual(platforms.extract_video_id(test_url), "C9AbCd123")
            self.assertEqual(platforms.canonicalize_reel_url(test_url, resolve_redirects=False), (test_url, "threads"))
            self.assertEqual(
                platforms.fallback_video_url("threads", "C9AbCd123", "creator"),
                "https://www.threads.net/@creator/post/C9AbCd123",
            )
        finally:
            platforms.unregister_platform("threads")
        self.assertIsNone(platforms.get_platform("threads"))

    def test_parallel_retention_manifest_atomic(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            vdir = Path(tmp_dir)
            t_now = datetime.now(timezone.utc)

            def _worker(idx: int) -> None:
                fpath = vdir / f"vid_{idx}.mp4"
                fpath.write_bytes(b"mp4")
                register_video(vdir, f"vid_{idx}", fpath, retention_days=7, now=t_now)

            with ThreadPoolExecutor(max_workers=8) as pool:
                list(pool.map(_worker, range(8)))

            manifest = load_manifest(vdir)
            self.assertEqual(len(manifest), 8)
            for i in range(8):
                self.assertIn(f"vid_{i}", manifest)

    def test_single_flight_deduplication(self):
        sf = runtime.SingleFlight()
        store = {}
        fetch_count = 0
        guard = threading.Lock()
        barrier = threading.Barrier(6)

        def _worker(_idx: int) -> str:
            barrier.wait(timeout=5)
            with sf.acquire("shared_key"):
                nonlocal fetch_count
                if "shared_key" not in store:
                    time.sleep(0.02)
                    with guard:
                        fetch_count += 1
                    store["shared_key"] = "value-1"
                return store["shared_key"]

        with ThreadPoolExecutor(max_workers=6) as pool:
            results = list(pool.map(_worker, range(6)))

        self.assertEqual(fetch_count, 1)
        self.assertEqual(results, ["value-1"] * 6)

    def test_parallel_profile_pipeline_deterministic_order(self):
        now_iso = datetime.now(timezone.utc).isoformat()
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            cfg = ViralAnalyzerConfig(
                storage=StorageConfig(
                    video_dir=tmp_path / "videos",
                    output_file=tmp_path / "out.json",
                ),
                targets=[
                    {"handle": "slow_one", "url": "https://www.facebook.com/slow_one", "platform": "facebook"},
                    {"handle": "fast_two", "url": "https://www.facebook.com/fast_two", "platform": "facebook"},
                ],
            )

            def _fake_fetch(target, *_args, **_kwargs):
                h = target["handle"]
                if h == "slow_one":
                    time.sleep(0.04)
                return [{"video_id": f"id_{h}", "url": f"https://www.facebook.com/reel/{h}", "view_count": 500, "creation_time": now_iso, "_source": "glasser"}]

            with (
                mock.patch("tools.loop.viral_analyzer.profile_research.pipeline.fetch_target_reels", side_effect=_fake_fetch),
                mock.patch("tools.loop.viral_analyzer.profile_research.pipeline.persist_to_database"),
            ):
                res = run_analyzer_pipeline(cfg, transcribe=False)

            self.assertEqual([r["author_handle"] for r in res["all_reels"]], ["slow_one", "fast_two"])
            self.assertEqual(res["source_breakdown"]["glasser_api"], ["slow_one", "fast_two"])

    def test_unified_keyword_research_cli_subcommands(self):
        from tools.loop.viral_analyzer.keyword_research.__main__ import _parser

        parser = _parser()
        subparsers_actions = [a for a in parser._actions if hasattr(a, "choices") and isinstance(a.choices, dict)]
        self.assertTrue(subparsers_actions)
        cmds = set(subparsers_actions[0].choices.keys())
        self.assertEqual(
            cmds,
            {
                "search",
                "build-prompt",
                "import-response",
                "plan",
                "collect",
                "report",
                "build-review-prompt",
                "record-review",
                "history",
                "scrape",
            },
        )

    def test_backend_research_engine_uses_canonical_engines(self):
        backend_re_dir = Path(__file__).resolve().parents[2] / "app" / "backend" / "research_engine"
        for removed in ("keyword_search.py", "profile_research.py", "reel_research.py"):
            self.assertFalse((backend_re_dir / removed).exists(), f"Removed shim still exists: {removed}")
        try:
            from tools.app.backend import research_engine
        except ModuleNotFoundError as exc:
            if exc.name in ("psycopg", "boto3", "openpyxl", "fastapi", "google"):
                self.skipTest(f"Backend optional dependency {exc.name!r} not installed in system Python")
            raise
        from tools.loop.viral_analyzer.keyword_research import pipeline as kw_pipeline
        from tools.loop.viral_analyzer.profile_research import pipeline as prof_pipeline
        from tools.loop.viral_analyzer.video_research import pipeline as vid_pipeline

        self.assertIs(research_engine.run_profile_research, prof_pipeline.run_profile_research)
        self.assertIs(research_engine.research_single_reel, vid_pipeline.research_single_reel)
        self.assertIs(research_engine.run_viral_video_search, kw_pipeline.run_viral_video_search)


if __name__ == "__main__":
    unittest.main()
