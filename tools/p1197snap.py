#!/usr/bin/env python3
"""P1197: zone_edit snaps to the map's own corners and edges (surf_sinsane_ez's start).

One owned listen client hosts surf_sinsane_ez (copied from Momentum's maps folder into the
overlay) and drives the subject's own hooks, which print every snap they take:
- `zone_edit snapprobe` straight down at the start spawn finds the floor and its surface;
  `zone_edit wsurf` lists that surface's points: the corners to hit.
- From the spawn's eye, each corner is aimed at a few units inside it and must snap to
  "map corner" exactly; a long edge's middle must take "map edge" on the segment; with
  `zone_edit edges 0` the same corner aims take the grid (the control, which must miss some).
- `zone_edit snapcost` times one full surface search; a second probe on the same surface
  must not search again.
- Placing with the real view aimed at a corner by setpos: the status line must say map corner,
  and screenshots (edges on and off) are kept for a human to look at.
A probe whose trace did not reach its target is reported as not measured, not as a pass or fail.
--out must be fresh and beneath an owned task root; --progs holds the three .dat files.
"""
import argparse
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
MAPS = Path('C:/Program Files (x86)/Steam/steamapps/common/Momentum Mod Playtest/momentum/maps')
MAP = 'surf_sinsane_ez'
SPAWN = (12089.6006, 8393.60059, 13777.0312)   # the start's teleDestPos in Lex's local zone file
NUM = r'(-?[0-9.]+)'


class Client:
    def __init__(self, exe, base, cfg):
        self.log = base / 'ftesurf/logs/probe.log'
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 4              # shown without taking focus: a minimised client draws nothing
        self.proc = subprocess.Popen(
            [str(exe), '-plugin', '-nohome', '-noreset', '-nobrowse',
             '-basedir', str(base), '-manifest', str(base / 'default.fmf'),
             '-window', '-width', '640', '-height', '480', '-nosound',
             '+set', 'cfg_save_auto', '0', '+exec', cfg],
            cwd=str(base), stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, startupinfo=si)
        (base / 'owned-pid.txt').write_text(str(self.proc.pid) + '\n')

    def text(self):
        return self.log.read_text(encoding='utf-8', errors='replace') if self.log.exists() else ''

    def send(self, line):
        self.proc.stdin.write(line.encode('utf-8') + b'\n')
        self.proc.stdin.flush()

    def wait(self, pattern, offset=0, timeout=60):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            found = re.search(pattern, self.text()[offset:])
            if found:
                return found
            if self.proc.poll() is not None:
                raise RuntimeError(f'client exited {self.proc.returncode}: {self.log}')
            time.sleep(.1)
        raise RuntimeError(f'not reached: {pattern}: {self.log}')

    def query(self, command, pattern, timeout=30):
        offset = len(self.text())
        self.send(command)
        return self.wait(pattern, offset, timeout)

    def stop(self):
        if self.proc.poll() is None:
            self.send('quit')
            try:
                self.proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self.proc.terminate()
                self.proc.wait(timeout=10)


def sha(path):
    import hashlib
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:8]


def prepare(a):
    base = a.out / 'client'
    game = base / 'ftesurf'
    for folder in ('cfg', 'maps', 'logs'):
        (game / folder).mkdir(parents=True, exist_ok=True)
    for leaf in ('qwprogs.dat', 'csprogs.dat', 'menu.dat'):
        shutil.copy2(a.progs / leaf, game / leaf)
    shutil.copy2(ROOT / 'ftesurf/cfg/default.cfg', game / 'cfg/default.cfg')
    shutil.copy2(MAPS / f'{MAP}.bsp', game / f'maps/{MAP}.bsp')
    shutil.copytree(ROOT / 'ftesurf/scripts', game / 'scripts')   # zones.shader: P1203's x-ray handles
    (base / 'default.fmf').write_text(
        'FTEMANIFEST 1\nGAME FTESurfZoneSnapFixture\nBASEGAME ftesurf\n'
        'DISABLEHOMEDIR 1\nMAINCONFIG snap-unused\n')
    subprocess.run(['python', str(ROOT / 'tools/seed_csprogs.py'), str(game / 'csprogs.dat')],
                   check=True, capture_output=True)
    common = ['cfg_save_auto 0', 'con_savehistory 0', 'log_enable 1', 'log_dir logs',
              'log_name probe', 'log_readable 1', 'set cl_idlefps 0', 'set cl_maxfps 60',
              'set run_resume 0', 'set lobby_dir ""', 'set lobby_master ""', 'set lobby_enable 0',
              'set cl_run_upload 0', 'set cl_board_url ""', 'set sv_public 0', 'set fov 90',
              'set scr_sshot_type png', 'cl_threadedphysics 0', 'name Zoner', f'map {MAP}']
    (game / 'probe.cfg').write_text('\n'.join(common) + '\n')
    return base


def angles(eye, target):
    d = [target[i] - eye[i] for i in range(3)]
    yaw = math.degrees(math.atan2(d[1], d[0]))
    pitch = -math.degrees(math.atan2(d[2], math.hypot(d[0], d[1])))
    return pitch, yaw


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--progs', type=Path, required=True)
    ap.add_argument('--client', type=Path, default=Path('C:/FTESurf/ftesurf64.exe'))
    a = ap.parse_args()
    a.out = a.out.resolve()
    if not any((p / 'OWNER.md').is_file() for p in a.out.parents):
        ap.error('--out must be beneath an owned task root')
    a.out.mkdir(parents=True, exist_ok=False)
    checks, notes = [], []
    report = {'progs': {p: sha(a.progs / p) for p in ('qwprogs.dat', 'csprogs.dat', 'menu.dat')},
              'client': sha(a.client), 'map': sha(MAPS / f'{MAP}.bsp'), 'checks': checks, 'notes': notes}

    def check(ok, name, seen=''):
        checks.append({'name': name, 'pass': bool(ok), 'seen': seen})
        print(('PASS ' if ok else 'FAIL ') + name + (f'  [{seen}]' if seen else ''), flush=True)

    def note(s):
        notes.append(s)
        print('NOTE ' + s, flush=True)

    cl = None
    try:
        base = prepare(a)
        cl = Client(a.client, base, 'probe.cfg')
        end = time.monotonic() + 150
        while True:                     # the command exists once CSQC is up on the map
            try:
                cl.query('zone_edit status', r'zone_edit: state \d+ map ', timeout=3)
                break
            except RuntimeError:
                if time.monotonic() > end or cl.proc.poll() is not None:
                    raise
        time.sleep(4)                   # frames drawn: the VBSP meshes are filled by the batch builder
        cl.send('zone_edit')            # the hooks answer only with the editor open
        cl.query('zone_edit status', r'zone_edit: state 1 map ' + MAP)

        def probe(eye, target):
            m = cl.query('zone_edit snapprobe %.3f %.3f %.3f %.3f %.3f %.3f' % (*eye, *target),
                         r'zone_edit: snap (.+?) ok (\d) hit ' + ' '.join([NUM] * 3) + r' floor ' + NUM +
                         r' raw ' + ' '.join([NUM] * 3) + r' surf (-?\d+) asks (\d+)')
            g = m.groups()
            return {'kind': g[0], 'ok': int(g[1]), 'hit': tuple(map(float, g[2:5])), 'floor': float(g[5]),
                    'raw': tuple(map(float, g[6:9])), 'surf': int(g[9]), 'asks': int(g[10])}

        def wsurf(p):
            off = len(cl.text())
            m = cl.query('zone_edit wsurf %.3f %.3f %.3f' % p,
                         r'zone_edit: wsurf (-?\d+) points (\d+) tris (\d+) normal ' + ' '.join([NUM] * 3))
            n = int(m.group(2))
            pts = []
            if n:
                cl.wait(r'zone_edit: wsurf pt %d ' % (n - 1), off)
                pts = [tuple(map(float, x)) for x in
                       re.findall(r'zone_edit: wsurf pt \d+ ' + ' '.join([NUM] * 3), cl.text()[off:])[:n]]
            return {'surf': int(m.group(1)), 'n': n, 'tris': int(m.group(3)),
                    'normal': tuple(map(float, m.groups()[3:6])), 'pts': pts}

        eye = (SPAWN[0], SPAWN[1], SPAWN[2] + 64)
        down = probe(eye, (SPAWN[0], SPAWN[1], SPAWN[2] - 256))
        check(down['ok'] and down['surf'] >= 0, 'the aim down at the spawn finds a world surface', down)
        floor = down['raw'][2]
        s = wsurf((SPAWN[0], SPAWN[1], floor))
        report['surface'] = s
        ring = s['n'] >= 3 and s['tris'] == s['n'] - 2
        check(ring and s['normal'][2] > 0.7, 'the spawn stands on a ring floor surface',
              f"surf {s['surf']} n {s['n']} tris {s['tris']} normal {s['normal']}")
        report['corners'] = s['pts']
        offgrid = sum(1 for v in s['pts'] if v[0] % 16 or v[1] % 16)
        note(f"{len(s['pts'])} corners on the spawn's floor surface, {offgrid} off the 16 grid")

        cx = sum(v[0] for v in s['pts']) / max(1, len(s['pts']))
        cy = sum(v[1] for v in s['pts']) / max(1, len(s['pts']))

        def inward(v, by):
            dx, dy = cx - v[0], cy - v[1]
            L = math.hypot(dx, dy) or 1
            return (v[0] + dx / L * by, v[1] + dy / L * by, v[2])

        results = {'on': [], 'off': []}
        for mode in ('on', 'off'):
            cl.send('zone_edit edges %d' % (mode == 'on'))
            for v in s['pts']:
                t = inward(v, 3)
                r = probe(eye, t)
                reached = math.dist(r['raw'], t) < 1.5
                results[mode].append({'corner': v, 'target': t, **r, 'reached': reached})
        report['corner_probes'] = results
        measured = [i for i, r in enumerate(results['on']) if r['reached']]
        unreached = len(s['pts']) - len(measured)
        if unreached:
            note(f'{unreached} corner aims did not reach their target from the spawn eye: not measured')
        exact = [i for i in measured if results['on'][i]['kind'] == 'map corner' and
                 math.hypot(results['on'][i]['hit'][0] - s['pts'][i][0],
                            results['on'][i]['hit'][1] - s['pts'][i][1]) < 0.01 and
                 abs(results['on'][i]['floor'] - s['pts'][i][2]) < 0.01 and
                 results['on'][i]['hit'][2] == math.floor(s['pts'][i][2] / 16) * 16]
        check(measured and len(exact) == len(measured), 'Edge snap on: every reached corner aim takes that corner exactly',
              f'{len(exact)}/{len(measured)}')
        missed = [i for i in measured if math.hypot(results['off'][i]['hit'][0] - s['pts'][i][0],
                                                    results['off'][i]['hit'][1] - s['pts'][i][1]) >= 0.01]
        grid_kind = all(results['off'][i]['kind'] == 'grid 16' for i in measured)
        check(grid_kind and missed, 'control, Edge snap off: the same aims take the grid and miss corners',
              f'{len(missed)}/{len(measured)} missed')

        # A long edge's middle, two units inside: an edge point, on the segment, not a corner. With
        # the grid on it is the grid point's foot on the edge; with Surface, the aim's.
        pts = s['pts']

        def foot(p, v, w):
            ex, ey = w[0] - v[0], w[1] - v[1]
            k = max(0, min(1, ((p[0] - v[0]) * ex + (p[1] - v[1]) * ey) / (ex * ex + ey * ey)))
            return (v[0] + k * ex, v[1] + k * ey)

        def inside(p, poly):
            c = False
            for (x0, y0, _), (x1, y1, _) in zip(poly, poly[1:] + poly[:1]):
                if (y0 > p[1]) != (y1 > p[1]) and p[0] < x0 + (p[1] - y0) * (x1 - x0) / (y1 - y0):
                    c = not c
            return c

        # Each edge is a split or a real edge by the surface lists alone: a split has another face of
        # the same flat floor just outside it (surf_sinsane_ez: the triangle's x 12176 edge, whose
        # floor goes on to a strip ending at the slope at x 12198).
        splits = set()
        for i, v in enumerate(pts):
            w = pts[(i + 1) % len(pts)]
            mid = ((v[0] + w[0]) / 2, (v[1] + w[1]) / 2, v[2])
            o = inward(mid, -3)
            n2 = wsurf((o[0], o[1], floor))
            if (n2['surf'] not in (-1, s['surf']) and n2['normal'][2] > 0.999 and n2['pts'] and
                    all(abs(p[2] - v[2]) < 0.05 for p in n2['pts']) and inside(o, n2['pts'])):
                splits.add(i)
        report['split_edges'] = sorted(splits)
        note(f'{len(splits)} of the {len(pts)} edges are splits of one flat floor (by the surface lists)')

        cl.send('zone_edit edges 1')
        for mode in ('grid', 'surface'):
            cl.send('zone_edit grid 16' + (' surface' if mode == 'surface' else ''))
            edge_cases, split_cases = [], []
            for i, v in enumerate(pts):
                w = pts[(i + 1) % len(pts)]
                if math.dist(v[:2], w[:2]) < 128:
                    continue
                mid = ((v[0] + w[0]) / 2, (v[1] + w[1]) / 2, (v[2] + w[2]) / 2)
                t = inward(mid, 2)
                r = probe(eye, t)
                if math.dist(r['raw'], t) >= 1.5:
                    continue
                if i in splits:
                    split_cases.append({'edge': [v, w], 'kind': r['kind'], 'hit': r['hit']})
                    continue
                ex, ey = w[0] - v[0], w[1] - v[1]
                L = math.hypot(ex, ey)
                perp = abs((r['hit'][0] - v[0]) * ey - (r['hit'][1] - v[1]) * ex) / L
                along = ((r['hit'][0] - v[0]) * ex + (r['hit'][1] - v[1]) * ey) / L
                src = ((round(r['raw'][0] / 16) * 16, round(r['raw'][1] / 16) * 16) if mode == 'grid'
                       else r['raw'][:2])
                off = math.dist(r['hit'][:2], foot(src, v, w))
                edge_cases.append({'edge': [v, w], 'kind': r['kind'], 'perp': perp, 'along': along,
                                   'len': L, 'hit': r['hit'], 'raw': r['raw'], 'off_foot': off})
            report['edge_probes_' + mode] = edge_cases
            report['split_probes_' + mode] = split_cases
            if not edge_cases:
                note(f'no real edge of 128+ units was reachable ({mode}): edge snap not measured')
            else:
                check(all(c['kind'] == 'map edge' and c['perp'] < 0.01 and 1 < c['along'] < c['len'] - 1 and
                          c['off_foot'] < 0.02 for c in edge_cases),
                      f'{mode}: a real edge aimed at its middle takes the {mode} point\'s foot on that edge',
                      '; '.join('%s %.3f %.3f off %.3f' % (c['kind'], c['hit'][0], c['hit'][1], c['off_foot'])
                                for c in edge_cases))
            if not split_cases:
                note(f'no split edge was reachable ({mode}): split refusal not measured')
            else:
                check(all(c['kind'] in ('grid 16', 'surface') for c in split_cases),
                      f'{mode}: a split edge in one flat floor is not snapped to',
                      '; '.join('%s %.3f %.3f' % (c['kind'], c['hit'][0], c['hit'][1]) for c in split_cases))
        cl.send('zone_edit grid 16')

        # The floor's real end past the split: the strip's x 12198 edge, where the slope starts.
        strip = wsurf((12187.0, SPAWN[1], floor))
        far = [p for p in strip['pts'] if abs(p[0] - 12198) < .01]
        if strip['surf'] == s['surf'] or len(far) < 2:
            note(f"no strip ending at x 12198 beside the start ({strip['surf']}): its edge not measured")
        else:
            r = probe(eye, (12196.0, SPAWN[1], floor))
            check(r['kind'] == 'map edge' and abs(r['hit'][0] - 12198) < .01 and r['hit'][1] == round(SPAWN[1] / 16) * 16,
                  'the floor\'s real end past the split (x 12198, the slope) is a map edge, on the grid along it',
                  f"{r['kind']} {r['hit']}")

        # Far from every edge: the grid.
        dmin = min((abs((SPAWN[0] - v[0]) * (w[1] - v[1]) - (SPAWN[1] - v[1]) * (w[0] - v[0])) /
                    (math.dist(v[:2], w[:2]) or 1)) for v, w in zip(pts, pts[1:] + pts[:1]))
        mid = probe(eye, (SPAWN[0] + 40, SPAWN[1], floor))
        if dmin < 96:
            note(f'the spawn is {dmin:.0f} units from an edge of its surface: grid-in-the-open not measured')
        else:
            check(mid['kind'] == 'grid 16', 'in the open, far from any edge, the aim keeps the grid', mid['kind'])

        # Cost and the cache.
        c = cl.query('zone_edit snapcost 20 %.3f %.3f %.3f' % (SPAWN[0], SPAWN[1], floor),
                     r'zone_edit: snapcost 20 searches (\d+) ms')
        report['snapcost_ms_per_search'] = int(c.group(1)) / 20
        note(f'one full surface search: {int(c.group(1)) / 20:.2f} ms')
        first = probe(eye, (SPAWN[0] + 8, SPAWN[1] + 8, floor))
        again = probe(eye, (SPAWN[0] - 8, SPAWN[1] - 8, floor))
        check(first['surf'] == again['surf'] == s['surf'] and again['asks'] == first['asks'],
              'a second aim on the same surface does not search again', f"asks {first['asks']} -> {again['asks']}")

        # Placing with the real view: aim at the corner nearest the spawn, read the status, shoot.
        if measured:
            i = min(measured, key=lambda k: math.dist(pts[k][:2], SPAWN[:2]))
            t = inward(pts[i], 3)
            cl.send('sv_cheats 1')
            cl.query('zone_edit status', r'zone_edit: state 1 ')
            cl.send('zone_edit place start')
            cl.query('zone_edit status', r'zone_edit: state 2 ')
            org = (SPAWN[0], SPAWN[1], SPAWN[2] + 8)
            view = None
            for _ in range(3):
                pitch, yaw = angles(view or org, t)
                cl.send('setpos %.3f %.3f %.3f %.3f %.3f 0' % (*org, pitch, yaw))
                time.sleep(1.0)
                m = cl.query('zone_edit status', r'zone_edit: snap (.+?) edges (\d) surf (-?\d+) at ' +
                             ' '.join([NUM] * 3) + ' eye ' + ' '.join([NUM] * 3))
                view = tuple(map(float, m.groups()[6:9]))
            kind, at = m.group(1), tuple(map(float, m.groups()[3:6]))
            check(kind == 'map corner' and math.dist(at[:2], pts[i][:2]) < 0.01,
                  'placing with the view aimed at a corner: the status says map corner, at it', f'{kind} {at}')
            shots = base / 'ftesurf/screenshots'
            cl.send('screenshot p1197_edges_on')
            time.sleep(1.5)
            # The real click path: MOUSE1 takes the snapped corner as the first floor corner.
            cl.send('zone_edit click')
            time.sleep(0.5)
            m = cl.query('zone_edit status', r'zone_edit: state (\d) .*\n.*\n.*\n.*\n.*placing type \d+ seg \d+ cp \d+ a ' +
                         ' '.join([NUM] * 3))
            first = tuple(map(float, m.groups()[1:4]))
            check(m.group(1) == '3' and math.dist(first[:2], pts[i][:2]) < 0.01,
                  'a click there takes the corner as the first floor corner', f'state {m.group(1)} a {first}')
            cl.send('zone_edit back')       # answered in the next frame's draw pass
            time.sleep(0.5)
            cl.query('zone_edit status', r'zone_edit: state 2 ')
            cl.send('zone_edit edges 0')
            time.sleep(1.0)
            m = cl.query('zone_edit status', r'zone_edit: snap (.+?) edges (\d)')
            check(m.group(1) == 'grid 16', 'the same view with Edge snap off says grid', m.group(1))
            cl.send('screenshot p1197_edges_off')
            time.sleep(1.5)
            # Polygon placing (Lex's start zone is one): the same corner, the same snap.
            cl.send('zone_edit back')
            time.sleep(0.5)
            cl.query('zone_edit status', r'zone_edit: state 1 ')
            cl.send('zone_edit shape polygon')
            cl.send('zone_edit edges 1')
            cl.send('zone_edit place start')
            time.sleep(1.0)
            m = cl.query('zone_edit status', r'zone_edit: state (\d) [^\n]*\n(?:.*\n){4}.*zone_edit: snap (.+?) edges (\d) surf (-?\d+) at ' +
                         ' '.join([NUM] * 3))
            at = tuple(map(float, m.groups()[4:7]))
            check(m.group(1) == '5' and m.group(2) == 'map corner' and math.dist(at[:2], pts[i][:2]) < 0.01,
                  'polygon placing: the same view snaps to the same corner', f'state {m.group(1)} {m.group(2)} {at}')
            cl.send('screenshot p1197_polygon')
            time.sleep(1.5)
            report['screenshots'] = sorted(str(p) for p in shots.glob('p1197_*'))
            check(len(report['screenshots']) == 3, 'three screenshots written', report['screenshots'])
    except Exception as e:                  # recorded, then the cleanup still runs
        check(False, 'arm ran to the end', repr(e))
    finally:
        if cl:
            cl.stop()
        (a.out / 'report.json').write_text(json.dumps(report, indent=1))
    fails = [c['name'] for c in checks if not c['pass']]
    print(f"{len(checks) - len(fails)}/{len(checks)} pass" + (f"; FAIL: {fails}" if fails else ''))
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
