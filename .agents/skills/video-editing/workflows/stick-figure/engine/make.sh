#!/usr/bin/env bash
# Build a stick-figure reel end to end: voice -> word timings -> music + SFX -> picture -> <reel>/<name>.mp4
#   make.sh <reel-folder> [kokoro | elevenlabs | path/to/voiceover.mp3]
# Examples:
#   make.sh ~/reels/pirate                 # reuse the voice already in audio/ (or the free Kokoro take)
#   make.sh ~/reels/pirate kokoro          # new take in the free built-in voice
#   make.sh ~/reels/pirate elevenlabs      # new ElevenLabs take (needs ELEVENLABS_API_KEY)
#   make.sh ~/reels/pirate ~/take.mp3      # your own recording
#   AUDIO_ONLY=1 make.sh ~/reels/pirate    # remix the sound only (reuses the last picture)
set -euo pipefail
ENGINE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KIT="$(cd "$ENGINE/../../../kit" && pwd)"
DIR="$(cd "${1:?usage: make.sh <reel-folder> [kokoro|elevenlabs|file]}" && pwd)"
VOICE="${2:-keep}"
WORKERS="${WORKERS:-4}"
PY="$KIT/.venv/bin/python"
[ -x "$PY" ] || { echo "the voice tools aren't set up: run  bash $KIT/setup.sh --voice"; exit 1; }
export NODE_PATH="$KIT/node_modules"
NAME="$(basename "$DIR")"
cd "$DIR"; mkdir -p audio

echo "== voice: $VOICE"
case "$VOICE" in
  keep)       [ -f audio/vo.wav ] || { [ -f audio/vo_kokoro.wav ] || "$PY" "$ENGINE/tools/tts_kokoro.py"; cp audio/vo_kokoro.wav audio/vo.wav; } ;;
  kokoro)     "$PY" "$ENGINE/tools/tts_kokoro.py"; cp audio/vo_kokoro.wav audio/vo.wav ;;
  elevenlabs) "$PY" "$ENGINE/tools/tts_elevenlabs.py" audio/vo_el.mp3
              ffmpeg -v error -y -i audio/vo_el.mp3 -ac 1 -ar 44100 audio/vo.wav ;;
  *)          ffmpeg -v error -y -i "$VOICE" -ac 1 -ar 44100 audio/vo.wav ;;
esac
# trim leading/trailing silence so the hook lands on frame 1
ffmpeg -v error -y -i audio/vo.wav -af "silenceremove=start_periods=1:start_threshold=-45dB,areverse,silenceremove=start_periods=1:start_threshold=-45dB,areverse" audio/vo_trim.wav && mv audio/vo_trim.wav audio/vo.wav

echo "== aligning words to the voice"
"$PY" "$ENGINE/tools/align.py" audio/vo.wav

echo "== music + sfx mix"
"$PY" audio.py

if [ "${AUDIO_ONLY:-0}" != "1" ] || [ ! -f silent.mp4 ]; then
  echo "== rendering shots with $WORKERS workers"
  rm -rf seg; mkdir -p seg
  N=$(grep -c "SHOTS.push" web/shots.js)
  pids=()
  for ((w = 0; w < WORKERS; w++)); do
    ids=""; for ((i = w; i < N; i += WORKERS)); do ids="${ids:+$ids,}$i"; done
    [ -n "$ids" ] && { node "$ENGINE/tools/render.js" segments "$ids" > "seg/log$w.txt" 2>&1 & pids+=($!); }
  done
  for p in "${pids[@]}"; do wait "$p"; done
  [ "$(ls seg/shot_??.mp4 | wc -l)" -eq "$N" ] || { echo "a shot failed to render, see $DIR/seg/log*.txt"; exit 1; }
  for f in seg/shot_??.mp4; do echo "file '$PWD/$f'"; done > seg/list.txt
  ffmpeg -v error -y -f concat -safe 0 -i seg/list.txt -c copy silent.mp4
fi

echo "== final mux"
ffmpeg -v error -y -i silent.mp4 -i audio/mix.wav -map 0:v -map 1:a -c:v copy \
  -af "alimiter=limit=0.8:attack=2:release=60,loudnorm=I=-14:TP=-1.5:LRA=9" \
  -c:a aac -b:a 192k -ar 48000 -shortest -movflags +faststart "$NAME.part.mp4"
mv "$NAME.part.mp4" "$NAME.mp4"
echo "done: $DIR/$NAME.mp4"
