#!/usr/bin/env python3
"""Patch 745: grade runlines_hidden.cfg's log.

python tools/test_runlines_hidden.py <rig>/ftesurf/logs/runlines_smoke.log [--control <log>]

With hud_trail 0 the live line must still grow (the `trail` line's points), a rewind
must open on it (`rewind: on 1`), and turning the line back on shows the run so far.
A control log from a build before the patch must fail the first check: there the
line is reset while hidden and the rewind refuses with "hud_trail is off".
"""
import argparse
import re
import sys

TRAIL = re.compile(r'trail: cv (\S+)\s+live slot \S+ \((\d+) pts, on (\d+)\)')
REWIND = re.compile(r'rewind: on (\d+) counting (\d+)')


def sections(text):
    out = {}
    name = None
    for line in text.splitlines():
        m = re.search(r'==== (.+?) ====', line)
        if m:
            name = m.group(1)
            out.setdefault(name, [])
            continue
        if name:
            out[name].append(line)
    return out


def grade(path):
    text = open(path, encoding='utf-8', errors='replace').read()
    s = sections(text)
    fails = []

    def trail(name):
        for line in s.get(name, []):
            m = TRAIL.search(line)
            if m:
                return float(m.group(1)), int(m.group(2)), int(m.group(3))
        return None

    def rewind(name):
        for line in s.get(name, []):
            m = REWIND.search(line)
            if m:
                return int(m.group(1)), int(m.group(2))
        return None

    run = trail('HIDDEN RUN')
    print('hidden run trail (cv, pts, on):', run)
    if not run or run[0] != 0:
        fails.append('HIDDEN RUN: no trail line with hud_trail 0')
    elif run[1] < 10 or run[2] != 1:
        fails.append('HIDDEN RUN: the hidden line did not grow (%d pts, on %d)' % (run[1], run[2]))
    if not any('timer: running' in line for line in s.get('HIDDEN RUN', [])):
        fails.append('HIDDEN RUN: cmd timer never said running')
    rw = rewind('HIDDEN REWIND')
    print('rewind with the line hidden (on, counting):', rw)
    if not rw or rw[0] != 1:
        fails.append('HIDDEN REWIND: the rewind did not open (%s)' % (rw,))
    if 'hud_trail is off' in text:
        fails.append('a rewind was refused for hud_trail')
    closed = rewind('HIDDEN CLOSED')
    print('after leaving (on, counting):', closed)
    if not closed or (closed[0] != 0 and closed[1] != 1):
        fails.append('HIDDEN CLOSED: the leave was not taken (%s)' % (closed,))
    shown = trail('SHOWN AGAIN')
    print('shown again trail (cv, pts, on):', shown)
    if not shown or shown[0] != 1 or not run or shown[1] < run[1]:
        fails.append('SHOWN AGAIN: the line was not there to show')
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
