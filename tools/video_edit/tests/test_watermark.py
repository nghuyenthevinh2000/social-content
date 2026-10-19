"""Contract tests for the official backend, without downloading or running it."""

import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from tools.video_edit import watermark
from tools.video_edit.cli import build_parser
from tools.video_edit.corners import QuadError


class BackendTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source.mp4"
        self.source.write_bytes(b"original")

    def run_backend(self, command, **kwargs):
        Path(command[command.index("-o") + 1]).write_bytes(b"cleaned")
        return subprocess.CompletedProcess(command, 0, "[OK] source [239/240 frames (1 skip) +audio]", "")

    def test_default_cli_has_one_backend_and_no_old_methods(self):
        args = build_parser().parse_args(["watermark", "--video", str(self.source)])
        self.assertTrue(args.cpu)
        self.assertFalse(hasattr(args, "method"))
        help_text = build_parser()._subparsers._group_actions[0].choices["watermark"].format_help()
        for obsolete in ("--method", "--mask-file", "--clone-offset", "--regressor-grow"):
            self.assertNotIn(obsolete, help_text)

    def test_forwards_options_preserves_source_and_reports_skips(self):
        out = self.root / "out"
        with patch.object(watermark, "find_backend", return_value=Path(sys.executable)), \
                patch.object(watermark.subprocess, "run", side_effect=self.run_backend) as run:
            report = watermark.render_watermark(self.source, out, region="576,1136,48,48", alpha=.63)
        command = run.call_args.args[0]
        self.assertIn("--cpu", command)
        self.assertIn("--veo-alpha", command)
        self.assertEqual(self.source.read_bytes(), b"original")
        self.assertEqual((out / "result.mp4").read_bytes(), b"cleaned")
        self.assertEqual(report["reported_skipped_frames"], 1)
        self.assertTrue((out / "backend.log").exists())
        self.assertEqual(json.loads((out / "manifest.json").read_text())["schema_version"], 2)

    def test_individual_frame_repair_uses_same_engine(self):
        with patch.object(watermark, "find_backend", return_value=Path(sys.executable)), \
                patch.object(watermark.subprocess, "run", side_effect=self.run_backend) as run:
            watermark.render_watermark(self.source, self.root / "image", image=True, legacy=True,
                                       region="576,1136,48,48", alpha=.63, sigma=20, force=True)
        command = run.call_args.args[0]
        for flag in ("--legacy", "--force", "--denoise", "ai", "--sigma"):
            self.assertIn(flag, command)
        self.assertTrue((self.root / "image/result.png").exists())

    def test_refuses_overwriting_source_or_existing_results(self):
        for directory in (self.root / "same", self.root / "existing"):
            directory.mkdir()
            (directory / "result.mp4").write_bytes(b"keep")
            source = directory / "result.mp4" if directory.name == "same" else self.source
            with self.assertRaises(QuadError):
                watermark.render_watermark(source, directory)
            self.assertEqual((directory / "result.mp4").read_bytes(), b"keep")

    def test_failure_retains_log_but_does_not_publish_partial_output(self):
        def fail(command, **kwargs):
            self.run_backend(command)
            return subprocess.CompletedProcess(command, 2, "failure", "bad profile")

        out = self.root / "failed"
        with patch.object(watermark, "find_backend", return_value=Path(sys.executable)), \
                patch.object(watermark.subprocess, "run", side_effect=fail), self.assertRaises(QuadError):
            watermark.render_watermark(self.source, out)
        self.assertFalse((out / "result.mp4").exists())
        self.assertIn("bad profile", (out / "backend.log").read_text())

    def test_bad_settings_fail_before_backend_runs(self):
        for options in ({"alpha": 0}, {"sigma": 151}, {"region": "1,2,0,4"}, {"region": "bad"}):
            with self.subTest(options=options), self.assertRaises(QuadError):
                watermark.render_watermark(self.source, self.root / "out", **options)

    def test_missing_backend_has_actionable_install_message(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(watermark.shutil, "which", return_value=None):
            with self.assertRaisesRegex(QuadError, "watermark-install"):
                watermark.find_backend()

    def test_installer_checks_digest_and_extracts_only_expected_binary(self):
        bundle = io.BytesIO()
        with zipfile.ZipFile(bundle, "w") as archive:
            archive.writestr(watermark.EXECUTABLE, b"backend")
            archive.writestr("../unwanted", b"do not extract")
        data = bundle.getvalue()
        digest = hashlib.sha256(data).hexdigest()
        for expected, succeeds in (("0" * 64, False), (digest, True)):
            with patch.object(watermark.platform, "system", return_value="Darwin"), \
                    patch.object(watermark, "ASSETS", {"Darwin": ("macOS-Universal", expected)}), \
                    patch.object(watermark, "BIN_DIR", self.root / "bin"), \
                    patch.object(watermark.urllib.request, "urlopen", return_value=io.BytesIO(data)):
                if succeeds:
                    binary = watermark.install_backend()
                    self.assertEqual(binary.read_bytes(), b"backend")
                    self.assertTrue(os.access(binary, os.X_OK))
                else:
                    with self.assertRaisesRegex(QuadError, "checksum"):
                        watermark.install_backend()
                    self.assertFalse((self.root / "bin").exists())
        self.assertFalse((self.root / "unwanted").exists())
