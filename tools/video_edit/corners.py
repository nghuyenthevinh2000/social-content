"""Locate the four corners of a product's flat surface in a proxy frame.

Default backend is OpenCV: a colour/edge mask, largest connected region, then a
four-point polygon fit. A SAM 2 backend is available but import-guarded, so the
package works without torch installed.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np


class QuadError(RuntimeError):
    """Raised when no usable four-corner region can be found."""


@dataclass
class QuadDetection:
    """A detected quadrilateral, ordered top-left, top-right, bottom-right, bottom-left."""

    corners: np.ndarray
    method: str
    score: float
    mask: np.ndarray | None = None
    notes: list[str] = field(default_factory=list)

    def as_list(self) -> list[list[float]]:
        return [[float(x), float(y)] for x, y in self.corners]


def order_corners(points: np.ndarray) -> np.ndarray:
    """Order four points as top-left, top-right, bottom-right, bottom-left.

    Uses sum/difference of coordinates, which is stable for the roughly
    convex, roughly axis-aligned quads a product photo produces.
    """
    pts = np.asarray(points, dtype=np.float32).reshape(-1, 2)
    if pts.shape[0] != 4:
        raise QuadError(f"expected 4 points, got {pts.shape[0]}")

    total = pts.sum(axis=1)
    delta = pts[:, 0] - pts[:, 1]
    ordered = np.stack(
        [
            pts[np.argmin(total)],
            pts[np.argmax(delta)],
            pts[np.argmax(total)],
            pts[np.argmin(delta)],
        ]
    ).astype(np.float32)

    if len({(round(float(x), 3), round(float(y), 3)) for x, y in ordered}) != 4:
        raise QuadError("corner ordering degenerated; points are colinear or duplicated")
    return ordered


def parse_corners(text: str) -> np.ndarray:
    """Parse manual corners such as ``12,20;900,40;880,700;40,690`` into an ordered quad."""
    raw = [chunk for chunk in text.replace("\n", ";").replace(" ", ";").split(";") if chunk.strip()]
    if len(raw) != 4:
        raise QuadError(f"expected 4 'x,y' pairs, got {len(raw)} in {text!r}")
    points = []
    for chunk in raw:
        parts = chunk.split(",")
        if len(parts) != 2:
            raise QuadError(f"expected 'x,y', got {chunk!r}")
        try:
            points.append((float(parts[0]), float(parts[1])))
        except ValueError as error:
            raise QuadError(f"non-numeric coordinate in {chunk!r}") from error
    return order_corners(np.asarray(points, dtype=np.float32))


def _mask_saturated(image: np.ndarray, s_min: int, v_min: int) -> np.ndarray:
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    h, s, val = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]
    sat = (s >= s_min) & (val >= v_min)
    if s_min >= 120:
        # Retain bright specular reflections on crimson/red cardstock where S dips slightly below s_min.
        spec_red = ((h <= 5) | (h >= 175)) & (s >= int(0.70 * s_min)) & (val >= max(145, v_min))
        sat = sat | spec_red
    return sat.astype(np.uint8) * 255


def _mask_edges(image: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(gray, 60, 180)
    return cv2.morphologyEx(edges, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))


def _mask_bright(image: np.ndarray, v_min: int) -> np.ndarray:
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    return (hsv[:, :, 2] >= v_min).astype(np.uint8) * 255


def _clean(mask: np.ndarray, kernel: int) -> np.ndarray:
    k = np.ones((kernel, kernel), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k, iterations=2)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, k, iterations=1)
    return mask


def colour_mask(
    image: np.ndarray,
    *,
    s_min: int = 150,
    v_min: int = 40,
    kernel: int = 7,
    dilate: int = 1,
) -> np.ndarray:
    """Mask of the strongly saturated product pixels in ``image`` (uint8 0/255).

    The largest region identifies the product. Its dominant hue and median
    brightness then reject saturated skin/shadows connected to that region.
    This assumes a single-colour product; saturation alone is not a material
    classifier (dark neck shadows can be highly saturated too).
    """
    raw_mask = _mask_saturated(image, s_min, v_min)
    mask = _clean(raw_mask, kernel)
    # Only the product, not disconnected saturated lips, jewellery or noise.
    # Connected components preserve holes where fingers overlap the surface.
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask)
    if count > 1:
        largest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        mask = (labels == largest).astype(np.uint8) * 255
    samples = (mask > 0) & (raw_mask > 0)
    if not samples.any():
        return np.zeros_like(mask)
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    hue = hsv[:, :, 0].astype(np.int16)
    dominant_hue = int(np.bincount(hue[samples], minlength=180).argmax())
    hue_distance = np.abs(hue - dominant_hue)
    hue_distance = np.minimum(hue_distance, 180 - hue_distance)
    # OpenCV hue wraps at 180. Learn the paper colour, rather than hardcoding
    # red, and reject dim shadows relative to the material's own exposure.
    median_v = float(np.median(hsv[:, :, 2][samples]))
    brightness_floor = max(v_min, 0.55 * median_v)
    deep_shadow_floor = max(v_min, 0.35 * median_v)
    material = ((hue_distance <= 4) & (hsv[:, :, 2] >= brightness_floor)) | (
        (hue_distance <= 5) & (hsv[:, :, 1] >= 180) & (hsv[:, :, 2] >= deep_shadow_floor)
    )
    raw_mask = cv2.bitwise_and(raw_mask, material.astype(np.uint8) * 255)
    if dilate > 0:
        size = dilate * 2 + 1
        mask = cv2.dilate(mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (size, size)), iterations=1)
    # Morphology selects the product but must never invent foreground pixels:
    # closing/dilation can bridge across a moving finger or into the background.
    mask = cv2.bitwise_and(mask, raw_mask)
    # The colour test can detach an attached skin patch. Select again *after*
    # that test; otherwise disconnected red reflections can survive selection.
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask)
    if count > 1:
        largest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        mask = (labels == largest).astype(np.uint8) * 255
    return mask


def refine_sheet_quad(mask: np.ndarray, quad: np.ndarray) -> np.ndarray:
    """Intersect long sheet edges instead of treating finger tips as corners.

    A rough quad only seeds edge directions. Top, right and bottom must have
    visible straight segments; a clipped/hidden left edge may use the seed.
    This is a flat-sheet fit, not a model of curved or folded products.
    """
    tl, tr, br, bl = quad
    centre = quad.mean(axis=0)
    horizontal = (tr-tl) + (br-bl)
    vertical = (br-tr) + (bl-tl)
    horizontal = horizontal / max(float(np.linalg.norm(horizontal)), 1e-6)
    vertical = vertical / max(float(np.linalg.norm(vertical)), 1e-6)
    min_length = max(30, int(.15 * np.sqrt(np.count_nonzero(mask))))
    segments = cv2.HoughLinesP(cv2.Canny(mask, 80, 160), 1, np.pi/720,
                               threshold=30, minLineLength=min_length, maxLineGap=15)
    if segments is None:
        raise QuadError("no straight sheet edges")
    groups: list[list[tuple[float, np.ndarray]]] = [[], [], [], []]
    for segment in segments.reshape(-1, 4):
        a, b = segment.reshape(2, 2).astype(np.float64)
        direction = b-a
        length = float(np.linalg.norm(direction))
        direction /= max(length, 1e-6)
        hu, vv = abs(direction @ horizontal), abs(direction @ vertical)
        if max(hu, vv) < np.cos(np.deg2rad(25)):
            continue
        midpoint = .5*(a+b) - centre
        if hu > vv:
            side = 0 if midpoint @ vertical < 0 else 2
        else:
            side = 1 if midpoint @ horizontal > 0 else 3
        groups[side].append((length, segment))
    h_img, w_img = mask.shape[:2]
    bottom_clipped = float(br[1]) >= h_img - 3.0 and float(bl[1]) >= h_img - 3.0
    left_clipped = float(tl[0]) <= 2.0 and float(bl[0]) <= 2.0
    if bottom_clipped:
        groups[2].clear()
    if left_clipped:
        groups[3].clear()
    required = (0, 1) if bottom_clipped else (0, 1, 2)
    if any(not groups[side] for side in required):
        raise QuadError("top, right and bottom edges must be visible")
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    points = max(contours, key=cv2.contourArea).reshape(-1, 2).astype(np.float32)
    seed_edges = ((tl, tr), (tr, br), (br, bl), (bl, tl))
    lines = []
    for side, group in enumerate(groups):
        if group:
            _, segment = max(group, key=lambda item: item[0])
            a, b = segment.reshape(2, 2).astype(np.float64)
        else:
            a, b = seed_edges[side]  # clipped boundary stays on the image border
        direction = b-a
        normal = np.array([-direction[1], direction[0]], np.float64)
        normal /= max(float(np.linalg.norm(normal)), 1e-6)
        near = points[np.abs((points-a) @ normal) < 2.5]
        if group and len(near) >= 8:
            vx, vy, x, y = cv2.fitLine(near, cv2.DIST_HUBER, 0, .01, .01).ravel()
            normal = np.array([-vy, vx], np.float64)
            a = np.array([x, y])
        lines.append((normal, float(normal @ a)))
    corners = []
    for first, second in ((3, 0), (0, 1), (1, 2), (2, 3)):
        normals = np.stack([lines[first][0], lines[second][0]])
        if abs(np.linalg.det(normals)) < .1:
            raise QuadError("sheet edge intersections are unstable")
        corners.append(np.linalg.solve(normals, [lines[first][1], lines[second][1]]))
    result = np.array(corners, np.float32)
    if not cv2.isContourConvex(result) or np.max(np.linalg.norm(result-quad, axis=1)) > .5*np.hypot(*mask.shape):
        raise QuadError("sheet edge fit is inconsistent with the detected region")
    return result


def detect_quad(
    image: np.ndarray,
    *,
    mode: str = "saturated",
    min_area_ratio: float = 0.02,
    kernel: int = 5,
    s_min: int = 60,
    v_min: int = 40,
    grow: int = 1,
) -> QuadDetection:
    """Detect the largest card-like quadrilateral in ``image`` (uint8 BGR).

    ``mode`` selects the segmentation strategy:

    ``saturated``  a saturated, bright region (a coloured card on a neutral set)
    ``edges``      strong edges closed into a region (a low-contrast card)
    ``bright``     the brightest region (a pale card on a dark set)
    """
    if image is None:
        raise QuadError("image could not be read")
    height, width = image.shape[:2]
    frame_area = float(height * width)

    if mode == "saturated":
        mask = _mask_saturated(image, s_min, v_min)
    elif mode == "edges":
        mask = _mask_edges(image)
    elif mode == "bright":
        mask = _mask_bright(image, v_min)
    else:
        raise QuadError(f"unknown detection mode {mode!r}")

    mask = _clean(mask, kernel)
    if grow > 0:
        mask = cv2.dilate(mask, np.ones((grow * 2 + 1, grow * 2 + 1), np.uint8), iterations=1)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        raise QuadError(f"no region found with mode {mode!r}; try another mode or pass --corners")

    contour = max(contours, key=cv2.contourArea)
    contour_area = float(cv2.contourArea(contour))
    if contour_area < frame_area * min_area_ratio:
        raise QuadError(
            f"largest region covers {contour_area / frame_area:.1%} of the frame, "
            f"below the {min_area_ratio:.1%} minimum"
        )

    notes: list[str] = []
    perimeter = cv2.arcLength(contour, True)
    quad = None
    for epsilon in (0.01, 0.02, 0.03, 0.05, 0.08):
        approx = cv2.approxPolyDP(contour, epsilon * perimeter, True)
        if len(approx) == 4 and cv2.isContourConvex(approx):
            quad = approx.reshape(4, 2).astype(np.float32)
            notes.append(f"four-point fit at epsilon={epsilon}")
            method = "approxpoly"
            break

    if quad is None:
        box = cv2.boxPoints(cv2.minAreaRect(contour)).astype(np.float32)
        quad = box
        method = "minarearect"
        notes.append("no four-point fit; fell back to the minimum-area rotated rectangle")

    quad = order_corners(quad)
    quad_area = max(float(cv2.contourArea(quad.astype(np.float32))), 1.0)
    score = float(np.clip(contour_area / quad_area, 0.0, 1.0))

    filled = np.zeros((height, width), np.uint8)
    cv2.drawContours(filled, [contour], -1, 255, thickness=cv2.FILLED)

    return QuadDetection(corners=quad, method=method, score=score, mask=filled, notes=notes)


def detect_quad_sam2(
    image: np.ndarray,
    *,
    point: tuple[int, int],
    checkpoint: str,
    model_cfg: str = "configs/sam2.1/sam2.1_hiera_s.yaml",
) -> QuadDetection:
    """Detect the card via SAM 2, then fit a quad to the returned mask.

    Optional: requires ``torch`` and the ``sam2`` package plus a checkpoint.
    Prompt ``point`` must be inside the card. Install with::

        uv pip install torch sam2 --index-url https://download.pytorch.org/whl/cpu

    then download a checkpoint from the SAM 2 repository.
    """
    try:
        import torch  # noqa: F401
        from sam2.build_sam import build_sam2
        from sam2.sam2_image_predictor import SAM2ImagePredictor
    except ImportError as error:
        raise QuadError(
            "the sam2 backend needs torch and the sam2 package; install them or use the "
            "default OpenCV backend"
        ) from error

    predictor = SAM2ImagePredictor(build_sam2(model_cfg, checkpoint))
    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    predictor.set_image(rgb)
    masks, scores, _ = predictor.predict(
        point_coords=np.array([point], dtype=np.float32),
        point_labels=np.array([1], dtype=np.int32),
        multimask_output=True,
    )
    best = masks[int(np.argmax(scores))]
    mask = (best.astype(np.uint8)) * 255
    mask = _clean(mask, 5)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        raise QuadError("SAM 2 returned an empty mask")
    contour = max(contours, key=cv2.contourArea)
    perimeter = cv2.arcLength(contour, True)
    for epsilon in (0.01, 0.02, 0.03, 0.05):
        approx = cv2.approxPolyDP(contour, epsilon * perimeter, True)
        if len(approx) == 4 and cv2.isContourConvex(approx):
            return QuadDetection(
                corners=order_corners(approx.reshape(4, 2)),
                method="sam2",
                score=float(np.clip(float(np.max(scores)), 0.0, 1.0)),
                mask=mask,
                notes=[f"sam2 prompt point {point}", f"four-point fit at epsilon={epsilon}"],
            )
    box = cv2.boxPoints(cv2.minAreaRect(contour))
    return QuadDetection(
        corners=order_corners(box),
        method="sam2+minarearect",
        score=float(np.clip(float(np.max(scores)), 0.0, 1.0)),
        mask=mask,
        notes=[f"sam2 prompt point {point}", "no four-point fit; fell back to minAreaRect"],
    )
