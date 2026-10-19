"""Motion borrowing must use clean donors, not propagate the stationary mark."""

import unittest
import tempfile
from pathlib import Path

import cv2
import numpy as np

from tools.video_edit.temporal import borrow_frame
from tools.video_edit.watermark import RemoveConfig, harmonic_fill, region_from_box, render_watermark


class TemporalTests(unittest.TestCase):
    def test_render_records_temporal_method_and_writes_frames(self):
        from tools.video_edit.tests.test_watermark import write_clip

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            video = root / "clip.mp4"
            write_clip(video)
            manifest = render_watermark(
                video, root / "out", region=region_from_box((228, 164, 44, 44), (240, 320)),
                config=RemoveConfig(method="temporal"), limit=2, skip_encode=True,
            )
            self.assertEqual(manifest["config"]["method"], "temporal")
            self.assertEqual(manifest["frames_cleaned"], 2)
            self.assertTrue((root / "out/frames/00001.png").exists())
            self.assertIn("donor", manifest["what_this_is"])

    def test_static_scene_uses_fallback_and_preserves_outside(self):
        frame = np.full((96, 96, 3), 80, np.uint8)
        mask = np.zeros((96, 96), bool)
        mask[40:56, 40:56] = True
        frame[mask] = 240
        fallback = np.full_like(frame, 80)
        frames = [frame] * 9
        guides = [np.full((96, 96), 80, np.uint8)] * 9
        got, coverage = borrow_frame(0, frames, guides, mask, fallback)
        self.assertEqual(coverage, 0)
        np.testing.assert_array_equal(got[~mask], frame[~mask])
        np.testing.assert_array_equal(got[44:52, 44:52], fallback[44:52, 44:52])

    def test_translation_recovers_detail_from_clean_donor(self):
        rng = np.random.default_rng(7)
        noise = rng.uniform(0, 255, (128, 128)).astype(np.float32)
        scene = cv2.GaussianBlur(noise, (0, 0), 2)
        scene = np.clip((scene - 128) * 6 + 128, 0, 255).astype(np.uint8)
        scene = cv2.cvtColor(scene, cv2.COLOR_GRAY2BGR)
        mask = np.zeros((128, 128), bool)
        mask[60:68, 60:68] = True
        frames, guides = [], []
        hole = cv2.dilate(mask.astype(np.uint8), np.ones((7, 7), np.uint8)) > 0
        config = RemoveConfig(method="harmonic")
        for index in range(9):
            shifted = cv2.warpAffine(scene, np.float32([[1, 0, index * 1.75], [0, 1, 0]]),
                                     (128, 128), borderMode=cv2.BORDER_REFLECT)
            shifted[mask] = 240
            frames.append(shifted)
            guides.append(cv2.cvtColor(harmonic_fill(shifted, hole, config), cv2.COLOR_BGR2GRAY))
        fallback = harmonic_fill(frames[0], mask, config)
        got, coverage = borrow_frame(0, frames, guides, mask, fallback)
        self.assertGreater(coverage, .5)
        interior = np.zeros_like(mask)
        interior[63:65, 63:65] = True
        error = np.abs(got.astype(float) - scene)[interior].mean()
        baseline = np.abs(fallback.astype(float) - scene)[interior].mean()
        self.assertLess(error, baseline)
        np.testing.assert_array_equal(got[~mask], frames[0][~mask])
