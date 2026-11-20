#!/usr/bin/env python3
"""/graph: spec.json -> a smooth line graph that draws itself while one number counts up (1080x1920, 4 s).

    python3 build.py <spec.json> [--snap 1.5,3.2]
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'kit'))
import anim  # noqa: E402

DEFAULTS = {'label': '', 'values': None, 'labels': [], 'final': None, 'prefix': '', 'suffix': '', 'decimals': 0, 'dark': False}


def check(spec):
    v = spec['values']
    if not isinstance(v, list) or len(v) < 2 or not all(isinstance(x, (int, float)) and x >= 0 for x in v):
        sys.exit('spec: "values" needs 2 or more numbers, all 0 or above')
    if max(v) <= 0:
        sys.exit('spec: at least one value must be above 0')


if __name__ == '__main__':
    anim.build(HERE / 'template.html', DEFAULTS, duration=lambda s: 4.0, check=check)
