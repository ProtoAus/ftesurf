#!/usr/bin/env python3
"""CS:S round logic: maps whose logic_timer, or a delayed logic_auto, switches a trigger_teleport
on or off (jails, "round over" and "time's up" teleports).  With no rounds those switches fire
once after the map loads and stay -- surf_network2008_final's start fall box became a jail 30 s in.
Patch 890's cfg/maps/entfix_<map>.cfg is how one is fixed; this lists the candidates and whether
the map has a zone file (only a zoned map is timed).

  python tools/census/roundlogic.py <maps dir> [more dirs] [--zones dir ...] [--map name]
"""
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bsplib


def outputs(pairs):
    for k, v in pairs:
        if not k.lower().startswith('on'):
            continue
        p = v.replace('\x1b', ',').split(',')
        if len(p) < 4:
            continue
        try:
            delay = float(p[3] or 0)
        except ValueError:
            delay = 0.0
        yield k, p[0].lower(), p[1].lower(), delay


def scan(path):
    ents, _ = bsplib.read_pairs(path)
    teles = {}
    for e in ents:
        d = {k.lower(): v for k, v in e}
        if d.get('classname') == 'trigger_teleport' and d.get('targetname'):
            teles[d['targetname'].lower()] = d.get('target', '')
    rows = []
    for e in ents:
        d = {k.lower(): v for k, v in e}
        cl = d.get('classname')
        if cl not in ('logic_timer', 'logic_auto'):
            continue
        for key, tgt, inp, delay in outputs(e):
            if tgt in teles and inp in ('enable', 'disable', 'toggle') and (cl == 'logic_timer' or delay > 0):
                rows.append('%s %s %s %s@%g -> %s' % (cl, d.get('targetname', '-'), tgt, inp, delay,
                                                       teles[tgt] or '(no target)'))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('dirs', nargs='+')
    ap.add_argument('--zones', action='append', default=[])
    ap.add_argument('--map')
    a = ap.parse_args()
    zoned = set()
    for z in a.zones:
        if os.path.isdir(z):
            zoned |= {f.rsplit('.', 1)[0].lower() for f in os.listdir(z)}
    seen = set()
    hits = 0
    for d in a.dirs:
        for fn in sorted(os.listdir(d)):
            if not fn.lower().endswith('.bsp'):
                continue
            name = fn[:-4].lower()
            if name in seen or (a.map and name != a.map.lower()):
                continue
            seen.add(name)
            try:
                rows = scan(os.path.join(d, fn))
            except Exception as ex:
                print('%s: unreadable (%s)' % (name, ex), file=sys.stderr)
                continue
            if rows:
                hits += 1
                print('%s%s' % (name, '  [zoned]' if name in zoned else ''))
                for r in rows:
                    print('    ' + r)
    print('%d of %d maps switch teleports from a timer' % (hits, len(seen)))


if __name__ == '__main__':
    main()
