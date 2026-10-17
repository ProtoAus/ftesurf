#!/usr/bin/env python3
"""Patch 745: grade runlines_demowin.cfg's log.

python tools/test_runlines_demowin.py <rig>/ftesurf/logs/runlines_smoke.log [--control <log>]

Reads the demo slot's `lnd` (playhead, window on, window ends) and `lnd2` (points drawn)
lines from `replay marktrace` in each section.  The window must be off for `whole`,
[t-1, t+4] for 4 s, [t-2, t+8] for "as board lines" at hud_lines_order 8, the console's
own [t-6, t+2] when hud_lines_win/winf are set, and the replay's own distance must draw
fewer points than the whole line, as hud_watch_path_far does.  The review's cases: with
hud_watch_path_ahead 0 the window is the span behind the playhead, [t-4, t+0.8]; the
line's name only sits on the windowed stretch (its point's nearest recorded sample is
inside the window); and at a demo distance of 40 u no name is further than that from
the eye, though a board line drawn the same frame reaches 12000.  A control log from a
build before the patch must fail: it has no window at 4 s.
"""
import math
import os
import argparse
import re
import sys

LND = re.compile(r'lnd 0 (\S+) (\S+) (\S+) (\S+)')
LND2 = re.compile(r'lnd2 0 (\S+) (\S+) (\S+) (\S+) (\S+)')
EYE = re.compile(r'linegraph: eye (\S+) (\S+) (\S+)')
LABEL0 = re.compile(r'linegraph: label 0 at (\S+) (\S+) (\S+)')


def samples(rec):
    out, body = [], False
    for line in open(rec, encoding='utf-8', errors='replace'):
        if line.startswith('begin'):
            body = True
            continue
        if body and line[:1] in '-0123456789':
            w = line.split()
            out.append((float(w[0]), (float(w[1]), float(w[2]), float(w[3]))))
    return out


def sections(text):
    out, name = {}, None
    for line in text.splitlines():
        m = re.search(r'==== (.+?) ====', line)
        if m:
            name = m.group(1)
            out.setdefault(name, [])
        elif name:
            out[name].append(line)
    return out


def first(lines, rx):
    for line in lines:
        m = rx.search(line)
        if m:
            return [float(g) for g in m.groups()]
    return None


def grade(path):
    s = sections(open(path, encoding='utf-8', errors='replace').read())
    fails = []
    got = {}
    rec = os.path.join(os.path.dirname(os.path.dirname(path)), 'cfg', 'test', 'runlines_sample.rec')
    pts = samples(rec) if os.path.isfile(rec) else []
    for name in ('WHOLE', 'AHEAD4', 'ASBOARD', 'OVERRIDE', 'NEAR', 'PATHFAR'):
        d, d2 = first(s.get(name, []), LND), first(s.get(name, []), LND2)
        got[name] = (d, d2)
        print(name, 'lnd', d, 'lnd2', d2)
        if not d or not d2:
            fails.append('%s: no demo-slot trace' % name)
    if fails:
        return fails

    def window(name, behind, ahead):
        t, on, a, b = got[name][0]
        if on != 1:
            fails.append('%s: no window' % name)
        elif abs(a - (t - behind)) > 0.01 or abs(b - (t + ahead)) > 0.01:
            fails.append('%s: window %.3f..%.3f around %.3f, wanted -%g/+%g' % (name, a, b, t, behind, ahead))

    if got['WHOLE'][0][1] != 0:
        fails.append('WHOLE: a window was set')
    window('AHEAD4', 1, 4)
    window('ASBOARD', 2, 8)
    window('OVERRIDE', 6, 2)
    if got['NEAR'][0][1] != 0:
        fails.append('NEAR: a window was set')
    whole, near, pathfar = got['WHOLE'][1][2], got['NEAR'][1][2], got['PATHFAR'][1][2]
    if not near < whole * 0.8:
        fails.append('NEAR: %g points drawn against %g whole: the distance did not take' % (near, whole))
    if not pathfar < whole * 0.8:
        fails.append('PATHFAR: hud_watch_path_far 1500 drew %g of %g' % (pathfar, whole))
    if abs(near - pathfar) > max(8, 0.1 * near):
        fails.append('NEAR %g against PATHFAR %g: the two distances disagree' % (near, pathfar))
    if not got['AHEAD4'][1][2] < whole:
        fails.append('AHEAD4: the window drew no fewer points than the whole line')

    a0 = first(s.get('AHEAD0', []), LND)
    print('AHEAD0 lnd', a0)
    if not a0:
        fails.append('AHEAD0: no demo-slot trace')
    else:
        t, on, a, b = a0
        if on != 1 or abs(a - (t - 4)) > 0.01 or abs(b - (t + 0.8)) > 0.01:
            fails.append('AHEAD0: window %s..%s around %s, wanted -4/+0.8' % (a, b, t))
        lab = first(s.get('AHEAD0', []), LABEL0)
        print('AHEAD0 name at', lab)
        if lab and pts:
            tn = min(pts, key=lambda q: math.dist(q[1], lab))[0]
            print('AHEAD0 name sits on the sample at t', tn)
            if not a - 0.05 <= tn <= b + 0.05:
                fails.append('AHEAD0: the name sits at t %.3f, outside the drawn %.3f..%.3f' % (tn, a, b))
        elif lab:
            fails.append('AHEAD0: no recording in the rig to place the name with')
    eye = first(s.get('NAMENEAR', []) or s.get('NAMEFAR', []), EYE) or first(s.get('NAMEFAR', []), EYE)
    lab = first(s.get('NAMENEAR', []), LABEL0)
    print('NAMENEAR name at', lab, 'eye', eye)
    if 'NAMENEAR' not in s:
        fails.append('NAMENEAR: section missing')
    elif lab and eye and math.dist(lab, eye) > 40.5:
        fails.append('NAMENEAR: the name is %.1f u from the eye past a 40 u demo line' % math.dist(lab, eye))
    return fails


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('log')
    ap.add_argument('--control', help='a log from a build before Patch 745: must fail')
    a = ap.parse_args()
    fails = grade(a.log)
    for f in fails:
        print('FAIL', f)
    if a.control:
        print('--- control ---')
        cf = grade(a.control)
        for f in cf:
            print('control fails (wanted):', f)
        if not cf:
            print('FAIL the control passed: the arm does not tell the builds apart')
            return 1
    print('PASS' if not fails else 'FAILED')
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
