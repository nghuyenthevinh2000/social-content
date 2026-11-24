# Reference Video Reverse-Engineering (`rea-video`)

| Aspect | Rule |
|---|---|
| Submodule source | `.agents/skills/video-editing/scripts/rea-video` (`https://github.com/JuneYaooo/rea-video.git`) |
| Isolated environment | Install into gitignored `local/rea-video/.venv` (Python 3.12); never install into system Python or repo `.venv` |
| Output workspace | Store all downloads and breakdowns under `local/rea-video-runs/<id>/` |
| Visual review gate | Deterministic stats often misclassify 2D flat-vector animation as 3D render; always run `review` + inspect frames + `apply-review` |
| Audio & VLM honesty | Mark unverified BGM/SFX sources as inferred (`to confirm`); optional VLM keys go in `--env-file` only (never print or commit) |

```text
yt-dlp (source.mp4) -> rea-video decompose -> rea-video review -> inspect frames -> apply-review -> summary & VIDEO.md
```

| Stage | Command from repository root |
|---|---|
| 1. Create venv (one-time) | `uv venv --python 3.12 local/rea-video/.venv && uv pip install --python local/rea-video/.venv/bin/python -e ".agents/skills/video-editing/scripts/rea-video[ocr,asr]"` |
| 2. Fix `cv2` conflict (Python ≤ 3.12) | `uv pip uninstall --python local/rea-video/.venv/bin/python opencv-python \|\| true && uv pip install --python local/rea-video/.venv/bin/python --reinstall --no-deps "opencv-python-headless>=4.8,<5"` |
| 3. Download reference | `uv run yt-dlp -o "local/rea-video-runs/<id>/source.mp4" -f "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best" --merge-output-format mp4 "<URL>"` |
| 4. Decompose shots & audio | `local/rea-video/.venv/bin/rea-video decompose local/rea-video-runs/<id>/source.mp4 -o local/rea-video-runs/<id>/out --lang en` |
| 5. Generate review tasks | `local/rea-video/.venv/bin/rea-video review local/rea-video-runs/<id>/out` |
| 6. Inspect & annotate | Inspect `out/storyboard.jpg`, `out/audio.png`, and `priority=high` `out/shots/shot_XXX.jpg`; fill `out/review_answers.json` (`label_probs`, `cast`, `story`, `narrative`) |
| 7. Merge & read breakdown | `local/rea-video/.venv/bin/rea-video apply-review local/rea-video-runs/<id>/out --by <agent> --lang en && local/rea-video/.venv/bin/rea-video summary local/rea-video-runs/<id>/out/breakdown.json` |

| Artifact | Purpose |
|---|---|
| `out/VIDEO.md` | Layered shot-by-shot breakdown for AI agents |
| `out/report.html` | Human-readable visual report and remake guide |
| `out/stems/` & `out/sfx/` | Separated `vocals.wav`, `music.wav`, and detected SFX clips |
| `out/packaging/` | Extracted `subtitles.srt`, `overlays.ass`, and `timeline.json` |
