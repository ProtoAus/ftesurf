#!/usr/bin/env python3
"""P1203: zone_edit handles -- a zone's corners, edges and faces dragged with the crosshair.

One owned listen client hosts surf_sinsane_ez (tools/p1197snap.py's overlay). Every step runs
the editor's own per-frame code with `zone_edit aimfix` standing in for the view, `zone_edit
click` / `drop` / `back` for Mouse1 down / up and Mouse2, and `zone_edit ring` printing the
selected zone exactly. A fresh box (11904..12096 x 8320..8480, z 13776 + 128, around the start's
spawn) is added for each case. Cases: the handle each aim lights; a corner onto the start floor's
map corner (11718 8396) with Edge snap; a corner on grid 16 and 8; an edge on grid 16; a side
face pushed out; the top and the bottom pulled; a crossing move refused; Mouse2 cancelling; a
click on another zone selecting it. Then the real view, aimed by setpos, for two screenshots.
--out must be fresh and beneath an owned task root; --progs holds the three .dat files.
"""
import argparse
import json
import math
from pathlib import Path
import re
import sys
import time

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import p1197snap as S  # noqa: E402

NUM = r'(-?[0-9.]+)'
EYE = (12089.6, 8393.6, 13841.0)
BOX = (11904, 8320, 12096, 8480, 13776, 128)


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
    report = {'progs': {p: S.sha(a.progs / p) for p in ('qwprogs.dat', 'csprogs.dat', 'menu.dat')},
              'client': S.sha(a.client), 'checks': checks, 'notes': notes, 'cases': {}}

    def check(ok, name, seen=''):
        checks.append({'name': name, 'pass': bool(ok), 'seen': str(seen)})
        print(('PASS ' if ok else 'FAIL ') + name + (f'  [{seen}]' if seen else ''), flush=True)

    cl = None
    try:
        base = S.prepare(a)
        cl = S.Client(a.client, base, 'probe.cfg')
        end = time.monotonic() + 150
        while True:
            try:
                cl.query('zone_edit status', r'zone_edit: state \d+ map ', timeout=3)
                break
            except RuntimeError:
                if time.monotonic() > end or cl.proc.poll() is not None:
                    raise
        time.sleep(4)
        cl.send('zone_edit')
        cl.query('zone_edit status', r'zone_edit: state 1 map ' + S.MAP)

        def frames(k=0.35):
            time.sleep(k)

        def ring():
            off = len(cl.text())
            m = cl.query('zone_edit ring', r'zone_edit: ring (-?\d+) pts (\d+) bottom ' + NUM + ' top ' + NUM +
                         r' handle (\d+) (\d+) (\d+) drag (\d) bad (\d)')
            n = int(m.group(2))
            cl.wait(r'zone_edit: ring pt %d ' % (n - 1), off)
            pts = [tuple(map(float, p)) for p in
                   re.findall(r'zone_edit: ring pt \d+ ' + NUM + ' ' + NUM, cl.text()[off:])[:n]]
            g = m.groups()
            return {'sel': int(g[0]), 'bottom': float(g[2]), 'top': float(g[3]), 'hk': int(g[4]),
                    'hi': int(g[5]), 'hl': int(g[6]), 'drag': int(g[7]), 'bad': int(g[8]), 'pts': pts}

        def state():
            return int(cl.query('zone_edit status', r'zone_edit: state (\d+) ').group(1))

        def aim(t, eye=EYE):
            cl.send('zone_edit aimfix %.3f %.3f %.3f %.3f %.3f %.3f' % (*eye, *t))
            frames()

        def fresh(grid=16, edges=1):
            # Back to the panel, an empty table, one box, selected, in the edit state.
            cl.send('zone_edit aimfix off')
            if state() != 1:
                cl.send('zone_edit back')
                frames()
            for _ in range(4):
                cl.send('zone_edit del 0')
            frames()
            cl.send('zone_edit add start 0 %d %d %d %d %d %d' % BOX)
            frames()
            cl.send('zone_edit sel 0')
            cl.send('zone_edit grid %d' % grid)
            cl.send('zone_edit edges %d' % edges)
            cl.send('zone_edit edit')
            frames()
            st = state()
            r = ring()
            return st, r

        def idx(r, x, y):
            for i, p in enumerate(r['pts']):
                if abs(p[0] - x) < .01 and abs(p[1] - y) < .01:
                    return i
            return -1

        def drag(grab, to, drop=True):
            aim(grab)
            cl.send('zone_edit click')
            frames()
            aim(to)
            frames()
            mid = ring()
            if drop:
                cl.send('zone_edit drop')
                frames()
            return mid, ring()

        x0, y0, x1, y1, zb, h = BOX
        st, r0 = fresh()
        report['cases']['fresh'] = r0
        check(st == 6 and len(r0['pts']) == 4 and r0['bottom'] == zb and r0['top'] == zb + h,
              'Edit shape enters the edit state on a fresh box', f"state {st} {r0}")

        # Highlight: what each aim lights.
        lit = {}
        aim((x0, y0, zb)); lit['corner'] = ring()
        aim((x1, (y0 + y1) / 2, zb)); lit['edge'] = ring()
        aim(((x0 + x1) / 2, y1, zb + h / 2)); lit['side'] = ring()
        aim(((x0 + x1) / 2 - 40, (y0 + y1) / 2, zb + h)); lit['top'] = ring()
        aim(((x0 + x1) / 2 - 40, (y0 + y1) / 2, zb)); lit['bottom'] = ring()
        report['cases']['lit'] = lit
        check(lit['corner']['hk'] == 1 and lit['corner']['hl'] == 0 and lit['corner']['hi'] == idx(r0, x0, y0) and
              lit['edge']['hk'] == 2 and lit['edge']['hl'] == 0 and lit['side']['hk'] == 3 and
              lit['top']['hk'] == 4 and lit['bottom']['hk'] == 5,
              'each aim lights its handle: corner, edge, side, top, bottom',
              {k: (v['hk'], v['hi'], v['hl']) for k, v in lit.items()})

        # A corner onto the start floor's map corner, with Edge snap.
        st, r = fresh()
        i = idx(r, x0, y0)
        mid, end_ = drag((x0, y0, zb), (11721.0, 8396.0, 13776.0))
        report['cases']['corner_map'] = [mid, end_]
        check(mid['drag'] == 1 and end_['drag'] == 0 and i >= 0 and
              abs(end_['pts'][i][0] - 11718) < .01 and abs(end_['pts'][i][1] - 8396) < .01,
              'a corner dragged near the map corner lands on it exactly (Edge snap)', end_['pts'][i] if i >= 0 else r)
        d = int(cl.query('zone_edit status', r'zone_edit: state \d+ map \S+ zones \d+ points \d+ dirty (\d)').group(1))
        check(d == 1, 'a drop marks the table changed (not saved)', f'dirty {d}')

        # Grid 16 and 8, Edge snap off: the aim on the corner's level, rounded.
        for g in (16, 8):
            st, r = fresh(grid=g, edges=0)
            i = idx(r, x1, y1)
            mid, end_ = drag((x1, y1, zb), (12150.3, 8501.7, zb))
            want = (round(12150.3 / g) * g, round(8501.7 / g) * g)
            report['cases'][f'corner_grid{g}'] = end_
            check(i >= 0 and end_['pts'][i] == want, f'a corner on grid {g} goes to the aim rounded to {g}',
                  f"{end_['pts'][i] if i >= 0 else r} want {want}")

        # An edge (the east one) on grid 16: both ends move by the rounded offset.
        st, r = fresh(edges=0)
        ia, ib = idx(r, x1, y0), idx(r, x1, y1)
        mid, end_ = drag((x1, (y0 + y1) / 2, zb), (x1 + 34, (y0 + y1) / 2 + 10, zb))
        report['cases']['edge'] = [mid, end_]
        check(mid['hk'] == 2 and end_['pts'][ia] == (x1 + 32, y0 + 16) and end_['pts'][ib] == (x1 + 32, y1 + 16),
              'an edge on grid 16 moves both corners by the rounded offset',
              f"{end_['pts'][ia]} {end_['pts'][ib]}")

        # The north side face pushed out 50 -> 48 on grid 16, along its normal only.
        st, r = fresh(edges=0)
        ia, ib = idx(r, x0, y1), idx(r, x1, y1)
        mid, end_ = drag(((x0 + x1) / 2, y1, zb + h / 2), ((x0 + x1) / 2 + 30, y1 + 50, zb + h / 2))
        report['cases']['side'] = [mid, end_]
        check(mid['hk'] == 3 and end_['pts'][ia] == (x0, y1 + 48) and end_['pts'][ib] == (x1, y1 + 48),
              'a side face moves along its own normal, on the grid', f"{end_['pts'][ia]} {end_['pts'][ib]}")

        # The top pulled to the height the aim passes nearest; the bottom with the floor-down rule.
        st, r = fresh(edges=0)
        gx, gy = (x0 + x1) / 2 - 40, (y0 + y1) / 2
        mid, end_ = drag((gx, gy, zb + h), (gx, gy, 13990.0))
        report['cases']['top'] = [mid, end_]
        check(mid['hk'] == 4 and end_['top'] == round(13990 / 16) * 16 and end_['bottom'] == zb,
              'the top face takes the aimed height on the grid', f"top {end_['top']} bottom {end_['bottom']}")
        st, r = fresh(edges=0)
        mid, end_ = drag((gx, gy, zb), (gx, gy, 13700.0))
        report['cases']['bottom'] = [mid, end_]
        check(mid['hk'] == 5 and end_['bottom'] == math.floor(13700 / 16) * 16 and end_['top'] == zb + h,
              'the bottom face takes the aimed height, down to the grid', f"bottom {end_['bottom']} top {end_['top']}")

        # A crossing move is refused; the zone stays as it was.
        st, r = fresh(edges=0)
        i = idx(r, x0, y0)
        mid, end_ = drag((x0, y0, zb), (12000.0, 8560.0, zb))
        report['cases']['crossing'] = [mid, end_]
        check(mid['bad'] == 1 and end_['pts'] == r['pts'], 'a move that would cross the outline is refused',
              f"bad {mid['bad']} {end_['pts']}")

        # Mouse2 mid-drag puts it back.
        st, r = fresh(edges=0)
        mid, _ = drag((x0, y0, zb), (11850.0, 8300.0, zb), drop=False)
        cl.send('zone_edit back')
        frames()
        back = ring()
        report['cases']['cancel'] = [mid, back]
        check(mid['pts'] != r['pts'] and back['pts'] == r['pts'] and back['drag'] == 0 and state() == 6,
              'Mouse2 mid-drag puts the zone back and stays in the edit state', f"{mid['pts']} -> {back['pts']}")

        # A click on another zone (nothing of the selected one under the aim) selects it.
        cl.send('zone_edit aimfix off')
        cl.send('zone_edit back')
        frames()
        cl.send('zone_edit add end 0 11000 8000 11128 8128 13776 128')
        frames()
        sel_end = None
        for z in range(2):
            cl.send(f'zone_edit sel {z}')
            if ring()['pts'][0][0] < 11500:
                sel_end = z
        cl.send('zone_edit sel %d' % (1 - sel_end))
        cl.send('zone_edit edit')
        frames()
        # From above the end zone: nothing of the start box is near this aim.
        aim((11064.0, 8070.0, 13800.0), eye=(11064.0, 8064.0, 14000.0))
        cl.send('zone_edit click')
        frames()
        picked = ring()
        check(picked['sel'] == sel_end and picked['drag'] == 0, 'a click on another zone selects it',
              f"sel {picked['sel']} want {sel_end}")

        # The real view: setpos aims at a corner of a fresh box; lit, then held.
        st, r = fresh(edges=1)
        cl.send('zone_edit aimfix off')
        cl.send('sv_cheats 1')
        org = (EYE[0], EYE[1], 13785.0)
        target = (x0, y0, zb)
        view = None
        for _ in range(3):
            pitch, yaw = S.angles(view or (org[0], org[1], org[2] + 55), target)
            cl.send('setpos %.3f %.3f %.3f %.3f %.3f 0' % (*org, pitch, yaw))
            time.sleep(1.0)
            m = cl.query('zone_edit status', r'eye ' + ' '.join([NUM] * 3))
            view = tuple(map(float, m.groups()))
        lit_real = ring()
        check(lit_real['hk'] == 1 and lit_real['hi'] == idx(r, x0, y0),
              'the real view aimed at a corner lights it', (lit_real['hk'], lit_real['hi'], lit_real['hl']))
        cl.send('screenshot p1203_lit')
        time.sleep(1.5)
        cl.send('zone_edit click')
        frames()
        pitch, yaw = S.angles(view, (11760.0, 8380.0, zb))
        cl.send('setpos %.3f %.3f %.3f %.3f %.3f 0' % (*org, pitch, yaw))
        time.sleep(1.0)
        held = ring()
        check(held['drag'] == 1, 'Mouse1 holds it while the view turns', held['drag'])
        cl.send('screenshot p1203_held')
        time.sleep(1.5)
        cl.send('zone_edit drop')
        frames()
        report['screenshots'] = sorted(str(p) for p in (base / 'ftesurf/screenshots').glob('p1203_*'))
        check(len(report['screenshots']) == 2, 'two screenshots written', report['screenshots'])

        # Review 1. A top corner with Edge snap on: a map corner on the floor far below is not its
        # target, and an aim that never meets the top's level does not move it.
        st, r = fresh(edges=1)
        i = idx(r, x0, y0)
        mid, end_ = drag((x0, y0, zb + h), (11721.0, 8396.0, 13776.0))
        report['cases']['top_corner_snap'] = [mid, end_]
        check(mid['hk'] == 1 and mid['hl'] == 1 and end_['pts'][i] == (x0, y0),
              'review 1: a top corner does not jump to a map corner on the floor below',
              f"handle {mid['hk']} {mid['hl']} corner {end_['pts'][i]}")

        # Review 2: a corner's vertical edge, grabbed mid-height, still takes the floor's map corner.
        st, r = fresh(edges=1)
        i = idx(r, x0, y0)
        mid, end_ = drag((x0, y0, zb + h / 2), (11721.0, 8396.0, 13776.0))
        report['cases']['vertical_edge_snap'] = [mid, end_]
        check(mid['hk'] == 1 and mid['hl'] == 2 and abs(end_['pts'][i][0] - 11718) < .01 and abs(end_['pts'][i][1] - 8396) < .01,
              'review 2: a vertical edge grabbed mid-height snaps to the map corner below',
              f"handle {mid['hk']} {mid['hl']} corner {end_['pts'][i]}")

        # Review 3: with no snap, that vertical edge goes where the aim meets the floor (on the grid),
        # not where the aim crosses the grab's height (near the eye when that is eye level).
        st, r = fresh(edges=0)
        i = idx(r, x0, y0)
        mid, end_ = drag((x0, y0, zb + h / 2), (11950.0, 8365.0, 13776.0))
        report['cases']['vertical_edge_floor'] = [mid, end_]
        check(mid['hk'] == 1 and mid['hl'] == 2 and end_['pts'][i] == (11952.0, 8368.0),
              'review 3: a vertical edge with no snap goes to the aimed floor point on the grid',
              f"handle {mid['hk']} {mid['hl']} corner {end_['pts'][i]} want (11952, 8368)")

        # Review 4: a side face taken above the eye, aimed down at the floor beyond it, still moves.
        st, r = fresh(edges=0)
        ia, ib = idx(r, x0, y1), idx(r, x1, y1)
        mid, end_ = drag(((x0 + x1) / 2, y1, zb + h - 14), (12010.0, 8530.0, 13776.0))
        report['cases']['side_above_eye'] = [mid, end_]
        check(mid['hk'] == 3 and end_['pts'][ia] == (x0, y1 + 48) and end_['pts'][ib] == (x1, y1 + 48),
              'review 4: a side face taken above the eye follows the aim on the floor',
              f"handle {mid['hk']} {end_['pts'][ia]} {end_['pts'][ib]}")

        # Review 4: the bottom face ignores a map corner across the room (the slope's foot at
        # 12230 8331 13749): its height is where the aim passes the grab's vertical.
        st, r = fresh(edges=1)
        gx, gy = (x0 + x1) / 2 - 40, (y0 + y1) / 2
        mid, end_ = drag((gx, gy, zb), (12227.0, 8333.0, 13749.0))
        report['cases']['bottom_far_snap'] = [mid, end_]
        # NOT a check: the review-3 build (no gate) also gave a bottom other than 13744 here, so this
        # aim never produced the far snap the gate refuses. Recorded, not graded.
        notes.append(f"bottom face aimed at a far corner: handle {mid['hk']} bottom {end_['bottom']} (not discriminating)")

        # Another panel opening mid-drag puts the zone back.
        st, r = fresh(edges=0)
        mid, _ = drag((x0, y0, zb), (11850.0, 8300.0, zb), drop=False)
        cl.send('scores open')
        frames(0.6)
        under = ring()
        cl.send('scores close')
        frames()
        report['cases']['blocker'] = [mid, under]
        check(mid['pts'] != r['pts'] and under['pts'] == r['pts'] and under['drag'] == 0,
              'review 1: a panel opening mid-drag puts the zone back', f"{mid['pts']} -> {under['pts']}")

        # The table replaced under a held drag (zone_reload of the saved file): let go, nothing written.
        st, r = fresh(edges=0)
        cl.send('zone_edit back')
        frames()
        cl.send('zone_edit save force')
        frames(0.8)
        cl.send('zone_edit add end 0 11000 8000 11128 8128 13776 128')
        frames()
        sel_a = None
        for z in range(2):
            cl.send(f'zone_edit sel {z}')
            if ring()['pts'][0][0] > 11500:
                sel_a = z
        cl.send(f'zone_edit sel {sel_a}')
        cl.send('zone_edit edit')
        frames()
        mid, _ = drag((x0, y0, zb), (11850.0, 8300.0, zb), drop=False)
        cl.send('zone_reload')
        frames(0.8)
        zones = int(cl.query('zone_edit status', r'zone_edit: state \d+ map \S+ zones (\d+)').group(1))
        cl.send('zone_edit sel 0')
        after = ring()
        report['cases']['reload'] = [mid, after, zones]
        check(mid['pts'] != r['pts'] and zones == 1 and after['pts'] == r['pts'] and after['drag'] == 0,
              'review 1: a table replaced mid-drag is let go, the reloaded zone untouched',
              f"zones {zones} {after['pts']} drag {after['drag']}")

        # Last (the review-0 build dies here): the editor closed mid-drag, then opened again.
        st, r = fresh(edges=0)
        mid, _ = drag((x0, y0, zb), (11850.0, 8300.0, zb), drop=False)
        cl.send('zone_edit')
        frames()
        cl.send('zone_edit')
        frames(0.8)
        st = state()
        cl.send('zone_edit sel 0')
        again = ring()
        report['cases']['close_reopen'] = [mid, again, st]
        check(cl.proc.poll() is None and st == 1 and again['pts'] == r['pts'] and again['drag'] == 0,
              'review 1: closing the editor mid-drag puts the zone back; reopening is safe',
              f"state {st} {again['pts']}")
    except Exception as e:
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
