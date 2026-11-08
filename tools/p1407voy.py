#!/usr/bin/env python3
"""P1407 arm: surf_voyager hands-free, N attempts in one hosted game.

    python -B tools/p1407voy.py --out <new dir under an OWNER.md root> --fps 60 --holds 600,600,600

The real install (C:/FTESurf, its progs and map cfgs) with a private homedir. Each attempt:
zone_goto 0, settle, +back for HOLD ms, release, then poll `cmd timer` every 2 s for up to 85 s.
Graded on the timer's own lines (state, ticks) and `viewpos` at the end. Needs the rig lock.
"""
import argparse
import json
import random
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, 'C:/FTESurf/tools')
import p840clock as R  # noqa: E402

EXE = Path('C:/FTESurf/ftesurf64.exe')
TIMER = re.compile(r'timer\^7: (\w+) on surf_voyager, tick (\S+)')
CLOCK = re.compile(r'^\s+(\d+:\d+\.\d+|\d+\.\d+)\s+pb ')
VIEW = re.compile(r'setpos ([-\d.]+) ([-\d.]+) ([-\d.]+)')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--fps', type=int, default=250)
    ap.add_argument('--holds', default='600')
    ap.add_argument('--extra', default='', help='more console lines, ; separated')
    ap.add_argument('--hitch', type=int, default=0, help='random frame hitches per flight (cl_maxfps 15 for 60-250 ms)')
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--tap', default='', help='SECONDS:CMD:HOLD -- e.g. 2.0:duck:0.12 presses +duck 2 s after release')
    a = ap.parse_args()
    out = a.out.resolve()
    R.owned(out)
    home = out / 'home'
    (home / 'ftesurf/logs').mkdir(parents=True)
    (home / 'ftesurf/data').mkdir(parents=True)
    (home / 'ftesurf/data/consent.txt').write_text('version 4\n')   # no terms prompt: it ate the console
    log = home / 'ftesurf/logs/voy.log'
    cfg = ['cfg_save_auto 0', 'con_savehistory 0', 'log_enable 1', 'log_dir logs', 'log_name voy',
           'log_readable 1', 'developer 0', 'cl_idlefps 0', f'cl_maxfps {a.fps}', 'set run_resume 0',
           'set lobby_dir ""', 'set lobby_master ""', 'set sv_public 0', 'set update_autocheck 0',
           'name "P1407 Arm"', 'map surf_voyager']
    cfg += [c.strip() for c in a.extra.split(';') if c.strip()]
    (home / 'ftesurf/p1407.cfg').write_text('\n'.join(cfg) + '\n')
    res = {'fps': a.fps, 'extra': a.extra, 'attempts': []}
    R.take_lock(f'p1407 voyager hands-free fps {a.fps} (ftesurf-3a)')
    proc = None
    try:
        proc = subprocess.Popen([str(EXE), '-plugin', '-noreset', '-nobrowse', '-basedir', 'C:/FTESurf', '-homedir', str(home), '-window',
                                 '-width', '960', '-height', '540', '-nosound', '+set', 'cfg_save_auto', '0',
                                 '+exec', 'p1407.cfg'], cwd='C:/FTESurf', stdin=subprocess.PIPE,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        (out / 'owned-pid.txt').write_text(f'{proc.pid}\n')

        def text():
            return log.read_text(encoding='utf-8', errors='replace') if log.exists() else ''

        def send(line):
            proc.stdin.write(line.encode() + b'\n')
            proc.stdin.flush()

        end = time.monotonic() + 240
        while 'FTESurf CSQC loaded' not in text():
            if time.monotonic() > end or proc.poll() is not None:
                raise SystemExit('no CSQC load: ' + str(log))
            time.sleep(0.5)
        time.sleep(8)
        for hold in [int(h) for h in a.holds.split(',')]:
            off = len(text())
            send('zone_goto 0')
            time.sleep(2.5)
            send('+back')
            time.sleep(hold / 1000)
            send('-back')
            t0 = time.monotonic()
            rnd = random.Random(a.seed * 1000 + len(res['attempts']))
            hitches = sorted(rnd.uniform(1, 62) for _ in range(a.hitch))
            hitlog = []
            if a.tap:
                ts, tc, th = a.tap.split(':')
                time.sleep(float(ts))
                send('+' + tc)
                time.sleep(float(th))
                send('-' + tc)
                hitlog.append(('tap', ts, tc, th))
            states = []
            path = []
            fin = None
            while time.monotonic() - t0 < 88:
                nxt = time.monotonic() + 2
                while hitches and t0 + hitches[0] < nxt:
                    time.sleep(max(0, t0 + hitches[0] - time.monotonic()))
                    dur = rnd.uniform(0.06, 0.25)
                    send('cl_maxfps 15')
                    time.sleep(dur)
                    send(f'cl_maxfps {a.fps}')
                    hitlog.append((round(hitches.pop(0), 2), round(dur, 3)))
                time.sleep(max(0, nxt - time.monotonic()))
                o2 = len(text())
                send('cmd timer')
                send('viewpos')
                time.sleep(0.4)
                seg = text()[o2:]
                m = TIMER.search(seg)
                vp = VIEW.search(seg)
                if vp:
                    path.append((round(time.monotonic() - t0, 1), [round(float(x)) for x in vp.groups()]))
                if m:
                    states.append((round(time.monotonic() - t0, 1), m[1]))
                    if m[1] == 'finished':
                        c = [l for l in seg.splitlines() if CLOCK.search(l[20:] if len(l) > 20 else l)]
                        fin = c[0].strip()[:60] if c else '?'
                        break
                    if m[1] in ('idle', 'armed') and len(states) > 3:
                        break
            o3 = len(text())
            send('viewpos')
            time.sleep(0.5)
            v = VIEW.search(text()[o3:])
            att = {'hold': hold, 'secs': round(time.monotonic() - t0, 1), 'states': states[-4:],
                   'result': 'finished' if fin else (states[-1][1] if states else 'none'), 'clock': fin,
                   'viewpos': v.groups() if v else None, 'path': path, 'hitches': hitlog,
                   'edges': [l[20:].split('... ')[-1] + ' ' + l[20:].split()[3] for l in text()[off:].splitlines()
                             if 'touch end edge' in l][:12],
                   'lines': [l[20:] for l in text()[off:].splitlines()
                             if 'timer' in l or 'finish' in l.lower() or 'record' in l.lower()][:6]}
            for r in home.rglob('*_run.rec'):
                shutil.copy2(r, out / f"rec_{len(res['attempts'])}_{r.name}")
                r.unlink()
            res['attempts'].append(att)
            print(json.dumps(att), flush=True)
        send('quit')
        try:
            proc.wait(15)
        except subprocess.TimeoutExpired:
            proc.kill()
    finally:
        if proc is not None and proc.poll() is None:
            proc.kill()
        R.drop_lock()
    res['recs'] = sorted(str(p.relative_to(home)) for p in home.rglob('*.rec'))
    (out / 'report.json').write_text(json.dumps(res, indent=1))
    print(json.dumps({k: res[k] for k in ('fps', 'recs')}, indent=1))


if __name__ == '__main__':
    main()
