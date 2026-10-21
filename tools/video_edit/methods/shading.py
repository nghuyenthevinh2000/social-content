"""Method 1: Deterministic 2D perspective swap with Gaussian illumination-carry shading."""

from __future__ import annotations

import cv2
import numpy as np

_LUMA = np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)

BLEND_MODES = (
    "shading",
    "pbr",
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
    """Composite ``top`` over ``base`` using a named mode."""
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
    if mode in ("shading", "pbr"):
        return t
    raise ValueError(f"unhandled blend mode {mode!r}")


def compute_shading_illumination(
    proxy_lum: np.ndarray,
    light_mask: np.ndarray,
    sigma: float,
    max_darken: float,
    max_lighten: float,
) -> tuple[np.ndarray, float]:
    """Low-pass Gaussian illumination field normalised to mean 1.0 inside the mask."""
    denominator = max(float(light_mask.sum()), 1e-6)
    fill_value = float((proxy_lum * light_mask).sum() / denominator)
    filled = proxy_lum * light_mask + fill_value * (1.0 - light_mask)
    illumination = cv2.GaussianBlur(filled, (0, 0), sigma)
    reference = max(float((illumination * light_mask).sum() / denominator), 1e-6)
    illumination = np.clip(illumination / reference, max_darken, max_lighten)
    return illumination.astype(np.float32), reference


def apply_shading(rgb: np.ndarray, illumination: np.ndarray, strength: float) -> np.ndarray:
    """Multiply RGB by a normalised illumination field."""
    field = _as_three_channel(illumination.astype(np.float32), rgb.shape)
    field = 1.0 + (field - 1.0) * float(strength)
    return rgb * field
