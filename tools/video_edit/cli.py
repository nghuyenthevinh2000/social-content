"""Command line interface: ``python -m tools.video_edit <command>``."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np

from . import __version__
from .blend import BLEND_MODES
from .compose import ComposeConfig, compose, config_to_dict, INTERPOLATIONS
from .corners import (
    QuadError,
    detect_quad,
    detect_quad_sam2,
    parse_corners,
)
from .io import (
    describe_image,
    overlay_quad,
    read_quad,
    utc_now,
    write_json,
    write_png,
)
from .proxy import smooth_proxy, synthetic_card_proxy
from .shell import run_blender_simulation
from .video import encode, plan_frames, probe_video, render
from .watermark import find_backend, install_backend, render_watermark

_DETECT_MODES = ("saturated", "edges", "bright")


def _load_image(path: Path, label: str) -> np.ndarray:
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        raise SystemExit(f"could not read the {label} image: {path}")
    return image


def _default_flatten_sigma(texture: np.ndarray) -> float:
    return max(12.0, 0.35 * min(texture.shape[:2]))


def _resolve_quad(args, frame: np.ndarray):
    """Return (corners, detection_payload) from manual input or detection."""
    if args.corners:
        corners = parse_corners(args.corners)
        return corners, {"method": "manual", "score": 1.0, "corners": corners.tolist(), "notes": ["--corners"]}
    if args.corners_file:
        corners = read_quad(args.corners_file)
        return corners, {
            "method": "manual-file",
            "score": 1.0,
            "corners": corners.tolist(),
            "notes": [str(args.corners_file)],
        }
    if args.detect == "sam2":
        if not args.sam2_checkpoint:
            raise SystemExit("--detect sam2 needs --sam2-checkpoint")
        if not args.sam2_point:
            raise SystemExit("--detect sam2 needs --sam2-point 'x,y' inside the card")
        try:
            point_x, point_y = (float(part) for part in args.sam2_point.split(","))
        except ValueError as error:
            raise SystemExit("--sam2-point must look like 'x,y'") from error
        detection = detect_quad_sam2(
            frame,
            point=(int(point_x), int(point_y)),
            checkpoint=args.sam2_checkpoint,
            model_cfg=args.sam2_config,
        )
    else:
        detection = detect_quad(
            frame,
            mode=args.detect,
            min_area_ratio=args.min_area_ratio,
            kernel=args.kernel,
            s_min=args.s_min,
            v_min=args.v_min,
        )
    return detection.corners, {
        "method": detection.method,
        "score": detection.score,
        "corners": detection.as_list(),
        "notes": detection.notes,
    }


def _compose_config(args, texture: np.ndarray) -> ComposeConfig:
    flatten = args.texture_flatten
    if flatten is None:
        flatten = _default_flatten_sigma(texture)
    return ComposeConfig(
        blend_mode=args.blend_mode,
        shading_strength=args.shading_strength,
        lighting_sigma=args.lighting_sigma,
        max_darken=args.max_darken,
        max_lighten=args.max_lighten,
        edge_feather=args.edge_feather,
        inset=args.inset,
        texture_scale=args.texture_scale,
        grain_angle=args.grain_angle,
        texture_flatten=flatten,
        texture_gain=args.texture_gain,
        tile=not args.no_tile,
        interpolation=args.interpolation,
    )


def cmd_run(args) -> int:
    proxy_path = Path(args.proxy)
    texture_path = Path(args.texture)
    out_dir = Path(args.out_dir)

    proxy = _load_image(proxy_path, "proxy")
    texture = _load_image(texture_path, "texture")

    corners, detection_payload = _resolve_quad(args, proxy)
    cfg = _compose_config(args, texture)
    result = compose(proxy, texture, corners, cfg)

    out_dir.mkdir(parents=True, exist_ok=True)
    frame_path = write_png(out_dir / "frame0.png", result.image)
    write_png(out_dir / "mask.png", (result.mask * 255).astype(np.uint8))
    write_png(out_dir / "overlay.png", overlay_quad(proxy, result.corners, mask=result.mask, title="detected surface"))
    write_json(out_dir / "quad.json", {"corners": result.corners.tolist(), "detection": detection_payload})

    if args.debug:
        write_png(out_dir / "debug" / "tiled.png", result.tiled)
        write_png(out_dir / "debug" / "warped.png", result.warped)
        write_png(out_dir / "debug" / "illumination.png", (np.clip(result.illumination, 0, 1) * 255).astype(np.uint8))

    manifest = {
        "schema_version": 1,
        "generated_on": utc_now(),
        "architecture": "deterministic-perspective-texture-swap",
        "what_this_is": (
            "Real camera pixels from the texture were perspective-warped onto the proxy's "
            "detected surface and modulated by the proxy's lighting. No generative step ran."
        ),
        "inputs": {"proxy": describe_image(proxy_path), "texture": describe_image(texture_path)},
        "detection": detection_payload,
        "config": config_to_dict(cfg),
        "stats": result.stats,
        "outputs": {
            "frame0": "frame0.png",
            "mask": "mask.png",
            "overlay": "overlay.png",
            "quad": "quad.json",
        },
        "i2v": {
            "frame0": str(frame_path),
            "use": "Feed frame0.png as frame 0 of an image-to-video model.",
            "note": "Render the proxy at the target video resolution so no rescaling softens the grain.",
        },
        "provenance": {
            "generative_texture": False,
            "proxy_kind": args.proxy_kind,
        },
        "limits": [
            "The perspective warp resamples the texture, so pixels are geometrically transformed, not bit-identical.",
            "The lighting-carry blend scales the texture's brightness; it preserves relative grain, not absolute exposure.",
            "A filled line-art mask is assumed: the detected quad must be a flat, visible surface.",
        ],
    }
    write_json(out_dir / "manifest.json", manifest)

    print(f"frame0      {frame_path}")
    print(f"detection   {detection_payload['method']} (score {detection_payload['score']:.3f})")
    print(f"sheet       {result.stats['sheet_size']} px  tiles {result.stats['tiles']}")
    print(f"illumination {result.stats['illumination_min']:.3f}..{result.stats['illumination_max']:.3f}")
    print(f"output      {out_dir / 'frame0.png'}")
    return 0


def cmd_video(args) -> int:
    out_dir = Path(args.out_dir)
    out_path = Path(args.out) if args.out else out_dir / "result.mp4"
    frames_dir = Path(args.frames_dir) if args.frames_dir else out_dir / "frames"

    info = probe_video(args.video)
    texture = _load_image(Path(args.texture), "texture")
    planned = plan_frames(
        info,
        detect_mode=args.detect,
        detect_kwargs={
            "min_area_ratio": args.min_area_ratio,
            "kernel": args.kernel,
            "s_min": args.s_min,
            "v_min": args.v_min,
        },
        start=args.start,
        limit=args.limit,
        use_aspect=not args.no_aspect_stabilise,
        motion_window=args.motion_window,
    )
    cfg = _compose_config(args, texture)
    rows = render(
        info,
        texture,
        planned.plans,
        cfg,
        frames_dir,
        occlusion=not args.no_occlusion,
        mask_kwargs={"s_min": args.mask_s_min, "kernel": args.mask_kernel, "dilate": args.mask_dilate},
    )

    written = len(rows)
    encoded = None
    if not args.skip_encode:
        encoded = encode(frames_dir, info.path, out_path, info.fps, crf=args.crf, preset=args.preset)

    manifest = {
        "schema_version": 1,
        "generated_on": utc_now(),
        "architecture": "deterministic-perspective-texture-swap",
        "what_this_is": (
            "Every frame's product surface was replaced with real camera texture: detection, "
            "perspective warp, and lighting-carry blend. No generative step ran on the surface."
        ),
        "video": info.as_dict(),
        "texture": describe_image(args.texture),
        "stabilisation": {
            "occlusion_aware": not args.no_occlusion,
            "aspect_stabilised": not args.no_aspect_stabilise,
            "fixed_texture_canvas": True,
            **planned.as_dict(),
        },
        "mask": {
            "s_min": args.mask_s_min,
            "kernel": args.mask_kernel,
            "dilate": args.mask_dilate,
        },
        "config": config_to_dict(cfg),
        "outputs": {
            "video": None if encoded is None else str(encoded),
            "frames_dir": str(frames_dir),
            "manifest": str(out_dir / "manifest.json"),
        },
        "frames": rows,
        "provenance": {"generative_texture": False, "proxy_kind": "input-video"},
        "limits": [
            "Frames are re-encoded with H.264, so grain is partly smoothed by compression; raise --crf quality or export a lossless intermediate.",
            "The perspective warp resamples the texture; it is not bit-identical to the source pixels.",
            "The lighting-carry blend scales the texture's brightness, so relative grain is preserved, not absolute exposure.",
            "Occlusion masking relies on the surface's saturation differing from whatever overlaps it.",
        ],
    }
    write_json(out_dir / "manifest.json", manifest)

    print(f"video       {info.width}x{info.height} @ {info.fps:.2f}fps, {info.frame_count} frames")
    print(f"sheet aspect {planned.aspect if planned.aspect is None else round(planned.aspect, 3)}")
    print(f"detection   {planned.detection_counts}")
    print(f"clipped     {planned.clipped_frames} frames, rebuilt {planned.reconstructed_frames}")
    print(f"frames      {written} written to {frames_dir}")
    print(f"output      {encoded if encoded else '(encoding skipped)'}")
    return 0


def cmd_corners(args) -> int:
    frame = _load_image(Path(args.image), "image")
    if args.corners:
        corners = parse_corners(args.corners)
        payload = {"method": "manual", "score": 1.0, "corners": corners.tolist(), "notes": ["--corners"]}
    else:
        detection = detect_quad(
            frame,
            mode=args.detect,
            min_area_ratio=args.min_area_ratio,
            kernel=args.kernel,
            s_min=args.s_min,
            v_min=args.v_min,
        )
        corners = detection.corners
        payload = {
            "method": detection.method,
            "score": detection.score,
            "corners": detection.as_list(),
            "notes": detection.notes,
        }

    payload["image"] = str(args.image)
    if args.out:
        write_json(args.out, payload)
        print(f"wrote {args.out}")
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    if args.overlay:
        write_png(args.overlay, overlay_quad(frame, corners, title=payload["method"]))
        print(f"wrote {args.overlay}")
    return 0


def cmd_proxy(args) -> int:
    if args.mode == "smooth":
        if not args.src:
            raise SystemExit("--mode smooth needs --src")
        source = _load_image(Path(args.src), "source")
        proxy = smooth_proxy(
            source,
            diameter=args.diameter,
            sigma_color=args.sigma_color,
            sigma_space=args.sigma_space,
            iterations=args.iterations,
            lowpass=args.lowpass,
        )
        write_png(args.out, proxy)
        print(f"proxy       {args.out}  (edge-preserving smooth of {args.src})")
        return 0

    proxy, quad = synthetic_card_proxy(
        args.width,
        args.height,
        seed=args.seed,
        shadow=args.shadow,
        lighting=args.lighting,
    )
    write_png(args.out, proxy)
    print(f"proxy       {args.out}  (synthetic fixture, {args.width}x{args.height})")
    if args.quad_out:
        write_json(
            args.quad_out,
            {
                "corners": quad.tolist(),
                "source": "synthetic fixture ground truth",
                "mode": "card",
            },
        )
        print(f"quad        {args.quad_out}")
    return 0


def cmd_watermark(args) -> int:
    render_watermark(
        args.video or args.image,
        args.out_dir,
        backend=args.backend,
        image=bool(args.image),
        cpu=args.cpu,
        legacy=args.legacy,
        region=args.region,
        alpha=args.alpha,
        sigma=args.sigma,
        ml=args.ml,
        force=args.force,
    )
    return 0


def cmd_watermark_install(args) -> int:
    print(f"installed   {install_backend()}")
    return 0


def cmd_sim(args) -> int:
    manifest = run_blender_simulation(
        args.texture,
        args.out_dir,
        frames=args.frames,
        blender_bin=args.blender,
    )
    print(f"preset      {manifest['outputs']['blend_preset']}")
    print(f"frames      {args.frames} written to {manifest['outputs']['frames_dir']}")
    print(f"output      {manifest['outputs']['video']}")
    return 0


def cmd_doctor(args) -> int:
    print(f"video_edit {__version__}")
    print(f"python        {sys.version.split()[0]}")
    print(f"opencv        {cv2.__version__}")
    print(f"numpy         {np.__version__}")
    try:
        print(f"watermark     {find_backend()}")
    except QuadError:
        print("watermark     not installed (run watermark-install)")
    try:
        import sam2  # noqa: F401

        print("sam2          available")
    except ImportError:
        print("sam2          not installed (OpenCV backend is the default)")
    print(f"cwd           {Path.cwd()}")
    return 0


def _add_compose_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--blend-mode", choices=BLEND_MODES, default="shading")
    parser.add_argument("--shading-strength", type=float, default=1.0)
    parser.add_argument("--lighting-sigma", type=float, default=0.0, help="0 derives it from the surface size")
    parser.add_argument("--max-darken", type=float, default=0.7)
    parser.add_argument("--max-lighten", type=float, default=1.35)
    parser.add_argument("--edge-feather", type=float, default=1.5)
    parser.add_argument("--inset", type=float, default=0.0)
    parser.add_argument("--texture-scale", type=float, default=1.0)
    parser.add_argument("--grain-angle", type=float, default=0.0)
    parser.add_argument(
        "--texture-flatten", type=float, default=None, help="sigma; 0 disables; default derives from texture size"
    )
    parser.add_argument("--texture-gain", type=float, default=1.0)
    parser.add_argument("--interpolation", choices=INTERPOLATIONS, default="lanczos4")
    parser.add_argument("--no-tile", action="store_true", help="stretch one tile instead of repeating at native scale")


def _add_detect_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--detect", choices=_DETECT_MODES + ("sam2",), default="saturated")
    parser.add_argument("--min-area-ratio", type=float, default=0.02)
    parser.add_argument("--kernel", type=int, default=5)
    parser.add_argument("--s-min", type=int, default=60, help="saturation floor for --detect saturated")
    parser.add_argument("--v-min", type=int, default=40, help="value floor for saturated/bright")
    parser.add_argument("--sam2-checkpoint", help="SAM 2 checkpoint path")
    parser.add_argument("--sam2-config", default="configs/sam2.1/sam2.1_hiera_s.yaml")
    parser.add_argument("--sam2-point", help="'x,y' inside the card for SAM 2")


def _add_manual_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--corners", help="'x,y;x,y;x,y;x,y' manual corners, bypassing detection")
    parser.add_argument("--corners-file", help="JSON with a 'corners' list")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="video_edit",
        description="Deterministic perspective texture-swap: paste real texture pixels onto a proxy frame.",
    )
    parser.add_argument("--version", action="version", version=f"video_edit {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="detect, warp, blend and write the frame 0 and manifest")
    run.add_argument("--proxy", required=True)
    run.add_argument("--texture", required=True)
    run.add_argument("--out-dir", default="out")
    run.add_argument("--proxy-kind", default="provided", help="label for the manifest: provided|smoothed-photo|synthetic-fixture")
    _add_manual_args(run)
    _add_detect_args(run)
    _add_compose_args(run)
    run.add_argument("--debug", action="store_true", help="also write tiled/warped/illumination images")
    run.set_defaults(func=cmd_run)

    video = sub.add_parser("video", help="apply the swap to every frame of a video and encode an MP4")
    video.add_argument("--video", required=True)
    video.add_argument("--texture", required=True)
    video.add_argument("--out-dir", default="out/video")
    video.add_argument("--out", help="output MP4 (default <out-dir>/result.mp4)")
    video.add_argument("--frames-dir", help="where PNG frames go (default <out-dir>/frames)")
    video.add_argument("--start", type=int, default=0)
    video.add_argument("--limit", type=int, help="process only this many frames, for a quick look")
    video.add_argument("--no-occlusion", action="store_true", help="ignore overlapping hands; paste the whole quad")
    video.add_argument("--no-aspect-stabilise", action="store_true", help="use the raw clipped quad")
    video.add_argument("--motion-window", type=int, default=11, help="odd temporal fitting window; 1 disables (default 11)")
    video.add_argument("--mask-s-min", type=int, default=150, help="saturation floor for the occlusion mask")
    video.add_argument("--mask-kernel", type=int, default=7)
    video.add_argument("--mask-dilate", type=int, default=1)
    video.add_argument("--crf", type=int, default=16)
    video.add_argument("--preset", default="slow")
    video.add_argument("--skip-encode", action="store_true", help="write frames and manifest only")
    _add_detect_args(video)
    _add_compose_args(video)
    video.set_defaults(func=cmd_video)

    corners = sub.add_parser("corners", help="report the detected corners as JSON")
    corners.add_argument("--image", required=True)
    corners.add_argument("--out")
    corners.add_argument("--overlay")
    _add_manual_args(corners)
    _add_detect_args(corners)
    corners.set_defaults(func=cmd_corners)

    proxy = sub.add_parser("proxy", help="build a proxy frame (deterministic stand-in for the AI step)")
    proxy.add_argument("--src", help="source photo for --mode smooth")
    proxy.add_argument("--out", required=True)
    proxy.add_argument("--mode", choices=("smooth", "card"), default="smooth")
    proxy.add_argument("--width", type=int, default=1280)
    proxy.add_argument("--height", type=int, default=960)
    proxy.add_argument("--seed", type=int, default=7)
    proxy.add_argument("--shadow", type=float, default=0.45)
    proxy.add_argument("--lighting", type=float, default=0.35)
    proxy.add_argument("--quad-out")
    proxy.add_argument("--diameter", type=int, default=9)
    proxy.add_argument("--sigma-color", type=float, default=75.0)
    proxy.add_argument("--sigma-space", type=float, default=75.0)
    proxy.add_argument("--iterations", type=int, default=3)
    proxy.add_argument("--lowpass", type=float, default=0.0)
    proxy.set_defaults(func=cmd_proxy)

    watermark = sub.add_parser(
        "watermark", help="remove visible Gemini/Veo watermarks using the official calibrated backend"
    )
    media = watermark.add_mutually_exclusive_group(required=True)
    media.add_argument("--video", help="original video; audio is passed through by the backend")
    media.add_argument("--image", help="PNG frame for calibrated repair of skipped frames")
    watermark.add_argument("--out-dir", default="out/video-clean")
    watermark.add_argument("--backend", help="executable override; otherwise VEO_WATERMARK_BIN or the pinned installation")
    watermark.add_argument("--cpu", action=argparse.BooleanOptionalAction, default=True, help="CPU denoise by default; --no-cpu allows GPU")
    watermark.add_argument("--legacy", action="store_true", help="older watermark profile; also used for calibrated V1 frame repair")
    watermark.add_argument("--region", help="explicit watermark x,y,w,h in pixels; default auto-detects")
    watermark.add_argument("--alpha", type=float, help="constant calibrated intensity, 0.05..3; default backend estimation")
    watermark.add_argument("--sigma", type=float, help="denoise strength, 1..150; default backend setting")
    watermark.add_argument("--ml", action="store_true", help="opt into upstream ML intensity estimation")
    watermark.add_argument("--force", action="store_true", help="bypass detection for a known watermark, mainly individual PNG repairs")
    watermark.set_defaults(func=cmd_watermark)

    installer = sub.add_parser("watermark-install", help="download the pinned official backend and verify its SHA256")
    installer.set_defaults(func=cmd_watermark_install)

    sim = sub.add_parser("sim", help="run headless Blender 120gsm thin-shell Cloth + Cycles PBR simulation")
    sim.add_argument("--texture", required=True)
    sim.add_argument("--out-dir", default="out/sim")
    sim.add_argument("--frames", type=int, default=24)
    sim.add_argument("--blender", help="path to blender executable")
    sim.set_defaults(func=cmd_sim)

    doctor = sub.add_parser("doctor", help="report versions and backend availability")
    doctor.set_defaults(func=cmd_doctor)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except QuadError as error:
        print(f"detection failed: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
