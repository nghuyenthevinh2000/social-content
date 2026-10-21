"""Method 4: Standardized interior optical-flow + RANSAC affine surface tracker."""

from __future__ import annotations

import cv2
import numpy as np

from ..corners import QuadError, colour_mask, detect_quad, order_corners


def track_surface_flow(
    frames_iter,
    *,
    s_min: int = 150,
    v_min: int = 40,
) -> list[np.ndarray]:
    """Track a surface quad across frames via interior PyrLK optical flow + RANSAC affine fit.

    Unlike contour corner fitting, interior RANSAC tracking is invariant to which
    edges are clipped by the camera frame or folded at a single corner.
    """
    frames = [frame for _, frame in frames_iter]
    if not frames:
        return []

    anchor_idx = 0
    anchor_quad = None
    for idx, frame in enumerate(frames):
        try:
            det = detect_quad(frame, mode="saturated", s_min=s_min, v_min=v_min)
            anchor_idx = idx
            anchor_quad = det.corners.astype(np.float32)
            break
        except QuadError:
            continue
    if anchor_quad is None:
        h, w = frames[0].shape[:2]
        anchor_quad = np.array([[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]], np.float32)

    quads: list[np.ndarray] = [anchor_quad.copy() for _ in frames]

    def _step(src_frame: np.ndarray, dst_frame: np.ndarray, q_curr: np.ndarray) -> np.ndarray:
        mask = colour_mask(src_frame, s_min=s_min, v_min=v_min, kernel=5, dilate=0)
        mask = cv2.erode(mask, np.ones((9, 9), np.uint8), iterations=1)
        g0 = cv2.cvtColor(src_frame, cv2.COLOR_BGR2GRAY)
        g1 = cv2.cvtColor(dst_frame, cv2.COLOR_BGR2GRAY)
        pts0 = cv2.goodFeaturesToTrack(g0, maxCorners=120, qualityLevel=0.01, minDistance=8, mask=mask)
        if pts0 is None or len(pts0) < 6:
            return q_curr
        pts1, st, _ = cv2.calcOpticalFlowPyrLK(g0, g1, pts0, None, winSize=(21, 21), maxLevel=3)
        if pts1 is None or st is None:
            return q_curr
        good0 = pts0[st.ravel() == 1].reshape(-1, 2)
        good1 = pts1[st.ravel() == 1].reshape(-1, 2)
        if len(good0) < 6:
            return q_curr
        mat, _ = cv2.estimateAffinePartial2D(good0, good1, method=cv2.RANSAC, ransacReprojThreshold=3.0)
        if mat is None:
            return q_curr
        transformed = cv2.transform(q_curr.reshape(1, 4, 2), mat).reshape(4, 2).astype(np.float32)
        try:
            return order_corners(transformed)
        except QuadError:
            return q_curr

    for i in range(anchor_idx + 1, len(frames)):
        quads[i] = _step(frames[i - 1], frames[i], quads[i - 1])
    for i in range(anchor_idx - 1, -1, -1):
        quads[i] = _step(frames[i + 1], frames[i], quads[i + 1])
    return quads
