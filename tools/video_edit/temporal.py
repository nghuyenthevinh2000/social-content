"""Borrow unmarked pixels from motion-aligned frames in a single shot."""

import cv2
import numpy as np


def borrow_frame(index, frames, guides, mask, fallback):
    """Return a filled crop and the fraction supported by clean donor pixels.

    Flow is measured on filled guides, not on the stationary watermark. Donors
    must clear the source mask and pass forward/backward flow consistency.
    Frames must belong to one continuous shot; cuts should be split first.
    """
    height, width = mask.shape
    yy, xx = np.mgrid[:height, :width].astype(np.float32)
    unsafe = cv2.dilate(mask.astype(np.uint8), np.ones((7, 7), np.uint8))
    ring = (cv2.dilate(unsafe, np.ones((15, 15), np.uint8)) > 0) & ~(unsafe > 0)
    target = guides[index]
    total = np.zeros_like(fallback, dtype=np.float32)
    weights = np.zeros(mask.shape, np.float32)
    for distance in (8, 16, 32, 64, 96, 128, 192):
        for donor in (index - distance, index + distance):
            if not 0 <= donor < len(frames):
                continue
            source = guides[donor]
            flow = cv2.calcOpticalFlowFarneback(target, source, None, .5, 4, 35, 5, 7, 1.5, 0)
            reverse = cv2.calcOpticalFlowFarneback(source, target, None, .5, 4, 35, 5, 7, 1.5, 0)
            mx, my = xx + flow[..., 0], yy + flow[..., 1]
            valid = (mx >= 0) & (my >= 0) & (mx < width - 1) & (my < height - 1)
            clean = cv2.remap(unsafe, mx, my, cv2.INTER_LINEAR,
                              borderMode=cv2.BORDER_CONSTANT, borderValue=1) == 0
            back = cv2.remap(reverse, mx, my, cv2.INTER_LINEAR)
            error = np.linalg.norm(flow + back, axis=2)
            warped = cv2.remap(frames[donor], mx, my, cv2.INTER_LINEAR).astype(np.float32)
            support = ring & clean & valid & (error < 1.5)
            if support.sum() < 30:
                continue
            difference = frames[index].astype(np.float32) - warped
            shift = np.median(difference[support], axis=0)
            mismatch = np.median(np.abs(difference[support] - shift))
            if mismatch > 10 or np.max(np.abs(shift)) > 15:
                continue
            weight = (mask & valid & clean & (error < 1.5)).astype(np.float32)
            weight *= np.exp(-error * error / 2) / (1 + mismatch)
            total += (warped + shift) * weight[..., None]
            weights += weight
    supported = weights > 0
    result = fallback.astype(np.float32).copy()
    result[supported] = total[supported] / weights[supported, None]
    # Blend inward only: never touch an unmasked pixel.
    feather = np.minimum(cv2.distanceTransform(mask.astype(np.uint8), cv2.DIST_L2, 3) / 3, 1)
    result = frames[index] * (1 - feather[..., None]) + result * feather[..., None]
    return np.clip(result, 0, 255).astype(np.uint8), float(supported[mask].mean())
