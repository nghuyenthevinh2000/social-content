# Align one continuous VO take (audio/vo_new.wav) to the script, word by word.
# Writes audio/words_new.json and audio/warp.json (old-time -> new-time anchors).
import json, re, difflib, os, shutil, numpy as np, soundfile as sf, sherpa_onnx, glob, sys
ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
KIT = os.path.realpath(os.path.join(ROOT, "..", "..", "..", "kit"))  # the voice models live in kit/models
src = sys.argv[1] if len(sys.argv) > 1 else 'audio/vo.wav'
d = glob.glob(os.path.join(KIT, "models", "sherpa-onnx-nemo-parakeet*"))
if not d: sys.exit(f"the word-timing model is missing: run  bash {KIT}/setup.sh --voice")
d = d[0]
rec = sherpa_onnx.OfflineRecognizer.from_transducer(encoder=f"{d}/encoder.int8.onnx", decoder=f"{d}/decoder.int8.onnx",
    joiner=f"{d}/joiner.int8.onnx", tokens=f"{d}/tokens.txt", model_type="nemo_transducer")
a, sr = sf.read(src, dtype='float32')
if a.ndim > 1: a = a.mean(1)
if sr != 16000:
    n = int(len(a) * 16000 / sr); a = np.interp(np.linspace(0, len(a) - 1, n), np.arange(len(a)), a).astype(np.float32); sr = 16000
s = rec.create_stream(); s.accept_waveform(sr, a); rec.decode_stream(s); r = s.result
asr = []
for tok, ts in zip(r.tokens, r.timestamps):
    if tok.startswith(' ') or tok.startswith('▁') or not asr: asr.append([tok.strip(' ▁'), ts])
    else: asr[-1][0] += tok
norm = lambda w: re.sub(r"[^a-z0-9]", "", w.lower())
lines = json.load(open('script.json'))
REPL = json.load(open('captions.json')) if os.path.exists('captions.json') else {}
script = []
for li, L in enumerate(lines):
    for k, v in REPL.items(): L = L.replace(k, v)
    for w in L.split(): script.append((w, li))
# ASR may say "99" / "ninety nine percent"; collapse for matching
A = [norm(w[0]) for w in asr]; S = [norm(w) for w, _ in script]
S2 = ['99' if x == '99' else x for x in S]
sm = difflib.SequenceMatcher(a=S2, b=A, autojunk=False)
start = [None] * len(script)
for blk in sm.get_matching_blocks():
    for k in range(blk.size): start[blk.a + k] = asr[blk.b + k][1]
# special: '99%' may appear as 'ninety','nine','percent' or '99'
for i, (w, _) in enumerate(script):
    if start[i] is None:
        # interpolate between neighbours
        lo = next((j for j in range(i - 1, -1, -1) if start[j] is not None), None)
        hi = next((j for j in range(i + 1, len(script)) if start[j] is not None), None)
        if lo is not None and hi is not None: start[i] = start[lo] + (start[hi] - start[lo]) * (i - lo) / (hi - lo)
        elif lo is not None: start[i] = start[lo] + .3
        else: start[i] = 0
dur = len(a) / sr
words = []
for i, (w, li) in enumerate(script):
    e = start[i + 1] if i + 1 < len(script) else dur
    words.append({'w': w, 's': round(start[i], 3), 'e': round(min(e, start[i] + 1.2), 3), 'line': li})
json.dump(words, open('audio/words_new.json', 'w'), indent=0)
if not os.path.exists('audio/words_ref.json'): shutil.copy('audio/words_new.json', 'audio/words_ref.json')  # new reel: this voice becomes the timing reference
old = json.load(open('audio/words_ref.json'))
assert len(old) == len(words), f'script changed since the animation was timed ({len(old)} vs {len(words)} words): re-time shots.js or delete audio/words_ref.json'
anchors = [[o['s'], n['s']] for o, n in zip(old, words)]
# keep strictly increasing
clean = [anchors[0]]
for p in anchors[1:]:
    if p[0] > clean[-1][0] + 1e-3 and p[1] > clean[-1][1] + 1e-3: clean.append(p)
json.dump({'anchors': clean, 'old_end': old[-1]['e'], 'new_end': dur}, open('audio/warp.json', 'w'))
print('matched', sum(1 for b in sm.get_matching_blocks() for _ in range(b.size)), 'of', len(script), 'dur', round(dur, 2))
print(' '.join(f"{w['w']}@{w['s']:.2f}" for w in words[:20]))

open('web/words.js', 'w').write('const WORDS=' + json.dumps(words) + ';')
open('web/warp.js', 'w').write('window.WARP=' + json.dumps(json.load(open('audio/warp.json'))) + ';')
