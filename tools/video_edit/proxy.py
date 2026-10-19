"""Proxy frames and texture tiling.

Two things live here:

* ``smooth_proxy`` turns a real photo into an edge-preserving smooth version.
  It is a deterministic stand-in for the "AI generates a clean, smooth
  placeholder" step, so the pipeline runs without an image model. When a real
  generated proxy exists, pass it to ``compose`` instead.
* ``tile_mirror`` repeats a small real texture seamlessly at native pixel
  scale so grain is never resampled up.
"""

from __future__ import annotations

import cv2
import numpy as np

from .blend import bgr_to_rgb_float, rgb_float_to_bgr
from .corners import order_corners


def smooth_proxy(
    image: np.ndarray,
    *,
    diameter: int = 9,
    sigma_color: float = 75.0,
    sigma_space: float = 75.0,
    iterations: int = 3,
    lowpass: float = 0.0,
) -> np.ndarray:
    """Edge-preserving smoothing that removes micro-texture but keeps lighting.

    A bilateral filter flattens grain and fibre while preserving the object
    outline and the large-scale shading. ``lowpass`` adds a final gentle
    blur (sigma in pixels) for surfaces that still show residual speckle.
    """
    out = image.copy()
    for _ in range(max(1, iterations)):
        out = cv2.bilateralFilter(out, diameter, sigma_color, sigma_space)
    if lowpass > 0:
        radius = int(max(1, round(lowpass * 3)))
        out = cv2.GaussianBlur(out, (radius * 2 + 1, radius * 2 + 1), lowpass)
    return out


def tile_mirror(image: np.ndarray, width: int, height: int) -> np.ndarray:
    """Tile ``image`` to ``width`` x ``height`` using mirrored edges.

    Mirroring makes every tile boundary continuous, so no hard seam appears
    across a repeated texture. Tiles stay at the source image's native pixel
    scale; the texture is never scaled up.
    """
    if width <= 0 or height <= 0:
        raise ValueError("width and height must be positive")
    src_h, src_w = image.shape[:2]
    if src_h == 0 or src_w == 0:
        raise ValueError("source texture is empty")

    block = np.concatenate(
        [
            np.concatenate([image, np.fliplr(image)], axis=1),
            np.concatenate([np.flipud(image), np.flipud(np.fliplr(image))], axis=1),
        ],
        axis=0,
    )
    reps_y = int(np.ceil(height / block.shape[0]))
    reps_x = int(np.ceil(width / block.shape[1]))
    tiled = np.tile(block, (reps_y, reps_x, 1))
    return tiled[:height, :width].copy()


def rotate_texture(image: np.ndarray, angle: float) -> np.ndarray:
    """Rotate a texture about its centre, expanding the canvas and reflecting edges."""
    if abs(angle) < 0.01:
        return image
    height, width = image.shape[:2]
    centre = (width / 2.0, height / 2.0)
    matrix = cv2.getRotationMatrix2D(centre, angle, 1.0)
    cos, sin = abs(matrix[0, 0]), abs(matrix[0, 1])
    new_w = int(height * sin + width * cos)
    new_h = int(height * cos + width * sin)
    matrix[0, 2] += new_w / 2.0 - centre[0]
    matrix[1, 2] += new_h / 2.0 - centre[1]
    return cv2.warpAffine(
        image,
        matrix,
        (new_w, new_h),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REFLECT_101,
    )


def flatten_texture(image: np.ndarray, sigma: float) -> np.ndarray:
    """Remove a texture's own low-frequency lighting, keeping its albedo detail.

    A close-up photo carries its own vignette and illumination gradient. Tiling
    it directly repeats those gradients. Dividing by a heavily blurred copy of
    its own luminance leaves the grain, and lets the proxy frame's lighting
    drive the final result.
    """
    if sigma <= 0:
        return image
    rgb = bgr_to_rgb_float(image)
    lum = rgb @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    base = cv2.GaussianBlur(lum, (0, 0), sigma)
    base = np.maximum(base, 1e-3)
    scale = (float(base.mean()) / base)[..., None]
    return rgb_float_to_bgr(np.clip(rgb * scale, 0.0, 1.0))


def synthetic_card_proxy(
    width: int = 1280,
    height: int = 960,
    *,
    seed: int = 7,
    corners: np.ndarray | None = None,
    card_bgr: tuple[int, int, int] = (40, 33, 197),
    background_bgr: tuple[int, int, int] = (206, 204, 198),
    shadow: float = 0.45,
    lighting: float = 0.35,
    feather: float = 1.2,
) -> tuple[np.ndarray, np.ndarray]:
    """Render a deterministic test fixture: a smooth matte card on a neutral set.

    This is a fixture for tests and for exercising the pipeline, **not** a
    product image and **not** a substitute for an AI-generated proxy. It
    returns ``(image, quad)`` where ``quad`` is the ground-truth corner order.
    """
    rng = np.random.default_rng(seed)
    del rng  # reserved for future jitter; the fixture is currently fully deterministic

    if corners is None:
        quad = np.array(
            [[0.18, 0.14], [0.84, 0.20], [0.80, 0.86], [0.14, 0.80]], dtype=np.float32
        ) * np.array([width, height], dtype=np.float32)
    else:
        quad = np.asarray(corners, dtype=np.float32)
    quad = order_corners(quad)

    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)

    canvas = np.zeros((height, width, 3), np.float32)
    canvas[:] = np.asarray(background_bgr, np.float32)
    canvas *= (1.0 + 0.06 * (xx / width - 0.5) - 0.08 * (yy / height - 0.5))[..., None]

    shadow_layer = np.zeros((height, width), np.float32)
    offset = quad + np.array([width * 0.025, height * 0.035], np.float32)
    cv2.fillPoly(shadow_layer, [offset.astype(np.int32)], 1.0)
    shadow_layer = cv2.GaussianBlur(shadow_layer, (0, 0), max(8.0, width * 0.02))
    canvas *= (1.0 - shadow * shadow_layer)[..., None]

    card_mask = np.zeros((height, width), np.float32)
    cv2.fillPoly(card_mask, [quad.astype(np.int32)], 1.0)
    card_mask = cv2.GaussianBlur(card_mask, (0, 0), feather)

    card = np.zeros((height, width, 3), np.float32)
    card[:] = np.asarray(card_bgr, np.float32)
    ramp = (xx / width) * 0.6 + (yy / height) * 0.4
    card *= (1.0 + lighting * (0.5 - ramp))[..., None]

    out = canvas * (1.0 - card_mask[..., None]) + card * card_mask[..., None]
    return np.clip(out, 0.0, 255.0).astype(np.uint8), quad
