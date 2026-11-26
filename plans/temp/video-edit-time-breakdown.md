# Video Edit Time Breakdown

| Edit Job | Approach | Wall-Clock (Request → Verified) | FFmpeg Render Time | Key Bottleneck |
|---|---|---:|---:|---|
| **Job 1 (`7703460530031234325`)** | Initial custom script → migrated to `highlight_lines` JSON | `08:14:14 → 08:17:53` (`~3m 39s`, interrupted once by user cancel) | `2.86s` (`apply_edit.py`) / `3.50s` (`effect_editor.py`) | First-time Whisper `small` model download + transcription (`40s`) |
| **Job 2 (`7706525655550151956`)** | Extended `text_box.py` (neon glow/strokes) + JSON render | `08:23:28 → 08:25:53` (`~2m 25s`) | `3.12s` | Planning + editing `text_box.py` before rendering |
| **Job 3 (`7693012050204839220`)** | Extended `text_box.py` (brackets/accent bar) + JSON render | `08:27:02 → 08:29:01` (`~1m 59s`) | `3.84s` | Downloading `259.50 MiB` reference TikTok (`14s` at `18.04 MiB/s`) |

```text
Typical Edit Time Split (Observed Phases)
Reference Download   |==| 1s - 14s (0.8 MiB to 259.5 MiB)
Target Transcribe    |========| 40s once (cached for Jobs 2 & 3)
Frame/Color Inspect  |=| 2s - 3s per job
Engine/JSON Edit     |====================| ~1m - 1.5m (agent read/edit/plan)
Render + Probe       |=| 4s - 6s (FFmpeg ~3.1s - 3.8s)
```

## Observed Command Timings

| Phase | Job 1 (`7703460530031234325`) | Job 2 (`7706525655550151956`) | Job 3 (`7693012050204839220`) |
|---|---|---|---|
| **Download + Probe** | `6s` (`14.19 MiB`) | `4s` (`788.75 KiB`) | `14s+` (`259.50 MiB`) |
| **Sample Frames + Colors** | `2s` extract + `1s` color sample | `3s` color sample + volumedetect | Included in download command |
| **Whisper Transcription** | `40s` (`task-31`, `faster_whisper small`) | `0s` (reused `target_transcript.json`) | `0s` (reused `target_transcript.json`) |
| **Self-Check + Render + Probe** | `5s` (JSON re-render, `3.50s` FFmpeg) | `5s` (`3.12s` FFmpeg) | `6s` (`3.84s` FFmpeg) |

## Optimization Takeaways

| Lever | Impact |
|---|---|
| **JSON-First Engine (`effect_editor.py`)** | Eliminates custom render scripts; FFmpeg composite + `loudnorm` consistently finishes in `3.1s–3.8s` for a `15s` `720×1280` clip. |
| **Cached Transcripts** | Reusing `target_transcript.json` saved `~40s` on Jobs 2 and 3. |
| **Reusable `text_box.py` Variants** | Now that `highlight_lines`, `glow_radius`/`outer_stroke_*`, and `brackets`/`accent_bar_color` live in `text_box.py`, matching styles skip engine edits and planning. |
