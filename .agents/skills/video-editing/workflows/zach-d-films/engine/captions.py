#!/usr/bin/env python3
"""Turns word timings into the CAPTIONS list for src/shots.js: 1 to 3 words per caption, broken at punctuation.

    python3 captions.py <voiceover.words.json>    # from kit/words.py; paste the output over CAPTIONS in src/shots.js
"""
import json
import re
import sys


SMALL = {'a', 'an', 'the', 'at', 'to', 'of', 'in', 'on', 'and', 'or', 'but', 'for', 'with', 'by', 'it', 'is', 'like', 'as', 'so'}


def chunks(words, maxw=3, maxc=18):
    out, cur = [], []
    for i, w in enumerate(words):
        cur.append(w)
        text = ' '.join(x['w'] for x in cur)
        stop = re.search(r'[.,?!;:]$', w['w'])
        dangling = w['w'].lower() in SMALL and i + 1 < len(words) and len(cur) < maxw + 1
        if stop or ((len(cur) >= maxw or len(text) >= maxc) and not dangling):
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return out


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    words = json.load(open(sys.argv[1]))
    print('export const CAPTIONS = [')
    groups = chunks(words)
    for i, g in enumerate(groups):
        text = re.sub(r'[.,;:]+$', '', ' '.join(x['w'] for x in g)).replace("'", "\\'")
        end = f", {g[-1]['e'] + .3:.2f}" if i == len(groups) - 1 else ''
        print(f"  [{g[0]['s']:.2f}, '{text}'{end}],")
    print('];')
    print(f'export const DURATION = {words[-1]["e"] + .5:.2f};')


if __name__ == '__main__':
    main()
