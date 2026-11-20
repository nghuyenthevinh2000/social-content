#!/usr/bin/env python3
"""/map-route: spec.json -> a white 3D city where the route draws itself, the pin drops and the camera pulls back (1080x1920, 4 s).

    python3 build.py <spec.json> [--snap 1.0,3.6]
"""
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'kit'))
import anim  # noqa: E402

DEFAULTS = {'destination': None, 'minutes': None, 'distance': None, 'unit': 'km',
            'places': ['North Quay', 'Botanic Gardens', 'Market Hall', 'Elm Park', 'The Canal'],
            'accent': '#2f7cf6', 'seed': 7}


def check(spec):
    if not spec['destination'] or spec['minutes'] is None or spec['distance'] is None:
        sys.exit('spec: "destination", "minutes" and "distance" are required')
    if not re.fullmatch(r'#[0-9a-fA-F]{6}', spec['accent']):
        sys.exit('spec: "accent" must be a hex colour like "#2f7cf6"')
    if len(spec['destination']) > 26:
        print('note: a destination over ~26 characters makes a wide card; shorten it if the sheet looks cramped')
    spec['places'] = (list(spec['places']) + [''] * 5)[:5]


if __name__ == '__main__':
    anim.build(HERE / 'template.html', DEFAULTS, duration=lambda s: 4.0, three=True, check=check)
