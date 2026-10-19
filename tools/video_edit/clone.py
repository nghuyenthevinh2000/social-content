"""Cover a mark with a nearby patch of the same frame, not a reconstruction."""

import cv2
import numpy as np

from .corners import QuadError
from .blend import apply_shading, rgb_float_to_bgr
from .proxy import tile_mirror


def _patch_clone_frame(frame, mask, offset=None, previous=None):
    """Choose a clean donor by matching the surrounding ring, then blend it.

    A small preference for the previous offset reduces donor switching on video.
    Returns the frame and donor offset (source minus destination, in pixels).
    """
    unsafe = cv2.dilate((mask > 0).astype(np.uint8), np.ones((7, 7), np.uint8))
    ys, xs = np.where(unsafe > 0)
    if not len(xs):
        raise QuadError("the clone mask is empty")
    # A rectangular patch avoids retaining a sparkle-shaped blending boundary.
    unsafe[ys.min():ys.max() + 1, xs.min():xs.max() + 1] = 1
    height, width = mask.shape
    x0, x1 = max(0, int(xs.min()) - 10), min(width, int(xs.max()) + 11)
    y0, y1 = max(0, int(ys.min()) - 10), min(height, int(ys.max()) + 11)
    footprint = unsafe[y0:y1, x0:x1] > 0
    ring = (cv2.dilate(unsafe, np.ones((17, 17), np.uint8)) > 0)[y0:y1, x0:x1] & ~footprint
    target = frame[y0:y1, x0:x1].astype(np.float32)
    gray = cv2.cvtColor(target, cv2.COLOR_BGR2GRAY)
    gradient = cv2.magnitude(cv2.Sobel(gray, cv2.CV_32F, 1, 0), cv2.Sobel(gray, cv2.CV_32F, 0, 1))
    ring_weight = 1 + np.minimum(gradient[ring] / 10, 10)
    size = max(int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1))
    radius = 2 * size
    step = max(4, size // 8)
    candidates = [offset] if offset is not None else [
        (dx, dy) for dy in range(-radius, radius + 1, step)
        for dx in range(-radius, radius + 1, step)
    ]
    best = None
    for dx, dy in candidates:
        if x0 + dx < 0 or y0 + dy < 0 or x1 + dx > width or y1 + dy > height:
            continue
        donor_mask = unsafe[y0 + dy:y1 + dy, x0 + dx:x1 + dx]
        if donor_mask[footprint | ring].any():
            continue
        donor = frame[y0 + dy:y1 + dy, x0 + dx:x1 + dx].astype(np.float32)
        delta = target[ring] - donor[ring]
        if not len(delta):
            continue
        correction = np.clip(np.median(delta, axis=0), -20, 20)
        score = float(np.average(np.abs(delta - correction).mean(axis=1), weights=ring_weight))
        score += .2 * float(np.abs(correction).mean())
        score += .005 * np.hypot(dx, dy)
        if previous is not None:
            score += .03 * np.hypot(dx - previous[0], dy - previous[1])
        if best is None or score < best[0]:
            best = score, donor, correction, (dx, dy)
    if best is None:
        raise QuadError("no clean clone donor fits; use a smaller mask or a different clone offset")
    _, donor, correction, chosen = best
    feather = np.minimum(cv2.distanceTransform(footprint.astype(np.uint8), cv2.DIST_L2, 3) / 3, 1)
    filled = target * (1 - feather[..., None]) + (donor + correction) * feather[..., None]
    result = frame.copy()
    local = result[y0:y1, x0:x1]
    local[footprint] = np.clip(filled[footprint], 0, 255).astype(np.uint8)
    return result, chosen


def clone_frame(frame, mask, offset=None, previous=None):
    """Overlay clean neighbouring texture without copying a donor's silhouette.

    Like the texture compositor, surface coverage and texture are independent.
    The automatic path separates neutral and chromatic surfaces (paper/skin),
    estimates shading from clean pixels of each surface, and overlays nearby
    texture using the shared shading blend. Explicit offsets retain patch mode.
    """
    if offset is not None:
        return _patch_clone_frame(frame, mask, offset, previous)
    protected = cv2.dilate((mask > 0).astype(np.uint8), np.ones((13, 13), np.uint8)) > 0
    ys, xs = np.where(protected)
    if not len(xs):
        raise QuadError("the clone mask is empty")
    height, width = mask.shape
    margin = max(24, int(max(xs.max() - xs.min(), ys.max() - ys.min())))
    x0, x1 = max(0, int(xs.min()) - margin), min(width, int(xs.max()) + margin + 1)
    y0, y1 = max(0, int(ys.min()) - margin), min(height, int(ys.max()) + margin + 1)
    crop = frame[y0:y1, x0:x1]
    hole = protected[y0:y1, x0:x1]
    known = ~hole
    if not known.any():
        raise QuadError("no clean surrounding pixels for the clone overlay")
    values = crop.astype(np.float32)
    chroma = values.max(axis=2) - values.min(axis=2)
    high = float(np.percentile(chroma[known], 90))
    threshold = max(6.0, .15 * high)
    colour = np.clip((chroma - threshold + 2) / 4, 0, 1)
    colour = cv2.GaussianBlur(colour, (0, 0), .7)
    # A white mark can make a weakly coloured single surface look neutral.
    # Do not invent a second material with no clean evidence around the hole.
    if np.count_nonzero(known & (colour < .05)) < 8:
        colour.fill(1)
    elif np.count_nonzero(known & (colour > .95)) < 8:
        colour.fill(0)
    # A white translucent mark reduces chroma, but does not turn skin neutral.
    # Keep this signal for coverage only; never use marked brightness as lighting.
    surfaces = (1 - colour, colour)
    reconstruction = np.zeros_like(values)
    total = np.zeros(hole.shape, np.float32)
    representative = (0, 0)
    for surface in surfaces:
        sources = known & (surface > .95)
        if sources.sum() < 8:
            continue
        weight = sources.astype(np.float32)
        sigma = max(8.0, margin * .4)
        density = cv2.GaussianBlur(weight, (0, 0), sigma)
        light = cv2.GaussianBlur(values * weight[..., None], (0, 0), sigma)
        light /= np.maximum(density, 1e-6)[..., None]
        # Relax the low-frequency illumination within each surface separately;
        # coupling paper and skin would round off the original moving boundary.
        active = hole & (surface > .5)
        domain = surface > .5
        light[known] = values[known]
        for _ in range(240):
            summed = np.zeros_like(light)
            count = np.zeros(hole.shape, np.float32)
            for axis, shift in ((0, 1), (0, -1), (1, 1), (1, -1)):
                valid = domain & np.roll(domain, shift, axis)
                if axis == 0:
                    valid[0 if shift == 1 else -1, :] = False
                else:
                    valid[:, 0 if shift == 1 else -1] = False
                summed += np.roll(light, shift, axis) * valid[..., None]
                count += valid
            update = active & (count > 0)
            light[update] = summed[update] / count[update, None]
        # Use one clean texture tile, not nearest-neighbour colour propagation:
        # the latter stretches individual boundary pixels into visible spokes.
        # Test the actual square footprint, including frame borders. A thin
        # surface may only support a tiny tile, not the usual 13x13 patch.
        for half in range(6, -1, -1):
            candidates = cv2.erode(
                sources.astype(np.uint8), np.ones((2 * half + 1, 2 * half + 1), np.uint8),
                borderType=cv2.BORDER_CONSTANT, borderValue=0,
            ) > 0
            if candidates.any():
                break
        cy, cx = np.array(hole.shape) // 2
        yy, xx = np.mgrid[:hole.shape[0], :hole.shape[1]]
        score = (xx - cx) ** 2 + (yy - cy) ** 2
        score[~candidates] = np.iinfo(score.dtype).max
        donor_y, donor_x = np.unravel_index(score.argmin(), score.shape)
        texture = values[donor_y - half:donor_y + half + 1,
                         donor_x - half:donor_x + half + 1]
        if texture.shape[:2] != (2 * half + 1, 2 * half + 1):
            raise QuadError("no clean texture tile fits within the frame")
        smooth = cv2.GaussianBlur(texture, (0, 0), 2)
        detail = np.clip(texture / np.maximum(smooth, 1), .9, 1.1)
        tiled = tile_mirror(detail, hole.shape[1], hole.shape[0])
        # Same per-channel lighting-carry blend as the product compositor.
        shaded = apply_shading(tiled[..., ::-1], light[..., ::-1] / 255, 1)
        reconstruction += rgb_float_to_bgr(shaded).astype(np.float32) * surface[..., None]
        total += surface
        representative = int(donor_x - cx), int(donor_y - cy)
    if not (total[hole] > 0).all():
        raise QuadError("not enough clean pixels of the same surface for the clone overlay")
    reconstruction /= np.maximum(total, 1e-6)[..., None]
    feather = np.minimum(cv2.distanceTransform(hole.astype(np.uint8), cv2.DIST_L2, 5) / 5, 1)
    filled = values * (1 - feather[..., None]) + reconstruction * feather[..., None]
    result = frame.copy()
    local = result[y0:y1, x0:x1]
    local[hole] = np.clip(filled[hole], 0, 255).astype(np.uint8)
    return result, representative
