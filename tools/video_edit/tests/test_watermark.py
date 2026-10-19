"""Tests for static-watermark removal.

Run:  uv run python -m unittest discover -s tools/video_edit/tests -t .

The synthetic clips carry a known overlay, so the fill is scored against the
clean frames the encoder never saw, not merely against a plausible-looking
output.
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

from tools.video_edit.watermark import (  # noqa: E402
    RemoveConfig,
    clean_frame,
    clean_video,
    detect_watermark,
    fit_unmix,
    harmonic_fill,
    overlay_field,
    region_from_box,
    region_from_mask_file,
)

WIDTH, HEIGHT = 320, 240
MARK_CENTRE = (250, 186)
MARK_RADIUS = 20.0
MARK_ALPHA = 0.30
MARK_COLOUR = 242.0


def star_mask(centre=MARK_CENTRE, radius=MARK_RADIUS, shape=(HEIGHT, WIDTH)) -> np.ndarray:
    """The four-point sparkle: an astroid, which is the mark's actual shape."""
    ys, xs = np.mgrid[0:shape[0], 0:shape[1]].astype(np.float32)
    u = np.abs(xs - centre[0]) / radius
    v = np.abs(ys - centre[1]) / radius
    return (np.power(u, 2 / 3) + np.power(v, 2 / 3)) <= 1.0


def star_alpha(soft: float = 0.0, shape=(HEIGHT, WIDTH)) -> np.ndarray:
    """The mark's coverage. A real mark has a soft antialiased edge, so a test
    that leaves ``soft`` at 0 only exercises the easy case."""
    hard = star_mask(shape=shape).astype(np.float32)
    return cv2.GaussianBlur(hard, (0, 0), soft) if soft > 0 else hard


def clean_background(index: int, rng: np.random.Generator, size=(WIDTH, HEIGHT),
                     speed: float = 3.0, edge: float = 0.0) -> np.ndarray:
    """A smooth gradient that slides sideways, plus speckle that also moves.

    ``edge`` adds a step that slides too -- the card edge of the real clip. A
    membrane spans such a step and rounds it off, so clips that carry one are
    where the translucent inverse earns its keep.
    """
    width, height = size
    ys, xs = np.mgrid[0:height, 0:width].astype(np.float32)
    base = (70.0 + 110.0 * (xs + speed * index) / width + 20.0 * ys / height)[..., None]
    if edge:
        moving = (xs + speed * index) > 0.55 * width
        base = base + edge * moving[..., None]
    return np.clip(base + rng.normal(0.0, 2.0, (height, width, 3)), 0, 255).astype(np.uint8)


def composite(frame: np.ndarray, alpha: np.ndarray, opacity: float = MARK_ALPHA) -> np.ndarray:
    weight = (alpha * opacity)[..., None]
    return np.clip(frame.astype(np.float32) * (1 - weight) + MARK_COLOUR * weight, 0, 255).astype(np.uint8)


def write_clip(path: Path, frames: int = 12, soft: float = 0.0,
               size=(WIDTH, HEIGHT), speed: float = 3.0, edge: float = 0.0,
               opacity: float = MARK_ALPHA) -> tuple[list[np.ndarray], np.ndarray]:
    """Write a clip carrying a static sparkle; also return the clean frames."""
    alpha = star_alpha(soft, shape=(size[1], size[0]))
    rng = np.random.default_rng(11)
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 12.0, size)
    clean = []
    for index in range(frames):
        base = clean_background(index, rng, size, speed=speed, edge=edge)
        clean.append(base)
        writer.write(composite(base, alpha, opacity))
    writer.release()
    return clean, alpha


class RegionTests(unittest.TestCase):
    def test_region_from_box_reads_pixels_and_clips_to_the_frame(self):
        region = region_from_box("300,200,40,60", (HEIGHT, WIDTH))
        self.assertEqual(region.box, (300, 200, 20, 40), "the box is clipped to the frame")
        self.assertEqual(region.area, 20 * 40)

    def test_region_from_box_accepts_a_sequence_and_growth(self):
        self.assertEqual(region_from_box((10, 20, 30, 40), (HEIGHT, WIDTH)).box, (10, 20, 30, 40))
        self.assertEqual(region_from_box((10, 20, 30, 40), (HEIGHT, WIDTH), grow=2).box, (8, 18, 34, 44))

    def test_region_from_mask_file_reads_a_png(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            path = tmp / "mask.png"
            image = np.zeros((HEIGHT, WIDTH), np.uint8)
            image[100:120, 100:130] = 255
            cv2.imwrite(str(path), image)
            region = region_from_mask_file(path)
            self.assertEqual(region.box, (100, 100, 30, 20))
            self.assertEqual(region.method, "mask-file")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class HarmonicFillTests(unittest.TestCase):
    def test_pixels_outside_the_mask_are_untouched(self):
        frame = np.random.default_rng(3).integers(0, 255, (HEIGHT, WIDTH, 3), dtype=np.uint8)
        mask = np.zeros((HEIGHT, WIDTH), np.uint8)
        cv2.circle(mask, (150, 120), 12, 255, -1)
        crop = frame[100:180, 100:220]
        filled = harmonic_fill(crop, mask[100:180, 100:220] > 0, RemoveConfig())
        outside = mask[100:180, 100:220] == 0
        np.testing.assert_array_equal(filled[outside], crop[outside])

    def test_fill_is_deterministic(self):
        frame = np.random.default_rng(4).integers(0, 255, (HEIGHT, WIDTH, 3), dtype=np.uint8)
        region = region_from_box((138, 108, 25, 25), (HEIGHT, WIDTH))
        np.testing.assert_array_equal(
            clean_frame(frame, region, RemoveConfig()),
            clean_frame(frame, region, RemoveConfig()),
        )

    def test_a_hole_in_a_curved_surface_is_rebuilt_within_a_couple_of_levels(self):
        """Skin is a smooth, curved shading field, which is what the membrane assumes."""
        ys, xs = np.mgrid[0:HEIGHT, 0:WIDTH].astype(np.float32)
        radius = np.sqrt((xs - 150) ** 2 + (ys - 120) ** 2)
        truth = np.repeat((200 - 0.55 * radius)[:, :, None], 3, axis=2)
        region = region_from_box((126, 96, 49, 49), (HEIGHT, WIDTH))
        got = clean_frame(np.clip(truth, 0, 255).astype(np.uint8), region, RemoveConfig())
        error = np.abs(got.astype(np.float32) - truth)[region.mask > 0].mean()
        self.assertLess(float(error), 8.0, f"the membrane should track the shading, off by {error:.2f}")

    def test_a_hard_edge_is_what_the_inpainting_method_is_for(self):
        """The membrane spans a boundary, so it rounds a hard step off.

        This is the documented trade-off, not a bug: on content with a genuine
        hard edge behind the mark, ``--method telea`` reproduces the step far
        better. On soft edges -- everything in the clip this was written for --
        the membrane wins because it does not propagate a contaminated boundary.
        """
        truth = np.zeros((HEIGHT, WIDTH, 3), np.float32)
        truth[:, 160:] = 140.0
        region = region_from_box((140, 100, 41, 41), (HEIGHT, WIDTH))
        board = np.clip(truth, 0, 255).astype(np.uint8)
        errors = {}
        for method in ("harmonic", "telea"):
            got = clean_frame(board, region, RemoveConfig(method=method))
            errors[method] = float(np.abs(got.astype(np.float32) - truth)[region.mask > 0].mean())
        self.assertLess(errors["telea"], errors["harmonic"])


class DetectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.video = self.tmp / "clip.mp4"
        self.clean, self.alpha = write_clip(self.video)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_the_static_response_peaks_on_the_mark(self):
        field, window, _ = overlay_field(self.video)
        x, y, w, h = window
        nx, ny = MARK_CENTRE[0] - x, MARK_CENTRE[1] - y
        pad = 30
        around = field[max(0, ny - pad):ny + pad, max(0, nx - pad):nx + pad]
        self.assertGreater(float(around.max()), 0.8 * float(field.max()),
                           "the static response should peak on the mark, not elsewhere in the window")

    def test_detected_box_lands_on_the_mark(self):
        region = detect_watermark(self.video)
        x, y, w, h = region.box
        self.assertLess(abs(x + w / 2 - MARK_CENTRE[0]), 6.0)
        self.assertLess(abs(y + h / 2 - MARK_CENTRE[1]), 6.0)
        covered = (region.mask > 0) & star_mask()
        self.assertGreater(covered.sum() / star_mask().sum(), 0.9, "the mask must cover the mark")

    def test_detection_is_not_tied_to_the_default_window(self):
        for search in ((0.6, 0.6, 0.4, 0.4), "200,140,120,100"):
            region = detect_watermark(self.video, search=search)
            self.assertLess(abs(region.box[0] + region.box[2] / 2 - MARK_CENTRE[0]), 6.0, search)

    def test_detection_fails_loudly_on_a_clip_without_a_mark(self):
        plain = self.tmp / "plain.mp4"
        rng = np.random.default_rng(5)
        writer = cv2.VideoWriter(str(plain), cv2.VideoWriter_fourcc(*"mp4v"), 12.0, (WIDTH, HEIGHT))
        for index in range(12):
            writer.write(composite(clean_background(index, rng), np.zeros((HEIGHT, WIDTH), np.float32)))
        writer.release()
        with self.assertRaises(Exception) as caught:
            detect_watermark(plain)
        self.assertIn("watermark", str(caught.exception).lower())


class RemovalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.video = self.tmp / "clip.mp4"
        self.clean, self.alpha = write_clip(self.video)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_cleaned_frames_come_back_to_the_unmarked_frames(self):
        region = detect_watermark(self.video)
        capture = cv2.VideoCapture(str(self.video))
        mark_energy, left_energy = 0.0, 0.0
        for index in range(len(self.clean)):
            ok, frame = capture.read()
            self.assertTrue(ok)
            cleaned = clean_frame(frame, region, RemoveConfig())
            weight = (region.mask > 0) & (self.alpha > 0)
            left_energy += float(np.abs(cleaned.astype(np.float32)
                                        - self.clean[index].astype(np.float32))[weight].mean())
            mark_energy += float(np.abs(frame.astype(np.float32)
                                        - self.clean[index].astype(np.float32))[weight].mean())
        capture.release()
        self.assertLess(left_energy / mark_energy, 0.25,
                        f"the mark is {mark_energy:.0f} levels across the clip; {left_energy:.0f} remain")

    def test_clean_video_writes_every_frame_and_reports_a_lower_residual(self):
        region = detect_watermark(self.video)
        written, residual, fit, refused = clean_video(self.video, region, self.tmp,
                                                     config=RemoveConfig(), frames_dir=self.tmp / "f")
        self.assertEqual(written, list(range(12)))
        self.assertLess(residual, 0.35 * region.residual)
        self.assertTrue((self.tmp / "f" / "00000.png").exists())
        self.assertIsNone(refused, "the synthetic clip moves enough to be measured")


class ResidualTests(unittest.TestCase):
    """The property that chose the default method.

    A mark's soft edge reaches a pixel or two past any reasonable footprint, so
    the mask boundary carries a little of the mark. A boundary fill propagates
    that straight back into the hole and reconstructs the mark's own outline;
    the membrane averages the whole boundary, so a thin contaminated rim barely
    moves it.
    """

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.video = self.tmp / "soft.mp4"
        write_clip(self.video, soft=2.0)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def residuals(self) -> dict[str, float]:
        region = region_from_box((230, 166, 40, 40), (HEIGHT, WIDTH))
        out = {}
        for method in ("harmonic", "telea", "ns"):
            _, residual, _, _ = clean_video(self.video, region, self.tmp,
                                            config=RemoveConfig(method=method),
                                            frames_dir=self.tmp / method)
            out[method] = residual
        return out

    def test_membrane_leaves_far_less_static_residue_than_a_boundary_fill(self):
        residuals = self.residuals()
        self.assertGreater(residuals["telea"], 2.0, "the test only means something if telea does leak")
        self.assertLess(residuals["harmonic"], 0.25 * residuals["telea"])
        self.assertLess(residuals["harmonic"], 0.5 * residuals["ns"])


class UnmixTests(unittest.TestCase):
    """The translucent-overlay model, scored against the frames the encoder never saw.

    The synthetic clip carries a mark of known opacity (``MARK_ALPHA``) over a
    scene that slides, which is exactly the situation the model is measured
    from. A membrane cannot recover the scene under a translucent mark -- it
    only smooths over it -- so these are the tests that say the inverse is real.
    """

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.video = self.tmp / "clip.mp4"
        self.clean, self.alpha = write_clip(self.video, speed=6.0, soft=1.5, edge=55.0)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _region(self):
        return region_from_box((228, 164, 44, 44), (HEIGHT, WIDTH))

    def test_the_measured_opacity_matches_the_overlay_that_was_composited(self):
        fit = fit_unmix(self.video, self._region())
        self.assertAlmostEqual(fit.opacity, MARK_ALPHA, delta=0.12,
                               msg=f"measured opacity {fit.opacity:.3f}")

    def test_the_model_reproduces_the_unmarked_frames_better_than_the_membrane(self):
        region = self._region()
        fit = fit_unmix(self.video, region)
        capture = cv2.VideoCapture(str(self.video))
        errors = {"unmix": 0.0, "harmonic": 0.0}
        for index in range(len(self.clean)):
            ok, frame = capture.read()
            self.assertTrue(ok)
            weight = (region.mask > 0) & (self.alpha > 0)
            for method in errors:
                if method == "unmix":
                    got = clean_frame(frame, region, RemoveConfig(), fit)
                else:
                    got = clean_frame(frame, region, RemoveConfig(method="harmonic"))
                errors[method] += float(np.abs(got.astype(np.float32)
                                               - self.clean[index].astype(np.float32))[weight].mean())
        capture.release()
        self.assertLess(errors["unmix"], 0.6 * errors["harmonic"],
                        f"unmix {errors['unmix']:.1f} vs harmonic {errors['harmonic']:.1f}")

    def test_the_model_is_measured_from_the_clip_not_from_a_preset(self):
        """Halving the overlay's opacity must halve the measured opacity."""
        faint = self.tmp / "faint.mp4"
        write_clip(faint, speed=6.0, soft=1.5, edge=55.0, opacity=MARK_ALPHA / 2)
        fit = fit_unmix(faint, self._region())
        self.assertAlmostEqual(fit.opacity, MARK_ALPHA / 2, delta=0.10,
                               msg=f"measured opacity {fit.opacity:.3f}")

    def test_a_scene_that_does_not_move_falls_back_to_the_membrane(self):
        still = self.tmp / "still.mp4"
        write_clip(still, speed=0.0, soft=1.5, edge=55.0)
        region = self._region()
        fit = fit_unmix(still, region)
        self.assertLess(fit.motion, RemoveConfig().min_motion)
        _, _, used, refused = clean_video(still, region, self.tmp,
                                          config=RemoveConfig(), frames_dir=self.tmp / "still")
        self.assertIsNone(used)
        self.assertIn("barely moves", refused)

    def test_an_opaque_mark_falls_back_to_the_membrane(self):
        solid = self.tmp / "solid.mp4"
        write_clip(solid, speed=6.0, soft=1.5, edge=55.0, opacity=1.0)
        region = self._region()
        _, _, used, refused = clean_video(solid, region, self.tmp,
                                          config=RemoveConfig(), frames_dir=self.tmp / "solid")
        self.assertIsNone(used)
        self.assertIn("opaque", refused)

    def test_an_unmeasured_model_is_the_membrane(self):
        """``clean_frame`` with no fit is the documented fallback, not NS inpainting."""
        region = self._region()
        rng = np.random.default_rng(2)
        board = clean_background(3, rng)
        fallback = clean_frame(board, region, RemoveConfig())
        membrane = clean_frame(board, region, RemoveConfig(method="harmonic"))
        # The two crop to different margins, so the fills agree only to rounding.
        self.assertLessEqual(int(np.abs(fallback.astype(int) - membrane.astype(int)).max()), 1)
        self.assertGreater(int(fallback.astype(int).var()), 0)


class WatermarkCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.video = self.tmp / "clip.mp4"
        write_clip(self.video)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_command_writes_frames_mask_preview_and_manifest(self):
        from tools.video_edit.cli import main

        out_dir = self.tmp / "out"
        code = main(["watermark", "--video", str(self.video), "--out-dir", str(out_dir), "--skip-encode"])
        self.assertEqual(code, 0)
        manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["frames_cleaned"], 12)
        self.assertIsNone(manifest["outputs"]["video"])
        self.assertLess(manifest["static_residual_after"], manifest["region"]["static_residual_before"])
        for name in ("mask.png", "preview.png", "manifest.json"):
            self.assertTrue((out_dir / name).exists(), name)
        self.assertTrue((out_dir / "frames" / "00000.png").exists())

    def test_box_bypasses_detection_and_grows_by_request(self):
        from tools.video_edit.cli import main

        out_dir = self.tmp / "out"
        code = main(["watermark", "--video", str(self.video), "--out-dir", str(out_dir),
                     "--box", "230,166,40,40", "--grow", "0", "--skip-encode"])
        self.assertEqual(code, 0)
        manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["region"]["method"], "manual-box")
        self.assertEqual(manifest["region"]["area_px"], 40 * 40)


class RealClipTests(unittest.TestCase):
    """The clip this module was written for; the box was measured by hand."""

    SOURCE = MODULE_ROOT.parents[1] / "local/paper-ink-product/Girl_presenting_red_paper_20261018230134.mp4"
    MEASURED_BOX = (574, 1134, 52, 52)

    def setUp(self):
        if not self.SOURCE.exists():
            self.skipTest("source video is not present")

    def test_detection_finds_the_measured_box(self):
        region = detect_watermark(self.SOURCE)
        for got, want in zip(region.box, self.MEASURED_BOX):
            self.assertLess(abs(got - want), 6)
        self.assertGreater(region.residual, 5.0)

    def test_the_mark_is_gone_from_the_frames_where_it_was_hardest(self):
        """Around frames 30 and 210 the arm edge crosses the mark."""
        region = detect_watermark(self.SOURCE)
        config = RemoveConfig()
        capture = cv2.VideoCapture(str(self.SOURCE))
        residuals = []
        for index in (0, 30, 210, 239):
            capture.set(cv2.CAP_PROP_POS_FRAMES, index)
            ok, frame = capture.read()
            self.assertTrue(ok)
            cleaned = clean_frame(frame, region, config)
            ys, xs = np.where(region.mask > 0)
            gray = cv2.cvtColor(cleaned, cv2.COLOR_BGR2GRAY).astype(np.float32)
            source = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(np.float32)
            diameter = cv2.GaussianBlur(gray, (0, 0), 6.0)
            residuals.append(np.abs((gray - diameter)[ys, xs]).mean())
            self.assertGreater(float(np.abs(gray - source)[ys, xs].mean()), 1.0,
                               "the mark must actually be changed")
        capture.release()
        # The mark's own edge response measured 13.2 in the same units.
        self.assertLess(float(np.mean(residuals)), 6.0)


if __name__ == "__main__":
    unittest.main()
