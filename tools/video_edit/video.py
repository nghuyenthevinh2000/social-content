"""Apply the perspective texture swap to every frame of a video.

Two things make video harder than a still, and both are handled here:

* **Clipping.** A held sheet commonly runs off the frame edge, so the detected
  quad has corners sitting on the border. Stretching the texture to that clipped
  quad would change the apparent grain density whenever the clip changed. The
  sheet is rigid, so its in-plane aspect ratio is measured once from the frames
  where it is fully visible, and each frame's quad is rebuilt from the reliable
   edge plus that ratio. The trajectories are then temporally fitted, with one
   fixed texture coordinate canvas for the shot to avoid grain phase jitter.
* **Occlusion.** A material-colour mask independently defines the silhouette,
  so an imperfect quad does not expose smooth strips or paint over fingers.

Frames are written as PNGs and encoded with ffmpeg, which keeps the source
audio and avoids OpenCV's lossy video writer.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from .compose import ComposeConfig, compose
from .corners import QuadError, colour_mask, detect_quad, order_corners, refine_sheet_quad
from .io import write_png

BORDER_TOLERANCE = 2.0


@dataclass
class VideoInfo:
    path: Path
    width: int
    height: int
    fps: float
    frame_count: int
    has_audio: bool = False

    def as_dict(self) -> dict:
        return {
            "path": str(self.path),
            "width": self.width,
            "height": self.height,
            "fps": round(self.fps, 4),
            "frame_count": self.frame_count,
            "has_audio": self.has_audio,
        }


@dataclass
class FramePlan:
    """What to do with one frame: which quad, which occlusion mask, and why."""

    index: int
    quad: np.ndarray
    detection: str
    score: float
    clipped: bool
    reconstructed: bool


@dataclass
class PlanSet:
    """The result of pass 1: a plan per frame plus how the shot behaved."""

    plans: list[FramePlan]
    aspect: float | None
    detection_counts: dict[str, int]
    clipped_frames: int
    reconstructed_frames: int
    motion_window: int = 1

    def as_dict(self) -> dict:
        return {
            "frames_planned": len(self.plans),
            "sheet_aspect": None if self.aspect is None else round(self.aspect, 4),
            "detection_counts": self.detection_counts,
            "clipped_frames": self.clipped_frames,
            "reconstructed_frames": self.reconstructed_frames,
            "motion_window": self.motion_window,
        }


def probe_video(path: str | Path) -> VideoInfo:
    path = Path(path)
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise SystemExit(f"could not open the video: {path}")
    info = VideoInfo(
        path=path,
        width=int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)),
        height=int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        fps=float(capture.get(cv2.CAP_PROP_FPS)) or 24.0,
        frame_count=int(capture.get(cv2.CAP_PROP_FRAME_COUNT)),
    )
    capture.release()
    info.has_audio = _has_audio(path)
    return info


def _has_audio(path: Path) -> bool:
    if not shutil.which("ffprobe"):
        return False
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index",
         "-of", "csv=p=0", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )
    return bool(probe.stdout.strip())


def iter_frames(path: str | Path, *, start: int = 0, limit: int | None = None):
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise SystemExit(f"could not open the video: {path}")
    if start:
        capture.set(cv2.CAP_PROP_POS_FRAMES, start)
    index = start
    try:
        while limit is None or index - start < limit:
            ok, frame = capture.read()
            if not ok:
                break
            yield index, frame
            index += 1
    finally:
        capture.release()


def _is_clipped(point: np.ndarray, width: int, height: int, tolerance: float = BORDER_TOLERANCE) -> bool:
    x, y = float(point[0]), float(point[1])
    return x <= tolerance or y <= tolerance or x >= width - 1 - tolerance or y >= height - 1 - tolerance


def measure_aspect(quads: list[np.ndarray], width: int, height: int) -> float | None:
    """Median in-plane width/height over frames where the whole sheet is visible.

    Height is taken from the right edge, because that is the edge
    :func:`rebuild_quad` anchors on when the left side of a sheet runs off
    frame. Using the same reference in both keeps the scale consistent.
    """
    ratios = []
    for quad in quads:
        if quad is None:
            continue
        if any(_is_clipped(point, width, height) for point in quad):
            continue
        tl, tr, br, bl = quad
        edge_u = 0.5 * (float(np.linalg.norm(tr - tl)) + float(np.linalg.norm(br - bl)))
        edge_v = float(np.linalg.norm(br - tr))
        if edge_v > 1.0:
            ratios.append(edge_u / edge_v)
    if not ratios:
        return None
    return float(np.median(ratios))


def _unit(vector: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vector))
    if norm < 1e-6:
        return np.array([1.0, 0.0], np.float32)
    return (vector / norm).astype(np.float32)


def rebuild_quad(quad: np.ndarray, aspect: float | None, width: int, height: int) -> tuple[np.ndarray, bool]:
    """Rebuild a possibly clipped quad from its reliable edge and the sheet aspect.

    Returns the quad and whether it was rebuilt. The edge that is not on the
    frame border is kept exactly as detected; the clipped side is placed at the
    distance the sheet's real proportions imply.
    """
    if aspect is None:
        return quad, False
    tl, tr, br, bl = quad
    right_ok = not _is_clipped(tr, width, height) and not _is_clipped(br, width, height)
    left_ok = not _is_clipped(tl, width, height) and not _is_clipped(bl, width, height)
    if right_ok == left_ok:
        # Nothing clipped, or both sides clipped and nothing to anchor to.
        return quad, False

    if right_ok:
        anchor_top, anchor_bottom = tr, br
    else:
        anchor_top, anchor_bottom = tl, bl

    # Each edge keeps its own direction: when a corner is clipped, the detected
    # point still sits where that edge crosses the frame border, so the edge
    # direction stays valid.
    top_dir = _unit(tr - tl)
    bottom_dir = _unit(br - bl)

    height_v = float(np.linalg.norm(anchor_bottom - anchor_top))
    if height_v < 2.0:
        return quad, False
    width_u = aspect * height_v
    if right_ok:
        rebuilt = np.stack(
            [
                anchor_top - top_dir * width_u,
                anchor_top,
                anchor_bottom,
                anchor_bottom - bottom_dir * width_u,
            ]
        )
    else:
        rebuilt = np.stack(
            [
                anchor_top,
                anchor_top + top_dir * width_u,
                anchor_bottom + bottom_dir * width_u,
                anchor_bottom,
            ]
        )
    try:
        return order_corners(rebuilt), True
    except QuadError:
        return quad, False


def smooth_quads(quads: np.ndarray, window: int = 11) -> np.ndarray:
    """Offline robust quadratic fit: suppress detection jitter without EMA lag.

    The mask still follows each source frame; only the texture coordinates are
    filtered. ponytail: one continuous shot; split at cuts before using on edits.
    """
    if window < 1 or window % 2 == 0:
        raise ValueError("motion window must be a positive odd number")
    data = np.asarray(quads, dtype=np.float64)
    if window == 1 or len(data) < 3:
        return data.astype(np.float32)
    flat = data.reshape(len(data), -1)
    # A short median gives the robust fit an initial estimate not dominated by
    # an occluding hand changing the four-point polygon for a single frame.
    seed = np.array([np.median(flat[max(0, i-2):i+3], axis=0) for i in range(len(flat))])
    result = np.empty_like(flat)
    half = window // 2
    for i in range(len(flat)):
        lo, hi = max(0, i-half), min(len(flat), i+half+1)
        t = (np.arange(lo, hi) - i) / max(half, 1)
        design = np.column_stack([np.ones_like(t), t, t*t])
        values = flat[lo:hi]
        fit = np.linalg.lstsq(design, seed[lo:hi], rcond=None)[0]
        for _ in range(4):
            residual = np.sqrt(np.mean((values - design @ fit)**2, axis=1))
            weights = np.sqrt(np.minimum(1.0, 1.5 / np.maximum(residual, 1e-6)))
            fit = np.linalg.lstsq(design * weights[:, None], values * weights[:, None], rcond=None)[0]
        result[i] = fit[0]
    return result.reshape(data.shape).astype(np.float32)


def _detect_series(
    video: VideoInfo,
    *,
    detect_mode: str,
    detect_kwargs: dict,
    start: int = 0,
    limit: int | None = None,
) -> tuple[list[np.ndarray | None], list[tuple[str, float]]]:
    quads: list[np.ndarray | None] = []
    meta: list[tuple[str, float]] = []
    s_min = detect_kwargs.get("s_min", 150)
    for index, frame in iter_frames(video.path, start=start, limit=limit):
        try:
            detection = detect_quad(frame, mode=detect_mode, **detect_kwargs)
            if detect_mode == "saturated":
                material = colour_mask(frame, s_min=s_min, kernel=3, dilate=0)
                try:
                    detection.corners = refine_sheet_quad(material, detection.corners)
                    detection.method += "+edges"
                except QuadError:
                    pass  # retain the polygon fit if straight edges are hidden
            quads.append(detection.corners)
            meta.append((detection.method, detection.score))
        except QuadError as error:
            quads.append(None)
            meta.append((f"failed: {error}", 0.0))
    return quads, meta


def plan_frames(
    video: VideoInfo,
    *,
    detect_mode: str,
    detect_kwargs: dict,
    start: int = 0,
    limit: int | None = None,
    use_aspect: bool = True,
    motion_window: int = 11,
) -> PlanSet:
    """Pass 1: detect a quad per frame, then stabilise it."""
    if detect_mode == "saturated" and detect_kwargs.get("s_min", 60) < 150:
        high_kwargs = {**detect_kwargs, "s_min": 150}
        quads, meta = _detect_series(
            video, detect_mode=detect_mode, detect_kwargs=high_kwargs, start=start, limit=limit
        )
        if not any(q is not None for q in quads):
            quads, meta = _detect_series(
                video, detect_mode=detect_mode, detect_kwargs=detect_kwargs, start=start, limit=limit
            )
    else:
        quads, meta = _detect_series(
            video, detect_mode=detect_mode, detect_kwargs=detect_kwargs, start=start, limit=limit
        )

    filled: list[np.ndarray | None] = list(quads)
    last: np.ndarray | None = None
    for position, quad in enumerate(filled):
        if quad is None and last is not None:
            filled[position] = last
            meta[position] = ("held-previous", meta[position][1])
        if filled[position] is not None:
            last = filled[position]

    present = [quad for quad in filled if quad is not None]
    if not present:
        raise SystemExit("no frame yielded a usable quadrilateral; try another --detect mode or pass --corners")
    first_valid = present[0]
    for position, quad in enumerate(filled):
        if quad is None:
            filled[position] = first_valid
            meta[position] = ("held-next", meta[position][1])
        else:
            break

    aspect = measure_aspect(present, video.width, video.height) if use_aspect else None
    bottom_clipped_shot = use_aspect and (
        sum(
            1
            for q in present
            if _is_clipped(q[2], video.width, video.height) and _is_clipped(q[3], video.width, video.height)
        )
        > 0.5 * len(present)
    )
    if bottom_clipped_shot:
        right_heights = [float(np.linalg.norm(q[2] - q[1])) for q in present]
        top_widths = [
            float(np.linalg.norm(q[1] - q[0]))
            for q in present
            if not _is_clipped(q[0], video.width, video.height) and not _is_clipped(q[1], video.width, video.height)
        ]
        h_sheet = float(np.percentile(right_heights, 90))
        w_sheet = float(np.median(top_widths)) if top_widths else h_sheet * 0.95
        aspect = w_sheet / max(h_sheet, 1.0)

    plans: list[FramePlan] = []
    for position, quad in enumerate(filled):
        if quad is None:
            continue
        clipped = any(_is_clipped(point, video.width, video.height) for point in quad)
        if bottom_clipped_shot and not _is_clipped(quad[1], video.width, video.height):
            tl, tr, br, _ = quad
            top_dir = _unit(tr - tl)
            right_dir = (
                _unit(br - tr)
                if float(np.linalg.norm(br - tr)) > 140.0
                else np.array([-top_dir[1], top_dir[0]], np.float32)
            )
            tl_r = tr - top_dir * w_sheet
            rebuilt = np.stack([tl_r, tr, tr + right_dir * h_sheet, tl_r + right_dir * h_sheet]).astype(np.float32)
            reconstructed = True
        else:
            rebuilt, reconstructed = rebuild_quad(quad, aspect, video.width, video.height)
        plans.append(
            FramePlan(
                index=start + position,
                quad=rebuilt,
                detection=meta[position][0],
                score=meta[position][1],
                clipped=clipped,
                reconstructed=reconstructed,
            )
        )

    smoothed = smooth_quads(np.array([plan.quad for plan in plans]), motion_window)
    for plan, quad in zip(plans, smoothed):
        try:
            plan.quad = order_corners(quad)
        except QuadError:
            pass

    counts: dict[str, int] = {}
    for plan in plans:
        key = plan.detection.split(":")[0]
        counts[key] = counts.get(key, 0) + 1

    return PlanSet(
        plans=plans,
        aspect=aspect,
        detection_counts=counts,
        clipped_frames=sum(1 for plan in plans if plan.clipped),
        reconstructed_frames=sum(1 for plan in plans if plan.reconstructed),
        motion_window=motion_window,
    )


def encode(
    frames_dir: str | Path,
    source: str | Path,
    output: str | Path,
    fps: float,
    *,
    crf: int = 16,
    preset: str = "slow",
) -> Path:
    """Encode a PNG sequence with ffmpeg, copying the source audio when present."""
    if not shutil.which("ffmpeg"):
        raise SystemExit("ffmpeg is required to encode the result; install it with: brew install ffmpeg")
    frames_dir = Path(frames_dir)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg", "-y", "-v", "error",
        "-framerate", f"{fps}",
        "-i", str(frames_dir / "%05d.png"),
        "-i", str(source),
        "-map", "0:v:0", "-map", "1:a?",
        "-c:v", "libx264", "-crf", str(crf), "-preset", preset,
        "-pix_fmt", "yuv420p", "-c:a", "copy", "-shortest",
        "-movflags", "+faststart",
        str(output),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise SystemExit(f"ffmpeg failed:\n{result.stderr.strip()}")
    return output


def render(
    video: VideoInfo,
    texture: np.ndarray,
    plans: list[FramePlan],
    config: ComposeConfig,
    frames_dir: str | Path,
    *,
    occlusion: bool = True,
    mask_kwargs: dict | None = None,
) -> list[dict]:
    """Pass 2: compose every planned frame and write it as a PNG."""
    frames_dir = Path(frames_dir)
    frames_dir.mkdir(parents=True, exist_ok=True)
    mask_kwargs = mask_kwargs or {}
    wanted = {plan.index: plan for plan in plans}
    rows: list[dict] = []
    # One UV canvas for the whole shot: resizing/re-anchoring the native-scale
    # tile per frame changes its phase even if the physical sheet barely moves.
    quads = np.array([plan.quad for plan in plans])
    widths = .5 * (np.linalg.norm(quads[:, 1]-quads[:, 0], axis=1)
                    + np.linalg.norm(quads[:, 2]-quads[:, 3], axis=1))
    heights = .5 * (np.linalg.norm(quads[:, 3]-quads[:, 0], axis=1)
                     + np.linalg.norm(quads[:, 2]-quads[:, 1], axis=1))
    texture_size = (max(2, int(round(float(np.median(widths))))),
                    max(2, int(round(float(np.median(heights))))))

    for index, frame in iter_frames(video.path):
        plan = wanted.get(index)
        if plan is None:
            continue
        coverage = colour_mask(frame, **mask_kwargs) if occlusion else None
        if coverage is not None and np.count_nonzero(coverage) < 0.01 * frame.shape[0] * frame.shape[1]:
            coverage.fill(0)
        # The quad supplies UV geometry, not the silhouette. Occlusion can make
        # its polygon cut across visible paper; intersecting the two masks left
        # an exposed smooth strip that looked like a second sheet during motion.
        result = compose(
            frame, texture, plan.quad, config, coverage_mask=coverage,
            surface_mask=occlusion,
            texture_size=texture_size,
        )
        write_png(frames_dir / f"{index:05d}.png", result.image)
        rows.append(
            {
                "frame": index,
                "detection": plan.detection,
                "score": round(float(plan.score), 4),
                "clipped": bool(plan.clipped),
                "reconstructed": bool(plan.reconstructed),
                "mask_coverage": result.stats["mask_coverage"],
                "sheet_size": result.stats["sheet_size"],
            }
        )
    return rows
