"""Tests for the deterministic perspective texture-swap pipeline.

Run:  uv run python -m unittest discover -s tools/video_edit/tests -t .
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

MODULE_ROOT = Path(__file__).resolve().parents[1]
if str(MODULE_ROOT.parents[1]) not in sys.path:
    sys.path.insert(0, str(MODULE_ROOT.parents[1]))

from tools.video_edit import compose, detect_quad, order_corners, parse_corners  # noqa: E402
from tools.video_edit.blend import apply_shading, bgr_to_rgb_float, blend, luminance  # noqa: E402
from tools.video_edit.compose import ComposeConfig  # noqa: E402
from tools.video_edit.corners import QuadError  # noqa: E402
from tools.video_edit.proxy import smooth_proxy, synthetic_card_proxy, tile_mirror  # noqa: E402

PROJECT = MODULE_ROOT.parents[1] / "local" / "paper-ink-product"
CLOSE_UP = PROJECT / "paper_do_nhung_close.jpg"


def textured_red_card(width: int = 300, height: int = 240, seed: int = 3) -> np.ndarray:
    """A synthetic stand-in for a macro shot: flat red with fine grain."""
    rng = np.random.default_rng(seed)
    base = np.zeros((height, width, 3), np.float32)
    base[:] = np.array([40, 33, 197], np.float32)
    grain = rng.normal(0.0, 14.0, size=(height, width, 1)).astype(np.float32)
    base += grain
    return np.clip(base, 0, 255).astype(np.uint8)


class CornerTests(unittest.TestCase):
    def test_order_corners_is_invariant_to_input_order(self):
        points = [(100, 40), (900, 60), (880, 700), (60, 680)]
        expected = np.array([[100, 40], [900, 60], [880, 700], [60, 680]], np.float32)
        for permutation in ([0, 1, 2, 3], [2, 0, 3, 1], [3, 2, 1, 0], [1, 3, 0, 2]):
            shuffled = [points[i] for i in permutation]
            np.testing.assert_allclose(order_corners(np.array(shuffled, np.float32)), expected)

    def test_parse_corners_accepts_common_separators(self):
        expected = np.array([[10, 20], [300, 30], [290, 400], [15, 390]], np.float32)
        for text in ("10,20;300,30;290,400;15,390", "10,20 300,30 290,400 15,390", "15,390;300,30;10,20;290,400"):
            np.testing.assert_allclose(parse_corners(text), expected)

    def test_degenerate_points_are_rejected(self):
        with self.assertRaises(QuadError):
            order_corners(np.array([[0, 0], [10, 0], [20, 0], [30, 0]], np.float32))
        with self.assertRaises(QuadError):
            parse_corners("1,2;3,4")

    def test_detect_quad_finds_the_fixture_card(self):
        frame, truth = synthetic_card_proxy(640, 480, seed=1)
        detection = detect_quad(frame)
        self.assertEqual(detection.method, "approxpoly")
        error = np.linalg.norm(detection.corners - order_corners(truth), axis=1)
        self.assertLess(float(error.max()), 6.0, f"corners off by {error}")
        self.assertGreater(detection.score, 0.9)

    def test_detect_quad_reports_when_nothing_is_found(self):
        flat = np.full((120, 160, 3), 90, np.uint8)
        with self.assertRaises(QuadError):
            detect_quad(flat, mode="saturated")


class TilingTests(unittest.TestCase):
    def test_tile_mirror_fills_the_requested_size(self):
        source = textured_red_card(50, 40)
        tiled = tile_mirror(source, 173, 122)
        self.assertEqual(tiled.shape, (122, 173, 3))

    def test_mirrored_boundaries_are_continuous(self):
        source = textured_red_card(48, 32)
        tiled = tile_mirror(source, 192, 128).astype(np.float32)
        seam = tiled[:, 48, :] - tiled[:, 47, :]
        interior = tiled[:, 47, :] - tiled[:, 46, :]
        self.assertLess(float(np.abs(seam).mean()), 3.0)
        self.assertLess(float(np.abs(seam).mean()), float(np.abs(interior).mean()) + 3.0)


class BlendTests(unittest.TestCase):
    def test_operations_stay_in_range_for_stackable_modes(self):
        base = np.full((4, 4, 3), 0.5, np.float32)
        top = np.full((4, 4, 3), 0.5, np.float32)
        for mode in ("multiply", "screen", "normal", "overlay", "soft_light", "hard_light", "shading"):
            result = blend(base, top, mode)
            self.assertGreaterEqual(float(result.min()), -1e-6, mode)
            self.assertLessEqual(float(result.max()), 1.0 + 1e-6, mode)

    def test_soft_light_matches_w3c_reference_points(self):
        base = bgr_to_rgb_float(np.full((1, 1, 3), 100, np.uint8))
        black = bgr_to_rgb_float(np.full((1, 1, 3), 0, np.uint8))
        white = bgr_to_rgb_float(np.full((1, 1, 3), 255, np.uint8))
        # W3C soft-light with a fully dark source reduces to base squared.
        np.testing.assert_allclose(blend(base, black, "soft_light"), base**2, atol=1e-5)
        np.testing.assert_allclose(blend(base, white, "soft_light"), base ** 0.5, atol=2e-2)
        self.assertLess(float(blend(base, black, "soft_light").mean()), float(base.mean()))
        self.assertGreater(float(blend(base, white, "soft_light").mean()), float(base.mean()))

    def test_shading_scales_all_channels_equally(self):
        rgb = np.array([[[0.6, 0.3, 0.2]]], np.float32)
        shaded = apply_shading(rgb, np.array([[0.5]], np.float32), 1.0)
        np.testing.assert_allclose(shaded[0, 0], rgb[0, 0] * 0.5, atol=1e-6)

    def test_shading_strength_zero_is_a_no_op(self):
        rgb = np.array([[[0.6, 0.3, 0.2]]], np.float32)
        np.testing.assert_allclose(apply_shading(rgb, np.array([[0.4]], np.float32), 0.0), rgb)

    def test_pbr_preserves_sharp_fold_step_and_attenuates_shadow_grooves(self):
        proxy = np.full((120, 160, 3), (30, 20, 180), np.uint8)
        proxy[:, 80:] = (15, 10, 80)  # sharp fold cast shadow step
        quad = np.array([[10, 10], [150, 10], [150, 110], [10, 110]], np.float32)
        tex = textured_red_card(80, 60, seed=7)
        shading = compose(proxy, tex, quad, ComposeConfig(blend_mode="shading"))
        pbr = compose(proxy, tex, quad, ComposeConfig(blend_mode="pbr"))
        # Bilateral illumination in pbr mode keeps the step across x=80 much sharper than Gaussian shading.
        step_shading = abs(float(shading.illumination[60, 76] - shading.illumination[60, 84]))
        step_pbr = abs(float(pbr.illumination[60, 76] - pbr.illumination[60, 84]))
        self.assertGreater(step_pbr, step_shading * 1.8)
        # Grooves are attenuated in deep shadow relative to the lit side.
        lit_var = float(cv2.Laplacian(cv2.cvtColor(pbr.image[:, 20:70], cv2.COLOR_BGR2GRAY), cv2.CV_32F).var())
        shadow_var = float(cv2.Laplacian(cv2.cvtColor(pbr.image[:, 90:140], cv2.COLOR_BGR2GRAY), cv2.CV_32F).var())
        self.assertGreater(lit_var, shadow_var * 2.0)

    def test_shell_flap_warp_rotates_grooves_only_on_bent_flap(self):
        from tools.video_edit.shell import warp_shell_flap

        h, w = 240, 240
        warped = textured_red_card(w, h, seed=9)
        mask = np.ones((h, w), np.float32)
        illum = np.ones((h, w), np.float32)
        illum[90:140, 60:180] = 0.65  # cast shadow wedge
        illum[20:88, 80:200] = 1.15   # bright folded flap above crease
        bent = warp_shell_flap(warped, mask, illum)
        self.assertGreater(float(np.abs(bent[30:80, 90:190].astype(float) - warped[30:80, 90:190]).mean()), 1.0)
        np.testing.assert_array_equal(bent[160:220, 40:200], warped[160:220, 40:200])


class ComposeTests(unittest.TestCase):
    def setUp(self):
        self.proxy, self.truth = synthetic_card_proxy(560, 420, seed=5)
        self.texture = textured_red_card(120, 90)
        self.cfg = ComposeConfig()

    def test_output_matches_proxy_outside_the_card(self):
        result = compose(self.proxy, self.texture, self.truth, self.cfg)
        outside = result.mask < 0.002
        np.testing.assert_allclose(result.image[outside], self.proxy[outside], atol=1)

    def test_surface_mask_covers_paper_beyond_an_inaccurate_quad(self):
        proxy = np.full((160, 200, 3), 180, np.uint8)
        surface = np.zeros((160, 200), np.uint8)
        surface[20:140, 20:180] = 255
        surface[60:90, 90:110] = 0  # foreground finger
        quad = np.array([[50, 40], [150, 40], [150, 120], [50, 120]], np.float32)
        texture = np.full((20, 20, 3), (30, 40, 200), np.uint8)
        result = compose(
            proxy, texture, quad, ComposeConfig(edge_feather=0),
            coverage_mask=surface, surface_mask=True,
        )
        np.testing.assert_array_equal(result.mask, surface / 255.0)
        np.testing.assert_array_equal(result.image[surface == 0], proxy[surface == 0])
        # A finite texture patch must extend without a black seam or smooth rim.
        np.testing.assert_allclose(result.image[surface > 0],
                                   np.tile([30, 40, 200], (int((surface > 0).sum()), 1)), atol=1)

    def test_colour_mask_excludes_disconnected_red_objects(self):
        from tools.video_edit.corners import colour_mask

        frame = np.full((160, 200, 3), 180, np.uint8)
        frame[40:140, 20:100] = (30, 40, 200)
        frame[10:20, 140:170] = (30, 40, 200)  # lips, not the sheet
        mask = colour_mask(frame, kernel=3, dilate=0)
        self.assertEqual(int(mask[15, 150]), 0)
        self.assertEqual(int(mask[80, 60]), 255)

    def test_surface_feather_does_not_spill_outside_mask(self):
        proxy = np.full((160, 200, 3), 180, np.uint8)
        surface = np.zeros((160, 200), np.uint8)
        surface[20:140, 20:180] = 255
        surface[60:90, 90:110] = 0
        quad = np.array([[20, 20], [180, 20], [180, 140], [20, 140]], np.float32)
        result = compose(proxy, self.texture, quad, ComposeConfig(edge_feather=1.5),
                         coverage_mask=surface, surface_mask=True)
        np.testing.assert_array_equal(result.image[surface == 0], proxy[surface == 0])
        self.assertTrue(np.all(result.mask[surface == 0] == 0))

    def test_colour_mask_cleanup_cannot_fill_a_finger_gap(self):
        from tools.video_edit.corners import colour_mask

        frame = np.full((100, 100, 3), (30, 40, 200), np.uint8)
        frame[30:70, 49:51] = 180
        mask = colour_mask(frame, kernel=7, dilate=2)
        self.assertTrue(np.all(mask[30:70, 49:51] == 0))

    def test_colour_mask_rejects_saturated_neck_shadow_attached_to_paper(self):
        from tools.video_edit.corners import colour_mask

        hsv = np.zeros((160, 200, 3), np.uint8)
        hsv[:, :, 2] = 180
        hsv[30:140, 20:110] = (178, 225, 192)
        hsv[50:80, 110:150] = (7, 170, 80)  # attached saturated neck shadow
        hsv[85:100, 110:140] = (7, 170, 180)  # brighter skin, still wrong hue
        frame = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
        mask = colour_mask(frame, kernel=3, dilate=0)
        self.assertEqual(int(mask[60, 130]), 0)
        self.assertEqual(int(mask[90, 130]), 0)
        self.assertEqual(int(mask[60, 60]), 255)

    def test_texture_replaces_the_smooth_card(self):
        result = compose(self.proxy, self.texture, self.truth, self.cfg)
        inside = result.mask > 0.5
        proxy_detail = cv2.Laplacian(cv2.cvtColor(self.proxy, cv2.COLOR_BGR2GRAY), cv2.CV_32F)[inside].var()
        output_detail = cv2.Laplacian(cv2.cvtColor(result.image, cv2.COLOR_BGR2GRAY), cv2.CV_32F)[inside].var()
        self.assertGreater(output_detail, proxy_detail * 10, "real grain should survive the swap")

    def test_mask_sits_on_the_detected_card(self):
        result = compose(self.proxy, self.texture, self.truth, self.cfg)
        ys, xs = np.nonzero(result.mask > 0.5)
        centre = np.array([xs.mean(), ys.mean()])
        expected = self.truth.mean(axis=0)
        distance = float(np.linalg.norm(centre - expected))
        self.assertLess(distance, 12.0, "the warped texture must land on the card, not elsewhere in the frame")

    def test_lighting_gradient_from_the_proxy_is_transferred(self):
        uniform = np.full((120, 90, 3), (40, 33, 197), np.uint8)
        result = compose(self.proxy, uniform, self.truth, self.cfg)
        output_lum = luminance(bgr_to_rgb_float(result.image))
        proxy_lum = luminance(bgr_to_rgb_float(self.proxy))
        # Interior only: the feathered rim mixes card and background by design.
        inside = cv2.erode(
            (result.mask > 0.99).astype(np.uint8), np.ones((9, 9), np.uint8), iterations=1
        ).astype(bool)
        self.assertGreater(int(inside.sum()), 1000)
        correlation = float(np.corrcoef(output_lum[inside], proxy_lum[inside])[0, 1])
        self.assertGreater(correlation, 0.98, f"output should follow the proxy lighting, got r={correlation:.3f}")

    def test_shading_is_normalised_to_about_one(self):
        result = compose(self.proxy, self.texture, self.truth, self.cfg)
        inside = result.mask > 0.5
        mean = float(result.illumination[inside].mean())
        self.assertTrue(0.9 < mean < 1.1, f"illumination should be centred on 1, got {mean:.3f}")

    def test_grain_is_not_upscaled_when_tiling(self):
        cfg = ComposeConfig(texture_flatten=0.0)
        result = compose(self.proxy, self.texture, self.truth, cfg)
        sheet_w, sheet_h = result.stats["sheet_size"]
        expected = [
            int(np.ceil(sheet_w / self.texture.shape[1])),
            int(np.ceil(sheet_h / self.texture.shape[0])),
        ]
        self.assertEqual(result.stats["tiles"], expected)
        self.assertEqual(result.tiled.shape[:2], (sheet_h, sheet_w))
        self.assertGreaterEqual(result.stats["tiles"][0], 2, "the card is wider than one tile")

    def test_sheet_size_tracks_in_plane_edges_not_the_bounding_box(self):
        # A rotated square: its in-plane edges are L, but its axis-aligned
        # bounding box is wider. Sizing from the bbox would stretch the texture.
        length = 200.0
        angle = np.deg2rad(25.0)
        rot = np.array([[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]], np.float32)
        half = length / 2.0
        local = np.array([[-half, -half], [half, -half], [half, half], [-half, half]], np.float32)
        square = local @ rot.T + np.array([300.0, 300.0], np.float32)
        result = compose(self.proxy, self.texture, square, ComposeConfig(texture_flatten=0.0))
        self.assertAlmostEqual(result.stats["sheet_size"][0], int(round(length)), delta=1)
        self.assertAlmostEqual(result.stats["sheet_size"][1], int(round(length)), delta=1)
        bbox_width = result.stats["sheet_bbox"][2] - result.stats["sheet_bbox"][0]
        self.assertGreater(bbox_width, int(length * 1.25))

    def test_results_are_deterministic(self):
        first = compose(self.proxy, self.texture, self.truth, self.cfg).image
        second = compose(self.proxy, self.texture, self.truth, self.cfg).image
        np.testing.assert_array_equal(first, second)

    def test_edges_stay_anti_aliased(self):
        result = compose(self.proxy, self.texture, self.truth, self.cfg)
        partial = ((result.mask > 0.05) & (result.mask < 0.95)).sum()
        self.assertGreater(int(partial), 0, "feathering should produce partial coverage pixels")

    def test_lanczos_keeps_more_grain_than_bilinear(self):
        def high_frequency(result):
            gray = cv2.cvtColor(result.image, cv2.COLOR_BGR2GRAY)
            inside = result.mask > 0.5
            return float(cv2.Laplacian(gray, cv2.CV_32F)[inside].var())

        lanczos = compose(
            self.proxy, self.texture, self.truth, ComposeConfig(interpolation="lanczos4", texture_flatten=0.0)
        )
        linear = compose(
            self.proxy, self.texture, self.truth, ComposeConfig(interpolation="linear", texture_flatten=0.0)
        )
        self.assertGreater(high_frequency(lanczos), high_frequency(linear))

    def test_unknown_interpolation_is_rejected(self):
        with self.assertRaises(ValueError):
            compose(self.proxy, self.texture, self.truth, ComposeConfig(interpolation="mitchell"))

    def test_coverage_mask_narrows_the_paste(self):
        coverage = np.full(self.proxy.shape[:2], 255, np.uint8)
        hole = np.zeros(self.proxy.shape[:2], np.uint8)
        cv2.circle(hole, (280, 210), 40, 255, -1)
        coverage[hole > 0] = 0

        result = compose(self.proxy, self.texture, self.truth, self.cfg, coverage_mask=coverage)
        kept = hole > 0
        self.assertGreater(int((result.mask[kept] > 0.5).sum()), 0)
        self.assertLess(float(result.mask[kept].mean()), 0.5)
        # Well inside the occluded patch, the pixels must be the original proxy;
        # the patch boundary feathers into the paste by design.
        interior = cv2.erode(hole, np.ones((9, 9), np.uint8), iterations=1) > 0
        self.assertGreater(int(interior.sum()), 100)
        np.testing.assert_allclose(result.image[interior], self.proxy[interior], atol=1)

    def test_coverage_mask_shape_is_validated(self):
        with self.assertRaises(ValueError):
            compose(self.proxy, self.texture, self.truth, self.cfg, coverage_mask=np.ones((10, 10), np.uint8))


class ProxyTests(unittest.TestCase):
    def test_smooth_proxy_removes_grain_but_keeps_colour(self):
        texture = textured_red_card(200, 150)
        smoothed = smooth_proxy(texture, iterations=2)
        self.assertLess(
            cv2.Laplacian(cv2.cvtColor(smoothed, cv2.COLOR_BGR2GRAY), cv2.CV_32F).var(),
            cv2.Laplacian(cv2.cvtColor(texture, cv2.COLOR_BGR2GRAY), cv2.CV_32F).var() / 4,
        )
        np.testing.assert_allclose(
            smoothed.reshape(-1, 3).mean(axis=0), texture.reshape(-1, 3).mean(axis=0), atol=6
        )

    def test_synthetic_fixture_is_reproducible(self):
        first, first_quad = synthetic_card_proxy(320, 240, seed=11)
        second, second_quad = synthetic_card_proxy(320, 240, seed=11)
        np.testing.assert_array_equal(first, second)
        np.testing.assert_allclose(first_quad, second_quad)


class CliTests(unittest.TestCase):
    def test_run_writes_the_expected_artifacts(self):
        from tools.video_edit.cli import main

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            frame, _ = synthetic_card_proxy(480, 360, seed=2)
            cv2.imwrite(str(tmp_path / "proxy.png"), frame)
            cv2.imwrite(str(tmp_path / "texture.png"), textured_red_card(100, 80))
            out_dir = tmp_path / "out"

            code = main(
                [
                    "run",
                    "--proxy",
                    str(tmp_path / "proxy.png"),
                    "--texture",
                    str(tmp_path / "texture.png"),
                    "--out-dir",
                    str(out_dir),
                    "--debug",
                ]
            )
            self.assertEqual(code, 0)
            for name in ("frame0.png", "mask.png", "overlay.png", "quad.json", "manifest.json"):
                self.assertTrue((out_dir / name).exists(), name)
            for name in ("tiled.png", "warped.png", "illumination.png"):
                self.assertTrue((out_dir / "debug" / name).exists(), name)

            manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
            self.assertFalse(manifest["provenance"]["generative_texture"])
            self.assertEqual(manifest["detection"]["method"], "approxpoly")
            self.assertEqual(manifest["outputs"]["frame0"], "frame0.png")

            composited = cv2.imread(str(out_dir / "frame0.png"))
            self.assertEqual(composited.shape, frame.shape)

    def test_manual_corners_bypass_detection(self):
        from tools.video_edit.cli import main

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            frame, _ = synthetic_card_proxy(400, 300, seed=4)
            cv2.imwrite(str(tmp_path / "proxy.png"), frame)
            cv2.imwrite(str(tmp_path / "texture.png"), textured_red_card(80, 60))
            out_dir = tmp_path / "out"
            code = main(
                [
                    "run",
                    "--proxy",
                    str(tmp_path / "proxy.png"),
                    "--texture",
                    str(tmp_path / "texture.png"),
                    "--out-dir",
                    str(out_dir),
                    "--corners",
                    "72,42;336,60;320,258;56,240",
                ]
            )
            self.assertEqual(code, 0)
            quad = json.loads((out_dir / "quad.json").read_text(encoding="utf-8"))
            self.assertEqual(quad["detection"]["method"], "manual")


@unittest.skipUnless(CLOSE_UP.exists(), "real close-up texture is not present")
class RealTextureTests(unittest.TestCase):
    def test_screenshot_frame_32_neck_remains_unpainted(self):
        from tools.video_edit.corners import colour_mask

        video = CLOSE_UP.parent / "Girl_presenting_red_paper_20261018230134.mp4"
        if not video.exists():
            self.skipTest("source video is not present")
        capture = cv2.VideoCapture(str(video))
        try:
            capture.set(cv2.CAP_PROP_POS_FRAMES, 32)
            ok, frame = capture.read()
        finally:
            capture.release()
        self.assertTrue(ok)
        mask = colour_mask(frame, kernel=3, dilate=0)
        # Manually identified neck ROI from the user's screenshot, not an ROI
        # derived from the same segmentation being tested.
        self.assertEqual(int(np.count_nonzero(mask[550:568, 332:366])), 0)
        self.assertTrue(np.all(mask[650:750, 100:200] == 255))

    def test_real_close_up_composites_at_native_scale(self):
        texture = cv2.imread(str(CLOSE_UP), cv2.IMREAD_COLOR)
        frame, truth = synthetic_card_proxy(900, 700, seed=9)
        result = compose(frame, texture, truth, ComposeConfig())
        self.assertEqual(result.image.shape, frame.shape)
        self.assertGreater(result.stats["tiles"][0], 1, "a 254px texture should repeat across a wide card")
        inside = result.mask > 0.5
        self.assertGreater(
            cv2.Laplacian(cv2.cvtColor(result.image, cv2.COLOR_BGR2GRAY), cv2.CV_32F)[inside].var(), 1.0
        )


if __name__ == "__main__":
    unittest.main()
