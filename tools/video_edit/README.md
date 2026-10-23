# video_edit

Prompting a diffusion model for a physical surface means translating dozens of
micro-optical properties into English words, and every new SKU restarts the
fight. This package takes the other route for one specific problem: the moment
where a clean, smooth product has to become the *actual* product.

Architecture implemented here (and only this one):

1. **Proxy frame** — a smooth, matte version of the scene. A generative model
   can make it, because lighting, hands and geometry are things it handles well
   when it does not have to invent a microstructure.
2. **Segment the surface** — find the four corners of the product's flat face
   (OpenCV by default, SAM 2 optional).
3. **Perspective warp + lighting-carry blend** — warp a real close-up onto
   those four corners and scale it by the proxy's own luminance, so the proxy's
   lighting and shadows survive and the surface pixels are real.

`frame0.png` goes into image-to-video as frame 0.

## Why not just prompt it

A generative redraw invents fibres, and the invented fibres drift between
generations. Here the surface pixels come from a photograph of the actual
material. Nothing is generated inside the product's face.

## Install and run

The package needs only OpenCV and NumPy, both already in this repository's
environment. Run it from the repository root using `uv run python -m tools.video_edit`.
The example media remains in `local/paper-ink-product`; from that directory,
use `PYTHONPATH=../.. uv run --project ../.. python -m tools.video_edit`.
The examples below assume the media directory and `PYTHONPATH=../..`:

```bash
# From local/paper-ink-product:
export PYTHONPATH=../..
# 1. Build a proxy. `card` is a labelled test fixture; `smooth` is a
#    deterministic stand-in that works on the owner's own photos.
uv run --project ../.. python -m tools.video_edit proxy --mode card \
  --width 1080 --height 1350 --out out/demo/proxy.png --quad-out out/demo/proxy_quad.json

# 2. Detect, warp, blend, and write frame 0 plus a run manifest.
uv run --project ../.. python -m tools.video_edit run \
  --proxy out/demo/proxy.png \
  --texture paper_do_nhung_close.jpg \
  --out-dir out/demo \
  --proxy-kind synthetic-fixture \
  --debug
```

With a real generated proxy, only step 2 changes: point `--proxy` at it and set
`--proxy-kind provided`.

Other commands:

```bash
python -m tools.video_edit doctor          # versions, SAM 2 availability
python -m tools.video_edit corners --image proxy.png --overlay corners.png
python -m tools.video_edit watermark --help   # lift a static corner watermark out
python -m tools.video_edit proxy --help
```

## Video

The same architecture applied per frame, which changes two things: the surface
moves, and a held sheet usually runs off the frame edge.

```bash
uv run --project ../.. python -m tools.video_edit video \
  --video Girl_presenting_red_paper_20261018230134.mp4 \
  --texture paper_do_nhung_close.jpg \
  --out-dir out/video \
  --detect saturated --s-min 150 \
  --texture-scale 1.0
```

Frames are written as PNGs and encoded with ffmpeg, which copies the source
audio across and avoids OpenCV's lossy writer.

### Clipping, and why the quad is rebuilt

A sheet held at the edge of frame has corners sitting *on* the frame border, so
the detected quad is cut short. Stretching the texture into that short quad
would squeeze the grain, and the squeeze would change whenever the clip changed
— visible breathing of the surface.

The sheet is rigid, so its in-plane width/height ratio is measured once across
the frames where it is fully visible (0.756 on the clip above, stable to two
decimals), and each frame's clipped side is rebuilt from the reliable edge plus
that ratio. 206 of 240 frames on that clip are rebuilt. Scale is then constant
for the whole shot, which is what makes the result hold still. `--no-aspect-stabilise`
turns this off for comparison.

### Occlusion

The video mask is the authoritative silhouette, independent of the perspective
quad. Texture is reflected beyond the finite warp patch wherever necessary to
cover that silhouette. Intersecting it with the approximate quad previously left
smooth strips during movement, producing a false second-sheet edge. Only the
largest saturated connected region is used, excluding lips and jewellery while
preserving finger holes. The quad still controls perspective; this is not a
guarantee of physically exact grain tracking on a bending sheet.

Corrected render for this clip: `out/video-fixed/result.mp4`. Render settings:
`--mask-kernel 3 --mask-dilate 0 --edge-feather 0.8` (other settings as above).

Superseding render: `out/video-material-mask/result.mp4`. The user's screenshot
identified a connected neck-shadow spill at frame 32 (1.33 s). Saturation and
connected-component selection alone did not exclude it. The mask now also
requires hue within 4 OpenCV hue units of the product's dominant hue and value
at least 55% of its median value (and at least `v_min`). Components are selected
again after that test. This assumes a single-colour surface and can reject very
deep product shadows. Feathering stays inward, and morphology cannot add pixels
outside the material test. A source-video regression checks the independently
identified neck region, not just agreement with our own generated mask.
`out/video-material-mask/screenshot-before-after.png` compares the reported
frame against the new encoded output. Rendering uses the settings above except
`--edge-feather 1.0 --crf 14`.

Fingers holding the sheet are *over* the surface, so pasting the whole quad
would paint them out. Coverage is intersected with a colour mask
(`--mask-s-min`, default 150): the sheet is strongly saturated, skin is not, so
whatever overlaps stays on top. `--no-occlusion` pastes the full quad.

### Video-specific parameters

Newest render: `out/video-edge-fit/result.mp4`. The reported 4–5 s jitter
was a geometry error, not merely high-frequency corner noise: the moving hand
was mistaken for the bottom-right corner, shortening the right edge to about
440 px. Saturated-video planning now fits the longest visible straight boundary
segments and intersects those lines before reconstruction and smoothing. This
extrapolates the paper corner behind fingers instead of anchoring to a finger.
The corrected right edge is 501–510 px over frames 96–120. Straight-edge fitting
succeeded on 237/240 frames; other frames retain the polygon fallback. The
silhouette/material and inward-feathering rules are unchanged. Tests include
an artificial occluded corner and the source-video frames 96–120.
`out/video-edge-fit/comparison-3.5-5.5-before-left-after-right.mp4` compares the
previous smoothed render (left) against the edge-fitted render (right).

Previous render: `out/video-stable/result.mp4`. Texture mapping uses an
11-frame robust, centred quadratic fit to the corner trajectories and one
fixed UV canvas (386×509 for this shot), rather than rebuilding the native-scale
patch each frame. The per-frame material mask remains independent, retaining
the neck-spill fix. This reduces mapping jitter; it does not stabilize the
original AI video's physical paper edges or guarantee exact material tracking
through bending. One continuous shot is assumed (split at cuts first).
`--motion-window 1` disables trajectory filtering. This render uses
`--mask-kernel 3 --mask-dilate 0 --edge-feather 1.0 --crf 14`.
`out/video-stable/comparison-before-left-after-right.mp4` is a magnified
three-second texture comparison (previous on the left, revised on the right).

| Parameter | Default | Effect |
| :--- | :--- | :--- |
| `--mask-s-min` | `150` | Saturation floor for the occlusion mask. Raise if a hand is being painted over, lower if the surface edge is left behind. |
| `--mask-kernel` / `--mask-dilate` | `7` / `1` | Clean-up and growth of that mask. |
| `--no-occlusion` | off | Paste the whole quad, ignoring overlap. |
| `--no-aspect-stabilise` | off | Use the raw clipped quad. |
| `--start` / `--limit` | `0` / — | Process a slice, for inspecting before committing to a render. |
| `--crf` / `--preset` | `16` / `slow` | x264 quality and speed. |
| `--skip-encode` | off | Write frames and manifest only. |

Detected quads are held over from the previous frame when detection fails, so a
single bad frame cannot flicker.

## Watermark

| Policy | Official workflow |
| :--- | :--- |
| Backend | [Allen Kuo's VeoWatermarkRemover](https://github.com/allenk/VeoWatermarkRemover), pinned to [v0.6.5-demo](https://github.com/allenk/VeoWatermarkRemover/releases/tag/v0.6.5-demo). |
| Installation | `uv run python -m tools.video_edit watermark-install` downloads the platform release, verifies its pinned SHA256, and installs under ignored `.bin/`. No downloads happen during rendering. macOS Universal and Linux/Windows x64 are supported. |
| Run from repository root | `uv run python -m tools.video_edit watermark --video INPUT.mp4 --out-dir NEW_OUTPUT_DIRECTORY` |
| Outputs | `result.mp4`, `backend.log`, `manifest.json` with hashes, engine options, and reported skips. Existing results and source media are never overwritten. |
| Scope | Visible Gemini/Veo watermarks only; does not remove invisible SynthID. Process original footage before texture replacement or repeated encoding. |
| Retired | The custom watermark algorithms and their old method/mask/slice flags have been removed. Texture compositing and its blend modes remain unchanged. |
| Upstream trust | Release executables are unsigned previews. Installation checks the published release digest, not an independent security audit. Review the upstream source and [license](https://github.com/allenk/GeminiWatermarkTool/blob/main/LICENSE). No OS security bypass is performed. |

```text
Verified install -> Original video -> Calibrated removal -> Inspect skips/edges -> Publish
                                                               |
                                                        Repair PNG frames
```

| Option | Default | Purpose |
| :--- | :--- | :--- |
| `--backend` / `VEO_WATERMARK_BIN` | Pinned local installation, then PATH | Override executable location. Override builds are identified by their actual binary hash; the pinned release link is a reference. |
| `--cpu` / `--no-cpu` | CPU | Matches the tested macOS workflow; opt into GPU if appropriate. |
| `--region x,y,w,h` | Auto-detect | Force a known watermark location. |
| `--alpha` | Backend estimation | Set constant calibrated intensity, 0.05–3. |
| `--sigma` | Backend setting | Denoise strength, 1–150. |
| `--legacy` | Off | Older watermark profile, or V1 small-template frame repair. |
| `--ml` | Off | Opt into upstream ML intensity estimation. |
| `--force` | Off | Bypass detection for a known mark; mainly individual PNG repairs. |
| `--image FRAME.png` | Video input | Use the same engine for an extracted frame; writes `result.png` instead of MP4. |

| Repair and verification | Required action |
| :--- | :--- |
| Skipped frames | Inspect `backend.log`; a successful exit does not mean every frame was cleaned. No custom fill fallback runs. |
| Tested single-frame repair | `uv run python -m tools.video_edit watermark --image FRAME.png --legacy --region 576,1136,48,48 --alpha 0.63 --sigma 20 --force --out-dir NEW_FRAME_DIRECTORY` — these values apply to the tested Tet clip, not every video. |
| Finish | Replace only confirmed problem frames and reassemble with original audio. Check frame count, FPS, duration, colour and audio; inspect moving boundaries and playback. |
| Local evidence | `local/paper-ink-product/out/tet-veo-calibrated/` holds the automatic trial, frame-131 repair, final video, comparison and provenance. Sampled frames were substantially cleaner than the retired overlay; perfect recovery is not guaranteed. |

## Outputs

| File | What it is |
| :--- | :--- |
| `frame0.png` | The composite. Feed this to image-to-video as frame 0. |
| `mask.png` | Coverage of the warped texture, white inside the product face. |
| `overlay.png` | The proxy with the detected quad and corner coordinates drawn on. |
| `quad.json` | The four corners and how they were found. Reusable via `--corners-file`. |
| `manifest.json` | Input hashes and sizes, detection, every parameter, stats, provenance, limits. |
| `debug/*.png` | `tiled`, `warped`, `illumination`, written with `--debug`. |

## How the blend works

`--blend-mode shading` (the default) does three things:

1. Takes luminance from the proxy and blurs it into a smooth illumination
   field (sigma derived from the card size, or `--lighting-sigma`).
2. Normalises that field to a mean of 1 inside the product face, then clamps it
   to `--max-darken` / `--max-lighten`.
3. Multiplies the warped texture by that field, per channel, preserving
   chromaticity. `--shading-strength` scales the effect, `0` disables it.

Because the field is smooth, the proxy's broad lighting and shadow gradients
transfer while the texture's own grain is left alone. `multiply`, `screen`,
`overlay`, `soft_light`, `hard_light` and `luminosity` are also available for
comparison; Photoshop-style `soft_light` follows the W3C formula.

## Parameters that matter

| Parameter | Default | Effect |
| :--- | :--- | :--- |
| `--texture-scale` | `1.0` | Pixel size of one tile. `1.0` keeps native scale: grain is repeated, never blown up. |
| `--interpolation` | `lanczos4` | Warp resampling. On a typical card, bilinear keeps roughly 45% of the source's high-frequency energy and Lanczos roughly 96%. |
| `--grain-angle` | `0.0` | Rotates the texture before tiling, for directional grain. |
| `--texture-flatten` | derived | Removes the close-up's own vignette so repeated tiles do not repeat a lighting gradient. `0` disables. |
| `--texture-gain` | `1.0` | Brightness of the texture before blending. |
| `--no-tile` | off | Stretches one tile across the face instead of repeating it. |
| `--edge-feather` / `--inset` | `1.5` / `0.0` | Anti-aliases the paste edge; `--inset` shrinks it away from the cut edge. |
| `--detect` | `saturated` | `saturated`, `edges`, `bright`, or `sam2`. |
| `--corners` / `--corners-file` | — | Manual corners: `'x,y;x,y;x,y;x,y'`. Bypasses detection. |

## Detection

`detect_quad` segments (by saturation, edges, or brightness), closes the mask,
takes the largest region and fits a four-point polygon, falling back to a
minimum-area rotated rectangle. It reports a score: the fitted quad's area
divided by the region's area, so `1.0` means a clean quadrilateral. Background
sets that are near-neutral and a card that is saturated are the easy case.

SAM 2 is supported but optional and import-guarded:

```bash
uv pip install torch sam2 --index-url https://download.pytorch.org/whl/cpu
python -m tools.video_edit run --detect sam2 \
  --sam2-checkpoint /path/to/sam2.1_hiera_small.pt \
  --sam2-point 540,700 ...
```

It segments from a prompt point inside the card, then fits a quad to the mask.

## What is and is not preserved

Stated plainly, because the difference matters:

- **Not generated:** the product's surface pixels. They come from the texture
  photo. Nothing invents fibres inside the face.
- **Geometrically transformed:** the perspective warp resamples the texture
  with Lanczos, so pixels are not bit-identical to the source file. At a
  near-1:1 card, measured high-frequency energy is retained at about 93%
  (437 of 468 Laplacian variance on `paper_do_nhung_close.jpg`).
- **Brightness-modulated:** the lighting blend scales the texture, so what is
  preserved is relative grain, not absolute exposure.
- **Outside the quad:** untouched proxy pixels. Hands, background and shadow
  are exactly the proxy's.
- **Requires a flat, visible face.** A curved or occluded surface needs a
  different mask and a mesh, not a quad.
- **On video, re-encoding costs grain.** The output is H.264, which smooths fine
  detail; `--crf 16` keeps most of it, and a lossless intermediate
  (`--skip-encode`) keeps all of it.
- If the proxy is itself a smoothed photograph of the product, its baked-in
  lighting is applied on top of the texture's. Use `--shading-strength` or
  `--max-darken` / `--max-lighten` to tame that; the `shading` mode assumes a
  proxy whose lighting is the lighting you want.

## Tests and demo artifacts

Run from the repository root:

```bash
uv run python -m unittest discover -s tools/video_edit/tests -t .
```

| Tests | Coverage |
| :--- | :--- |
| Texture/still | Corner ordering, detection against ground truth, mirrored tiling, blend modes, lighting, masks, determinism and CLI. |
| Video | Aspect measurement, quad reconstruction, occlusion, planning, rendering and source-video regressions when local media is present. |
| Official watermark wrapper | CLI routing, verified installation, explicit frame repair, input/output protection, backend failures, manifests and skipped-frame warnings. Unit tests mock the external engine; they do not certify removal quality. |
| Removed | Tests specific to retired custom watermark algorithms, including the failing unmix reconstruction tests. They were not weakened or reclassified as passing. |

Generated examples remain under `local/paper-ink-product`, in `out/demo/`, `out/demo2/`, `out/video/` and
`out/video-clean/`:

- `out/demo/` — synthetic fixture proxy at 1080×1350 (vertical), real Nhung đỏ
  close-up, `--debug`. Manifest records `proxy_kind: synthetic-fixture`.
- `out/demo2/` — `--mode smooth` on the owner's own `paper_do_nhung.jpg`, then
  the same close-up composited back. Demonstrates the no-AI path.
- `out/video/` — the held-sheet clip, all 240 frames re-surfaced. `frames/`
  holds the composited PNGs, `manifest.json` the per-frame detection record.
- `out/video-clean/` — historical output from the retired watermark backend,
  retained as an artifact, not an example of the official workflow.

These are build outputs, not product photos, and `local/` is not tracked by git.
