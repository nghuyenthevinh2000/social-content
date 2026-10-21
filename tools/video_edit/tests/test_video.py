"""Tests for the video path: clipping stabilisation, occlusion, and the CLI.

Run:  uv run python -m unittest discover -s tools/video_edit/tests -t .
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

MODULE_ROOT = Path(__file__).resolve().parents[1]
if str(MODULE_ROOT.parents[1]) not in sys.path:
    sys.path.insert(0, str(MODULE_ROOT.parents[1]))

from tools.video_edit.corners import colour_mask, order_corners, refine_sheet_quad  # noqa: E402
from tools.video_edit.proxy import synthetic_card_proxy  # noqa: E402
from tools.video_edit.video import (  # noqa: E402
    measure_aspect,
    plan_frames,
    probe_video,
    rebuild_quad,
    render,
    smooth_quads,
)
from tools.video_edit.compose import ComposeConfig  # noqa: E402

WIDTH, HEIGHT = 320, 240


def full_sheet_quad(width=WIDTH, height=HEIGHT):
    """A sheet fully inside the frame, slightly rotated."""
    return order_corners(
        np.array(
            [
                [width * 0.28, height * 0.20],
                [width * 0.80, height * 0.26],
                [width * 0.78, height * 0.84],
                [width * 0.26, height * 0.78],
            ],
            np.float32,
        )
    )


def clip_left(quad, x=0.0):
    """Run the sheet off the left border, keeping its corners on its own edges.

    A real clip moves a corner along its edge to the frame boundary; simply
    setting x = 0 would leave the corner off the sheet and corrupt the edge
    direction the reconstruction relies on.
    """
    tl, tr, br, bl = quad

    def project(start, end, target_x):
        if abs(float(end[0] - start[0])) < 1e-6:
            return np.array([target_x, float(start[1])], np.float32)
        t = (target_x - float(start[0])) / float(end[0] - start[0])
        return (start + t * (end - start)).astype(np.float32)

    return order_corners(
        np.stack([project(tl, tr, x), tr, br, project(bl, br, x)]).astype(np.float32)
    )


def write_test_video(path: Path, frames=6):
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 12.0, (WIDTH, HEIGHT))
    quad = full_sheet_quad()
    for index in range(frames):
        frame, _ = synthetic_card_proxy(WIDTH, HEIGHT, seed=index, corners=quad + index * 2.0)
        writer.write(frame)
    writer.release()
    return quad


class AspectTests(unittest.TestCase):
    def test_measure_aspect_uses_only_unclipped_frames(self):
        full = full_sheet_quad()
        clipped = clip_left(full)
        aspect = measure_aspect([full, clipped, full], WIDTH, HEIGHT)
        tl, tr, br, bl = full
        edge_u = 0.5 * (float(np.linalg.norm(tr - tl)) + float(np.linalg.norm(br - bl)))
        edge_v = float(np.linalg.norm(br - tr))
        self.assertAlmostEqual(aspect, edge_u / edge_v, places=5)

    def test_measure_aspect_returns_none_when_everything_is_clipped(self):
        self.assertIsNone(measure_aspect([clip_left(full_sheet_quad())], WIDTH, HEIGHT))

    def test_rebuild_restores_the_clipped_width(self):
        full = full_sheet_quad()
        clipped = clip_left(full)
        aspect = measure_aspect([full], WIDTH, HEIGHT)
        rebuilt, changed = rebuild_quad(clipped, aspect, WIDTH, HEIGHT)
        self.assertTrue(changed)
        # The right edge must be untouched, and the left corners are put back
        # where the sheet's real proportions say they belong.
        np.testing.assert_allclose(rebuilt[1], clipped[1], atol=0.01)
        np.testing.assert_allclose(rebuilt[2], clipped[2], atol=0.01)
        error = np.linalg.norm(rebuilt - full, axis=1)
        self.assertLess(float(error.max()), 4.0, f"rebuild should recover the true quad, off by {error}")

    def test_rebuild_invents_a_corner_that_is_genuinely_off_frame(self):
        # A sheet pushed left, so its real left corners are outside the frame.
        off_frame = order_corners(
            np.array([[-60.0, 40.0], [220.0, 46.0], [214.0, 200.0], [-66.0, 194.0]], np.float32)
        )
        clipped = clip_left(off_frame)
        aspect = float(np.linalg.norm(off_frame[1] - off_frame[0]) / np.linalg.norm(off_frame[3] - off_frame[0]))
        rebuilt, changed = rebuild_quad(clipped, aspect, WIDTH, HEIGHT)
        self.assertTrue(changed)
        self.assertLess(float(rebuilt[0][0]), 0.0, "the reconstructed corner belongs off-frame")
        np.testing.assert_allclose(rebuilt[1], clipped[1], atol=0.01)
        error = np.linalg.norm(rebuilt - off_frame, axis=1)
        self.assertLess(float(error.max()), 6.0)

    def test_rebuild_leaves_an_unclipped_quad_alone(self):
        full = full_sheet_quad()
        rebuilt, changed = rebuild_quad(full, 0.75, WIDTH, HEIGHT)
        self.assertFalse(changed)
        np.testing.assert_allclose(rebuilt, full)

    def test_rebuild_is_a_no_op_without_an_aspect(self):
        clipped = clip_left(full_sheet_quad())
        rebuilt, changed = rebuild_quad(clipped, None, WIDTH, HEIGHT)
        self.assertFalse(changed)
        np.testing.assert_allclose(rebuilt, clipped)


class ColourMaskTests(unittest.TestCase):
    def test_mask_excludes_an_overlapping_finger(self):
        frame = np.full((HEIGHT, WIDTH, 3), 210, np.uint8)
        quad = full_sheet_quad().astype(np.int32)
        cv2.fillPoly(frame, [quad], (40, 33, 197))
        finger = np.array([[150, 60], [175, 60], [175, 150], [150, 150]], np.int32)
        cv2.fillPoly(frame, [finger], (150, 170, 205))  # pale skin, low saturation
        mask = colour_mask(frame, s_min=150, kernel=7, dilate=1)
        self.assertGreater(float(mask[180, 120] / 255), 0.5, "sheet pixels stay in the mask")
        self.assertLess(float(mask[100, 162] / 255), 0.5, "the finger is excluded")

    def test_mask_is_zero_on_an_empty_scene(self):
        frame = np.full((HEIGHT, WIDTH, 3), 128, np.uint8)
        self.assertEqual(int(colour_mask(frame).max()), 0)


class MotionTests(unittest.TestCase):
    def test_long_edges_recover_corner_covered_by_hand(self):
        truth = np.array([[60, 40], [260, 60], [240, 220], [40, 200]], np.float32)
        mask = np.zeros((260, 320), np.uint8)
        cv2.fillConvexPoly(mask, truth.astype(np.int32), 255)
        mask[170:240, 225:300] = 0  # hand hides the bottom-right corner
        seed = truth.copy()
        seed[2] = (245, 165)  # polygon detector incorrectly stops at the hand
        fitted = refine_sheet_quad(mask, seed)
        self.assertLess(float(np.max(np.linalg.norm(fitted-truth, axis=1))), 3.0)

    def test_reported_four_to_five_second_section_does_not_shrink_at_hand(self):
        source = MODULE_ROOT.parents[1] / "local/paper-ink-product/Girl_presenting_red_paper_20261018230134.mp4"
        if not source.exists():
            self.skipTest("source video is not present")
        planned = plan_frames(probe_video(source), detect_mode="saturated",
                              detect_kwargs={"s_min": 150, "kernel": 7}, start=84, limit=49)
        quads = np.array([p.quad for p in planned.plans])[12:37]  # frames 96..120
        heights = np.linalg.norm(quads[:, 2]-quads[:, 1], axis=1)
        # Independent physical observation: the full right edge is about 505px;
        # the hand was previously truncating it to 440px around frame 104.
        self.assertGreater(float(heights.min()), 490.0)
        self.assertLess(float(np.ptp(heights)), 15.0)
        self.assertLess(float(np.sqrt(np.mean(np.diff(quads, n=2, axis=0)**2))), 2.5)

    def test_static_sheet_detection_noise_is_suppressed(self):
        truth = np.repeat(full_sheet_quad()[None], 80, axis=0)
        noisy = truth + np.random.default_rng(8).normal(0, 1.5, truth.shape)
        stable = smooth_quads(noisy)
        self.assertLess(float(np.std(stable[5:-5]-truth[5:-5])), 0.7 * float(np.std(noisy-truth)))

    def test_smooth_motion_has_no_temporal_lag_even_at_endpoints(self):
        t = np.arange(60, dtype=np.float32)
        truth = full_sheet_quad()[None] + (2*t + .01*t*t)[:, None, None]
        np.testing.assert_allclose(smooth_quads(truth), truth, atol=0.002)

    def test_single_frame_occlusion_outlier_is_rejected(self):
        truth = np.repeat(full_sheet_quad()[None], 40, axis=0)
        noisy = truth.copy()
        noisy[20] += 50
        self.assertLess(float(np.max(np.abs(smooth_quads(noisy)-truth))), 2.0)


class PlanTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.video = self.tmp / "clip.mp4"
        write_test_video(self.video)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_probe_reports_the_geometry(self):
        info = probe_video(self.video)
        self.assertEqual((info.width, info.height), (WIDTH, HEIGHT))
        self.assertAlmostEqual(info.fps, 12.0, places=2)
        self.assertEqual(info.frame_count, 6)
        self.assertFalse(info.has_audio)

    def test_plan_frames_detects_every_frame(self):
        info = probe_video(self.video)
        planned = plan_frames(info, detect_mode="saturated", detect_kwargs={"s_min": 60})
        self.assertEqual(len(planned.plans), 6)
        self.assertEqual(planned.detection_counts, {"approxpoly+edges": 6})
        self.assertEqual(planned.clipped_frames, 0)
        self.assertEqual(planned.reconstructed_frames, 0)
        self.assertIsNotNone(planned.aspect)

    def test_limit_stops_early(self):
        info = probe_video(self.video)
        planned = plan_frames(info, detect_mode="saturated", detect_kwargs={"s_min": 60}, limit=2)
        self.assertEqual(len(planned.plans), 2)

    def test_render_writes_one_png_per_planned_frame(self):
        info = probe_video(self.video)
        planned = plan_frames(info, detect_mode="saturated", detect_kwargs={"s_min": 60})
        texture = np.full((60, 45, 3), (40, 33, 197), np.uint8)
        rows = render(info, texture, planned.plans, ComposeConfig(), self.tmp / "frames")
        self.assertEqual(len(rows), 6)
        self.assertEqual(len({tuple(row['sheet_size']) for row in rows}), 1,
                         "all frames must share one texture coordinate canvas")
        for index in range(6):
            self.assertTrue((self.tmp / "frames" / f"{index:05d}.png").exists())


class VideoCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.video = self.tmp / "clip.mp4"
        write_test_video(self.video, frames=4)
        self.texture = self.tmp / "texture.png"
        cv2.imwrite(str(self.texture), np.full((60, 45, 3), (40, 33, 197), np.uint8))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_video_command_writes_frames_and_manifest(self):
        from tools.video_edit.cli import main

        out_dir = self.tmp / "out"
        code = main(
            [
                "video",
                "--video", str(self.video),
                "--texture", str(self.texture),
                "--out-dir", str(out_dir),
                "--s-min", "60",
                "--skip-encode",
            ]
        )
        self.assertEqual(code, 0)
        manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
        self.assertFalse(manifest["provenance"]["generative_texture"])
        self.assertEqual(manifest["stabilisation"]["frames_planned"], 4)
        self.assertEqual(len(manifest["frames"]), 4)
        self.assertTrue(manifest["stabilisation"]["occlusion_aware"])
        self.assertTrue((out_dir / "frames" / "00000.png").exists())
        self.assertIsNone(manifest["outputs"]["video"])

    def test_flow_track_mode_runs_from_unified_cli(self):
        from tools.video_edit.cli import main

        out_dir = self.tmp / "out-flow"
        code = main(
            [
                "video",
                "--video", str(self.video),
                "--texture", str(self.texture),
                "--out-dir", str(out_dir),
                "--track-mode", "flow",
                "--blend-mode", "pbr",
                "--s-min", "60",
                "--skip-encode",
            ]
        )
        self.assertEqual(code, 0)
        manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["stabilisation"]["detection_counts"], {"flow-ransac": 4})


if __name__ == "__main__":
    unittest.main()
