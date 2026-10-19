"""Deterministic perspective texture-swap for physical products.

Instead of asking a generative model to redraw a product's surface, a smooth
proxy frame supplies geometry, hands and lighting, and real camera pixels are
pasted onto the detected card surface with a perspective transform and a
lighting-carry blend.

This package implements only that one architecture. It uses OpenCV + NumPy and
has no generative step.

Public entry points:

    detect_quad      find the card's four corners in a proxy frame
    compose          warp + blend the real texture onto the proxy
    smooth_proxy     edge-preserving smoothing (deterministic proxy stand-in)
    synthetic_card_proxy  a labelled test fixture, not a product image
"""

from .blend import BLEND_MODES, bgr_to_rgb_float, blend, luminance, rgb_float_to_bgr
from .compose import ComposeConfig, ComposeResult, compose
from .corners import QuadDetection, QuadError, detect_quad, order_corners, parse_corners
from .proxy import smooth_proxy, synthetic_card_proxy, tile_mirror

__all__ = [
    "BLEND_MODES",
    "ComposeConfig",
    "ComposeResult",
    "QuadDetection",
    "QuadError",
    "bgr_to_rgb_float",
    "blend",
    "compose",
    "detect_quad",
    "luminance",
    "order_corners",
    "parse_corners",
    "rgb_float_to_bgr",
    "smooth_proxy",
    "synthetic_card_proxy",
    "tile_mirror",
]

__version__ = "0.1.0"
