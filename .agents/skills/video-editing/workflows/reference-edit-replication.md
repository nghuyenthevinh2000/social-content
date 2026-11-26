# Reference Edit Replication Workflow

```text
Inspect Ref + Target -> Existing effects/ sufficient?
                              yes -> Author edit_config.json -> Render -> Verify
                               no -> Extend effects/ + --check -> Author edit_config.json -> Render -> Verify
```

## Decision & Execution Loop

| Stage | Action | Command / Target | Gate |
|---|---|---|---|
| **1. Inspect Reference** | Download reference URL, probe streams, and extract sample frames (`0.5s`, `3s`, `6s`, `10s`, `15s`). | `uv run yt-dlp` + `ffprobe` + `ffmpeg -ss ... -vframes 1` | Visual style, colors, typography, transitions, and audio loudness documented. |
| **2. Inspect Target** | Probe target video and transcribe speech with word timestamps. | `ffprobe` + `faster_whisper` (`word_timestamps=True`) | Exact duration, dimensions, and phrase timecodes captured. |
| **3. JSON-First Check** | Check `EFFECT_REGISTRY` in `scripts/video_engine/effects/__init__.py` and primitive options. | Read `effects/*.py` | Confirm whether `edit_config.json` can express the edit directly. |
| **4. Extend Engine (If Needed)** | Never write a one-off render script. Add minimal, reusable parameters to the matching `effects/*.py` module and add a `--check` assertion. | Edit `effects/*.py` + `effect_editor.py`, run `effect_editor.py --check` | `self_test passed.` with zero regressions. |
| **5. Author & Render JSON** | Write `edit_config.json` in `local/video-edit/<job>/` and execute the declarative engine. | `.venv/bin/python .agents/skills/video-editing/scripts/video_engine/effect_editor.py <edit_config.json>` | Single-pass `BT.709`, `24fps`, `AAC 44.1kHz`, `loudnorm` MP4 produced. |
| **6. Verify Output** | Probe output container and visually inspect extracted keyframes across all 4 safe zones. | `ffprobe` + `ffmpeg -ss ... -vframes 1` + `read_file` | Zero text clipping, zero face/hand overlap, clean diacritics, valid contrast. |

## Rules & Boundaries

| Rule | Requirement |
|---|---|
| **No One-Off Scripts** | Always route through `effect_editor.py <edit_config.json>`. If an effect is missing, upgrade `effects/` so it becomes declarative JSON for future jobs. |
| **Ponytail Modularity** | Extend existing primitives (`text_box`, `punch_zoom`, `color_grade`, `transition`, `subtitles`, `bgm`, `sfx`) with optional keys before adding a new effect module. |
| **Safe Zones** | Keep overlays inside portrait safe margins (`y=100..1080` on `720×1280`), clear of faces, hands, and native platform UI (`y=1100..1280`). |
| **Non-Destructive** | Never overwrite source media; keep configs, extracted frames, and outputs under `local/video-edit/<job>/`. |
