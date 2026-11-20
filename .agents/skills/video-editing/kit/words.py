#!/usr/bin/env python3
"""Word timings for a voiceover, worked out on your computer (Parakeet through sherpa-onnx).
Needs the voice models: bash kit/setup.sh --voice. Run it with kit/.venv/bin/python.

    words.py <voiceover.wav|mp3|m4a> [script.txt | script.json]

Prints one sentence per line as word@seconds and writes <voiceover name>.words.json next to it
(audio.m4a -> audio.words.json), a list of {"w", "s", "e"}.
With a script, the words are spelled as in the script; the timings still come from the audio.
"""
import difflib
import glob
import json
import os
import re
import subprocess
import sys

import numpy as np

KIT = os.path.dirname(os.path.realpath(__file__))
SR = 16000


def recognizer():
    import sherpa_onnx
    d = glob.glob(os.path.join(KIT, 'models', 'sherpa-onnx-nemo-parakeet*'))
    if not d:
        sys.exit(f'the word-timing model is missing: run  bash "{KIT}/setup.sh" --voice')
    d = d[0]
    return sherpa_onnx.OfflineRecognizer.from_transducer(
        encoder=f'{d}/encoder.int8.onnx', decoder=f'{d}/decoder.int8.onnx', joiner=f'{d}/joiner.int8.onnx',
        tokens=f'{d}/tokens.txt', model_type='nemo_transducer')


def load(path):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-f', 'f32le', '-ac', '1', '-ar', str(SR), '-'],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32)


def recognise(a):
    """[[word, start], ...] as heard"""
    rec = recognizer()
    s = rec.create_stream()
    s.accept_waveform(SR, a)
    rec.decode_stream(s)
    r = s.result
    words = []
    for tok, ts in zip(r.tokens, r.timestamps):
        if tok.startswith((' ', '▁')) or not words:
            words.append([tok.strip(' ▁'), float(ts)])
        else:
            words[-1][0] += tok
    return [w for w in words if w[0]]


def follow_script(heard, script):
    """respell the heard words as the script has them, keeping the heard timings"""
    norm = lambda w: re.sub(r'[^a-z0-9]', '', w.lower())  # noqa: E731
    sw = script.split()
    sm = difflib.SequenceMatcher(a=[norm(w) for w in sw], b=[norm(w[0]) for w in heard], autojunk=False)
    start = [None] * len(sw)
    for blk in sm.get_matching_blocks():
        for k in range(blk.size):
            start[blk.a + k] = heard[blk.b + k][1]
    for i in range(len(sw)):                           # words the recogniser missed: spread between neighbours
        if start[i] is None:
            lo = next((j for j in range(i - 1, -1, -1) if start[j] is not None), None)
            hi = next((j for j in range(i + 1, len(sw)) if start[j] is not None), None)
            if lo is not None and hi is not None:
                start[i] = start[lo] + (start[hi] - start[lo]) * (i - lo) / (hi - lo)
            else:
                start[i] = (start[lo] + .3) if lo is not None else 0.0
    return [[w, t] for w, t in zip(sw, start)]


def timings(path, script=None):
    a = load(path)
    words = recognise(a)
    if script:
        words = follow_script(words, script)
    dur = len(a) / SR
    out = []
    for i, (w, t) in enumerate(words):
        e = words[i + 1][1] if i + 1 < len(words) else dur
        out.append({'w': w, 's': round(t, 3), 'e': round(min(e, t + 1.2), 3)})
    return out


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    path = sys.argv[1]
    script = None
    if len(sys.argv) > 2:
        raw = open(sys.argv[2]).read()
        script = ' '.join(json.loads(raw)) if sys.argv[2].endswith('.json') else raw
    ws = timings(path, script)
    out = os.path.splitext(path)[0] + '.words.json'
    with open(out, 'w') as f:
        json.dump(ws, f, indent=0)
    line = []
    for w in ws:
        line.append(f"{w['w']}@{w['s']:.2f}")
        if w['w'].endswith(('.', '?', '!')):
            print(' '.join(line))
            line = []
    if line:
        print(' '.join(line))
    print(f'wrote {out}')


if __name__ == '__main__':
    main()
