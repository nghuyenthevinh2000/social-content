---
name: video-editing
description: >-
  Compose, crop, overlay, and encode video files using ffmpeg on macOS.
  Use when the user asks to: combine or overlay videos, crop a face/person
  into a circular overlay, remove audio noise, sync multiple video tracks,
  extract frames, detect faces, or produce a composite social-media clip.
  Covers portrait video quirks (HEVC/Dolby Vision rotation, 10-bit color),
  variable-frame-rate sync bugs, YuNet face detection, and uv-based Python
  tooling for preprocessing steps.
---

# video-editing: Composite Video Production with ffmpeg

## What this skill covers

End-to-end pipeline for producing composite social-media video clips:

1. **Probe** both source videos (codecs, real resolution, frame rate, rotation)
2. **Detect faces** (OpenCV YuNet) to compute a face-centered crop
3. **Build the ffmpeg filter graph** (frame-rate normalization, crop, circle mask, overlay, audio map)
4. **Encode** the final output (`libx264 -crf 18`, `aac 192k`, `yuv420p`)
5. **Verify** duration, resolution, and visual correctness via frame extraction

---

## Environment prerequisites

| Tool | Check command | Install |
|---|---|---|
| ffmpeg ≥ 6.0 | `ffmpeg -version` | `brew install ffmpeg` |
| uv | `uv --version` | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Python venv | created via `uv venv` | see §Face Detection |

> [!IMPORTANT]
> Always use **uv** (not pip/virtualenv) for Python environment management.
> Never use system pip. Install packages with `uv pip install` into a uv-created venv.

---

## Step 1 — Probe source videos

Always probe both inputs before writing any filter graph. Misread metadata causes every bug downstream.

```bash
ffprobe -v quiet -show_streams -show_format -of json INPUT.mov 2>&1 | python3 -m json.tool
```

Critical fields to check:

| Field | Where to find it | Why it matters |
|---|---|---|
| `codec_name` | `streams[0].codec_name` | HEVC needs special handling (10-bit, Dolby Vision) |
| `width` × `height` | `streams[0].width/height` | May be *wrong* for portrait iPhones — see §Portrait trap |
| `r_frame_rate` | `streams[0].r_frame_rate` | May claim 120fps but content is ~18fps — see §VFR trap |
| `duration` | `format.duration` | Background vs speech clip lengths must be reconciled |
| `side_data` rotation | `streams[0].side_data_list` | iPhones encode portrait as landscape + rotate tag |

---

## ⚠️ Portrait iPhone Video Trap

iPhones (iPhone 15+) record portrait video as a **landscape-coded stream** with a rotation applied via a display matrix in the stream's side data.

- Raw metadata reports: `1920×1080` (landscape)
- Actual decoded frame: `1080×1920` (portrait) — ffmpeg auto-rotates

**How to confirm true decoded dimensions:**

```bash
ffmpeg -i speech_vn.MOV -frames:v 1 -vf showinfo -f null - 2>&1 | grep "n:0"
# Look for: w:1080 h:1920
```

> [!CAUTION]
> **Never** assume `width × height` from `ffprobe` metadata for iPhone videos.
> Always confirm true decoded frame size with `showinfo` before writing any crop filter.
> All crop coordinates must be based on the **decoded** (rotated) dimensions, not raw stream metadata.

**Crop filter coordinate system** for a true `1080×1920` portrait frame:

```
X axis: 0 → 1080 (left → right)
Y axis: 0 → 1920 (top → bottom)

Center horizontal crop:  crop=1080:1080:0:420       (square, top-aligned)
Face-centered crop:       crop=1080:1080:<cx-540>:<cy-540>  (see §Face Detection)
```

---

## ⚠️ Variable Frame Rate (VFR) Sync Trap

Background screen recordings often declare `120fps` (or high tbr) in container metadata but contain actual content at ~18fps (variable/sparse). This causes **catastrophic timing bugs** in overlay filter graphs:

- Overlay disappears too early (e.g. ends at 18s instead of 47s)
- Circle overlay duration doesn't match expected speech clip length
- `eof_action` on overlay filter fires at wrong time

**Fix: always normalize both inputs to a stable CFR before overlay:**

```
[0:v] fps=30,settb=AVTB [bg];
[1:v] fps=30,settb=AVTB, ... [circle];
[bg][circle] overlay=... [out]
```

> [!WARNING]
> Insert `fps=30,settb=AVTB` on **every** input branch — both background and speech —
> before any overlay, scale, or crop filter that must stay time-synced.
> `fps=30` is the normalized target; adjust if source genuinely needs higher fps.

---

## ⚠️ Dolby Vision / 10-bit HEVC Color Trap

iPhone videos with Dolby Vision (`HEVC Main10`, `yuv420p10le`, `bt2020nc/bt2020`) may render with washed-out or shifted colors if you feed them raw into an 8-bit output pipeline.

For face detection purposes this rarely matters (detection still works on color-shifted frames). For the final composite:

- The `format=yuva420p` filter in the circle mask branch + final `-pix_fmt yuv420p` encoding handles the 10-bit → 8-bit conversion implicitly via ffmpeg's auto color conversion.
- If colors look obviously wrong in output, add explicit tonemapping: `zscale=t=linear,tonemap=reinhard,zscale=t=bt709` before `format=yuv420p`.

---

## Step 2 — Face Detection (OpenCV YuNet)

> [!NOTE]
> OpenCV 5.x removed `CascadeClassifier`. Use `FaceDetectorYN` (YuNet model) instead.
> Haar cascades (`cv2.CascadeClassifier`) only work on OpenCV ≤ 4.x.

### Setup

```bash
# Create isolated venv with uv
uv venv /tmp/facedetect/.venv

# Install packages into venv
uv pip install opencv-python-headless numpy --python /tmp/facedetect/.venv/bin/python3

# Download YuNet model (~230KB)
curl -L -o /tmp/facedetect/face_detection_yunet_2023mar.onnx \
  "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
```

### Extract frames for detection

Use ffmpeg to extract frames (1fps) from the speech video, respecting decoded portrait orientation:

```bash
ffmpeg -y -i speech_vn.MOV \
  -vf "fps=1" \
  -frames:v 10 \
  /tmp/facedetect/speech_frame_%02d.png
```

Verify extracted frame dimensions (must be 1080×1920 for portrait iPhone):
```bash
python3 -c "import cv2; img=cv2.imread('/tmp/facedetect/speech_frame_01.png'); print(img.shape)"
# Expected: (1920, 1080, 3)
```

### Face detection script

The bundled script lives at `scripts/detect_face_crop.py` (relative to this skill folder).
Use it instead of writing an ad-hoc script:

```bash
SKILL_DIR="$REPO_ROOT/.agents/skills/video-editing"

/tmp/facedetect/.venv/bin/python3 "$SKILL_DIR/scripts/detect_face_crop.py" \
    --frame-dir  /tmp/facedetect \
    --frame-glob "speech_frame_*.png" \
    --model      /tmp/facedetect/face_detection_yunet_2023mar.onnx \
    --frame-w    1080 \
    --frame-h    1920 \
    --crop-size  1080
```

All flags are optional — defaults match the extraction paths above. Sample output:

```
  speech_frame_01.png: 1080x1920  → bbox=(298,757,395,524)  center=(495,1019)  conf=0.891
  ...

=== CROP RESULT (weighted average across 10 detection(s)) ===
Frame size   : 1080x1920
Face center  : (488, 1011)
Crop origin  : x=0, y=471
Crop size    : 1080x1080

ffmpeg filter : crop=1080:1080:0:471
```

The last line is machine-parseable — capture it in a shell variable:

```bash
CROP=$(/tmp/facedetect/.venv/bin/python3 "$SKILL_DIR/scripts/detect_face_crop.py" \
    --quiet | grep "^ffmpeg filter" | awk '{print $NF}')
# CROP="crop=1080:1080:0:471"
```

**Useful flags:**

| Flag | Default | Purpose |
|---|---|---|
| `--frame-dir` | `/tmp/facedetect` | Directory with extracted PNG frames |
| `--frame-glob` | `speech_frame_*.png` | Glob pattern to match frames |
| `--model` | `/tmp/facedetect/face_detection_yunet_2023mar.onnx` | YuNet model path |
| `--frame-w` | `1080` | True decoded frame width |
| `--frame-h` | `1920` | True decoded frame height |
| `--crop-size` | `1080` | Square crop side (before scaling to circle diameter) |
| `--score-threshold` | `0.5` | Confidence threshold — lower if no face found |
| `--quiet` | off | Print only the final `ffmpeg filter :` line |

---

## Step 3 — Build the ffmpeg Filter Graph

### Full composite pipeline template

```bash
ffmpeg -y \
  -i "$BACKGROUND"  \           # input 0: background video
  -i "$SPEECH"      \           # input 1: speech/overlay video
  -filter_complex "
    [0:v] fps=30,settb=AVTB [bg];

    [1:v] fps=30,settb=AVTB,
          crop=<CROP_W>:<CROP_H>:<CROP_X>:<CROP_Y>,
          scale=<CIRCLE_D>:<CIRCLE_D>,
          format=yuva420p,
          geq=lum='p(X,Y)':a='if(lte(hypot(X-<R>,Y-<R>),<R>),255,0)' [circle];

    [bg][circle] overlay=W-w-<MARGIN>:H-h-<MARGIN>:eof_action=pass [out]
  " \
  -map "[out]" \
  -map "1:a:0" \
  -c:v libx264 -crf 18 -preset medium -pix_fmt yuv420p \
  -c:a aac -b:a 192k \
  -movflags +faststart \
  "$OUTPUT"
```

### Parameter substitution table

| Placeholder | Description | Example value |
|---|---|---|
| `<CROP_W>:<CROP_H>` | Square crop size in source portrait pixels | `1080:1080` |
| `<CROP_X>:<CROP_Y>` | Crop origin from face detection (§Step 2) | `0:471` |
| `<CIRCLE_D>` | Circle diameter in output pixels (~30% of bg width) | `874` |
| `<R>` | Radius = `CIRCLE_D / 2` | `437` |
| `<MARGIN>` | Margin from bottom-right edge | `60` |

### Circle diameter sizing guide

| Background width | Recommended circle diameter (~30%) |
|---|---|
| 1920px | ~576px |
| 2560px | ~768px |
| 2912px | ~874px |
| 3840px | ~1152px |

### Audio mapping options

```bash
# Use speech_vn audio only (most common for talking-head overlays):
-map "1:a:0"

# Use background audio only:
-map "0:a:0"

# Mix both (equal volume):
-filter_complex "...; [0:a][1:a] amix=inputs=2:duration=first [audio]" -map "[audio]"
```

### Duration control

| Goal | How |
|---|---|
| Full background length, circle disappears when speech ends | `eof_action=pass` on overlay (default behavior) |
| Trim output to speech length | Add `-t <speech_duration>` after `-map "[out]"` |
| Loop speech video to fill background | `-stream_loop -1 -i "$SPEECH"` |

---

## Step 4 — Verify Output

### ffprobe check
```bash
ffprobe -v quiet \
  -show_entries format=duration,size \
  -show_entries stream=width,height,codec_name,r_frame_rate \
  -of json OUTPUT.mp4
```

Expected for a healthy composite:
- `codec_name`: `h264` (video), `aac` (audio)
- `r_frame_rate`: `30/1`
- `duration`: matches background length
- `width/height`: matches background resolution

### Visual frame extraction

```bash
# Extract frames at key timestamps for visual review
for T in 5 15 25 40; do
  ffmpeg -y -ss $T -i OUTPUT.mp4 -frames:v 1 /tmp/verify_${T}s.jpg 2>/dev/null
done
```

Review each frame:
- **Within speech clip duration**: face should be visible and well-centered in circle
- **After speech clip ends**: circle should be absent, only background visible
- **Face position**: eyes/nose should be roughly centered in the circle, not clipped

---

## Common Bugs & Fixes

### Bug: Circle disappears too early / video ends at wrong time

**Cause**: Background video has VFR mismatch (declared 120fps, actual ~18fps).  
**Fix**: Add `fps=30,settb=AVTB` on both `[0:v]` and `[1:v]` branches before overlay. See §VFR Trap.

### Bug: Face is off-center in circle

**Cause**: Crop was based on raw metadata dimensions, not true decoded dimensions.  
**Fix**: Run `showinfo` to get true frame size → re-run face detection → recompute crop origin.

### Bug: `cv2.CascadeClassifier` AttributeError

**Cause**: OpenCV 5.x removed Haar cascade classifiers from top-level namespace.  
**Fix**: Use `cv2.FaceDetectorYN_create()` with the YuNet `.onnx` model. See §Face Detection.

### Bug: `ModuleNotFoundError: No module named 'cv2'`

**Cause**: Running Python from the wrong interpreter (system Python, not venv).  
**Fix**: Always invoke venv Python explicitly: `/tmp/facedetect/.venv/bin/python3 script.py`

### Bug: Washed-out / gray colors in circle overlay

**Cause**: 10-bit HEVC Dolby Vision source feeding into 8-bit yuv420p pipeline without conversion.  
**Fix**: Add `zscale=t=linear,tonemap=reinhard,zscale=t=bt709` before `format=yuva420p` in the speech branch, or rely on ffmpeg's implicit 10→8-bit conversion (usually sufficient).

### Bug: Audio from background appears in output despite `-map "1:a:0"`

**Cause**: Missing explicit audio stream exclusion — ffmpeg may auto-select both.  
**Fix**: Add `-an` to the background input or use explicit `-map 1:a:0` *and* verify with `ffprobe -show_streams OUTPUT.mp4`.

---

## Quick Reference Cheat-Sheet

```bash
# 1. Probe video (true dimensions, fps, duration)
ffprobe -v quiet -show_streams -show_format -of json INPUT.mov

# 2. Confirm decoded portrait frame size
ffmpeg -i INPUT.MOV -frames:v 1 -vf showinfo -f null - 2>&1 | grep "n:0"

# 3. Setup face detection env
uv venv /tmp/facedetect/.venv
uv pip install opencv-python-headless numpy --python /tmp/facedetect/.venv/bin/python3
curl -L -o /tmp/facedetect/face_detection_yunet_2023mar.onnx \
  "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"

# 4. Extract frames for detection
ffmpeg -y -i INPUT.MOV -vf fps=1 -frames:v 10 /tmp/facedetect/speech_frame_%02d.png

# 5. Run detection → get crop=W:H:X:Y
/tmp/facedetect/.venv/bin/python3 detect_face.py

# 6. Build composite (fill in CROP_X, CROP_Y, CIRCLE_D, MARGIN from above)
ffmpeg -y -i BG.mov -i SPEECH.MOV \
  -filter_complex "
    [0:v] fps=30,settb=AVTB [bg];
    [1:v] fps=30,settb=AVTB,crop=1080:1080:CROP_X:CROP_Y,scale=CIRCLE_D:CIRCLE_D,
          format=yuva420p,geq=lum='p(X,Y)':a='if(lte(hypot(X-R,Y-R),R),255,0)' [c];
    [bg][c] overlay=W-w-MARGIN:H-h-MARGIN:eof_action=pass [out]
  " \
  -map "[out]" -map "1:a:0" \
  -c:v libx264 -crf 18 -preset medium -pix_fmt yuv420p \
  -c:a aac -b:a 192k -movflags +faststart OUTPUT.mp4

# 7. Verify output
ffprobe -v quiet -show_entries format=duration -show_entries stream=width,height,codec_name -of json OUTPUT.mp4
for T in 5 15 25; do ffmpeg -y -ss $T -i OUTPUT.mp4 -frames:v 1 /tmp/frame_${T}s.jpg 2>/dev/null; done
```

---

## Step 3b — Add Background Music

To mix a background music track into the composite, add a third input and blend it with the voice audio.

```bash
ffmpeg -y \
  -i "$BACKGROUND" \
  -i "$SPEECH" \
  -i "$MUSIC" \
  -filter_complex "
    [0:v] fps=30,settb=AVTB [bg];

    [1:v] fps=30,settb=AVTB,
          crop=<CROP_W>:<CROP_H>:<CROP_X>:<CROP_Y>,
          scale=<CIRCLE_D>:<CIRCLE_D>,
          format=yuva420p,
          geq=lum='p(X,Y)':a='if(lte(hypot(X-<R>,Y-<R>),<R>),255,0)',
          fade=t=out:st=<FADE_START>:d=<FADE_DUR>:alpha=1 [circle];

    [bg][circle] overlay=W-w-<MARGIN>:H-h-<MARGIN>:eof_action=pass [out_v];

    [1:a] apad=whole_dur=<BG_DURATION> [voice_padded];
    [2:a] volume=<MUSIC_VOL> [music];
    [voice_padded][music] amix=inputs=2:duration=first [out_a]
  " \
  -map "[out_v]" \
  -map "[out_a]" \
  -c:v libx264 -crf 18 -preset medium -pix_fmt yuv420p \
  -c:a aac -b:a 192k \
  -movflags +faststart \
  "$OUTPUT"
```

### Music parameter reference

| Placeholder | Description | Example |
|---|---|---|
| `<MUSIC_VOL>` | Music volume relative to original (0.0–1.0) | `0.14` |
| `<BG_DURATION>` | Full background video duration in seconds | `47.833` |

### Music volume guide

| `volume=` | Effect |
|---|---|
| `0.05–0.08` | Barely audible, very subtle presence |
| `0.10–0.15` | Comfortable background ambience ✅ |
| `0.18–0.22` | Music is present but voice still leads |
| `0.30+` | Music competes with voice |

> [!IMPORTANT]
> Always use `apad=whole_dur=<BG_DURATION>` on the voice audio **before** mixing.
> The speech clip is typically shorter than the background video — without `apad`,
> `amix` stops at the end of the voice track, silencing the music early too.
> See §Bug: Music stops early below.

### Music fade out at end (optional)

To fade the music out over the last few seconds instead of cutting abruptly:

```bash
[2:a] volume=0.14, afade=t=out:st=<FADE_START>:d=<FADE_DUR> [music];
```

Example for a 47.83s video, 4-second fade starting at 43.8s:
```bash
[2:a] volume=0.14, afade=t=out:st=43.8:d=4 [music];
```

---

## Step 3c — Circle Overlay Fade-Out

To make the face circle dissolve smoothly instead of cutting off abruptly when speech ends, add `fade` with `alpha=1` to the circle branch:

```bash
[1:v] fps=30,settb=AVTB,
      crop=<CROP_W>:<CROP_H>:<CROP_X>:<CROP_Y>,
      scale=<CIRCLE_D>:<CIRCLE_D>,
      format=yuva420p,
      geq=lum='p(X,Y)':a='if(lte(hypot(X-<R>,Y-<R>),<R>),255,0)',
      fade=t=out:st=<FADE_START>:d=<FADE_DUR>:alpha=1 [circle];
```

| Parameter | Description | Example (32.9s speech, 2s fade) |
|---|---|---|
| `t=out` | Fade direction | always `out` |
| `st=<FADE_START>` | When fade begins in seconds | `30.9` (= 32.9 − 2) |
| `d=<FADE_DUR>` | Fade duration in seconds | `2` |
| `alpha=1` | Fades alpha channel (transparency), not to black | always `1` |

> [!TIP]
> Formula: `st = speech_duration − fade_duration`
> A 2-second fade feels natural. 1s is abrupt; 3s+ can feel sluggish.

Verify with frames at 3 timestamps:

```bash
# Replace ST with your st value, D with fade duration
ffmpeg -y -ss $((ST-1)) -i OUTPUT.mp4 -frames:v 1 /tmp/fade_before.jpg 2>/dev/null
ffmpeg -y -ss $(echo "$ST + $D/2" | bc) -i OUTPUT.mp4 -frames:v 1 /tmp/fade_mid.jpg 2>/dev/null
ffmpeg -y -ss $(echo "$ST + $D + 0.5" | bc) -i OUTPUT.mp4 -frames:v 1 /tmp/fade_after.jpg 2>/dev/null
# before: circle fully visible
# mid:    circle semi-transparent
# after:  circle completely gone
```

---

## Bug: Music stops early (before video ends)

**Cause**: The voice audio in the source MP4 is shorter than the background video (e.g. 32.9s voice vs 47.8s video). `amix=duration=first` uses the first audio stream's length — if voice is first, music stops at 32.9s too.

**Fix**: Pad the voice audio with silence to match the full video duration before mixing:

```bash
[1:a] apad=whole_dur=<BG_DURATION> [voice_padded];
[2:a] volume=<MUSIC_VOL> [music];
[voice_padded][music] amix=inputs=2:duration=first [out_a]
```

`apad=whole_dur=47.833` extends the voice track with silence to 47.833s. The music then plays alongside silence (no voice) for the tail portion, which is the intended behaviour.

## Bug: Circle cuts off instead of fading

**Cause**: No fade filter on the circle branch — it disappears abruptly on the last frame.

**Fix**: Add `fade=t=out:st=<st>:d=<d>:alpha=1` to the circle filter chain. See §Step 3c.
