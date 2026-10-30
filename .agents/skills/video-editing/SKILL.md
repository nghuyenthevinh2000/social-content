---
name: video-editing
description: "Edit videos using the repository's tools/video_edit CLI first for deterministic product-surface texture replacement, proxy frames, corner detection, and static watermark processing. Use yt-dlp for downloading online source media from supported platforms. Use ffmpeg fallback for unsupported composition, face overlays, audio mixing, frame extraction, and encoding tasks."
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
| Video download | Use `uv run yt-dlp` to download source videos from URLs (Facebook, TikTok, YouTube, Instagram, X). Probe with `-F` and transcode to standard H.264 MP4 if needed. |
| Video translation & subtitle overlay | For translating foreign on-screen subtitles into Vietnamese with ASS vector masking, follow `workflows/vietnamese-video-translation.md` using `scripts/sub_scanner.py` and `scripts/ass_builder.py`. |
| Avatar UGC video synthesis | For synthesizing realistic avatar UGC videos mimicking real people (photo, voice, pose) with Vertex AI, ElevenLabs `eleven_v3` timestamp-aligned voice synthesis (`FXJGVNPXC71BGT9PjlMX`), and social web normalization, follow `workflows/avatar-ugc-synthesis.md`. |
| Fallback | For unsupported operations, read `references/ffmpeg-compositing.md` relative to this skill. Keep its face helper at the skill-root path `scripts/detect_face_crop.py`. Use a repository-local or approved temporary workspace instead of the reference's legacy `/tmp` examples. |

## Commands

| Task | Command from repository root |
|---|---|
| Check environment | `uv run python -m tools.video_edit doctor` |
| Inspect available commands | `uv run python -m tools.video_edit --help` |
| Download video from URL | `uv run yt-dlp -o "<OUT_PATH>" -f "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best" "<URL>"` |
| Inspect video formats & info | `uv run yt-dlp -F "<URL>"` or `uv run yt-dlp --dump-json "<URL>"` |
| Inspect parameters | `uv run python -m tools.video_edit video --help` or `uv run python -m tools.video_edit watermark --help` |
| Generate a test proxy | `uv run python -m tools.video_edit proxy --mode card --width 1080 --height 1350 --out local/video-edit/proxy.png --quad-out local/video-edit/proxy_quad.json` |
| Smooth an existing photo | `uv run python -m tools.video_edit proxy --mode smooth --src PHOTO --out local/video-edit/proxy.png` |
| Inspect a surface | `uv run python -m tools.video_edit corners --image PROXY --out local/video-edit/quad.json --overlay local/video-edit/corners.png` |
| Replace texture in a still | `uv run python -m tools.video_edit run --proxy PROXY --texture TEXTURE --out-dir local/video-edit/still --proxy-kind provided --debug` |
| Preview video texture replacement | `uv run python -m tools.video_edit video --video INPUT --texture TEXTURE --out-dir local/video-edit/texture-preview --limit 24` |
| Install watermark backend | `uv run python -m tools.video_edit watermark-install` — downloads the pinned official Veo backend and verifies its SHA256. |
| Watermark processing | `uv run python -m tools.video_edit watermark --video INPUT --out-dir local/video-edit/watermark-clean` — official calibrated backend only; use a new directory. |
| Scan subtitle segments | `uv run python .agents/skills/video-editing/scripts/sub_scanner.py --video INPUT --out-dir OUT_DIR --roi YMIN:YMAX,XMIN:XMAX` |
| Build ASS subtitle overlay | `uv run python .agents/skills/video-editing/scripts/ass_builder.py --segments SEGMENTS.json --translations TRANSLATIONS.json --out OUT.ass` |
| Burn ASS subtitles & delogo | `ffmpeg -y -i INPUT -vf "delogo=x:y:w:h:enable='between(t,t1,t2)',subtitles='OVERLAY.ass'" -c:v libx264 -crf 18 -preset fast -pix_fmt yuv420p -c:a copy -movflags +faststart OUTPUT.mp4` |

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
| Preview | Texture video supports `--start` and `--limit` in frames. Watermark processing delegates whole files to the official engine; extract a representative clip with ffmpeg if a short trial is needed. |
| Inspect | Review masks/corner overlays for texture work, and the encoded output plus `backend.log` for watermark work. Reject skin spill, shifted edges, texture jitter, visible patches, or unsupported claims of quality. |
| Render | Remove texture-video preview limits only after inspection. Keep each trial in a separate output directory. |
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
| Watermark placement | The official engine auto-detects supported Gemini/Veo profiles; override with `--region x,y,w,h` and optionally `--alpha` for a known calibration. Work from original footage before texture replacement. |
| Watermark backend | Use only the calibrated allenk/VeoWatermarkRemover backend. The custom methods and old `--method`, mask and slice flags are removed. CPU denoise is default; `--no-cpu` allows GPU, `--ml` opts into upstream ML estimation. |
| Watermark repair | Inspect reported skipped frames; success is not a quality guarantee. Use `watermark --image FRAME.png --legacy --region x,y,w,h --alpha VALUE --sigma VALUE --force --out-dir NEW_DIRECTORY` for calibrated PNG repair, then reassemble with original audio. Do not assume the Tet clip's calibration applies to every input. |
| Recovery claim | Never promise restoration of never-visible detail or an invisible watermark. Document actual visual results. |
| Fallback correctness | Confirm decoded portrait dimensions, normalize time bases/frame rates for overlays, map audio explicitly, and handle HDR-to-SDR conversion deliberately. Pixel-format conversion alone is not tone mapping. |
| Avatar UGC prompt hygiene | Never include platform brand names ('TikTok', 'Instagram', 'Reels') in visual style prompts. Doing so triggers latent training associations and causes generative video models to hallucinate fake watermarks and handles (e.g. @documentars). Always specify clean raw footage with explicit negative constraints: 'no watermarks, no logos, no text overlays, no usernames'. Follow `workflows/avatar-ugc-synthesis.md`. |
| Voice synthesis & lip-sync | Use ElevenLabs `textToSpeech.convertWithTimestamps("FXJGVNPXC71BGT9PjlMX", { modelId: "eleven_v3" })` with clause-level `atempo` window alignment instead of `eleven_multilingual_sts_v2` (which has `vi: false` and copies random guide dialects). |

## Outputs

| Operation | Artifacts to inspect |
|---|---|
| Still `run` | `frame0.png`, `mask.png`, `overlay.png`, `quad.json`, `manifest.json`; `debug/` with `--debug`. Label synthetic proxies as fixtures rather than product photography. |
| `video` | `result.mp4`, `frames/`, `manifest.json`, unless output paths or encoding are overridden. |
| `watermark` | `result.mp4` (or `result.png` for `--image`), `backend.log`, and `manifest.json`. No automatic custom-fill fallback or intermediate frame sequence. Existing sources and results are not overwritten. |
| Verification boundary | Read current documentation and actual artifacts; historical sample renders and test counts are not evidence for the current input. |
