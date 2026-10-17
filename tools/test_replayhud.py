#!/usr/bin/env python3
"""Patch 750: grade replayhud_infer.cfg -- a replay's panels for a file with no board,
stage or cp records.

python tools/test_replayhud.py [<rig>/ftesurf] [--ksf <rig of replayhud_ksf.cfg>/ftesurf] [--control]

NATIVE is Lex's surf_kitsune PB, whose own records are the truth. ASIMPORT is that file
as an import (`foreign`, those records and the plane columns gone, the ramp bit kept):
its split events, from the zones, must be NATIVE's (same stages, ticks within 1), and
its inferred boards must find NATIVE's (each within 2 ticks), with the plane the map
has and a velocity whose grade agrees. INFERRED also clears the ramp bit (contact
inferred, as a Momentum import's): reported, with a looser bar. Every replay's leaves
are kept (the Boarding leave row): ASIMPORT's are NATIVE's. MOM, a real surf_dune
Momentum import, has its two stage events and inferred boards, and its 40 s timer is
past stage 1. KSF (replayhud_ksf.cfg, a v2 clip with no ground flag): ground read from
vz lets its contact be inferred (step 12.00, the 66 t tick's gravity), so it has boards,
leaves, Segments rows and a trainer with contact. --control: a build without the patch
must fail the same checks.
Exit 2 is CANNOT MEASURE.
"""
import argparse
import math
import pathlib
import re
import sys

CANNOT = 'CANNOT MEASURE: '


def sections(text):
    out, name = {}, None
    for line in text.splitlines():
        line = re.sub(r'^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d ', '', line)
        m = re.search(r'==== (.+?) ====', line)
        if m:
            name = m.group(1)
            out.setdefault(name, [])
        elif name:
            out[name].append(line)
    return out


def table(body):
    boards, leaves, events, head = [], [], [], None
    for l in body:
        w = l.split()
        if not w:
            continue
        if w[0] == 'wtbd':
            head = [float(x) for x in w[1:4]]
        elif w[0] == 'wtb' and len(w) >= 10:
            boards.append((float(w[2]), tuple(map(float, w[4:7])), tuple(map(float, w[7:10]))))
        elif w[0] == 'wtl':
            leaves.append((float(w[2]), float(w[3]), float(w[4])))
        elif w[0] == 'wte':
            events.append((int(float(w[2])), int(float(w[3])), int(float(w[4]))))
    return head, boards, leaves, events


def panels(body):
    """What any build prints: the split list's length, `replay status`'s board count."""
    n = next((re.search(r'cl splits: n (\d+)', l) for l in body if 'cl splits: n' in l), None)
    b = next((re.search(r'seq \S+ rows \(\S+ shown\)  boards (\S+)', l) for l in body
              if 'rows (' in l), None)
    return (int(n.group(1)) if n else None), (float(b.group(1)) if b else None)


def grade(vin, n):
    """Board_Compute's losspct, kept % and Board_Grade."""
    sp = math.sqrt(sum(a * a for a in vin))
    if sp < 0.001:
        return None
    dot = min(1, abs(sum(a * b for a, b in zip(vin, n))) / sp)
    sina = math.sqrt(max(0, 1 - dot * dot))
    loss = dot * dot / (1 + sina)
    appr = math.degrees(math.acos(dot))
    f = max(1, math.sqrt(sp / 1500))
    g = 4
    for k, (lim, a) in enumerate(((0.005, 85), (0.015, 80), (0.030, 75), (0.050, 60))):
        if loss <= lim * f and appr >= a:
            g = k
            break
    return loss, sina * 100, g


def angle(a, b):
    d = sum(x * y for x, y in zip(a, b))
    return math.degrees(math.acos(max(-1, min(1, d))))


def boards_vs(name, truth, got, fails, notes, bar):
    gated = [b for b in truth if grade(b[2], b[1]) and math.dist(b[2], (0, 0, 0)) >= 100]
    match, used = [], set()
    for t, n, v in truth:
        best = None
        for k, (t2, n2, v2) in enumerate(got):
            if k in used or abs(t2 - t) > 0.031:
                continue
            if best is None or abs(t2 - t) < abs(got[best][0] - t):
                best = k
        if best is not None:
            used.add(best)
            match.append(((t, n, v), got[best]))
    extra = len(got) - len(used)
    na = sorted(angle(a[1], b[1]) for a, b in match)
    dk, same = [], 0
    for a, b in match:
        ga, gb = grade(a[2], a[1]), grade(b[2], b[1])
        if ga and gb:
            dk.append(abs(ga[1] - gb[1]))
            same += ga[2] == gb[2]
    med = lambda xs: xs[len(xs) // 2] if xs else float('nan')
    print('%s boards: %d recorded, %d inferred, %d matched within 2 ticks, %d extra; plane '
          'error median %.2f max %.2f deg; kept %% error median %.2f max %.2f; same grade %d of %d'
          % (name, len(truth), len(got), len(match), extra, med(na), na[-1] if na else float('nan'),
             med(sorted(dk)), max(dk) if dk else float('nan'), same, len(dk)))
    if not truth:
        notes.append(CANNOT + '%s: no recorded boards to grade against' % name)
        return
    if len(match) < bar['found'] * len(truth):
        fails.append('%s: found %d of %d boards' % (name, len(match), len(truth)))
    if extra > bar['extra'] * len(truth):
        fails.append('%s: %d boards with no recorded one' % (name, extra))
    if na and med(na) > bar['plane']:
        fails.append('%s: plane error median %.2f deg' % (name, med(na)))
    if dk and med(sorted(dk)) > bar['kept']:
        fails.append('%s: kept %% error median %.2f' % (name, med(sorted(dk))))
    if dk and same < bar['grade'] * len(dk):
        fails.append('%s: the grade agrees on %d of %d' % (name, same, len(dk)))


def ksf(rig, fails, notes):
    s = sections((rig / 'logs/runlines_smoke.log').read_text(errors='replace'))
    body = s.get('KSF', [])
    h, b, l, e = table(body)
    inf = next((re.search(r'ramp contact (\S+).*step (\S+)\s+share (\S+)', x) for x in body
                if 'ramp contact' in x), None)
    print('KSF: contact %s, %d boards (head %s), %d leaves, events %s'
          % (inf and inf.groups(), len(b), h, len(l), e))
    if not inf or inf.group(1) != 'inferred' or abs(float(inf.group(2)) - 12) > 0.005:
        fails.append('KSF: contact not inferred at the 12.00 step (%s)' % (inf and inf.groups(),))
    if not b:
        fails.append('KSF: no boards')
    if not l:
        fails.append('KSF: no leaves')
    k10 = s.get('KSF 10', [])
    tr = next((re.search(r'trainer: demo (\d) ready (\d) missing (\d) contact (\d)', x) for x in k10
               if 'trainer: demo' in x), None)
    sq = next((re.search(r'lvsb (\d+)', x) for x in k10 if x.startswith('lvsb')), None)
    print('KSF 10: trainer %s, Segments rows %s' % (tr and tr.groups(), sq and sq.group(1)))
    if not tr or tr.group(4) != '1':
        fails.append('KSF 10: the trainer has no contact')
    if not sq or int(sq.group(1)) < 1:
        fails.append('KSF 10: no Segments rows')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('rig', type=pathlib.Path, nargs='?')
    ap.add_argument('--ksf', type=pathlib.Path)
    ap.add_argument('--control', action='store_true')
    a = ap.parse_args()
    fails, notes = [], []
    if a.ksf:
        ksf(a.ksf, fails, notes)
    if a.rig:
        imports(a.rig, a.control, fails, notes)
    for n in notes:
        print(n)
    for f in fails:
        print('FAIL', f)
    if a.control:
        print('CONTROL: %d failures (a build without the patch must fail)' % len(fails))
        return 0 if fails else 1
    if fails:
        print('FAILED')
        return 1
    if any(n.startswith(CANNOT) for n in notes):
        return 2
    print('PASS')
    return 0


def imports(rig, control, fails, notes):
    s = sections((rig / 'logs/runlines_smoke.log').read_text(errors='replace'))
    tabs = {k: table(s.get(k, [])) for k in ('NATIVE', 'ASIMPORT', 'INFERRED', 'MOM')}
    nh, nb, nl, ne = tabs['NATIVE']
    if nh is None or not ne:
        print('NATIVE: no table (head %s, %d events)' % (nh, len(ne)))
        if not control:
            notes.append(CANNOT + 'NATIVE printed no board table or no stage events')
    print('NATIVE: %d boards, %d leaves, %d events %s' % (len(nb), len(nl), len(ne), ne))
    # Graded on what any build prints, so a build without the patch fails here too.
    nsp, nbd = panels(s.get('NATIVE', []))
    for name in ('ASIMPORT', 'MOM'):
        sp, bd = panels(s.get(name, []))
        print('%s: split list %s rows (NATIVE %s), status boards %s (NATIVE %s)' % (name, sp, nsp, bd, nbd))
        if name == 'ASIMPORT' and (sp is None or sp != nsp):
            fails.append('ASIMPORT: %s split rows at the end, the native file %s' % (sp, nsp))
        if name == 'ASIMPORT' and (bd is None or bd != nbd):
            fails.append('ASIMPORT: %s boards, the native file %s' % (bd, nbd))
        if name == 'MOM' and (sp is None or sp != 3):
            fails.append('MOM: %s split rows at the end of a three-stage run' % sp)
    for name in ('ASIMPORT', 'INFERRED'):
        h, b, l, e = tabs[name]
        print('%s: head %s, %d boards, %d leaves, events %s' % (name, h, len(b), len(l), e))
        kinds = [(k, sg) for k, sg, _ in e]
        if kinds != [(k, sg) for k, sg, _ in ne]:
            fails.append('%s: split events %s, the file\'s own %s' % (name, kinds, [(k, sg) for k, sg, _ in ne]))
        elif e:
            d = [abs(x[2] - y[2]) for x, y in zip(e, ne)]
            print('%s: split ticks off the recorded by %s' % (name, d))
            if max(d) > 1:
                fails.append('%s: a split %d ticks off the recorded' % (name, max(d)))
    boards_vs('ASIMPORT', nb, tabs['ASIMPORT'][1], fails, notes,
              {'found': 0.9, 'extra': 0.1, 'plane': 0.5, 'kept': 0.5, 'grade': 0.8})
    boards_vs('INFERRED', nb, tabs['INFERRED'][1], fails, notes,
              {'found': 0.75, 'extra': 0.25, 'plane': 1.0, 'kept': 1.0, 'grade': 0.6})
    al = tabs['ASIMPORT'][2]
    print('leaves: NATIVE %d, ASIMPORT %d' % (len(nl), len(al)))
    if not nl:
        fails.append('NATIVE: no leaves kept')
    elif len(al) != len(nl) or max(abs(x[0] - y[0]) for x, y in zip(al, nl)) > 0.0005:
        fails.append('ASIMPORT: leaves %d, NATIVE %d (or at other times)' % (len(al), len(nl)))
    for name in ('NATIVE 40', 'ASIMPORT 40'):
        m = [re.search(r'boarding: leave (\S+) u/s .* ok (\d) age (\S+)', l) for l in s.get(name, [])]
        m = [x for x in m if x]
        print('%s leave row: %s' % (name, m and m[0].groups()))
        if not m or float(m[0].group(3)) < 0:
            fails.append('%s: no leave row' % name)
    mh, mb, ml, me = tabs['MOM']
    print('MOM: %d boards inferred, %d leaves, events %s' % (len(mb), len(ml), me))
    if len([x for x in me if x[0] == 0]) != 2:
        fails.append('MOM: %d stage events on a three-stage map' % len([x for x in me if x[0] == 0]))
    if not mb:
        fails.append('MOM: no boards inferred')
    seg = [re.search(r'track 0  leg \S+  startseg \S+  seg (\S+) of (\S+)', l) for l in s.get('MOM 40', [])]
    rows = [l for l in s.get('MOM 40', []) if re.match(r'\s*row \d+: kind 0', l)]
    print('MOM 40: split rows %d' % len(rows))
    if not rows:
        fails.append('MOM 40: no split rows')


if __name__ == '__main__':
    sys.exit(main())
