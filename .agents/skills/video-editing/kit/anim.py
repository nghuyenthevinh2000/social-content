#!/usr/bin/env python3
"""Shared helpers for the animation skills. Standard library only (plus ffmpeg and npx on the PATH).

A builder fills a skill's template.html with its spec and renders it with HyperFrames:
    anim.build(template, defaults, duration=lambda spec: 4.0, three=False)

From the command line:
    python3 kit/anim.py sheet <video.mp4> <out.jpg> [n]     # contact sheet; the red frame is Instagram's safe area
    python3 kit/anim.py still <video.mp4> <t> <out.jpg>     # one frame
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parent
HYPERFRAMES = 'hyperframes@0.8.34'
W, H, FPS = 1080, 1920, 30
SAFE_TOP, SAFE_BOTTOM, SAFE_SIDE = 220, 1500, 100      # Instagram covers the top ~220 px and the bottom ~420 px


def run(cmd, **kw):
    return subprocess.run([str(c) for c in cmd], check=True, **kw)


def duration(video):
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(video)],
                       capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


def link(src, dst):
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy(src, dst)


def check_setup(three):
    missing = []
    if not (KIT / 'vendor' / 'gsap.min.js').exists():
        missing.append('GSAP')
    if three and not (KIT / 'node_modules' / 'three' / 'build' / 'three.module.js').exists():
        missing.append('three.js')
    if missing:
        sys.exit(f'{" and ".join(missing)} not found: run  bash "{KIT}/setup.sh"  once, then build again')


def load_spec(path, defaults):
    spec = json.loads(Path(path).read_text())
    for k, v in defaults.items():
        spec.setdefault(k, v)
    unknown = sorted(set(spec) - set(defaults) - {'out', 'hold', 'template'})
    if unknown:
        print(f'note: ignoring unknown spec fields: {", ".join(unknown)}')
    return spec


def prepare(template, spec, dur, work, three=False):
    """writes the render folder: index.html with the spec filled in, fonts, GSAP and (if needed) three.js"""
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    html = Path(template).read_text()
    data = json.dumps(spec, ensure_ascii=False).replace('</', '<\\/')
    (work / 'index.html').write_text(html.replace('__SPEC__', data).replace('__DURATION__', f'{dur:.3f}'))
    for f in (KIT / 'fonts').glob('*.woff2'):
        link(f, work / 'fonts' / f.name)
    link(KIT / 'vendor' / 'gsap.min.js', work / 'vendor' / 'gsap.min.js')
    if three:
        t = KIT / 'node_modules' / 'three'
        link(t / 'build' / 'three.module.js', work / 'vendor' / 'three' / 'three.module.js')
        for rel in ['environments/RoomEnvironment.js']:
            link(t / 'examples' / 'jsm' / rel, work / 'vendor' / 'three' / 'addons' / rel)


def hyperframes(*args):
    return subprocess.run(['npx', '--yes', HYPERFRAMES, *map(str, args)], capture_output=True, text=True)


def render(work, out):
    out = Path(out)
    if out.exists():
        out.unlink()
    print(f'rendering {out.name} ...', flush=True)
    r = hyperframes('render', work, '-o', out, '--fps', FPS, '-q', 'high')
    if not out.exists():
        sys.exit(f'render failed:\n{r.stdout[-3000:]}\n{r.stderr[-3000:]}')
    print('\n'.join(l.strip() for l in r.stdout.splitlines() if 'rendered in' in l))


def snapshots(work, times, out_dir):
    """quick PNG frames at the given times, without a full render"""
    r = hyperframes('snapshot', work, '--at', ','.join(f'{t:g}' for t in times))
    shots = sorted((work / 'snapshots').glob('frame-*.png'))
    if not shots:
        sys.exit(f'snapshot failed:\n{r.stdout[-3000:]}\n{r.stderr[-3000:]}')
    out_dir.mkdir(parents=True, exist_ok=True)
    for f in shots:
        shutil.copy(f, out_dir / f.name)
    print(f'wrote {len(shots)} snapshots to {out_dir}')


def sheet(video, out, n=6):
    """contact sheet of a finished video; the red frame is the part Instagram leaves uncovered"""
    tw, th = 270, 480
    k = tw / W
    draw = (f'drawbox=x={SAFE_SIDE * k:.0f}:y={SAFE_TOP * k:.0f}:w={(W - 2 * SAFE_SIDE) * k:.0f}:'
            f'h={(SAFE_BOTTOM - SAFE_TOP) * k:.0f}:color=red@0.8:t=2')
    rate = n / duration(video)
    run(['ffmpeg', '-v', 'error', '-y', '-i', video, '-vf', f'fps={rate:.5f},scale={tw}:{th},{draw},tile={n}x1',
         '-frames:v', '1', out])


def still(video, t, out):
    run(['ffmpeg', '-v', 'error', '-y', '-ss', f'{t:.3f}', '-i', video, '-frames:v', '1', out])


def build(template, defaults, duration=lambda spec: 4.0, three=False, check=None):
    """the whole builder CLI:  build.py <spec.json> [--snap 1.5,3.2]  ->  <spec>.mp4 + <spec>.sheet.jpg"""
    args = sys.argv[1:]
    if not args or args[0] in ('-h', '--help'):
        sys.exit(f'usage: {Path(sys.argv[0]).name} <spec.json> [--snap 1.5,3.2]')
    spec_path = Path(args[0]).resolve()
    snap = None
    if '--snap' in args:
        snap = [float(x) for x in args[args.index('--snap') + 1].split(',')]
    check_setup(three)
    spec = load_spec(spec_path, defaults)
    if check:
        check(spec)
    dur = duration(spec) + float(spec.get('hold', 0))
    out = Path(spec['out']) if spec.get('out') else spec_path.with_suffix('.mp4')
    if not out.is_absolute():
        out = spec_path.parent / out
    if spec.get('template'):                      # a customised copy of the skill's template, next to the spec
        template = (spec_path.parent / spec['template']).resolve()
    work = spec_path.parent / '.work' / out.stem
    prepare(template, spec, dur, work, three)
    if snap:
        snapshots(work, snap, out.with_suffix('.snaps'))
        return
    render(work, out)
    sh = out.with_suffix('.sheet.jpg')
    sheet(out, sh)
    print(f'done: {out}\nsheet: {sh}')


def main():
    a = sys.argv[1:]
    if len(a) >= 3 and a[0] == 'sheet':
        sheet(a[1], a[2], int(a[3]) if len(a) > 3 else 6)
        print('wrote', a[2])
    elif len(a) == 4 and a[0] == 'still':
        still(a[1], float(a[2]), a[3])
        print('wrote', a[3])
    else:
        sys.exit(__doc__)


if __name__ == '__main__':
    main()
