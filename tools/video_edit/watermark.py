"""Remove a static, corner-anchored watermark from a video.

The Gemini sparkle is a translucent white mark composited into every frame at
the same pixel position.  Two consequences shape this module.

**Finding it.**  Because the mark never moves, its edges survive a *temporal
median* of each frame's local contrast: content moves and averages away, the
mark does not.  That yields a mask with no model of the logo and no detector to
train.  The interior of a large mark has no local contrast, so the median gives
a ring; the ring's external contour is filled to get the footprint.

**Removing it.**  The mark is a *translucent* white overlay -- the scene shows
through it -- so the honest model of a pixel is affine::

    observed  =  (1 - a) * scene  +  a * colour

with ``a`` (how opaque the mark is) and ``colour`` fixed per pixel for the whole
clip.  The default method, ``unmix``, measures that per-pixel model from the
clip and inverts it, which *recovers the scene that was underneath* -- its
shading, its grain, and any edge that crossed the mark -- instead of guessing
it.  Nothing is invented: the inverse is exact given ``a`` and ``colour``.

Measuring ``a`` is the whole problem, because the scene behind the mark is\nnever observed.  Two facts make it tractable.  First, the scene moves, so a\npixel's brightness over time is a *record* of the scene it hid.  Regressing that\nrecord against an estimate of the scene gives a slope of ``(1 - a)``.  The\nestimate has to come from *outside* the mark -- a blur of the frame cannot serve,\nbecause it is scaled by the mark exactly as the mark itself is, and the two\ncancel to a slope of one.  So the estimate is a membrane stitched across a hole\ndrawn *wider* than the mark, which leaves a ring of genuinely unmarked pixels\nbetween the mark and the observed boundary to regress against.  That membrane is\nsmoother than the real scene, which biases the slope high, so the same\nregression is run on the ring, where ``a = 0``, and the slope there is divided\nout.  The intercept comes from the *mean* relation instead: the temporal mean of\nthe clip is filled with ``harmonic`` below, whose mean is a better low-frequency\nscene estimate than any membrane, and that fixes the fill's tone.

Two guards keep it honest on clips where the model cannot be measured: if the
scene barely moves behind the mark (nothing to regress against) or the mark
turns out to be nearly opaque (no scene left to recover), the fill falls back
to ``harmonic``.

``harmonic`` alone remains available.  It is the right tool when the mark is
opaque -- there is nothing to unmix -- and it is the low-frequency estimate the
unmix leans on.  Inpainting alone (``telea``/``ns``) fills the hole from its own
boundary, which flattens any silhouette that crosses the mark and leaves a
straight, stuck-in-place notch where the mark hid an edge.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from .corners import QuadError
from .io import utc_now, write_json, write_png
from .video import VideoInfo, encode, iter_frames, probe_video

# Default search window as fractions of the frame: the bottom-right corner,
# which is where a corner-anchored mark lives.  Wide enough that the mark is
# inside it with margin on every side, whatever its offset from the corner.
DEFAULT_SEARCH = (0.45, 0.60, 0.55, 0.40)
METHODS = ("unmix", "harmonic", "telea", "ns", "temporal", "clone")
# A translucent mark is modelled as value = (1 - a) * scene + a * colour.  The
# slope estimate is biased by the smoothness of the regressor, so it is
# calibrated against a ring of unmarked pixels; ``est_grow`` widens the model's
# footprint past the detected core so the mark's soft rim is covered too.
DEFAULT_ALPHA_FLOOR = 0.30     # invert no harder than 1 / this; caps noise gain
DEFAULT_EST_GROW = 3           # px the model reaches past the detected core
DEFAULT_MIN_MOTION = 2.0       # levels of temporal std below which unmix gives up
DEFAULT_ALPHA_FALLBACK = 0.75  # 90th-pct opacity above which there is nothing to unmix


@dataclass
class WatermarkRegion:
    """Where the mark is, as a full-frame mask plus its bounding box."""

    mask: np.ndarray  # uint8, 255 inside the mark
    method: str
    score: float
    notes: list[str]
    residual: float = 0.0

    @property
    def box(self) -> tuple[int, int, int, int]:
        ys, xs = np.where(self.mask > 0)
        return int(xs.min()), int(ys.min()), int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1)

    @property
    def area(self) -> int:
        return int((self.mask > 0).sum())

    def as_dict(self) -> dict:
        x, y, w, h = self.box
        return {
            "box": {"x": x, "y": y, "width": w, "height": h},
            "area_px": self.area,
            "method": self.method,
            "score": round(float(self.score), 4),
            "static_residual_before": round(float(self.residual), 4),
            "notes": list(self.notes),
        }

    def crop_window(self, margin: int) -> tuple[int, int, int, int]:
        """The mask's box grown by ``margin`` and clipped to the mask's frame."""
        x, y, w, h = self.box
        height, width = self.mask.shape[:2]
        x0 = max(0, x - margin)
        y0 = max(0, y - margin)
        x1 = min(width, x + w + margin)
        y1 = min(height, y + h + margin)
        return x0, y0, x1, y1


@dataclass
class RemoveConfig:
    method: str = "unmix"
    iterations: int = 600
    level_iterations: int = 120
    levels: tuple[int, ...] = (8, 4, 2)
    inpaint_radius: int = 3
    # unmix only
    regressor_grow: int = 0        # 0 -> derive from the mark's size
    alpha_floor: float = DEFAULT_ALPHA_FLOOR
    est_grow: int = DEFAULT_EST_GROW
    min_motion: float = DEFAULT_MIN_MOTION
    alpha_fallback: float = DEFAULT_ALPHA_FALLBACK
    clone_offset: tuple[int, int] | None = None


@dataclass
class UnmixFit:
    """The measured affine model of a translucent mark, over a crop window.

    ``observed = multiplier * scene + offset`` with both fields 1 / 0 outside
    the modelled footprint, so applying the fit to the whole crop is safe.
    """

    multiplier: np.ndarray  # float32 (h, w, 3); (1 - a), 1 where untouched
    offset: np.ndarray      # float32 (h, w, 3); a * colour, 0 where untouched
    alpha: np.ndarray       # float32 (h, w, 3); how opaque the mark is
    motion: float           # median temporal std of the regressor under the mark
    opacity: float          # 90th-percentile opacity of the mark (uncapped)
    grow: int               # how far the regressor's hole reached past the mark
    window: tuple[int, int, int, int]
    notes: list[str]

    def as_dict(self) -> dict:
        return {
            "multiplier_range": [round(float(self.multiplier.min()), 4), round(float(self.multiplier.max()), 4)],
            "opacity_p90": round(float(self.opacity), 4),
            "opacity_max": round(float(self.alpha.max()), 4),
            "regressor_hole": int(self.grow),
            "scene_motion": round(float(self.motion), 3),
            "calibration": list(self.notes),
        }


def _resolve_search(search, width: int, height: int) -> tuple[int, int, int, int]:
    """Accept 'x,y,w,h' as fractions (all <= 1) or pixels; default bottom-right."""
    if search is None:
        search = DEFAULT_SEARCH
    if isinstance(search, str):
        try:
            values = [float(part) for part in search.replace(" ", "").split(",")]
        except ValueError as error:
            raise SystemExit("--search must look like 'x,y,w,h'") from error
        if len(values) != 4:
            raise SystemExit("--search needs four numbers: x,y,w,h")
        search = tuple(values)
    x, y, w, h = search
    if max(abs(v) for v in search) <= 1.0:
        x, y, w, h = x * width, y * height, w * width, h * height
    x0 = int(max(0, min(width - 2, round(x))))
    y0 = int(max(0, min(height - 2, round(y))))
    x1 = int(max(x0 + 2, min(width, round(x + w))))
    y1 = int(max(y0 + 2, min(height, round(y + h))))
    return x0, y0, x1 - x0, y1 - y0


def overlay_field(
    video: str | Path,
    search=None,
    *,
    sigma: float = 6.0,
    stride: int = 1,
    limit: int | None = None,
) -> tuple[np.ndarray, tuple[int, int, int, int], VideoInfo]:
    """Temporal median of local contrast inside the search window.

    A static mark keeps a positive response at the same pixel in every frame; a
    moving scene does not survive the median.
    """
    info = probe_video(video)
    x, y, w, h = _resolve_search(search, info.width, info.height)
    samples: list[np.ndarray] = []
    for index, frame in iter_frames(info.path, limit=limit):
        if stride > 1 and index % stride:
            continue
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(np.float32)
        samples.append((gray - cv2.GaussianBlur(gray, (0, 0), sigma))[y:y + h, x:x + w])
    if not samples:
        raise QuadError("no frames were read from the video")
    return np.median(np.stack(samples), axis=0), (x, y, w, h), info


def _mask_from_field(
    field: np.ndarray,
    window: tuple[int, int, int, int],
    shape: tuple[int, int],
    *,
    threshold: float,
    grow: int,
    min_area: int,
    max_area_ratio: float,
) -> tuple[np.ndarray, float]:
    smoothed = cv2.GaussianBlur(field, (0, 0), 1.5)
    peak = float(smoothed.max())
    if peak <= 0:
        raise QuadError("the search window shows no static local contrast")
    # Frame-to-frame compression noise is a few tenths of a level; a mark's edge
    # runs an order of magnitude above it. Scale the floor by the median
    # absolute deviation so a darker or noisier clip does not need a new number.
    noise = 1.4826 * float(np.median(np.abs(smoothed - np.median(smoothed))))
    floor = max(2.0, 3.0 * noise)
    ring = (smoothed >= threshold * peak).astype(np.uint8) * 255
    ring = cv2.morphologyEx(ring, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    contours, _ = cv2.findContours(ring, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    height, width = shape
    max_area = max_area_ratio * height * width
    best: tuple[float, np.ndarray, np.ndarray] | None = None
    for contour in contours:
        filled = np.zeros_like(ring)
        cv2.drawContours(filled, [contour], -1, 255, cv2.FILLED)
        area = int((filled > 0).sum())
        if area < min_area or area > max_area:
            continue
        strength = float(smoothed[filled > 0].mean())
        # A closed ring around the mark averages far higher than a thin, broken
        # content edge, which the same field also contains.
        if best is None or strength > best[0]:
            best = (strength, filled, contour)
    if best is None:
        raise QuadError(
            "no watermark-shaped region found in the search window; pass --box or widen --search"
        )
    strength, core, _ = best
    if strength < floor:
        raise QuadError(
            f"the strongest candidate measures {strength:.2f}, at the noise floor "
            f"({floor:.2f}); no static watermark here. Widen --search or pass --box."
        )
    residual = float(smoothed[core > 0].max())
    if grow > 0:
        core = cv2.dilate(core, np.ones((3, 3), np.uint8), iterations=grow)
    x, y, _, _ = window
    mask = np.zeros(shape, np.uint8)
    mask[y:y + core.shape[0], x:x + core.shape[1]] = core
    return mask, strength, residual


def detect_watermark(
    video: str | Path,
    search=None,
    *,
    threshold: float = 0.15,
    grow: int = 2,
    sigma: float = 6.0,
    stride: int = 1,
    min_area: int = 40,
    max_area_ratio: float = 0.03,
    limit: int | None = None,
) -> WatermarkRegion:
    """Locate a static watermark from the video itself."""
    field, window, info = overlay_field(video, search, sigma=sigma, stride=stride, limit=limit)
    mask, strength, residual = _mask_from_field(
        field,
        window,
        (info.height, info.width),
        threshold=threshold,
        grow=grow,
        min_area=min_area,
        max_area_ratio=max_area_ratio,
    )
    region = WatermarkRegion(
        mask=mask,
        method="temporal-median-local-contrast",
        score=strength,
        notes=[
            f"search window x,y,w,h={window}",
            f"threshold={threshold} of peak, grow={grow}px",
        ],
    )
    region.residual = residual
    return region


def region_from_box(box, shape: tuple[int, int], grow: int = 0) -> WatermarkRegion:
    """A rectangular region given as 'x,y,w,h' in pixels."""
    if isinstance(box, str):
        try:
            values = [int(round(float(part))) for part in box.replace(" ", "").split(",")]
        except ValueError as error:
            raise SystemExit("--box must look like 'x,y,w,h'") from error
    else:
        values = [int(round(v)) for v in box]
    if len(values) != 4:
        raise SystemExit("--box needs four numbers: x,y,w,h")
    x, y, w, h = values
    height, width = shape
    mask = np.zeros(shape, np.uint8)
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(width, x + w), min(height, y + h)
    mask[y0:y1, x0:x1] = 255
    if grow > 0:
        mask = cv2.dilate(mask, np.ones((3, 3), np.uint8), iterations=grow)
    return WatermarkRegion(mask=mask, method="manual-box", score=1.0, notes=[f"box={x,y,w,h}"])


def region_from_mask_file(path: str | Path) -> WatermarkRegion:
    image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise SystemExit(f"could not read the mask image: {path}")
    return WatermarkRegion(
        mask=(image > 0).astype(np.uint8) * 255,
        method="mask-file",
        score=1.0,
        notes=[str(path)],
    )


def _pool(values: np.ndarray, factor: int) -> np.ndarray:
    height, width = values.shape[:2]
    h2, w2 = height // factor * factor, width // factor * factor
    trimmed = values[:h2, :w2]
    if trimmed.ndim == 2:
        return trimmed.reshape(h2 // factor, factor, w2 // factor, factor).mean(axis=(1, 3))
    return trimmed.reshape(h2 // factor, factor, w2 // factor, factor, trimmed.shape[2]).mean(axis=(1, 3))


def _relax(values: np.ndarray, mask3: np.ndarray, iterations: int) -> np.ndarray:
    for _ in range(iterations):
        neighbours = (
            np.roll(values, 1, 0) + np.roll(values, -1, 0)
            + np.roll(values, 1, 1) + np.roll(values, -1, 1)
        ) * 0.25
        values = values * (1.0 - mask3) + neighbours * mask3
    return values


def harmonic_fill(crop: np.ndarray, mask: np.ndarray, config: RemoveConfig) -> np.ndarray:
    """Keep the hole's boundary, relax its interior to the membrane spanning it."""
    mask3 = mask[..., None].astype(np.float32)
    seed = cv2.inpaint(
        np.clip(crop, 0, 255).astype(np.uint8), (mask * 255).astype(np.uint8),
        config.inpaint_radius, cv2.INPAINT_TELEA,
    )
    values = crop.astype(np.float32) * (1.0 - mask3) + seed.astype(np.float32) * mask3
    for factor in config.levels:
        if values.shape[0] % factor or values.shape[1] % factor:
            continue
        coarse = _pool(values, factor)
        coarse_mask = (_pool(mask.astype(np.float32), factor) > 0.4)[..., None].astype(np.float32)
        coarse = _relax(coarse, coarse_mask, config.level_iterations)
        lifted = cv2.resize(coarse, (values.shape[1], values.shape[0]), interpolation=cv2.INTER_LINEAR)
        values = values * (1.0 - mask3) + lifted * mask3
    values = _relax(values, mask3, config.iterations)
    return np.clip(values, 0, 255).astype(np.uint8)


def _model_margin(config: RemoveConfig, region: WatermarkRegion) -> int:
    """Crop margin wide enough for the regressor's hole, the ring and the fill."""
    size = max(region.box[2], region.box[3])
    if config.method != "unmix":
        return max(config.levels) + 4 if config.method in ("harmonic", "temporal") else 2
    return int(_regressor_grow(config, region) + max(config.levels) + 6)


def _regressor_grow(config: RemoveConfig, region: WatermarkRegion) -> int:
    """How far past the mark the regressor's hole reaches.

    The regressor must not be built from the pixels it is meant to explain --
    a blur of the frame scales with the mark exactly as the mark does, so the
    attenuation cancels and the opacity reads as zero.  Widening the filled
    hole puts a ring of genuinely unmarked pixels between the mark and the
    boundary the membrane is stitched from, and that ring both feeds a real
    estimate and calibrates the membrane's own bias.
    """
    if config.regressor_grow > 0:
        return int(config.regressor_grow)
    return max(4, int(round(0.22 * max(region.box[2], region.box[3]))))


def _ring(mask: np.ndarray, config: RemoveConfig, region: WatermarkRegion) -> np.ndarray:
    """A band of unmarked pixels inside the regressor's hole, for calibration."""
    grow = _regressor_grow(config, region)
    inner = max(2, grow // 3)
    outer = max(inner + 2, (2 * grow) // 3)
    kernel = np.ones((3, 3), np.uint8)
    near = cv2.dilate(mask.astype(np.uint8), kernel, iterations=inner) > 0
    far = cv2.dilate(mask.astype(np.uint8), kernel, iterations=outer) > 0
    return far & ~near


def fit_unmix(
    video: str | Path,
    region: WatermarkRegion,
    config: RemoveConfig | None = None,
    *,
    start: int = 0,
    limit: int | None = None,
) -> UnmixFit:
    """Measure the per-pixel affine model of a translucent mark from the clip.

    The scene moves, so a pixel under the mark holds a record of the scene it
    hid.  Regressing that record on an *independent* estimate of the scene -- a
    membrane stitched across a hole wider than the mark -- gives a slope of
    ``1 - a`` times the membrane's own bias; the same regression run on the ring
    of unmarked pixels between the mark and that hole measures the bias, which
    is divided out.  The intercept comes from the mean frame, whose low
    frequencies ``harmonic_fill`` estimates better than the membrane's bias
    would allow.
    """
    config = config or RemoveConfig()
    info = probe_video(video)
    x0, y0, x1, y1 = region.crop_window(_model_margin(config, region))
    mask = region.mask[y0:y1, x0:x1] > 0
    if not mask.any():
        raise QuadError("the watermark region is empty")
    kernel = np.ones((3, 3), np.uint8)
    hole = cv2.dilate(mask.astype(np.uint8), kernel,
                      iterations=_regressor_grow(config, region)) > 0

    count = 0
    total = np.zeros((y1 - y0, x1 - x0, 3), np.float64)
    total_g = np.zeros_like(total)
    total_gg = np.zeros_like(total)
    total_fg = np.zeros_like(total)
    for _, frame in iter_frames(info.path, start=start, limit=limit):
        crop = frame[y0:y1, x0:x1]
        regressor = harmonic_fill(crop, hole, config).astype(np.float32)
        cropf = crop.astype(np.float32)
        count += 1
        total += cropf
        total_g += regressor
        total_fg += cropf * regressor
        total_gg += regressor * regressor
    if count < 2:
        raise QuadError("need at least two frames to measure the mark")

    mean = total / count
    mean_g = total_g / count
    cov = total_fg / count - mean * mean_g
    var = total_gg / count - mean_g * mean_g
    slope = cov / np.maximum(var, 1e-6)

    ring = _ring(mask, config, region)
    weight = ring.astype(np.float32)[..., None]
    radius = max(3.0, 0.1 * max(region.box[2], region.box[3]))
    density = cv2.GaussianBlur(weight, (0, 0), radius)
    ratio = np.clip(
        cv2.GaussianBlur(slope.astype(np.float32) * weight, (0, 0), radius)
        / np.maximum(density, 1e-6)[..., None],
        0.3, 3.0,
    )
    raw = slope / ratio
    multiplier = np.clip(raw, config.alpha_floor, 1.0).astype(np.float32)
    alpha = 1.0 - multiplier
    # How opaque the mark *is*, before the floor caps how hard it may be
    # inverted -- the guard against an opaque mark has to see through the cap.
    opacity = float(np.percentile(np.clip(1.0 - raw[mask], 0.0, 1.0), 90))

    # The fill's tone: the harmonic membrane of the mean frame is a better
    # low-frequency scene estimate than the regressor's own membrane.
    base = harmonic_fill(np.clip(mean, 0, 255).astype(np.uint8), mask, config).astype(np.float32)
    offset = mean.astype(np.float32) - multiplier * base

    est = mask
    if config.est_grow > 0:
        est = cv2.dilate(mask.astype(np.uint8), kernel, iterations=config.est_grow) > 0
    ramp = np.clip(cv2.GaussianBlur(est.astype(np.float32), (0, 0), 1.5), 0, 1)[..., None]
    multiplier = (1.0 - ramp * (1.0 - multiplier)).astype(np.float32)
    offset = (ramp * offset).astype(np.float32)

    motion = float(np.median(np.sqrt(np.maximum(var, 0.0))[est]))
    return UnmixFit(
        multiplier=multiplier,
        offset=offset,
        alpha=alpha,
        motion=motion,
        opacity=opacity,
        grow=_regressor_grow(config, region),
        window=(x0, y0, x1, y1),
        notes=[f"regressor hole +{_regressor_grow(config, region)}px, ring {int(ring.sum())} px"],
    )


def clean_frame(
    frame: np.ndarray,
    region: WatermarkRegion,
    config: RemoveConfig,
    fit: UnmixFit | None = None,
) -> np.ndarray:
    if config.method == "clone":
        from .clone import clone_frame

        return clone_frame(frame, region.mask, config.clone_offset)[0]
    margin = _model_margin(config, region)
    x0, y0, x1, y1 = region.crop_window(margin)
    crop = frame[y0:y1, x0:x1]
    mask = region.mask[y0:y1, x0:x1] > 0
    if not mask.any():
        return frame
    if fit is not None:
        if fit.window != (x0, y0, x1, y1):
            raise QuadError("the unmix model was measured over a different window")
        # observed = multiplier * scene + offset, so scene = (observed - offset) / multiplier
        filled = np.clip((crop.astype(np.float32) - fit.offset) / fit.multiplier, 0, 255).astype(np.uint8)
    elif config.method in ("harmonic", "unmix", "temporal"):
        # ``unmix`` without a measured model is the documented fallback to the
        # membrane, which needs no model at all.
        filled = harmonic_fill(crop, mask, config)
    else:
        flags = cv2.INPAINT_TELEA if config.method == "telea" else cv2.INPAINT_NS
        filled = cv2.inpaint(crop, (mask * 255).astype(np.uint8), config.inpaint_radius, flags)
    out = frame.copy()
    out[y0:y1, x0:x1] = filled
    return out


def clean_video(
    video: str | Path,
    region: WatermarkRegion,
    out_dir: str | Path,
    *,
    config: RemoveConfig | None = None,
    frames_dir: str | Path | None = None,
    start: int = 0,
    limit: int | None = None,
) -> tuple[list[int], float, UnmixFit | None, str | None]:
    """Run the fill on every frame, write PNGs, and report what is left.

    Returns the frame indices written, the static residual left under the mark,
    the unmix model if one was measured, and the reason it was refused.
    """
    config = config or RemoveConfig()
    frames_dir = Path(frames_dir) if frames_dir else Path(out_dir) / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    fit: UnmixFit | None = None
    refused: str | None = None
    if config.method == "unmix":
        fit = fit_unmix(video, region, config, start=start, limit=limit)
        # Two ways the model can be meaningless, both of which the harmonic
        # membrane handles: nothing moved behind the mark to measure against,
        # or the mark is opaque so there is no scene left to recover.
        if fit.motion < config.min_motion:
            refused = (
                f"the scene barely moves behind the mark (scene_motion {fit.motion:.2f} < "
                f"{config.min_motion}); fell back to harmonic"
            )
            fit = None
        elif fit.opacity > config.alpha_fallback:
            refused = (
                f"the mark is nearly opaque (90th-pct opacity {fit.opacity:.2f} > "
                f"{config.alpha_fallback}); fell back to harmonic"
            )
            fit = None

    masked = region.mask > 0
    ys, xs = np.where(masked)
    residuals: list[np.ndarray] = []
    written: list[int] = []
    temporal_frames = []
    if config.method == "temporal":
        from .temporal import borrow_frame

        window = region.crop_window(96)
        x0, y0, x1, y1 = window
        local_mask = masked[y0:y1, x0:x1]
        temporal_frames = [frame[y0:y1, x0:x1].copy()
                           for _, frame in iter_frames(video, start=start, limit=limit)]
        guide_mask = cv2.dilate(local_mask.astype(np.uint8), np.ones((7, 7), np.uint8)) > 0
        guides = [cv2.cvtColor(harmonic_fill(crop, guide_mask, config), cv2.COLOR_BGR2GRAY)
                  for crop in temporal_frames]
        coverage = []
    previous_clone = None
    for index, frame in iter_frames(video, start=start, limit=limit):
        if config.method == "temporal":
            crop = temporal_frames[len(written)]
            fallback = harmonic_fill(crop, local_mask, config)
            filled, fraction = borrow_frame(len(written), temporal_frames, guides, local_mask, fallback)
            coverage.append(fraction)
            cleaned = frame.copy()
            cleaned[y0:y1, x0:x1] = filled
        elif config.method == "clone":
            from .clone import clone_frame

            cleaned, previous_clone = clone_frame(frame, region.mask, config.clone_offset, previous_clone)
        else:
            cleaned = clean_frame(frame, region, config, fit)
        write_png(frames_dir / f"{index:05d}.png", cleaned)
        written.append(index)
        gray = cv2.cvtColor(cleaned, cv2.COLOR_BGR2GRAY).astype(np.float32)
        hp = gray - cv2.GaussianBlur(gray, (0, 0), 6.0)
        residuals.append(hp[ys, xs])
    if not residuals:
        raise QuadError("no frames were written")
    stack = np.stack(residuals)
    # The mark is static, so any of it left over is still static: the median
    # over time isolates that from the frame that just moved.
    residual = float(np.median(stack, axis=0).max()) if len(stack) > 2 else float(stack.max())
    if config.method == "temporal":
        print(f"temporal    clean donor coverage {np.mean(coverage):.1%} (rest harmonic)")
    return written, residual, fit, refused


def render_watermark(
    video: str | Path,
    out_dir: str | Path,
    *,
    region: WatermarkRegion | None = None,
    search=None,
    threshold: float = 0.15,
    grow: int = 2,
    config: RemoveConfig | None = None,
    start: int = 0,
    limit: int | None = None,
    crf: int = 14,
    preset: str = "slow",
    skip_encode: bool = False,
) -> dict:
    """Detect (or accept) a watermark region, remove it, encode, and report."""
    config = config or RemoveConfig()
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    info = probe_video(video)

    if region is None:
        region = detect_watermark(video, search, threshold=threshold, grow=grow, limit=limit)

    write_png(out_dir / "mask.png", region.mask)
    preview = None
    for _, first in iter_frames(info.path, start=start, limit=1):
        preview = first.copy()
    if preview is not None:
        contours, _ = cv2.findContours(region.mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        cv2.drawContours(preview, contours, -1, (0, 255, 0), 1)
        x, y, w, h = region.box
        cv2.rectangle(preview, (x - 8, y - 8), (x + w + 8, y + h + 8), (0, 128, 255), 1)
        write_png(out_dir / "preview.png", preview)

    frames_dir = out_dir / "frames"
    written, residual_after, fit, refused = clean_video(
        video, region, out_dir, config=config, frames_dir=frames_dir, start=start, limit=limit
    )

    out_path = out_dir / "result.mp4"
    encoded = None
    if not skip_encode:
        encoded = encode(frames_dir, info.path, out_path, info.fps, crf=crf, preset=preset)

    if config.method == "clone":
        what = (
            "Nearby same-surface texture covers the watermark using the shared lighting-carry "
            "overlay blend. Explicit clone offsets use legacy rectangular patch copying."
        )
        limits = [
            "Copied surrounding pixels are not the original scene behind the watermark.",
            "Automatic coverage assumes neutral and chromatic materials, such as paper and skin; "
            "similar-coloured materials or opaque marks may not separate correctly.",
            "Small texture tiles are repeated; fine texture and shading are approximate.",
            "Automatic replacement extends six pixels past the mask with inward feathering; "
            "explicit offsets retain the rectangular patch and can misalign edges.",
        ]
    elif config.method == "temporal":
        what = "Motion-aligned unmarked donor pixels replace the watermark, with harmonic fallback."
        limits = [
            "One continuous shot is required; split at cuts first.",
            "Flow can misalign skin, occlusions or deforming surfaces; inspect moving edges.",
            "Pixels never exposed outside the watermark use a spatial harmonic fill.",
            "Only a local crop is buffered, but memory still grows with clip length.",
        ]
    elif fit is not None:
        what = (
            "A translucent static watermark was located from the video's own frames and its "
            "per-pixel opacity was measured, then inverted. The scene under the mark -- its "
            "shading and grain -- comes back from the frame itself; no pixels are invented."
        )
        limits = [
            "The inverse is exact only where the mark is translucent; a mark that is opaque "
            "anywhere in its core leaves that part of the scene unrecoverable.",
            "The opacity is measured from how the scene moves behind the mark, so a clip with "
            "very little movement there falls back to the harmonic fill.",
            "Inverting the mark also lifts the encoder's own grain by 1/(1-a) under the mark, "
            "so the mark's footprint carries slightly more noise than its surroundings.",
            "Detection assumes the mark is static and lies inside the search window.",
        ]
    else:
        what = (
            "A static watermark was located from the video's own frames and lifted out of every "
            "frame. No generative step ran: the fill comes from the frame boundary."
        )
        limits = [
            "The fill is a relaxation of the mark's own boundary, so a hard edge that passes "
            "behind the mark is continued smoothly, not reconstructed exactly.",
            "Detection assumes the mark is static and lies inside the search window.",
            "The output is re-encoded H.264, so fine grain is partly smoothed.",
        ]

    manifest = {
        "schema_version": 1,
        "generated_on": utc_now(),
        "what_this_is": what,
        "video": info.as_dict(),
        "region": region.as_dict(),
        "config": {
            "method": config.method,
            "clone_offset": config.clone_offset,
            "iterations": config.iterations,
            "level_iterations": config.level_iterations,
            "levels": list(config.levels),
            "inpaint_radius": config.inpaint_radius,
            "alpha_floor": config.alpha_floor,
            "est_grow": config.est_grow,
            "min_motion": config.min_motion,
            "alpha_fallback": config.alpha_fallback,
        },
        "mark_model": None if fit is None else fit.as_dict(),
        "fell_back": refused,
        "frames_cleaned": len(written),
        "static_residual_after": round(residual_after, 4),
        "outputs": {
            "video": None if encoded is None else str(encoded),
            "frames_dir": str(frames_dir),
            "mask": str(out_dir / "mask.png"),
            "preview": str(out_dir / "preview.png"),
        },
        "limits": limits,
    }
    write_json(out_dir / "manifest.json", manifest)
    print(f"region      x,y,w,h={region.box}  ({region.area} px, {region.method})")
    if fit is not None:
        print(
            f"mark model  opacity p90 {fit.opacity:.3f} max {fit.alpha.max():.3f}  "
            f"regressor hole +{fit.grow}px  scene motion {fit.motion:.2f}"
        )
    elif refused:
        print(f"mark model  {refused}")
    print(f"static residual {region.residual:.3f} -> {residual_after:.3f} (local contrast units)")
    print(f"frames      {len(written)} written to {frames_dir}")
    print(f"output      {encoded if encoded else '(encoding skipped)'}")
    return manifest
