#!/usr/bin/env python3
"""/kurzgesagt: spec.json -> a Kurzgesagt style flat-vector space scene: every planet drops in, to scale, between Earth and the Moon (1080x1920, 4 s).

    python3 build.py <spec.json> [--snap 2.7]
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'kit'))
import anim  # noqa: E402

DEFAULTS = {'lines': ['Could every planet fit', 'between Earth and the Moon?', 'At its farthest, yes.'], 'tag': 'They all fit'}


def check(spec):
    if not isinstance(spec['lines'], list) or not 1 <= len(spec['lines']) <= 3:
        sys.exit('spec: "lines" takes 1 to 3 captions (the third shows at the payoff)')
    for l in spec['lines']:
        if len(l) > 32:
            print(f'note: "{l}" is long; it may wrap. Keep each caption under ~30 characters.')
    if len(spec['tag']) > 18:
        print('note: a tag over ~18 characters makes a wide pill; shorten it if the sheet looks cramped')


if __name__ == '__main__':
    anim.build(HERE / 'template.html', DEFAULTS, duration=lambda s: 4.0, check=check)
