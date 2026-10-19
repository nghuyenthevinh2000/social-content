"""Filesystem helpers: hashing, image info, overlays, manifest writing."""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np

_CHUNK = 1 << 20
_CORNER_LABELS = ("TL", "TR", "BR", "BL")


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(_CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()


def describe_image(path: str | Path) -> dict:
    """Describe an input file for the manifest: size on disk, pixels, hash."""
    path = Path(path)
    image = cv2.imread(str(path))
    payload: dict = {"path": str(path), "bytes": path.stat().st_size, "sha256": sha256_file(path)}
    if image is None:
        payload["readable"] = False
        return payload
    payload["readable"] = True
    payload["width"], payload["height"] = int(image.shape[1]), int(image.shape[0])
    payload["channels"] = int(image.shape[2]) if image.ndim == 3 else 1
    return payload


def write_png(path: str | Path, image: np.ndarray) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(path), image):
        raise OSError(f"could not write {path}")
    return path


def write_json(path: str | Path, payload: dict) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def read_quad(path: str | Path) -> np.ndarray:
    """Read corners from a quad JSON written by this package or the CLI."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    corners = payload.get("corners") if isinstance(payload, dict) else payload
    if corners is None:
        raise ValueError(f"{path} does not contain a 'corners' list")
    return np.asarray(corners, dtype=np.float32).reshape(-1, 2)


def overlay_quad(
    image: np.ndarray,
    corners: np.ndarray,
    *,
    mask: np.ndarray | None = None,
    title: str | None = None,
) -> np.ndarray:
    """Draw the detected quad, corner markers and an optional coverage mask."""
    out = image.copy()
    if out.ndim == 2:
        out = cv2.cvtColor(out, cv2.COLOR_GRAY2BGR)

    if mask is not None:
        coverage = mask
        if coverage.dtype != np.float32:
            coverage = coverage.astype(np.float32) / 255.0
        tint = np.zeros_like(out)
        tint[:, :, 2] = 255
        weight = np.clip(coverage, 0.0, 1.0)[..., None] * 0.25
        out = (out.astype(np.float32) * (1.0 - weight) + tint.astype(np.float32) * weight).astype(np.uint8)

    quad = corners.astype(np.int32).reshape(-1, 1, 2)
    cv2.polylines(out, [quad], True, (0, 255, 0), 2, lineType=cv2.LINE_AA)

    for label, point in zip(_CORNER_LABELS, corners):
        centre = (int(round(point[0])), int(round(point[1])))
        cv2.circle(out, centre, 6, (0, 0, 255), -1, lineType=cv2.LINE_AA)
        cv2.putText(
            out,
            f"{label} ({centre[0]},{centre[1]})",
            (centre[0] + 10, centre[1] - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 0, 0),
            3,
            lineType=cv2.LINE_AA,
        )
        cv2.putText(
            out,
            f"{label} ({centre[0]},{centre[1]})",
            (centre[0] + 10, centre[1] - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 255),
            1,
            lineType=cv2.LINE_AA,
        )

    if title:
        cv2.putText(out, title, (16, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 4, lineType=cv2.LINE_AA)
        cv2.putText(out, title, (16, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 1, lineType=cv2.LINE_AA)
    return out


def utc_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat()
