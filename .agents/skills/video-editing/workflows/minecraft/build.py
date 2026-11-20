#!/usr/bin/env python3
"""/minecraft: spec.json -> a blocky voxel cottage builds itself block by block on a grassy hill, the chimney slams in and the windows light up (1080x1920, 4 s).

    python3 build.py <spec.json> [--snap 2.9]
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'kit'))
import anim  # noqa: E402

DEFAULTS = {'lines': ['block by block', 'home.']}


def check(spec):
    if not isinstance(spec['lines'], list) or not 1 <= len(spec['lines']) <= 2:
        sys.exit('spec: "lines" takes 1 or 2 short lines of text')
    if len(spec['lines'][0]) > 17:
        print('note: line one over ~17 characters runs off the frame at this size; shorten it')
    if len(spec['lines']) > 1 and len(spec['lines'][1]) > 9:
        print('note: line two is big (150 px); over ~9 characters it runs off the frame')


if __name__ == '__main__':
    anim.build(HERE / 'template.html', DEFAULTS, duration=lambda s: 4.0, three=True, check=check)
