"""Method 2: Inverse SVBRDF + edge-preserving PBR relighting + 2.5D thin-shell flap arch."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from ..io import write_png
from .shading import bgr_to_rgb_float, luminance, rgb_float_to_bgr


def extract_svbrdf(texture_bgr: np.ndarray, out_dir: str | Path) -> dict[str, Path]:
    """Decompose a single close-up paper photo into seamless SVBRDF maps."""
    from ..proxy import tile_mirror
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    h0, w0 = texture_bgr.shape[:2]
    tiled = tile_mirror(texture_bgr, w0 * 2, h0 * 2)
    rgb = bgr_to_rgb_float(tiled)
    lum = luminance(rgb)

    albedo_rgb = cv2.GaussianBlur(rgb, (0, 0), 45.0)
    base_lum = cv2.GaussianBlur(lum, (0, 0), 18.0)
    micro_h = cv2.GaussianBlur(lum - base_lum, (1, 5), 0.0)

    gx = cv2.Sobel(micro_h, cv2.CV_32F, 1, 0, ksize=3) * 14.0
    gy = cv2.Sobel(micro_h, cv2.CV_32F, 0, 1, ksize=3) * 14.0
    nz = np.ones_like(gx)
    norm = np.sqrt(gx * gx + gy * gy + nz * nz)
    normal_rgb = np.stack([0.5 - 0.5 * gx / norm, 0.5 - 0.5 * gy / norm, 0.5 + 0.5 * nz / norm], axis=-1)

    roughness = np.clip(0.84 - 1.8 * micro_h, 0.72, 0.95)
    paths = {
        "albedo": write_png(out_dir / "albedo.png", rgb_float_to_bgr(albedo_rgb)),
        "normal": write_png(out_dir / "normal.png", rgb_float_to_bgr(normal_rgb)),
        "roughness": write_png(out_dir / "roughness.png", (roughness * 255.0).astype(np.uint8)),
    }
    return paths


def compute_pbr_illumination(
    proxy_lum: np.ndarray,
    light_mask: np.ndarray,
    max_darken: float,
    max_lighten: float,
) -> tuple[np.ndarray, float]:
    """Edge-preserving bilateral illumination field that retains sharp fold shadow steps."""
    inside_vals = proxy_lum[light_mask > 0.5]
    reference = max(float(np.median(inside_vals)) if inside_vals.size else float(proxy_lum.mean()), 1e-6)
    norm_lum = (proxy_lum / reference).astype(np.float32)
    illumination = cv2.bilateralFilter(norm_lum, d=9, sigmaColor=0.08, sigmaSpace=12.0)
    illumination = np.clip(illumination, min(max_darken, 0.30), max_lighten)
    return illumination.astype(np.float32), reference


def warp_shell_flap(warped_bgr: np.ndarray, mask: np.ndarray, illumination: np.ndarray) -> np.ndarray:
    """Apply centroid-free 2.5D thin-shell cylindrical arch across a folded upper flap."""
    inside = mask > 0.5
    if int(inside.sum()) < 4000:
        return warped_bgr

    ys, _ = np.nonzero(inside)
    y_min, y_max = float(ys.min()), float(ys.max())
    h_sheet = max(y_max - y_min, 1.0)
    h, w = warped_bgr.shape[:2]
    grid_y, grid_x = np.mgrid[0:h, 0:w].astype(np.float32)

    wy = np.clip((y_min + 0.52 * h_sheet - grid_y) / (0.12 * h_sheet), 0.0, 1.0)
    shadow_upper = float((np.clip((0.78 - illumination) / 0.12, 0.0, 1.0) * inside * (wy > 0.05)).sum())
    alpha_crease = float(np.clip((shadow_upper - 1200.0) / 4500.0, 0.0, 1.0))
    if alpha_crease <= 1e-3:
        return warped_bgr

    bright_flap = np.clip((illumination - 1.02) / 0.16, 0.0, 1.0) * wy
    w_arch = cv2.GaussianBlur(bright_flap.astype(np.float32), (0, 0), 14.0) * wy * alpha_crease
    map_x = (grid_x - 3.6 * w_arch).astype(np.float32)
    map_y = (grid_y - 2.4 * w_arch).astype(np.float32)
    return cv2.remap(warped_bgr, map_x, map_y, cv2.INTER_LANCZOS4, borderMode=cv2.BORDER_REFLECT_101)


def apply_pbr_shading(rgb: np.ndarray, illumination: np.ndarray, strength: float) -> np.ndarray:
    """Single-image SVBRDF decomposition + raking-light relief + translucent bloom."""
    if strength == 0.0:
        return rgb
    albedo = cv2.GaussianBlur(rgb.astype(np.float32), (0, 0), 6.0)
    relief = rgb.astype(np.float32) - albedo
    illum = 1.0 + (illumination.astype(np.float32) - 1.0) * float(strength)
    raking = np.clip((illum - 0.62) / 0.38, 0.12, 1.25)[..., None]
    scarlet = np.array([0.96, 0.12, 0.14], dtype=np.float32)
    sss = (np.clip((illum - 1.0) / 0.35, 0.0, 1.0) * (0.35 * float(strength)))[..., None]
    shaded = albedo * illum[..., None] + relief * raking
    return shaded * (1.0 - sss) + scarlet * sss
