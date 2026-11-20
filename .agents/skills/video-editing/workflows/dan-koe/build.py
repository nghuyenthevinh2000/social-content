#!/usr/bin/env python3
"""/dan-koe: spec.json -> Dan Koe style black-and-white line art, one dot grows into a branching tree and the tips light up (1080x1920, about 4 s).

    python3 build.py <spec.json> [--snap 2.6]
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'kit'))
import anim  # noqa: E402

DEFAULTS = {'lines': ['one choice.', 'then the next.'], 'depth': 9, 'seed': 5, 'light': False}


def payoff(spec):
    """when the last tips land; the template uses the same numbers (T0 .3, STEP .25, GROW .27)"""
    return .3 + (spec['depth'] - 1) * .25 + .27


def check(spec):
    if not isinstance(spec['depth'], int) or not 6 <= spec['depth'] <= 10:
        sys.exit('spec: "depth" must be a whole number from 6 to 10')
    if not isinstance(spec['lines'], list) or not 1 <= len(spec['lines']) <= 2:
        sys.exit('spec: "lines" takes 1 or 2 short lines of text')
    for l in spec['lines']:
        if len(l) > 34:
            print(f'note: "{l}" is long; it may wrap. Keep each line under ~30 characters.')


if __name__ == '__main__':
    anim.build(HERE / 'template.html', DEFAULTS, duration=lambda s: payoff(s) + 1.43, check=check)
