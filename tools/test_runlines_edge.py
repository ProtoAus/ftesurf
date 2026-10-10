#!/usr/bin/env python3
"""Grade the off-ramp mark at the ramp's own edge (Patch 628).

  python tools/test_runlines_edge.py <rig>/ftesurf/logs/runlines_smoke.log
      --recording <the native surf_kitsune run the arm was given>
      --control-log <the same arm on the build before the patch>

The log is tools/runlines_smoke.py's, from ftesurf/cfg/test/runlines_edge.cfg.  Two maps, each with a
native recording made on it (cfg/test/p492voy.rec is surf_voyager's), replayed with hud_lines_edge 1
and again with 0; a board line of the first; and one recording replayed on the WRONG map.

WHAT IS TRUE WITHOUT THE PATCH, and is the control here: a ramp leave is stamped on the ride's last
sample carrying the ramp bit (tools/p449mark.py).  With hud_lines_edge 0 the client must still do
exactly that.

WHAT THE PATCH CLAIMS.  The bit says the mover clipped a ramp during a tick; its sample is where that
tick ENDED, usually past the lip.  With the map loaded the client asks where the hull was last against
a ramp face (`lnx` rows, one a leave it could place):
  how 1   the last contact sample is still against the ramp: the lip is in the tick after it
  how 2   it is not, the sample before it is: the lip is in the last contact tick itself
  how 3   a sample in the 0.08 s after the last bit is still against it: contact outlived the bit
and stamps the mark on the straight line between that sample and the next, at the last point found
against the ramp.  A leave it cannot place stays as stamped.

WHAT IS GRADED.  (a) off: the model, mark for mark.  (b) on: the table is in time order and no leave
is before the landing that opened its ride or after the sample it was seen on; every mark that is
not a ramp leave is the off run's; every ramp leave is either the off run's or has its `lnx` row,
and then: the two samples the row names are the file's own, NEXT TO EACH OTHER, and the right ones
for its `how`; the mark is on the line between them at the row's fraction -- time, place, sideways
speed, vz and v.v; and the map, asked afresh by the client at the answer and at the first point it
found off the ramp, says 1 and 0 (that re-ask is the client's own function: it catches a halving
that went the wrong way, not a trace that is wrong).  (c) the probe against the
recording's own bit (`rprb`): how many contact ticks have the hull against a ramp face -- the claim
rests on that number, and it is printed.  (d) a board line places its leaves where the replay does.
(e) on the wrong map nothing is against anything and every leave stays as stamped.

EXIT STATUSES.  0 right, 1 wrong, 2 CANNOT MEASURE (a log, a section or the recording missing; the
probe agreeing with under 90% of a map's contact ticks, which means the map in the rig is not the
run's and nothing below would mean anything; a control that already has `lnx` rows), 64 usage.
"""
import argparse
import math
from pathlib import Path
import re
import statistics
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p449mark  # noqa: E402
import rampinfer  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RAMP_LEAVE = (p449mark.E_LEAVE, p449mark.RAMP * 4 + p449mark.AIR)
CANNOT = 'CANNOT MEASURE: '


class Section:
    def __init__(self, body):
        self.slots, self.rows, slot = {}, {}, None
        for line in body.splitlines():
            line = re.sub(r'^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d ', '', line.strip())
            f = line.split()
            if line.startswith('lnx '):
                # slot how ordinal tL tF t fraction x y z on off
                self.rows.setdefault(int(f[1]), []).append(dict(
                    how=int(f[2]), i=int(f[3]), tl=float(f[4]), tf=float(f[5]), t=float(f[6]), lo=float(f[7]),
                    pos=(float(f[8]), float(f[9]), float(f[10])), on=int(f[11]), off=int(f[12])))
            elif line.startswith('lnmb '):
                slot = int(float(f[1]))
                self.slots[slot] = {'marks': [], 'how': None}
            elif line.startswith('lnm ') and slot is not None:
                self.slots[slot]['marks'].append(dict(
                    kind=int(float(f[2])), sub=int(float(f[3])), t=float(f[4]), i=int(float(f[5])),
                    pos=(float(f[6]), float(f[7]), float(f[8])), speed=float(f[9]), vv=float(f[10]),
                    vz=float(f[11]), edge=float(f[12])))
            elif line.startswith('lnmx ') and slot is not None:
                self.slots[slot]['how'] = tuple(int(float(x)) for x in f[2:7])     # on, as stamped, 1, 2, 3
        m = re.search(r'rprb contact (\d+) against a ramp (\d+) \| in the 0.08 s after a ride (\d+) against (\d+)'
                      r' \| 0.08 to 0.5 s after (\d+) against (\d+)(?: \| cannot tell (\d+))?', body)
        # contact, against; after a ride, still against; later, still against; contact ticks it could not judge
        self.probe = tuple(int(x or 0) for x in m.groups()) if m else None
        self.othermap = bool(re.search(r'replay: this run is on \S+ and you are on', body))


class Run:
    def __init__(self, log):
        text = log.read_text(errors='replace')
        self.complete = 'RUNLINES COMPLETE' in text
        parts = re.split(r'==== ([A-Z]+) ====', text)
        self.s = {name: Section(body) for name, body in zip(parts[1::2], parts[2::2])}

    def why_not(self, need):
        if not self.complete:
            return 'the run did not finish'
        for name, slot in need:
            if name not in self.s:
                return 'no %s section' % name
            if slot not in self.s[name].slots or not self.s[name].slots[slot]['marks']:
                return 'the %s section printed no marks for slot %d' % (name, slot)
        return None


def leaves(marks):
    return [m for m in marks if (m['kind'], m['sub']) == RAMP_LEAVE]


def dist(a, b):
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


class Edge(unittest.TestCase):
    subject = control = None
    recordings = {}

    def model(self, got, path):
        breaks = {m['i'] for m in got if m['kind'] == p449mark.E_BREAK}
        want, _ = p449mark.derive(str(path), breaks)
        self.assertEqual(len(got), len(want), 'marks %d, the model has %d' % (len(got), len(want)))
        for g, w in zip(got, want):
            self.assertEqual((g['kind'], g['sub'], g['i']), (w[0], w[1], w[3]))
            self.assertAlmostEqual(g['t'], w[2], delta=0.0002)
            self.assertAlmostEqual(g['speed'], w[4], delta=0.02)
            self.assertAlmostEqual(g['edge'], w[7], delta=0.0002)

    def check_map(self, on_name, off_name, path, least):
        on, off = self.subject.s[on_name], self.subject.s[off_name]
        a, b = on.slots[0]['marks'], off.slots[0]['marks']
        keys, rows = rampinfer.read(path)
        tick = rampinfer.tick_of(keys)
        self.model(b, path)                                         # (a) off is the model
        self.assertEqual(off.slots[0]['how'][0], 0, 'the off run reports the switch on')
        self.assertFalse(off.rows.get(0), 'the off run placed a leave')
        self.assertEqual(len(a), len(b))
        rowsx = {round(r['t'], 4): r for r in on.rows.get(0, [])}
        self.assertEqual(len(rowsx), len(on.rows.get(0, [])), 'two placed leaves share a time')
        placed, moved, hows = 0, [], [0, 0, 0, 0]
        # The off run's order is the model's.  A placed leave can move behind a mark that sat between
        # its last contact and the edge, so the on run is compared as a set of leaves plus the rest.
        la, lb = leaves(a), leaves(b)
        self.assertEqual(len(la), len(lb))
        rest = lambda ms: [(m['kind'], m['sub'], m['i'], round(m['t'], 4)) for m in ms if (m['kind'], m['sub']) != RAMP_LEAVE]
        self.assertEqual(rest(a), rest(b), 'a mark that is not a ramp leave differs from the off run')
        # The table the draw searches by time: in order, and each leave between the landing that
        # opened its ride and the sample its edge was seen on.
        times = [m['t'] for m in a]
        self.assertEqual(times, sorted(times), 'the on run\'s mark table is not in time order')
        opened = None
        for m in a:
            if m['kind'] == p449mark.E_LAND and m['sub'] % 4 == p449mark.RAMP:
                opened = m
            elif (m['kind'], m['sub']) == RAMP_LEAVE:
                if opened is not None:
                    self.assertGreaterEqual(m['t'], opened['t'] - 0.0002, 'a leave is stamped before its own landing')
                self.assertLessEqual(m['t'], m['edge'] + 0.0002, 'a leave is stamped after the sample it was seen on')
                opened = None
            elif m['kind'] in (p449mark.E_BREAK, p449mark.E_STITCH):
                opened = None
        for m, old in zip(la, lb):
            self.assertAlmostEqual(m['edge'], old['edge'], delta=0.0002, msg='a leave lost its edge clock')
            r = rowsx.get(round(m['t'], 4))
            if r is None:
                hows[0] += 1
                self.assertEqual((m['i'], round(m['t'], 4)), (old['i'], round(old['t'], 4)),
                                 'a leave moved with no `lnx` row')
                continue
            placed += 1
            hows[r['how']] += 1
            c = old['i']                                            # the last contact sample
            L = r['i']
            self.assertEqual(m['i'], L)
            self.assertTrue(rows[c][3] & 16, 'the off stamp is not a contact sample')
            if r['how'] == 1:
                self.assertEqual(L, c)
            elif r['how'] == 2:
                self.assertEqual(L, c - 1)
                self.assertTrue(rows[L][3] & 16, 'how 2 starts from a sample without the bit')
            else:
                self.assertEqual(r['how'], 3)
                self.assertGreater(L, c)
                self.assertFalse(rows[L][3] & 16, 'how 3 starts from a sample that has the bit')
                self.assertLessEqual(rows[L][0] - rows[c][0], 0.0801)
            self.assertAlmostEqual(r['tl'], rows[L][0], delta=0.0002)
            F = L + 1                                               # the tick halved is ONE tick, the next sample's
            self.assertLess(F, len(rows))
            self.assertAlmostEqual(r['tf'], rows[F][0], delta=0.0002, msg='the row\'s far sample is not the next one')
            if r['how'] == 2:
                self.assertEqual(F, c)
            self.assertTrue(0 <= r['lo'] < 1)
            self.assertAlmostEqual(r['t'], r['tl'] + (r['tf'] - r['tl']) * r['lo'], delta=0.0002)
            self.assertAlmostEqual(m['t'], r['t'], delta=0.0002)
            at = tuple(rows[L][1][k] + (rows[F][1][k] - rows[L][1][k]) * r['lo'] for k in range(3))
            self.assertLess(dist(m['pos'], at), 0.03, 'the mark is not on the line between its two samples')
            self.assertLess(dist(r['pos'], m['pos']), 0.02)
            v = [rows[L][2][k] + (rows[F][2][k] - rows[L][2][k]) * r['lo'] for k in range(3)]
            self.assertAlmostEqual(m['speed'], math.hypot(v[0], v[1]), delta=0.05)
            self.assertAlmostEqual(m['vz'], v[2], delta=0.05, msg='the mark\'s vz is not read off that line')
            vv = v[0] * v[0] + v[1] * v[1] + v[2] * v[2]
            self.assertAlmostEqual(m['vv'], vv, delta=1.0 + 0.0002 * vv, msg='the mark\'s v.v is not read off that line')
            self.assertEqual((r['on'], r['off']), (1, 0),
                             'the map, asked again at the answer and just past it, says %d and %d' % (r['on'], r['off']))
            moved.append((dist(m['pos'], old['pos']), (m['t'] - old['t']) / tick))
        self.assertEqual(on.slots[0]['how'], (1,) + tuple(hows), 'the client\'s own count of how it placed them')
        self.assertEqual(placed, len(rowsx), 'an `lnx` row belongs to no leave')
        d = sorted(x[0] for x in moved)
        dt = sorted(x[1] for x in moved)
        print('\n  %s: %d ramp leaves; as stamped %d, lip after the last contact %d, in the last contact tick %d, '
              'contact outlived the bit %d' % (on_name.lower(), len(la), hows[0], hows[1], hows[2], hows[3]))
        if moved:
            print('     placed marks moved a median %.1f u (most %.1f); in time %.2f to %+.2f ticks, median %+.2f'
                  % (statistics.median(d), d[-1], dt[0], dt[-1], statistics.median(dt)))
        self.assertGreaterEqual(placed, least, 'too few leaves placed for this arm to have acted')
        for dd, tt in moved:
            # from the tick before the last contact to the tick after the hold's last sample
            self.assertTrue(-1.0001 <= tt <= 0.08 / tick + 1.0001, 'a mark moved %.2f ticks' % tt)
        return hows

    def test_probe_agrees_with_the_recordings(self):
        for name in ('VOYAGER', 'KITSUNE'):
            p = self.subject.s[name].probe
            print('\n  %s: %d of %d contact ticks have the hull against a ramp face (%d it could not judge); of %d '
                  'samples in the 0.08 s after a ride %d still do; of %d from 0.08 to 0.5 s after, %d'
                  % (name.lower(), p[1], p[0], p[6], p[2], p[3], p[4], p[5]))
            self.assertGreater(p[1], 0.95 * p[0])
            self.assertLess(p[5], 0.05 * p[4] + 1)

    def test_voyager(self):
        hows = self.check_map('VOYAGER', 'VOYAGEROFF', ROOT / 'ftesurf/cfg/test/p492voy.rec', 20)
        self.assertGreater(hows[3], 0, 'no leave was placed after a sample the bit missed: that path did not run')
        self.assertGreater(hows[2], 0)

    def test_kitsune(self):
        hows = self.check_map('KITSUNE', 'KITSUNEOFF', self.recordings['kitsune'], 20)
        self.assertGreater(hows[1], 0, 'no lip in the tick after the last contact: that path did not run')
        self.assertGreater(hows[2], 0)

    def test_board_line_places_them_where_the_replay_does(self):
        rep = leaves(self.subject.s['VOYAGER'].slots[0]['marks'])
        brd = leaves(self.subject.s['VOYAGERBOARD'].slots[1]['marks'])
        rep = [m for m in rep if m['t'] >= 0]
        self.assertEqual(len(brd), len(rep))
        for a, b in zip(brd, rep):
            self.assertAlmostEqual(a['t'], b['t'], delta=0.0002)
            self.assertLess(dist(a['pos'], b['pos']), 0.02)
        self.assertEqual(self.subject.s['VOYAGERBOARD'].slots[1]['how'][2:],
                         self.subject.s['VOYAGER'].slots[0]['how'][2:])

    def test_wrong_map_places_nothing(self):
        sec = self.subject.s['WRONGMAP']
        print('\n  wrong map: %d of %d contact ticks against a ramp; leaves placed %s'
              % (sec.probe[1], sec.probe[0], sec.slots[0]['how'][2:]))
        self.assertGreater(sec.probe[0], 500, 'the run replayed on the wrong map has too little contact to say')
        self.assertLess(sec.probe[1], 0.01 * sec.probe[0])
        self.assertEqual(sec.slots[0]['how'][2:], (0, 0, 0))
        self.assertFalse(sec.rows.get(0))
        self.model(sec.slots[0]['marks'], self.recordings['kitsune'])

    def test_clip_ramps_are_seen(self):
        sec = self.subject.s.get('CLIPMAP')
        if sec is None or sec.probe is None or sec.probe[0] == 0 or sec.othermap:
            self.skipTest('NOT RUN: no surf_axiom recording was given (--mount --also runlines_clip.rec=...) or '
                          'the map did not load, so nothing here shows the trace is made as a player\'s hull')
        print('\n  a map of player-clip ramps: %d of %d contact ticks against a ramp; leaves %s'
              % (sec.probe[1], sec.probe[0], sec.slots[0]['how'][1:]))
        self.assertGreater(sec.probe[0], 200)
        self.assertGreater(sec.probe[1], 0.95 * sec.probe[0], 'the trace passes through player clip')
        self.assertGreater(sum(sec.slots[0]['how'][2:]), 0)

    def test_control_places_nothing(self):
        c = self.control.s['VOYAGER']
        self.assertFalse(c.rows, 'the control has `lnx` rows')
        self.model(c.slots[0]['marks'], ROOT / 'ftesurf/cfg/test/p492voy.rec')


def usage(parser):
    def error(message):
        parser.print_usage(sys.stderr)
        sys.stderr.write('%s: error: %s\n' % (parser.prog, message))
        sys.exit(64)
    return error


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.error = usage(ap)
    ap.add_argument('log', type=Path)
    ap.add_argument('--recording', type=Path, required=True)
    ap.add_argument('--control-log', type=Path, required=True)
    args = ap.parse_args()
    if not args.recording.is_file():
        print(CANNOT + 'the recording is not a file')
        sys.exit(2)
    need = (('VOYAGER', 0), ('VOYAGERBOARD', 1), ('VOYAGEROFF', 0), ('WRONGMAP', 0), ('KITSUNE', 0), ('KITSUNEOFF', 0))
    for name, path, want in (('subject', args.log, need), ('control', args.control_log, (('VOYAGER', 0),))):
        try:
            run = Run(path)
        except OSError as e:
            print(CANNOT + 'the %s log cannot be read (%s)' % (name, e))
            sys.exit(2)
        why = run.why_not(want)
        if why:
            print(CANNOT + 'the %s log: %s' % (name, why))
            sys.exit(2)
        setattr(Edge, name, run)
    for name in ('VOYAGER', 'KITSUNE', 'WRONGMAP'):
        p = Edge.subject.s[name].probe
        if p is None:
            print(CANNOT + 'the %s section has no `rprb` line' % name)
            sys.exit(2)
        if name != 'WRONGMAP' and p[1] < 0.9 * p[0]:
            print(CANNOT + 'on %s the hull is against a ramp face on %d of %d contact ticks: the map in the rig '
                  'is not the recording\'s' % (name.lower(), p[1], p[0]))
            sys.exit(2)
    Edge.recordings = {'kitsune': args.recording}
    unittest.main(argv=['test_runlines_edge.py'])
