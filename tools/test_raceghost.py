#!/usr/bin/env python3
"""Patch 746: grade raceghost_live.cfg (and raceghost_look.cfg) logs.

python tools/test_raceghost.py [<rig>/ftesurf] --pb <the PB .rec put into the rig>
    [--look <rig of raceghost_look.cfg>/ftesurf] [--stage <rig of raceghost_stage.cfg>/ftesurf]
    [--stagepb <rig of raceghost_stagepb.cfg>/ftesurf] [--pose <rig of raceghost_pose.cfg>/ftesurf]

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
hud_edit Ghost pane lists its nine rows and its first chip turns hud_ghost on.  Stage-PB
arm (the review's two): in stage 2's box its own PB is already loaded; it is the ghost
of the stage run, at the whole PB's place 4.98 s on (the file was cut from it); past
its end and hold no other PB stands in; three attempts read it once.
Pose arm (Patch 749): at each POSE the ghost's yaw is the file's view yaw at its clock
(the shortest way round between the two samples either side, within 0.2 degrees) and its
duck the nearer sample's flag; the arm must hold ducked and standing moments and one
where the view and the travel part by over 30 degrees, or it cannot tell the two apart.
The look arm's held ghost ducks as the file does there and its tag "Your PB" is drawn.
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
DUCK = re.compile(r' duck (\S+)$')
TAG = re.compile(r'raceghost: tag (\d+) "([^"]*)" drawn (\S+)')
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


def poses(path):
    """(t, (x, y, z), yaw, flags) for every sample."""
    out, body = [], False
    for line in open(path, encoding='utf-8', errors='replace'):
        if line.startswith('begin'):
            body = True
            continue
        if body and line[:1] in '-0123456789':
            w = line.split()
            if len(w) >= 10:
                out.append((float(w[0]), (float(w[1]), float(w[2]), float(w[3])),
                            float(w[8]), int(float(w[9]))))
    return out


def wrap(d):
    return (d + 180) % 360 - 180


def pose_at(rows, t):
    """The file's (yaw, ducked, travel yaw) at clock t, as RG_At reads it."""
    i = next((k for k in range(1, len(rows)) if rows[k][0] >= t), None)
    if i is None or t < rows[0][0]:
        return None
    (t0, p0, y0, f0), (t1, p1, y1, f1) = rows[i - 1], rows[i]
    f = (t - t0) / (t1 - t0) if t1 > t0 else 1
    if math.dist(p0, p1) > 64:
        f = 0 if f < 0.5 else 1
    yaw = (y0 + wrap(y1 - y0) * f) % 360
    duck = bool((f0 if f < 0.5 else f1) & 2)
    a, b = rows[max(0, i - 3)][1], rows[min(len(rows) - 1, i + 3)][1]
    travel = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])) % 360
    return yaw, duck, travel


def pose(rig, pb, fails, notes):
    s = (rig / 'logs/runlines_smoke.log').read_text(errors='replace')
    rows = poses(pb)
    secs, cur = [], None
    for line in s.splitlines():
        if '==== POSE ====' in line:
            cur = []
            secs.append(cur)
        elif cur is not None:
            cur.append(line)
    ducked = standing = parted = 0
    for k, body in enumerate(secs):
        g = [l for l in body if GHOST.search(l) and GHOST.search(l).group(2) == '68']
        if not g:
            fails.append('POSE %d: no ghost of the whole run\'s PB' % k)
            continue
        m = GHOST.search(g[0])
        t, yaw = float(m.group(3)), float(m.group(7)) % 360
        d = DUCK.search(g[0])
        want = pose_at(rows, t)
        if want is None:
            notes.append(CANNOT + 'POSE %d: t %.4f is outside the file' % (k, t))
            continue
        wy, wd, tr = want
        print('POSE %d t %.4f yaw %.1f (file %.1f, travel %.1f) duck %s (file %d)'
              % (k, t, yaw, wy, tr, d and d.group(1), wd))
        if abs(wrap(yaw - wy)) > 0.2:
            fails.append('POSE %d: yaw %.1f, the view was %.1f (travel %.1f)' % (k, yaw, wy, tr))
        if not d:
            fails.append('POSE %d: the ghost says nothing of ducking' % k)
        elif bool(float(d.group(1))) != wd:
            fails.append('POSE %d: duck %s, the file %d' % (k, d.group(1), wd))
        ducked += wd
        standing += not wd
        parted += abs(wrap(wy - tr)) > 30
    print('POSE %d moments: %d ducked, %d standing, %d where view and travel part'
          % (len(secs), ducked, standing, parted))
    if ducked < 3 or standing < 3 or not parted:
        notes.append(CANNOT + 'POSE: the moments cannot tell a pose from the travel '
                     '(%d ducked, %d standing, %d parted)' % (ducked, standing, parted))


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
        line = next(l for l in s.get(name, []) if GHOST.search(l))
        dk, want = DUCK.search(line), pose_at(poses(pb), gt)
        tag = [TAG.search(l) for l in s.get(name, []) if TAG.search(l)]
        print('look %s duck %s (file %s) tag %s' % (name, dk and dk.group(1), want and int(want[1]),
                                                  tag and tag[0].groups()))
        if not dk or want is None or bool(float(dk.group(1))) != want[1]:
            fails.append('look %s: duck %s, the file %s' % (name, dk and dk.group(1), want and want[1]))
        if not tag or tag[0].group(2) != 'Your PB' or tag[0].group(3) != '1':
            fails.append('look %s: no "Your PB" tag drawn (%s)' % (name, tag and tag[0].groups()))
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
            'he_o_hud_ghost_offset', 'he_o_hud_ghost_alpha', 'he_o_hud_ghost_dither', 'he_o_hud_ghost_near',
            'he_o_hud_ghost_names']
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
        # Patch 749: a ticked line's ghost is tagged with the run's owner.
        if name == 'LINE2' and slots == ['1']:
            owner = next((l.split(None, 1)[1].strip() for l in open(pb, encoding='utf-8', errors='replace')
                          if l.startswith('owner ')), '')
            tag = [TAG.search(l) for l in body if TAG.search(l)]
            print('stage LINE2 tag %s, the file\'s owner "%s"' % (tag and tag[0].groups(), owner))
            if not tag or tag[0].group(2) != owner:
                fails.append('LINE2: the ticked line\'s ghost is not tagged "%s" (%s)'
                             % (owner, tag and tag[0].groups()))
        if anchors and abs(anchors[0] - starts.get(1, -9)) > 0.031:
            fails.append('%s: anchored at %.4f, not the PB stage 2 start' % (name, anchors[0]))


def stagepb(rig, pb, fails, notes):
    log = (rig / 'logs/runlines_smoke.log').read_text(errors='replace')
    s = sections(log)
    pbrows = [r for r in samples(pb) if r[0] >= 0]
    inbox = '\n'.join(s.get('INBOX', []))
    m = re.search(r'raceghost: pb stage leg (\S+) state (\S+) pts (\S+)', inbox)
    print('stagepb INBOX stage slot leg/state/pts', m and m.groups())
    if not m or m.group(1) != '2' or m.group(2) != '3':
        fails.append('INBOX: the stage PB is not loaded while you stand in its box (%s)' % (m and m.groups(),))
    for name, off in (('STAGEPB', 0), ('AGAIN', 0)):
        body = s.get(name, [])
        c = next((CLOCK.search(l) for l in body if CLOCK.search(l)), None)
        g = [GHOST.search(l) for l in body if GHOST.search(l)]
        if not c or float(c.group(1)) < 0:
            notes.append(CANNOT + '%s: the stage run did not start' % name)
            continue
        slots = [x.group(2) for x in g]
        print('stagepb %s ghosts in slots %s' % (name, slots))
        if slots != ['67']:
            fails.append('%s: ghosts %s, wanted the stage PB alone (67)' % (name, slots))
            continue
        clock, gt = float(c.group(1)), float(g[0].group(3))
        gp = tuple(float(g[0].group(i)) for i in (4, 5, 6))
        d = math.dist(gp, at(pbrows, 4.98 + gt))
        print('stagepb %s t %.4f (clock %.4f), %.2f u off the whole PB 4.98 s on' % (name, gt, clock, d))
        if abs(gt - clock - off) > 0.0005 or d > 1:
            fails.append('%s: t %.4f clock %.4f, %.2f u off' % (name, gt, clock, d))
    body = s.get('FINISHED', [])
    c = next((CLOCK.search(l) for l in body if CLOCK.search(l)), None)
    slots = [GHOST.search(l).group(2) for l in body if GHOST.search(l)]
    print('stagepb FINISHED ghosts in slots', slots)
    if not c or float(c.group(1)) < 0:
        notes.append(CANNOT + 'FINISHED: the stage run did not start')
    elif slots:
        fails.append('FINISHED: the stage PB has finished and %s stands in (the review\'s pop-in)' % slots)
    ready = len(re.findall(r'raceghost: stage PB ready', log))
    print('stagepb stage PB reads', ready)
    if ready != 1:
        fails.append('the stage PB was read %d times over three attempts' % ready)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('rig', type=pathlib.Path, nargs='?')
    ap.add_argument('--pb', type=pathlib.Path, required=True)
    ap.add_argument('--look', type=pathlib.Path)
    ap.add_argument('--stage', type=pathlib.Path)
    ap.add_argument('--stagepb', type=pathlib.Path)
    ap.add_argument('--pose', type=pathlib.Path)
    a = ap.parse_args()
    fails, notes = [], []
    if a.rig:
        live(a.rig, a.pb, fails, notes)
    if a.look:
        look(a.look, a.pb, fails, notes)
    if a.stage:
        stage(a.stage, a.pb, fails, notes)
    if a.stagepb:
        stagepb(a.stagepb, a.pb, fails, notes)
    if a.pose:
        pose(a.pose, a.pb, fails, notes)
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
