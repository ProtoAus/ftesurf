#!/usr/bin/env python3
"""Patch 746: grade raceghost_live.cfg (and raceghost_look.cfg) logs.

python tools/test_raceghost.py <rig>/ftesurf --pb <the PB .rec put into the rig>
    [--look <rig of raceghost_look.cfg>/ftesurf] [--stage <rig of raceghost_stage.cfg>/ftesurf]

Live arm (dedicated, sv_minping 120): every printed ghost sits on the PB file at its
own clock (within 1 u), its clock is yours plus the offset, and yours is the drawn
body's: the server's own recording of the ride (the longest data/saves/*/run.rec in
the rig) at that clock is within 12 u of the predicted body, and nearer than at the
stat's clock without the lead.  Look arm: the -30 s offset holds the ghost at the start
of its run, hud_ghost 3 draws its highlight (the PB slot's marktrace has a window of
[t-0.6, t+0.06]), and hud_ghost 0 shows none.  Stage arm: a stage run of the whole
run's PB is anchored where the PB's own clock for that stage started, which the file
records independently of the zones (the LAST `stagestart <seg>` before `stage <seg+1>`:
a fail back into the box restarts it), and the ghost is the PB at anchor + your clock -
your anchor + the offset; a ticked board line of the same file is the ghost when the PB
is off (slot 1), one ghost with both on, none with hud_ghost_lines 0.  The look arm's
hud_edit Ghost pane lists its eight rows and its first chip turns hud_ghost on.
Exit 2 is CANNOT MEASURE.
"""
import argparse
import math
import pathlib
import re
import sys

CLOCK = re.compile(r'raceghost: clock (\S+) \(stat (\S+), lead (\S+)\)')
GHOST = re.compile(r'raceghost: ghost (\d+) slot (\d+) t (\S+) at (\S+) (\S+) (\S+) yaw (\S+) end (\S+) anchor (\S+) mine (\S+)')
YOU = re.compile(r'raceghost: you at (\S+) (\S+) (\S+)')
SHOWN = re.compile(r'raceghost: (\d+) shown')
CANNOT = 'CANNOT MEASURE: '


def samples(path):
    out, body = [], False
    for line in open(path, encoding='utf-8', errors='replace'):
        if line.startswith('begin'):
            body = True
            continue
        if body and line[:1] in '-0123456789':
            w = line.split()
            if len(w) >= 4:
                out.append((float(w[0]), (float(w[1]), float(w[2]), float(w[3]))))
    return out


def at(rows, t):
    if not rows:
        return None
    if t <= rows[0][0]:
        return rows[0][1]
    for (t0, p0), (t1, p1) in zip(rows, rows[1:]):
        if t0 <= t <= t1:
            f = (t - t0) / (t1 - t0) if t1 > t0 else 1
            return tuple(a + (b - a) * f for a, b in zip(p0, p1))
    return rows[-1][1]


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


def tick_of(path):
    for line in open(path, encoding='utf-8', errors='replace'):
        if line.startswith('tickrate'):
            return float(line.split()[1])
        if line.startswith('begin'):
            break
    return 0.015


def live(rig, pb, fails, notes):
    log = (rig / 'logs/runlines_smoke.log').read_text(errors='replace')
    s = sections(log)
    pbrows = [r for r in samples(pb) if r[0] >= 0]
    recs = sorted(rig.glob('data/saves/*/save*/run.rec'), key=lambda p: len(samples(p)))
    if not recs:
        notes.append(CANNOT + 'no run.rec in the rig: the saves missed the ride')
        return
    rec = samples(recs[-1])
    tick = tick_of(recs[-1])
    print('server recording %s: %d samples' % (recs[-1].relative_to(rig), len(rec)))
    seen = 0
    for name in ('R1', 'R2', 'R3', 'R4'):
        body = s.get(name, [])
        c = next((CLOCK.search(l) for l in body if CLOCK.search(l)), None)
        y = next((YOU.search(l) for l in body if YOU.search(l)), None)
        g = [GHOST.search(l) for l in body if GHOST.search(l)]
        if not c or float(c.group(1)) < 0:
            print(name, 'no run yet')
            continue
        clock, stat, lead = float(c.group(1)), float(c.group(2)), float(c.group(3))
        if not g:
            fails.append('%s: a run with a PB and no ghost' % name)
            continue
        seen += 1
        g = g[0]
        gt = float(g.group(3))
        gp = tuple(float(g.group(i)) for i in (4, 5, 6))
        want = at(pbrows, gt)
        d = math.dist(gp, want)
        print('%s ghost t %.4f (clock %.4f) %.2f u off the PB file' % (name, gt, clock, d))
        if abs(gt - clock) > 0.0005:
            fails.append('%s: ghost clock %.4f is not yours %.4f (offset 0)' % (name, gt, clock))
        if d > 1:
            fails.append('%s: the ghost is %.2f u off its PB at its own clock' % (name, d))
        you = tuple(float(y.group(i)) for i in (1, 2, 3))
        e1 = math.dist(you, at(rec, clock))
        e0 = math.dist(you, at(rec, stat * tick))
        print('%s you vs the server at your clock %.1f u, at the stat clock %.1f u (lead %.3f)'
              % (name, e1, e0, lead))
        # Whether there was latency to make up is the recording's to say, not the
        # subject's printed lead: a build that adds none would grade itself "no latency".
        if e0 <= 12:
            notes.append(CANNOT + '%s: the stat clock is already on the body (%.1f u)' % (name, e0))
            continue
        if e1 > 12:
            fails.append('%s: your clock puts the server %.1f u off the body' % (name, e1))
        if not e1 < e0:
            fails.append('%s: the lead does not bring the clock nearer the body (%.1f vs %.1f)' % (name, e1, e0))
    if not seen:
        notes.append(CANNOT + 'no section had a running clock')


def look(rig, pb, fails, notes):
    s = sections((rig / 'logs/runlines_smoke.log').read_text(errors='replace'))
    pbrows = [r for r in samples(pb) if r[0] >= 0]
    for name in ('DITHER', 'BLEND'):
        g = [GHOST.search(l) for l in s.get(name, []) if GHOST.search(l)]
        if not g:
            fails.append('look %s: no ghost' % name)
            continue
        gt = float(g[0].group(3))
        gp = tuple(float(g[0].group(i)) for i in (4, 5, 6))
        d = math.dist(gp, pbrows[0][1])
        print('look %s ghost t %.4f, %.2f u from the PB start' % (name, gt, d))
        if abs(gt - pbrows[0][0]) > 0.02 or d > 1:
            fails.append('look %s: a -30 s offset did not hold it at its start (t %.3f, %.1f u)' % (name, gt, d))
    hl = s.get('HIGHLIGHT', [])
    g = [GHOST.search(l) for l in hl if GHOST.search(l)]
    lnd = [l for l in hl if re.search(r'lnd 68 ', l)]
    print('look HIGHLIGHT ghosts %d, slot 68 draws %d' % (len(g), len(lnd)))
    if not g or not lnd:
        fails.append('look HIGHLIGHT: no highlight drawn for the PB slot')
    else:
        m = re.search(r'lnd 68 (\S+) (\S+) (\S+) (\S+)', lnd[0])
        t, on, a, b = (float(x) for x in m.groups())
        print('look HIGHLIGHT window %.3f..%.3f at %.3f' % (a, b, t))
        if on != 1 or abs(a - (t - 0.6)) > 0.01 or abs(b - (t + 0.06)) > 0.01:
            fails.append('look HIGHLIGHT: window %s..%s around %s' % (a, b, t))
        n2 = [l for l in hl if re.search(r'lnd2 68 ', l)]
        if n2:
            npt = float(n2[0].split()[-3 - 2])
            print('look HIGHLIGHT points', n2[0].split()[-4:])
    rw = s.get('REWIND', [])
    on = next((re.search(r'rewind: on (\d+)', l) for l in rw if re.search(r'rewind: on (\d+)', l)), None)
    hud = next((re.search(r'rewind: HUD (\d+) time (\S+)', l) for l in rw if re.search(r'rewind: HUD', l)), None)
    g = [GHOST.search(l) for l in rw if GHOST.search(l)]
    print('look REWIND on %s cursor %s ghost t %s' % (on and on.group(1), hud and hud.group(2),
                                                     g and g[0].group(3)))
    if not on or on.group(1) != '1' or not hud:
        notes.append(CANNOT + 'look REWIND: the rewind did not open')
    elif not g or abs(float(g[0].group(3)) - float(hud.group(2))) > 0.0005:
        fails.append('look REWIND: the ghost is not at the rewind cursor (%s)' % (g and g[0].group(3)))
    off = [SHOWN.search(l) for l in s.get('OFF', []) if SHOWN.search(l)]
    if not off or int(off[0].group(1)) != 0:
        fails.append('look OFF: hud_ghost 0 still shows ghosts')
    rows = ['he_o_hud_ghost', 'he_o_hud_ghost_sync', 'he_o_hud_ghost_pb', 'he_o_hud_ghost_lines',
            'he_o_hud_ghost_offset', 'he_o_hud_ghost_alpha', 'he_o_hud_ghost_dither', 'he_o_hud_ghost_near']
    ids = set(re.findall(r'sui_element \[(he_o_[^\]]+)\]', '\n'.join(s.get('PANE', []))))
    print('look PANE rows', sorted(ids))
    if [r for r in rows if r not in ids]:
        fails.append('look PANE: missing %s' % [r for r in rows if r not in ids])
    click = '\n'.join(s.get('PANECLICK', []))
    m = re.search(r'"hud_ghost" is "([^"]*)"', click)
    print('look PANECLICK hud_ghost', m and m.group(1))
    if not m or float(m.group(1)) != 1:
        fails.append('look PANECLICK: the Show chip did not turn hud_ghost from 0 to 1')


def stage_starts(path):
    """{seg: the clock its last start was written at} from the file's own records."""
    tick, out, nxt = tick_of(path), {}, {}
    for line in open(path, encoding='utf-8', errors='replace'):
        w = line.split()
        if len(w) == 3 and w[0] == 'stagestart':
            seg = int(w[1])
            if seg not in nxt:
                out[seg] = int(w[2]) * tick
        elif len(w) == 3 and w[0] == 'stage':
            nxt[int(w[1]) - 1] = True
    return out


def stage(rig, pb, fails, notes):
    s = sections((rig / 'logs/runlines_smoke.log').read_text(errors='replace'))
    pbrows = [r for r in samples(pb) if r[0] >= 0]
    starts = stage_starts(pb)
    for name, seg, off in (('S2RUN', 1, 0), ('S2STAGE', 1, 1), ('S7RUN', 6, 0)):
        body = s.get(name, [])
        c = next((CLOCK.search(l) for l in body if CLOCK.search(l)), None)
        g = [GHOST.search(l) for l in body if GHOST.search(l)]
        if not c or float(c.group(1)) < 0:
            notes.append(CANNOT + '%s: the stage run did not start' % name)
            continue
        if not g:
            fails.append('%s: a stage run with the whole PB loaded and no ghost' % name)
            continue
        clock = float(c.group(1))
        gt, anchor, mine = float(g[0].group(3)), float(g[0].group(9)), float(g[0].group(10))
        gp = tuple(float(g[0].group(i)) for i in (4, 5, 6))
        want = starts.get(seg)
        print('stage %s: anchor %.4f, the file says %s; t %.4f' % (name, anchor, want, gt))
        if want is None or abs(anchor - want) > 0.031:
            fails.append('%s: anchored at %.4f, the PB started stage %d at %s' % (name, anchor, seg + 1, want))
        if abs(gt - (anchor + clock - mine + off)) > 0.0005:
            fails.append('%s: t %.4f is not anchor + clock - mine + %g' % (name, gt, off))
        d = math.dist(gp, at(pbrows, gt))
        if d > 1:
            fails.append('%s: the ghost is %.2f u off its PB at its own clock' % (name, d))
    for name, want in (('LINE2', ['1']), ('DEDUPE', None), ('NOLINES', [])):
        body = s.get(name, [])
        c = next((CLOCK.search(l) for l in body if CLOCK.search(l)), None)
        if not c or float(c.group(1)) < 0:
            notes.append(CANNOT + '%s: the stage run did not start' % name)
            continue
        slots = [GHOST.search(l).group(2) for l in body if GHOST.search(l)]
        anchors = [float(GHOST.search(l).group(9)) for l in body if GHOST.search(l)]
        print('stage %s: ghosts in slots %s anchors %s' % (name, slots, anchors))
        if want is None:
            if len(slots) != 1:
                fails.append('DEDUPE: the PB ticked as a line as well shows %d ghosts' % len(slots))
        elif slots != want:
            fails.append('%s: ghosts in slots %s, wanted %s' % (name, slots, want))
        if anchors and abs(anchors[0] - starts.get(1, -9)) > 0.031:
            fails.append('%s: anchored at %.4f, not the PB stage 2 start' % (name, anchors[0]))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('rig', type=pathlib.Path)
    ap.add_argument('--pb', type=pathlib.Path, required=True)
    ap.add_argument('--look', type=pathlib.Path)
    ap.add_argument('--stage', type=pathlib.Path)
    a = ap.parse_args()
    fails, notes = [], []
    live(a.rig, a.pb, fails, notes)
    if a.look:
        look(a.look, a.pb, fails, notes)
    if a.stage:
        stage(a.stage, a.pb, fails, notes)
    for n in notes:
        print(n)
    for f in fails:
        print('FAIL', f)
    if fails:
        print('FAILED')
        return 1
    if any(n.startswith(CANNOT) for n in notes):
        return 2
    print('PASS')
    return 0


if __name__ == '__main__':
    sys.exit(main())
