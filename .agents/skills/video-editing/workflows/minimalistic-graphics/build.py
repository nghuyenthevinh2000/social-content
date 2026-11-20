#!/usr/bin/env python3
"""/minimalistic-graphics: spec.json -> black-and-white line art, a dot hops up the steps and lands the line (1080x1920).

    python3 build.py <spec.json> [--snap 2.2,3.5]
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'kit'))
import anim  # noqa: E402

DEFAULTS = {'lines': ['every step feels small.', 'until you look back.'], 'steps': 5, 'light': False}


def payoff(spec):
    """when the dot reaches the top; the template uses the same formula"""
    n = spec['steps']
    step = min(.5, max(.3, 1.6 / (n - 1)))
    return .42 + step * (n - 2) + .58


def check(spec):
    if not isinstance(spec['steps'], int) or not 3 <= spec['steps'] <= 7:
        sys.exit('spec: "steps" must be a whole number from 3 to 7')
    if not isinstance(spec['lines'], list) or not 1 <= len(spec['lines']) <= 2:
        sys.exit('spec: "lines" takes 1 or 2 short lines of text')
    for l in spec['lines']:
        if len(l) > 34:
            print(f'note: "{l}" is long; it may wrap. Keep each line under ~30 characters.')


if __name__ == '__main__':
    anim.build(HERE / 'template.html', DEFAULTS, duration=lambda s: payoff(s) + 1.6, check=check)
