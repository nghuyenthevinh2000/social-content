---
name: app-feature-showcase-reel
description: Turn app screenshots of one feature into a 15–25s vertical showcase reel (hook, step beats, CTA) with ffmpeg pan/zoom, kinetic captions, optional voiceover, and BGM.
---

# App Feature Showcase Reel

```text
Screenshots -> Beat script -> Per-beat clips (scroll / push-in / pop) -> Concat + captions + audio -> Normalize -> Audit
```

## Inputs

| Item | Convention | Example (`features-update/save-reel-and-analyze/`) |
|---|---|---|
| Screenshots | `features-update/<feature>/images/*.PNG`, iPhone 1170×2532 or cropped cards | `share_reel`, `kho_reel` (1170×1319), `reel_analysis_1`, `reel_analysis_2` |
| Work dir | `features-update/<feature>/render/` (never write into `images/`): `temp/` for intermediates (`clean/`, `beat*.mp4`, `raw*.mp4`, `check_*.png`) and `final/` for deliverables (`final.mp4`, `captions.ass`, `bgm_music.mp3`, `build_reel.py`) | `render/temp/beat1.mp4` … `render/final/final.mp4` |
| Canvas | 1080×1920, 30 fps, H.264 yuv420p, BT.709 | Background: app cream `#F3EEE8` or blurred copy of the screenshot |

## Beat script (fill before rendering)

| Beat | Time | Visual motion | On-screen caption (VI) | Example source |
|---|---|---|---|---|
| 1. Hook | 0–2s | Fast push-in 1.0→1.15× on the payoff screen | Pain/curiosity line, ≤7 words | `reel_analysis_1`: "Lướt thấy Reel hay mà quên mất?" |
| 2. Action | 2–6s | Scroll from reel bubble to confirmation | What the user does | `share_reel`: "Gửi Reel vào Messenger" → "Tự lưu vào Thư viện" |
| 3. Result list | 6–9s | Card pop-in (scale 0.85→1.0) + highlight on button | Proof it worked | `kho_reel`: "Mọi Reel ở một nơi" |
| 4. Payoff | 9–13s | Slow push-in on title + video card | Core value | `reel_analysis_1`: "Bấm Phân tích" |
| 5. Depth | 13–19s | Vertical scroll through transcript → "Vì sao viral" | Specific benefit | `reel_analysis_2`: "Có transcript + lý do viral" |
| 6. CTA | 19–22s | Hold logo/app screen, gentle zoom | One action | "Nhắn Reel cho Giúp Mẹ Học AI" |

## Per-beat ffmpeg recipes

| Motion | Filter core (input: `-loop 1 -t D -i IMG`) | Notes |
|---|---|---|
| Vertical scroll | `scale=1080:-2,crop=1080:1920:0:'(ih-1920)*t/D'` | Use for tall screens (2337px after scale); pick start/end y to frame the key element. |
| Push-in | `scale=4320:-2,zoompan=z='1+0.15*on/(D*30)':x='iw/2-iw/zoom/2':y='Y0':d=D*30:s=1080x1920:fps=30` | Upscale 4× first to remove zoompan jitter; set `Y0` to the focus row. |
| Card pop | Pad card on cream canvas: `color=c=0xF3EEE8:s=1080x1920` + `overlay` with `scale` animated via `zoompan` or `eval=frame` | For non-phone-ratio crops like `kho_reel`. |
| Highlight | `drawbox=x:y:w:h:color=0xD9541E@0.9:t=8:enable='between(t,a,b)'` | Brand orange ring around the tapped button. |
| Concat | `xfade=transition=slideup:duration=0.25:offset=…` chained, or concat demuxer for hard cuts | Hard cuts on beat drops; slide only between steps. |

## Captions, audio, finish

| Stage | Command / tool | Rule |
|---|---|---|
| Captions | ASS file burned via `subtitles=` (styles from `ugc-effect-editing-workflow.md`) | Top hook banner y≈150–350; step captions above bottom 320px; ≤2 lines. |
| Voiceover / BGM | `synthesize_eleven_v3.py` (`--voice-id` + `--text`, or `--music-prompt` for instrumental BGM) | Save to `render/temp/` or `render/final/`; time beats to `tts_v3_alignment.json` if voiced. |
| BGM + SFX | `effects/audio_mix.py` patterns; "whoosh" on slide, "pop" on card, "tap" on highlight | BGM ducked under voice (or standalone if instrumental); final −16 LUFS. |
| Normalize | `normalize_video.py render/temp/raw.mp4 render/final/final.mp4` | BT.709, AAC 44.1kHz stereo, faststart. |

## Pre-render cleanup (mandatory)

| Risk | Fix | Example coords (1170-wide source) |
|---|---|---|
| Unrelated ads/promos | Crop or cover with solid UI color | `share_reel` Zalopay banner y≈272–627 |
| Status bar clutter | Crop top ~140px or cover with clean bar | All iPhone screenshots |
| Third-party creator content | Blur faces/handles or get permission | Reel thumbnails in `share_reel`, `reel_analysis_1` |
| Personal data | Blur avatars, names, phone numbers | Chat avatar, phone number on product |

## Verification

| Check | Command | Pass |
|---|---|---|
| Container | `ffprobe -v error -show_streams -of json render/final/final.mp4` | 1080×1920, 30fps, AAC, 15–25s |
| Loudness | `ffmpeg -i render/final/final.mp4 -af ebur128 -f null -` | −16 ±1 LUFS |
| Frames | `ffmpeg -ss T -i render/final/final.mp4 -frames:v 1 render/temp/check_T.png` at each beat midpoint | Text readable, no jitter, no ads/PII, safe zones clear |
| Hook | Watch first 2s muted | Value is clear without sound |
| Cleanup | `rm -rf render/temp/` after verification | Keep `render/final/` clean with only deliverables |
