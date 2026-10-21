"""Perspective-warp real texture pixels onto a proxy frame's detected surface."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

import cv2
import numpy as np

from .corners import order_corners
from .methods import (
    apply_pbr_shading,
    apply_shading,
    bgr_to_rgb_float,
    blend,
    compute_pbr_illumination,
    compute_shading_illumination,
    luminance,
    rgb_float_to_bgr,
    warp_shell_flap,
)
from .proxy import flatten_texture, rotate_texture, tile_mirror


@dataclass
class ComposeConfig:
    """Knobs for one texture swap. Defaults aim at the "keep real pixels" case."""

    blend_mode: str = "shading"
    shading_strength: float = 1.0
    lighting_sigma: float = 0.0  # 0 derives a sigma from the card size
    max_darken: float = 0.7
    max_lighten: float = 1.35
    edge_feather: float = 1.5
    inset: float = 0.0
    texture_scale: float = 1.0
    grain_angle: float = 0.0
    texture_flatten: float = 0.0  # sigma in pixels; 0 disables
    texture_gain: float = 1.0
    tile: bool = True
    # Resampling used by the perspective warp. Grain fidelity differs a lot:
    # on a typical card, bilinear keeps ~45% of the source's high-frequency
    # energy and Lanczos keeps ~96%, so Lanczos is the default.
    interpolation: str = "lanczos4"


_INTERPOLATION = {
    "nearest": cv2.INTER_NEAREST,
    "linear": cv2.INTER_LINEAR,
    "cubic": cv2.INTER_CUBIC,
    "lanczos4": cv2.INTER_LANCZOS4,
}
INTERPOLATIONS = tuple(_INTERPOLATION)


@dataclass
class ComposeResult:
    """The composited frame plus the intermediate fields, for inspection."""

    image: np.ndarray  # uint8 BGR, same size as the proxy
    mask: np.ndarray  # float32 0..1 coverage of the warped texture
    warped: np.ndarray  # uint8 BGR, the raw warped texture before blending
    tiled: np.ndarray  # uint8 BGR, the tiled source texture
    illumination: np.ndarray  # float32 HxW, normalised proxy lighting field
    corners: np.ndarray  # float32 (4, 2), ordered
    stats: dict = field(default_factory=dict)


def _prepare_texture(texture_bgr: np.ndarray, cfg: ComposeConfig) -> np.ndarray:
    tex = texture_bgr
    if cfg.grain_angle:
        tex = rotate_texture(tex, cfg.grain_angle)
    if cfg.texture_scale != 1.0:
        height = max(1, int(round(tex.shape[0] * cfg.texture_scale)))
        width = max(1, int(round(tex.shape[1] * cfg.texture_scale)))
        tex = cv2.resize(tex, (width, height), interpolation=cv2.INTER_AREA if cfg.texture_scale < 1 else cv2.INTER_LANCZOS4)
    if cfg.texture_flatten > 0:
        tex = flatten_texture(tex, cfg.texture_flatten)
    if cfg.texture_gain != 1.0:
        tex = np.clip(tex.astype(np.float32) * cfg.texture_gain, 0, 255).astype(np.uint8)
    return tex


def _shrink_mask(mask: np.ndarray, inset: float) -> np.ndarray:
    if inset <= 0:
        return mask
    size = int(round(inset)) * 2 + 1
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (size, size))
    return cv2.erode(mask, kernel, iterations=1)


def compose(
    proxy_bgr: np.ndarray,
    texture_bgr: np.ndarray,
    corners: np.ndarray,
    config: ComposeConfig | None = None,
    coverage_mask: np.ndarray | None = None,
    *,
    surface_mask: bool = False,
    texture_size: tuple[int, int] | None = None,
) -> ComposeResult:
    """Warp ``texture_bgr`` onto ``corners`` of ``proxy_bgr`` and blend.

    The mask covers the quad only, so hands, background and every pixel outside
    the product surface come from the proxy untouched. Inside the quad, the
    proxy supplies lighting and the texture supplies material.

    ``coverage_mask`` optionally narrows that coverage for a frame (an HxW array,
    0..1 float or 0..255 uint8). Pass a colour-derived mask to keep objects that
    overlap the surface — fingers holding a sheet, for example — on top of the
    texture instead of being painted over.

    With ``surface_mask=True``, that mask defines the complete visible surface,
    not an intersection with the fitted quad. Texture is extrapolated beyond
    the quad so an imperfect fit cannot expose a second, smooth paper layer.
    ``texture_size`` fixes the source-plane canvas across video frames, so
    resizing the quad does not rebuild the tiled texture at a different phase.
    """
    if proxy_bgr is None or texture_bgr is None:
        raise ValueError("proxy and texture must both be loaded")
    cfg = config or ComposeConfig()
    if surface_mask and coverage_mask is None:
        raise ValueError("surface_mask requires a coverage_mask")
    frame_h, frame_w = proxy_bgr.shape[:2]
    quad = order_corners(corners)

    texture = _prepare_texture(texture_bgr, cfg)

    # Size the texture patch to the surface's own in-plane edges rather than to
    # its axis-aligned bounding box. A rotated or clipped quad would otherwise
    # stretch the texture anisotropically, changing apparent grain density from
    # frame to frame.
    tl, tr, br, bl = quad
    edge_u = 0.5 * (float(np.linalg.norm(tr - tl)) + float(np.linalg.norm(br - bl)))
    edge_v = 0.5 * (float(np.linalg.norm(bl - tl)) + float(np.linalg.norm(br - tr)))
    box_w = max(2, int(round(edge_u)))
    box_h = max(2, int(round(edge_v)))
    if texture_size is not None:
        box_w, box_h = texture_size
        if box_w < 2 or box_h < 2:
            raise ValueError("texture_size dimensions must be at least 2")

    if cfg.tile:
        tiled = tile_mirror(texture, box_w, box_h)
    else:
        tiled = cv2.resize(texture, (box_w, box_h), interpolation=cv2.INTER_LANCZOS4)

    src = np.array([[0, 0], [box_w, 0], [box_w, box_h], [0, box_h]], dtype=np.float32)
    matrix = cv2.getPerspectiveTransform(src, quad)

    if cfg.interpolation not in _INTERPOLATION:
        raise ValueError(
            f"unknown interpolation {cfg.interpolation!r}; expected one of {', '.join(INTERPOLATIONS)}"
        )
    interp = _INTERPOLATION[cfg.interpolation]

    warped = cv2.warpPerspective(
        tiled, matrix, (frame_w, frame_h), flags=interp,
        borderMode=cv2.BORDER_REFLECT_101 if surface_mask else cv2.BORDER_CONSTANT,
    )
    coverage = cv2.warpPerspective(
        np.ones((box_h, box_w), np.float32), matrix, (frame_w, frame_h), flags=interp
    )
    if coverage_mask is not None:
        extra = np.asarray(coverage_mask, dtype=np.float32)
        if extra.max() > 1.0:
            extra = extra / 255.0
        if extra.shape[:2] != (frame_h, frame_w):
            raise ValueError(
                f"coverage_mask is {extra.shape[:2]}, expected {(frame_h, frame_w)}"
            )
        extra = np.clip(extra, 0.0, 1.0)
        coverage = extra if surface_mask else coverage * extra
    coverage = _shrink_mask(coverage, cfg.inset)
    if cfg.edge_feather > 0:
        if surface_mask:
            # Feather inward only. Gaussian blur spreads replacement pixels
            # onto fingers, hair and background outside the measured surface.
            distance = cv2.distanceTransform((coverage > 0).astype(np.uint8), cv2.DIST_L2, 5)
            coverage = coverage * np.clip(distance / (3.0 * cfg.edge_feather), 0.0, 1.0)
        else:
            coverage = cv2.GaussianBlur(coverage, (0, 0), cfg.edge_feather)
    mask = np.clip(coverage, 0.0, 1.0).astype(np.float32)

    # Lighting: take luminance from the proxy, but fill everything outside the
    # card with the mean inside-card luminance first. The mask used for the
    # lighting field is eroded, so anti-aliased edge pixels (which mix card and
    # background) cannot bleed a bright or dark rim into the card.
    proxy_rgb = bgr_to_rgb_float(proxy_bgr)
    proxy_lum = luminance(proxy_rgb)
    light_mask = _shrink_mask(mask, max(2.0, cfg.edge_feather))
    if float(light_mask.sum()) < 1.0:
        light_mask = mask
    sigma = cfg.lighting_sigma if cfg.lighting_sigma > 0 else max(6.0, 0.06 * min(box_w, box_h))
    if cfg.blend_mode == "pbr":
        illumination, reference = compute_pbr_illumination(proxy_lum, light_mask, cfg.max_darken, cfg.max_lighten)
    else:
        illumination, reference = compute_shading_illumination(
            proxy_lum, light_mask, sigma, cfg.max_darken, cfg.max_lighten
        )

    if cfg.blend_mode == "pbr":
        warped = warp_shell_flap(warped, mask, illumination)
    warped_rgb = bgr_to_rgb_float(warped)
    if cfg.blend_mode == "shading":
        blended = apply_shading(warped_rgb, illumination, cfg.shading_strength)
    elif cfg.blend_mode == "pbr":
        blended = apply_pbr_shading(warped_rgb, illumination, cfg.shading_strength)
    else:
        blended = blend(proxy_rgb, warped_rgb, cfg.blend_mode)
        blended = np.clip(blended, 0.0, 1.0)

    mask3 = mask[..., None]
    out_rgb = proxy_rgb * (1.0 - mask3) + np.clip(blended, 0.0, 1.0) * mask3

    inside = mask > 0.5
    illumination_inside = illumination[inside] if inside.any() else np.array([1.0], np.float32)
    stats = {
        "frame_size": [frame_w, frame_h],
        "sheet_size": [box_w, box_h],
        "sheet_bbox": [
            int(np.floor(quad[:, 0].min())),
            int(np.floor(quad[:, 1].min())),
            int(np.ceil(quad[:, 0].max())),
            int(np.ceil(quad[:, 1].max())),
        ],
        "tiles": [
            int(np.ceil(box_w / texture.shape[1])),
            int(np.ceil(box_h / texture.shape[0])),
        ],
        "mask_coverage": round(float(mask.mean()), 4),
        "illumination_sigma": round(float(sigma), 2),
        "illumination_min": round(float(illumination_inside.min()), 4),
        "illumination_max": round(float(illumination_inside.max()), 4),
        "reference_luminance": round(reference, 4),
        "blend_mode": cfg.blend_mode,
        "coverage_narrowed": coverage_mask is not None,
    }

    return ComposeResult(
        image=rgb_float_to_bgr(out_rgb),
        mask=mask,
        warped=warped,
        tiled=tiled,
        illumination=illumination.astype(np.float32),
        corners=quad,
        stats=stats,
    )


def config_to_dict(config: ComposeConfig) -> dict:
    """Serialise a config for the run manifest."""
    return asdict(config)
