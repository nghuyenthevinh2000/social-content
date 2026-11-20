# Free voiceover with Kokoro, run from a reel/project folder: reads script.json (a list of sentences), writes audio/vo_kokoro.wav.
#   tts_kokoro.py [voice] [speed]     defaults: am_michael 1.12 (other voices: af_heart, am_adam, bf_emma, bm_george ...)
import json, sys, os, shutil, tempfile, numpy as np, soundfile as sf
ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
KIT = os.path.realpath(os.path.join(ROOT, "..", "..", "..", "kit"))  # the voice models live in kit/models
from kokoro_onnx import Kokoro, EspeakConfig
import espeakng_loader

# espeak-ng fails on a long data path (deep install folders), so use a copy at a short path when needed
data = espeakng_loader.get_data_path()
if len(data) > 100:
    short = os.path.join(tempfile.gettempdir(), "kokoro-espeak-ng-data")
    if not os.path.exists(os.path.join(short, "phontab")):
        shutil.rmtree(short, ignore_errors=True); shutil.copytree(data, short)
    data = short
espeak = EspeakConfig(lib_path=espeakng_loader.get_library_path(), data_path=data)

voice = sys.argv[1] if len(sys.argv) > 1 else "am_michael"
speed = float(sys.argv[2]) if len(sys.argv) > 2 else 1.12
k = Kokoro(os.path.join(KIT, "models/kokoro-v1.0.onnx"), os.path.join(KIT, "models/voices-v1.0.bin"), espeak_config=espeak)
os.makedirs("audio", exist_ok=True)
lines = json.load(open("script.json"))
GAP = 0.12  # seconds of air between lines (playbook: near-gapless VO)
out, t, meta = [], 0.0, []
for i, line in enumerate(lines):
    samples, sr = k.create(line, voice=voice, speed=speed, lang="en-us")
    # trim leading/trailing silence
    a = np.abs(samples); thr = 0.01
    idx = np.where(a > thr)[0]
    samples = samples[max(0, idx[0] - int(0.02 * sr)): idx[-1] + int(0.05 * sr)]
    sf.write(f"audio/line_{i:02d}.wav", samples, sr)
    meta.append({"i": i, "text": line, "start": round(t, 3), "dur": round(len(samples) / sr, 3)})
    out.append(samples)
    gap = GAP + (0.12 if i == 0 or line.rstrip().endswith(('?', '!')) else 0)   # a beat after the hook and after questions
    out.append(np.zeros(int(gap * sr), dtype=samples.dtype))
    t += len(samples) / sr + gap
vo = np.concatenate(out)
sf.write("audio/vo_kokoro.wav", vo, sr)
json.dump(meta, open("audio/lines.json", "w"), indent=1)
print(f"{voice} total {len(vo)/sr:.2f}s")
for m in meta: print(m)
