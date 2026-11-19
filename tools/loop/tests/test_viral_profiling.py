"""Tests for dedicated tools.loop.viral_analyzer.profiling spans and benchmarks."""

from __future__ import annotations

import io
import json
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
import tempfile
import unittest

from tools.loop.viral_analyzer import profiling


class TestViralAnalyzerProfiling(unittest.TestCase):
    def tearDown(self) -> None:
        profiling.configure(enabled=False, contexts="all")

    def test_disabled_by_default_and_context_filter(self) -> None:
        profiling.configure(enabled=False, contexts="all")
        self.assertFalse(profiling.is_enabled())
        self.assertFalse(profiling.is_enabled("profile"))

        buf = io.StringIO()
        with redirect_stderr(buf):
            with profiling.span("profile", "noop"):
                _ = 1 + 1
        self.assertEqual(buf.getvalue(), "")

        profiling.configure(enabled=True, contexts="core,video")
        self.assertTrue(profiling.is_enabled("core"))
        self.assertTrue(profiling.is_enabled("video"))
        self.assertFalse(profiling.is_enabled("keyword"))

        buf2 = io.StringIO()
        with redirect_stderr(buf2):
            with profiling.span("core", "sample_span"):
                _ = sum(range(100))
            with profiling.span("keyword", "filtered_span"):
                _ = sum(range(100))
        out = buf2.getvalue()
        self.assertIn("[viral-profile:core] sample_span", out)
        self.assertNotIn("filtered_span", out)

    def test_profile_callable_returns_cprofile_and_memory(self) -> None:
        res, stats_text, peak_kb = profiling.profile_callable(lambda n: [i * i for i in range(n)], 2000)
        self.assertEqual(len(res), 2000)
        self.assertIn("function calls", stats_text)
        self.assertGreater(peak_kb, 0.0)

    def test_run_benchmarks_offline_suites_and_speedups(self) -> None:
        res = profiling.run_benchmarks(
            ["core", "profile", "video", "keyword", "concurrency"],
            iterations=2,
            workers=5,
        )
        by_op = {row["operation"]: row for row in res["summary"]}
        self.assertIn("platforms.detect_and_canonicalize", by_op)
        self.assertIn("profile.pipeline_serial_1w", by_op)
        self.assertIn("profile.pipeline_parallel_5w", by_op)
        self.assertIn("profile.single_flight_stampede", by_op)
        self.assertIn("video.topics_and_prompts_20", by_op)
        self.assertIn("video.retention_flock_8t", by_op)
        self.assertIn("keyword.search_5plat_serial_1w", by_op)
        self.assertIn("keyword.search_5plat_parallel_5w", by_op)
        self.assertIn("keyword.campaign_flow_offline", by_op)
        self.assertIn("runtime.single_flight_16t_4k", by_op)

        self.assertLess(
            by_op["profile.pipeline_parallel_5w"]["p50_ms"],
            by_op["profile.pipeline_serial_1w"]["p50_ms"],
        )
        self.assertLess(
            by_op["keyword.search_5plat_parallel_5w"]["p50_ms"],
            by_op["keyword.search_5plat_serial_1w"]["p50_ms"],
        )
        self.assertIn("upstream=2/12 collapsed", by_op["profile.single_flight_stampede"]["note"])
        self.assertIn("| `core` |", res["table"])

    def test_cli_help_and_json_out(self) -> None:
        with self.assertRaises(SystemExit) as cm, redirect_stdout(io.StringIO()):
            profiling.main(["--help"])
        self.assertEqual(cm.exception.code, 0)

        with tempfile.TemporaryDirectory() as tmp:
            json_out = Path(tmp) / "bench.json"
            with redirect_stdout(io.StringIO()):
                rc = profiling.main(["--context", "core", "--iterations", "1", "--json-out", str(json_out)])
            self.assertEqual(rc, 0)
            payload = json.loads(json_out.read_text(encoding="utf-8"))
            self.assertEqual(payload["contexts"], ["core"])
            self.assertTrue(payload["summary"])


if __name__ == "__main__":
    unittest.main()
