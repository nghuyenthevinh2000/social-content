#!/usr/bin/env python3
"""/low-poly: spec.json -> a PS1-style low-poly scene at a train platform: a dog waits, a train comes and goes, he is still there (1080x1920, 4.8 s).

    python3 build.py <spec.json> [--snap 3.0]
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'kit'))
import anim  # noqa: E402

import re  # noqa: E402

DEFAULTS = {'lines': ['he waited every day', 'for almost 10 years'], 'sign': 'SHIBUYA', 'prev': 'EBISU', 'next': 'HARAJUKU', 'snow': True}


def check(spec):
    if not isinstance(spec['lines'], list) or not 1 <= len(spec['lines']) <= 2:
        sys.exit('spec: "lines" takes 1 or 2 short captions')
    for l in spec['lines']:
        if len(l) > 28:
            print(f'note: "{l}" is long; it may wrap. Keep each caption under ~26 characters.')
    for k, n in (('sign', 20), ('prev', 9), ('next', 9)):
        v = spec[k] or ''
        if not re.fullmatch(r"[A-Za-z0-9 .\-]*", v):
            sys.exit(f'spec: "{k}" can use letters, digits, spaces, dots and dashes (the sign is a tiny pixel font)')
        if len(v) > n:
            sys.exit(f'spec: "{k}" fits up to {n} characters on the sign')


if __name__ == '__main__':
    anim.build(HERE / 'template.html', DEFAULTS, duration=lambda s: 4.8, three=True, check=check)
