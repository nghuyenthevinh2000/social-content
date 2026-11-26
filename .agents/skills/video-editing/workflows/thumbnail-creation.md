---
name: thumbnail-creation
description: End-to-end workflow for creating high-contrast vertical (9:16) or landscape (16:9) video thumbnails from video keyframes, Playwright HTML/Canvas compositions, or generated artwork.
---

# Thumbnail Creation Workflow

```text
Source MP4 / Concept -> Pick Approach -> Compose & Render -> Inspect Safe Zones -> Export PNG/JPG
                          ├─ Keyframe + Overlay (ffmpeg / Playwright)
                          ├─ Pure HTML/Canvas Card (Playwright)
                          └─ Custom Artwork (image-generator + text overlay)
```

## Platform Dimensions & Safe Zones

| Platform / Format | Dimensions | Center / Profile-Grid Safe Zone | Avoid |
|---|---|---|---|
| **Reels / TikTok / Shorts Cover** | `1080 × 1920` (`9:16`) | `x: 90..990`, `y: 420..1500` (centered `1:1` / `4:5` crop for profile grid) | Top `y < 220` (header), bottom `y > 1540` (captions/UI), right `x > 920` (action icons) |
| **YouTube Thumbnail** | `1280 × 720` (`16:9`) | `x: 80..1200`, `y: 70..650` | Bottom-right corner (`x > 1040, y > 600` timestamp badge) |
| **Facebook / IG Feed Cover** | `1080 × 1350` (`4:5`) | `x: 80..1000`, `y: 120..1230` | Edge-touching headlines or small body text |

## Execution Stages

| Stage | Action | Command / Tool | Gate |
|---|---|---|---|
| **1. Source & Hook** | Select 1–2 focal elements (hero frame, diagram, or face) and a 3–6 word hook title. | `ffprobe` / `script.txt` | Hook is readable at mobile thumbnail scale (`<= 6` words). |
| **2. Extract Candidate Frames** | Pull 3–5 candidate frames from the rendered MP4 or `render.mjs stills`. | `ffmpeg -y -v error -ss <T> -i <VIDEO.mp4> -vframes 1 <OUT>/cand_<T>.png` | Sharp, expressive frame with zero motion blur or mid-blink. |
| **3. Compose Thumbnail** | Render via Playwright (`1080×1920` or `1280×720`) with `Montserrat` (`Cap`) 700, dark stroke/scrim, and brand palette; or generate base art via `image-generator` subagent. | `node render_thumb.mjs` or `ffmpeg` overlay | High text-to-background contrast (`>= 4.5:1`), clean Vietnamese diacritics. |
| **4. Visual Inspection** | Inspect the rendered thumbnail directly at full and zoomed-out glance. | `read_file` on `thumbnail.png` | Zero clipped glyphs, zero UI-zone overlap, focal point clear in 1 second. |
| **5. Export & (Optional) Embed** | Save `thumbnail.png` (or `cover.jpg` under `< 2 MB` for platform upload); optionally attach as MP4 cover stream. | `ffmpeg -y -i <VIDEO.mp4> -i cover.jpg -map 0 -map 1 -c copy -disposition:v:1 attached_pic <OUT.mp4>` | Valid image dimensions and file size for target platform. |

## Rules & Taste

| Rule | Requirement |
|---|---|
| **Grid-First Framing** | For `9:16` reels, keep the main headline and focal visual inside the center `1080 × 1080` (`y: 420..1500`) so it never crops awkwardly on profile grids. |
| **Max 2 Visual Elements** | Pair one clear focal visual (chart, diagram, face, or scene) with one short hook headline + optional 2–3 word kicker pill. |
| **Typography & Diacritics** | Use `@fontsource/montserrat` (`700`/`800`) with `lineHeight >= 1.15` and top padding so Vietnamese stacked diacritics (`ế`, `ồ`, `ậ`, `ữ`) never clip. |
| **No Clutter** | Never duplicate native platform badges, timestamps, or fake play buttons. |
