"""Spatial cloning covers the mark using actual neighbouring pixels."""

import unittest

import cv2
import numpy as np

from tools.video_edit.clone import clone_frame
from tools.video_edit.corners import QuadError


class CloneTests(unittest.TestCase):
    def test_white_mark_does_not_invent_an_unsupported_neutral_surface(self):
        frame = np.full((100, 140, 3), [160, 165, 170], np.uint8)
        mask = np.zeros((100, 140), np.uint8)
        mask[40:56, 60:76] = 255
        frame[mask > 0] = [208, 210, 212]
        got, _ = clone_frame(frame, mask)
        self.assertLess(np.abs(got[mask > 0].astype(float) - [160, 165, 170]).mean(), 2)

    def test_auto_overlay_keeps_curved_material_boundary_and_texture(self):
        yy, xx = np.mgrid[:128, :180]
        edge = 72 + 9 * np.sin(xx / 25)
        skin = yy < edge
        clean = np.where(skin[..., None], np.array([120, 155, 190]),
                         np.array([235, 235, 235])).astype(np.float32)
        grain = np.random.default_rng(3).normal(0, .8, clean.shape)
        clean = np.clip(clean + grain, 0, 255).astype(np.uint8)
        mask = np.zeros((128, 180), np.uint8)
        cv2.circle(mask, (90, 70), 17, 255, -1)
        marked = clean.copy()
        marked[mask > 0] = (clean[mask > 0] * .65 + 255 * .35).astype(np.uint8)
        got, _ = clone_frame(marked, mask)
        deep_skin = (mask > 0) & (yy < edge - 4)
        deep_paper = (mask > 0) & (yy > edge + 4)
        self.assertLess(np.abs(got.astype(float) - clean)[deep_skin | deep_paper].mean(), 3)
        self.assertGreater((got[..., 2].astype(float) - got[..., 0])[deep_skin].mean(), 60)
        self.assertLess((got.max(2).astype(float) - got.min(2))[deep_paper].mean(), 4)
        self.assertGreater(got[..., 0][deep_skin].std(), .3)
        outside = cv2.dilate(mask, np.ones((13, 13), np.uint8)) == 0
        np.testing.assert_array_equal(got[outside], marked[outside])

    def test_clean_patch_covers_mark_and_preserves_outside_rectangle(self):
        frame = np.full((120, 180, 3), 100, np.uint8)
        mask = np.zeros((120, 180), np.uint8)
        mask[50:66, 80:96] = 255
        frame[mask > 0] = 240
        got, offset = clone_frame(frame, mask, offset=(-40, 0))
        self.assertEqual(offset, (-40, 0))
        self.assertLess(np.abs(got[mask > 0].astype(float) - 100).mean(), 2)
        outside = np.ones(mask.shape, bool)
        outside[47:69, 77:99] = False
        np.testing.assert_array_equal(got[outside], frame[outside])

    def test_auto_donor_is_clean_and_deterministic(self):
        frame = np.full((120, 180, 3), 100, np.uint8)
        mask = np.zeros((120, 180), np.uint8)
        mask[50:66, 80:96] = 255
        frame[mask > 0] = 240
        got, offset = clone_frame(frame, mask)
        repeated, second_offset = clone_frame(frame, mask)
        self.assertEqual(offset, second_offset)
        np.testing.assert_array_equal(got, repeated)
        dx, dy = offset
        self.assertFalse(mask[50 + dy:66 + dy, 80 + dx:96 + dx].any())
        self.assertLess(got[mask > 0].mean(), 105)

    def test_rejects_contaminated_or_out_of_bounds_donor(self):
        frame = np.full((120, 180, 3), 100, np.uint8)
        mask = np.zeros((120, 180), np.uint8)
        mask[50:66, 80:96] = 255
        for offset in ((0, 0), (1000, 0)):
            with self.subTest(offset=offset), self.assertRaises(QuadError):
                clone_frame(frame, mask, offset)
