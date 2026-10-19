---
name: video-editing
description: "Edit videos using the repository's tools/video_edit CLI first for deterministic product-surface texture replacement, proxy frames, corner detection, and static watermark processing. Use ffmpeg fallback for unsupported composition, face overlays, audio mixing, frame extraction, and encoding tasks."
---

# Video editing

## Tool selection

| Requirement | Instruction |
|---|---|
| Primary tool | Use `tools/video_edit` for supported operations; do not recreate its detection, compositing, or watermark algorithms in ad-hoc scripts. |
| Invocation | Run `uv run python -m tools.video_edit` from the repository root. Use repository-relative paths rather than machine-specific absolute paths. |
| Source of truth | Read `tools/video_edit/README.md` and the relevant subcommand's `--help` before choosing parameters. Paths in this table are relative to the repository root. |
| Environment | Use the repository's uv-managed environment. OpenCV and NumPy are required; ffmpeg and ffprobe are needed for video processing. Do not install into system Python. |
| Capability boundary | This CLI is not a general nonlinear editor. It does not implement talking-head overlays, audio denoising, music mixing, or arbitrary cuts. |
| Fallback | For unsupported operations, read `references/ffmpeg-compositing.md` relative to this skill. Keep its face helper at the skill-root path `scripts/detect_face_crop.py`. Use a repository-local or approved temporary workspace instead of the reference's legacy `/tmp` examples. |

## Commands

| Task | Command from repository root |
|---|---|
| Check environment | `uv run python -m tools.video_edit doctor` |
| Inspect available commands | `uv run python -m tools.video_edit --help` |
| Inspect parameters | `uv run python -m tools.video_edit video --help` or `uv run python -m tools.video_edit watermark --help` |
| Generate a test proxy | `uv run python -m tools.video_edit proxy --mode card --width 1080 --height 1350 --out local/video-edit/proxy.png --quad-out local/video-edit/proxy_quad.json` |
| Smooth an existing photo | `uv run python -m tools.video_edit proxy --mode smooth --src PHOTO --out local/video-edit/proxy.png` |
| Inspect a surface | `uv run python -m tools.video_edit corners --image PROXY --out local/video-edit/quad.json --overlay local/video-edit/corners.png` |
| Replace texture in a still | `uv run python -m tools.video_edit run --proxy PROXY --texture TEXTURE --out-dir local/video-edit/still --proxy-kind provided --debug` |
| Preview video texture replacement | `uv run python -m tools.video_edit video --video INPUT --texture TEXTURE --out-dir local/video-edit/texture-preview --limit 24` |
| Preview watermark processing | `uv run python -m tools.video_edit watermark --video INPUT --method harmonic --out-dir local/video-edit/watermark-preview --limit 24` |

## Workflow

```text
Inspect inputs -> Supported by tools/video_edit?
                   yes -> CLI preview -> Inspect -> Full render -> Verify
                    no -> ffmpeg fallback -----------------------> Verify
```

| Stage | Required action |
|---|---|
| Inspect | Confirm input paths, requested effect, output location, duration, frame rate, rotation, decoded dimensions, and audio presence. Use ffprobe and decoded-frame inspection when needed. |
| Plan | Select a supported command or fallback. Use a new output directory; never overwrite source media. Split at scene cuts before motion-dependent processing. |
| Preview | Use `--start` and `--limit` for representative slices. Both are frame counts, not seconds. Inspect difficult movement, occlusions, and frame edges, not just the opening. |
| Inspect | Review masks, corner overlays, preview frames, and manifests. Reject skin spill, shifted edges, texture jitter, visible patches, or unsupported claims of quality. |
| Render | Remove preview limits only after inspection. Keep each trial in a separate output directory. |
| Verify | Probe the encoded MP4; check dimensions, duration, frame rate, audio, and representative frames. Partial renders need independent audio/timing checks; do not assume slice synchronization. |
| Report | Provide the output path, settings, checks performed, and remaining defects. Passing tests or reduced residuals do not prove visual quality. |

## Parameters and limits

| Area | Guidance |
|---|---|
| Texture geometry | Intended for a flat product face. Perspective warping resamples real texture; lighting modulation changes brightness. Do not claim bit-identical pixels or physically exact tracking on bending surfaces. |
| Video detection | Prefer `saturated` when the surface differs clearly from skin/background; `edges` and `bright` are alternatives. Video does not expose manual corners or SAM 2; those options belong to still-image operations. |
| Still geometry | `run` supports `--corners`, `--corners-file`, or optional SAM 2. SAM 2 requires extra dependencies, a checkpoint, and a prompt point. Do not install it unless needed. |
| Temporal stability | Video uses aspect reconstruction, straight-edge fitting where applicable, and a fixed texture canvas. `--motion-window` defaults to 11; 1 disables smoothing. Assume one continuous shot. |
| Occlusion | Mask quality depends on material colour. Tune `--mask-s-min`, `--mask-kernel`, `--mask-dilate`, and `--edge-feather` against previews. `--no-occlusion` can paint over hands. |
| Texture quality | Native-scale tiling is the default. `--texture-scale`, `--grain-angle`, and shading controls adjust appearance. Lower CRF improves encoded quality; `--skip-encode` preserves PNG intermediates. |
| Watermark placement | Automatic search defaults to bottom-right. Override with `--search`, `--box`, or `--mask-file`; inspect `preview.png` and `mask.png` before trusting detection. |
| Watermark methods | Explicitly select a method. CLI default `unmix` is experimental with documented failing reconstruction tests; do not treat it as verified. `harmonic` can soften hard edges; `clone` can repeat texture or mismatch shading; `temporal` can lack clean donors. `telea` and `ns` are alternatives, not guarantees. |
| Recovery claim | Never promise restoration of never-visible detail or an invisible watermark. Document actual visual results. |
| Fallback correctness | Confirm decoded portrait dimensions, normalize time bases/frame rates for overlays, map audio explicitly, and handle HDR-to-SDR conversion deliberately. Pixel-format conversion alone is not tone mapping. |

## Outputs

| Operation | Artifacts to inspect |
|---|---|
| Still `run` | `frame0.png`, `mask.png`, `overlay.png`, `quad.json`, `manifest.json`; `debug/` with `--debug`. Label synthetic proxies as fixtures rather than product photography. |
| `video` | `result.mp4`, `frames/`, `manifest.json`, unless output paths or encoding are overridden. |
| `watermark` | `result.mp4`, `frames/`, `mask.png`, `preview.png`, `manifest.json`, unless encoding is skipped. |
| Verification boundary | Read current documentation and actual artifacts; historical sample renders and test counts are not evidence for the current input. |
