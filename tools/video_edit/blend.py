"""Blend modes and colour helpers.

Everything here works on float32 RGB arrays in the 0..1 range. OpenCV reads
images as BGR uint8, so the conversion helpers are the only place where that
ordering is handled.
"""

from __future__ import annotations

import cv2
import numpy as np

# Luminance weights applied to an RGB array (Rec. 709).
_LUMA = np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)

# "shading" is not a Photoshop mode: it multiplies the warped texture by a
# normalised illumination field taken from the proxy. It is the mode that
# keeps the proxy's lighting and hand shadows while leaving real pixels intact
# in relative terms. The rest are provided for comparison.
BLEND_MODES = (
    "shading",
    "multiply",
    "screen",
    "overlay",
    "soft_light",
    "hard_light",
    "luminosity",
    "normal",
)


def bgr_to_rgb_float(image: np.ndarray) -> np.ndarray:
    """uint8 BGR (or already-float BGR in 0..1) -> float32 RGB in 0..1."""
    if image.dtype == np.uint8:
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        return rgb.astype(np.float32) / 255.0
    return np.clip(image, 0.0, 1.0).astype(np.float32)


def rgb_float_to_bgr(image: np.ndarray) -> np.ndarray:
    """float32 RGB in 0..1 -> uint8 BGR."""
    rgb = np.clip(image, 0.0, 1.0)
    return cv2.cvtColor((rgb * 255.0).astype(np.uint8), cv2.COLOR_RGB2BGR)


def luminance(rgb: np.ndarray) -> np.ndarray:
    """Rec. 709 luminance of an HxWx3 float RGB array."""
    return (rgb.astype(np.float32) @ _LUMA).astype(np.float32)


def _as_three_channel(value: np.ndarray, shape) -> np.ndarray:
    if value.ndim == 3:
        return value
    return np.repeat(value[..., None], shape[2], axis=2)


def _soft_light(base: np.ndarray, top: np.ndarray) -> np.ndarray:
    """W3C compositing soft-light: base is the backdrop, top is the source."""
    b = np.clip(base, 0.0, 1.0)
    s = np.clip(top, 0.0, 1.0)
    d = np.where(b <= 0.25, ((16.0 * b - 12.0) * b + 4.0) * b, np.sqrt(b))
    return np.where(s <= 0.5, b - (1.0 - 2.0 * s) * b * (1.0 - b), b + (2.0 * s - 1.0) * (d - b))


def _luminosity(base: np.ndarray, top: np.ndarray) -> np.ndarray:
    """Take lightness from the base (proxy), hue and chroma from the top (texture)."""
    base_lab = cv2.cvtColor((np.clip(base, 0, 1) * 255).astype(np.uint8), cv2.COLOR_RGB2LAB)
    top_lab = cv2.cvtColor((np.clip(top, 0, 1) * 255).astype(np.uint8), cv2.COLOR_RGB2LAB)
    out = top_lab.copy()
    out[..., 0] = base_lab[..., 0]
    out_rgb = cv2.cvtColor(out, cv2.COLOR_LAB2RGB)
    return out_rgb.astype(np.float32) / 255.0


def blend(base: np.ndarray, top: np.ndarray, mode: str) -> np.ndarray:
    """Composite ``top`` over ``base`` using a named mode.

    ``base`` is the proxy (backdrop) and ``top`` is the warped real texture.
    Both are float32 RGB in 0..1; the result is float32 RGB in 0..1. Modes
    other than ``shading`` can return values outside 0..1, so callers clamp.
    """
    if mode not in BLEND_MODES:
        raise ValueError(f"unknown blend mode {mode!r}; expected one of {', '.join(BLEND_MODES)}")

    b = base.astype(np.float32)
    t = top.astype(np.float32)

    if mode == "normal":
        return t
    if mode == "multiply":
        return b * t
    if mode == "screen":
        return 1.0 - (1.0 - b) * (1.0 - t)
    if mode == "overlay":
        return np.where(b <= 0.5, 2.0 * b * t, 1.0 - 2.0 * (1.0 - b) * (1.0 - t))
    if mode == "hard_light":
        return np.where(t <= 0.5, 2.0 * t * b, 1.0 - 2.0 * (1.0 - t) * (1.0 - b))
    if mode == "soft_light":
        return _soft_light(b, t)
    if mode == "luminosity":
        return _luminosity(b, t)
    if mode == "shading":
        # The caller multiplies by the illumination field; without one this is
        # a plain paste of the real pixels.
        return t
    raise ValueError(f"unhandled blend mode {mode!r}")


def apply_shading(rgb: np.ndarray, illumination: np.ndarray, strength: float) -> np.ndarray:
    """Multiply RGB by a normalised illumination field.

    ``illumination`` is an HxW array centred on 1.0, so a value of 0.8 darkens
    that pixel by 20%. ``strength`` 0 disables the effect, 1 applies it fully.
    Chromaticity is preserved because every channel is scaled equally.
    """
    field = _as_three_channel(illumination.astype(np.float32), rgb.shape)
    field = 1.0 + (field - 1.0) * float(strength)
    return rgb * field
