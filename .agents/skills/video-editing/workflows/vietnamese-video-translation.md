---
name: vietnamese-video-translation
description: End-to-end workflow for downloading source videos, extracting hardcoded subtitles via computer vision, building dynamic ASS masking overlays, and encoding Vietnamese translations.
---

# Vietnamese video translation workflow

## Pipeline flow

```text
URL -> yt-dlp -> ffprobe -> sub_scanner.py -> Translation -> ass_builder.py -> ffmpeg Preview -> ffmpeg Encode -> Verified MP4
```

## Execution stages

| Stage | Goal | Command or Action | Artifacts |
|---|---|---|---|
| 1. Download | Fetch source video at highest quality | `uv run yt-dlp -o "local/<project>/source.mp4" -f "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best" "<URL>"` | `source.mp4` |
| 2. Probe | Extract resolution, FPS, duration, audio | `ffprobe -v error -select_streams v:0 -show_entries stream=width,height,r_frame_rate,duration -of json local/<project>/source.mp4` | Stream metadata |
| 3. Scan | Detect subtitle segments, bounds, and preview crops | `uv run python .agents/skills/video-editing/scripts/sub_scanner.py --video local/<project>/source.mp4 --out-dir local/<project>/sub_scan --roi "968:1010,400:1520"` | `segments.json`, `seg_*.png` |
| 4. Translate | Map segment IDs to context-aware Vietnamese text | Author `translations.json` mapping segment ID to Vietnamese lines with register, pronouns, and style rules | `translations.json` |
| 5. Build ASS | Generate vector BoxBg mask and styled text | `uv run python .agents/skills/video-editing/scripts/ass_builder.py --segments local/<project>/sub_scan/segments.json --translations local/<project>/translations.json --out local/<project>/overlay.ass --res-x 1920 --res-y 1080` | `overlay.ass` |
| 6. Preview | Spot-check representative frames across cuts | `ffmpeg -y -i local/<project>/source.mp4 -ss <SECONDS> -vf "subtitles='local/<project>/overlay.ass'" -vframes 1 -q:v 2 local/<project>/preview_<NAME>.jpg` | `preview_*.jpg` |
| 7. Encode | Burn subtitles with zero audio re-encoding | `ffmpeg -y -i local/<project>/source.mp4 -vf "subtitles='local/<project>/overlay.ass'" -c:v libx264 -crf 18 -preset fast -pix_fmt yuv420p -c:a copy -movflags +faststart local/<project>/result.mp4` | `result.mp4` |
| 8. Verify | Check audio-video duration match and quality | `ffprobe -hide_banner local/<project>/result.mp4 && open local/<project>/result.mp4` | QC pass |

## Subtitle style reference

| Style | Purpose | Font & Size | Alignment & Position | BoxBg Mask |
|---|---|---|---|---|
| `BoxBg` | Opaque layer-0 vector mask covering original text | Arial 36pt (`&H00100E0C`), Outline 8 | `\an7\pos(x,y)` vector rectangle `m 0 0 l w 0 w h 0 h` | Self |
| `ViSub` | Standard bottom dialogue translation | Arial 35pt Bold, White, Outline 2.5, Shadow 1 | `\an5\pos(center_x, 989)` | Yes (dynamic width) |
| `ViLyric` | Stressed hook lyrics (placed below characters) | Arial 33pt Italic, White, Outline 2.5, Shadow 1 | `\pos(center_x, 980)` (or 930 on dialogue overlap) | Optional |
| `ViDialogueTop`| Top or floating dialogue | Arial 34pt Bold, White, Outline 2.5, Shadow 1 | `\pos(center_x, 960..995)` | Optional |
| `ViTitle` | Scene, location, or teaser cards | Arial 36pt Regular, White, Spacing 2.5, Outline 1.2 | `\pos(x, y)` with `\fad(in,out)` for cinematic pacing | Two-phase cut matching |

## Lyric filtering and consistency policy

| Content Type | Inclusion Rule | Styling & Positioning | Example |
|---|---|---|---|
| Spoken Dialogue | Always translate and mask original text | Style `ViDialogue`, bottom center (`y=980`) | "Harry. Cậu đến muộn đấy." |
| Title / Key Card | Always mask with vector box and translate | Style `ViTitle`, target position, matching `BoxBg` | "MÙA ĐÔNG BÊN EM" |
| Stressed Lyric Hook | Translate only climax, drop, or hook lines | Style `ViLyric` (italic), bottom screen (`y=980` or `930`) | "...Cho đến khi anh tìm thấy em" |
| Background Verse / Filler | Omit entirely to avoid visual clutter and flicker | None (do not display or mask) | Minor humming, bridge build-up |

## Visual preservation and immersion rules

| Rule | Requirement | Technical Implementation | Failure Mode Avoided |
|---|---|---|---|
| Character Protection | Never place subtitles over faces, bodies, or hair | Keep dialogue & lyrics at bottom (`y=980` standalone, `y=930` overlap) | Center text (`y=520`) obstructing character aesthetics |
| Atmospheric Pacing | Titles must not suddenly pop or snap onto screen | Use `\fad(1400..1800, 0)` for slow emergence on quiet/black scenes | Abrupt jarring text entry breaking scene mood |
| Cut-Accurate Masking | Match mask background color to exact scene cuts | Split into black mask phase (`BoxBgBlack`) and scene mask (`BoxBgSky`) | Blue box popping onto black void |
| Complex Background Clean | Avoid solid boxes over moving/textured backgrounds | Use ffmpeg `delogo=x:y:w:h:enable='between(t1,t2)'` filter | Dark boxes floating over trees or courtyard arches |
| PTS-Preserving Seeking | Maintain exact ASS subtitle timestamps during preview | Always place seek `-ss <time>` **after** `-i source.mp4` | Subtitles vanishing or desyncing due to PTS reset |

## Parameters and tuning

| Parameter | Default | Tuning guidance |
|---|---|---|
| `--roi` | `968:1010,400:1520` | Measure from extracted sample frame. Crop tightly around original subtitle height. |
| `--min-pixels` | `60` | Lower to 40 for tiny fonts; raise to 100 to eliminate noisy background edges. |
| `--iou-thresh` | `0.35` | Lower threshold triggers segment cuts on subtle text shifts (rapid dialogue). |
| `bg_color` | `&H00100E0C` | Match video letterbox or dark gradient. Use `&H00000000` for pure black letterbox. |
| `box_pad_x` | `18` px | Extends mask left/right past both original text and new Vietnamese text. |
| `box_pad_y` | `4` px | Expands mask vertically; combined with Outline 8 gives clean feathering. |
