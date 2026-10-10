#!/usr/bin/env python3
"""Grade the live run line behind a ping (Patch 611) against the server's own recording of the run.

  python tools/test_runlines_livelag.py <rig>/ftesurf [--fps 100]
      [--control <rig of a build before the patch>/ftesurf]

The rig is tools/runlines_smoke.py's, from ftesurf/cfg/test/runlines_livelag.cfg with --dedicated,
--map surf_kitsune and --server-arg "+set sv_minping 120". It holds the client's log (the live
line's mark table and the `trail` report) and the server's recording of the same run, written by
the arm's saves. Truth is the recording: every mark has to sit on the recorded sample that carries
its clock, within one tick and one rendered frame of travel (--fps is the arm's cl_maxfps).

THREE VERDICTS, THREE EXIT STATUSES. 0: measured and right. 1: measured and wrong. 2: CANNOT
MEASURE -- a run with no latency, a save that missed the ride, a mark the recording does not
reach. That is not a pass and not a defect; run the arm again. Only distances and counts are
printed.
"""
import argparse
import math
from pathlib import Path
import re
import sys
import unittest

E_LAND, E_LEAVE = 1, 2
AIR_TO_RAMP, RAMP_TO_AIR = 1 * 4 + 2, 2 * 4 + 1
F_RAMP = 16
MIN_LAG = 0.045              # seconds the acknowledged frame has to trail the two a local server shows
CANNOT = 'CANNOT MEASURE: '


def dist(a, b):
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5


class Recording:
    """The longest run.rec in a rig: its tick, and {tick index: (pos, vel, flags)}."""

    def __init__(self, gamedir):
        self.tick, self.rows = 0.015, {}
        for path in sorted(gamedir.glob('data/saves/*/save*/run.rec')):
            tick, rows, body = 0.015, {}, False
            for line in path.read_text(errors='replace').splitlines():
                if not body:
                    # The mover's own rate: `tickrate` is the cvar, which a mode file can leave behind.
                    if line.startswith('movetickrate '):
                        tick = float(line.split()[1])
                    body = line.strip() == 'begin'
                    continue
                if line[:1].isdigit() or line[:1] == '-':
                    f = line.split()
                    if len(f) >= 10:
                        rows[round(float(f[0]) / tick)] = (tuple(map(float, f[1:4])),
                                                           tuple(map(float, f[4:7])), int(float(f[9])))
            if rows and (not self.rows or max(rows) > max(self.rows)):
                self.tick, self.rows = tick, rows

    def at(self, t):
        """The recorded sample with this clock. Under the tick rate a recording has a sample a packet,
        not a tick, so a clock between two of them (at most three ticks apart) is read off the line
        between them; flags are the earlier sample's."""
        i = round(t / self.tick)
        if i in self.rows:
            return self.rows[i]
        lo = max((k for k in range(i - 2, i) if k in self.rows), default=None)
        hi = min((k for k in range(i + 1, i + 3) if k in self.rows), default=None)
        if lo is None or hi is None or hi - lo > 3:
            return None
        w = (i - lo) / (hi - lo)
        a, b = self.rows[lo], self.rows[hi]
        return (tuple(x + w * (y - x) for x, y in zip(a[0], b[0])),
                tuple(x + w * (y - x) for x, y in zip(a[1], b[1])), a[2])

    def rides(self):
        """(first, last) tick index of each raw ramp-bit run that ends inside the recording."""
        out, on, last = [], None, None
        for i in sorted(self.rows):
            bit = self.rows[i][2] & F_RAMP
            if bit and on is None:
                on = i
            if not bit and on is not None:
                out.append((on, last))
                on = None
            last = i
        return out


def live(gamedir):
    """The client's side, all of ONE slot: the live slot the `trail` report names, its marks, its span."""
    text = (gamedir / 'logs/runlines_smoke.log').read_text(errors='replace')
    if 'RUNLINES COMPLETE' not in text:
        raise SystemExit('Control did not finish: %s' % gamedir)
    slot = re.search(r'trail: cv \S+  live slot (\d+) \((\d+) pts', text)
    if not slot:
        raise SystemExit('No `trail` report: %s' % gamedir)
    tables, span, cur = {}, {}, None
    for line in text.splitlines():
        m = re.search(r'\blnmb (\d+) \S+ \S+ \S+ (\S+) (\S+)', line)
        if m:
            cur = int(m[1])
            tables[cur] = []
            span[cur] = (float(m[2]), float(m[3]))
            continue
        m = re.search(r'\blnm (\S.*)$', line)
        if m and cur is not None:
            f = m[1].split()
            tables[cur].append(dict(kind=int(f[1]), sub=int(f[2]), t=float(f[3]),
                                    pos=tuple(map(float, f[5:8]))))
    which = int(slot[1])
    samples = re.search(r'trail: run (\d+) samples', text)
    pair = re.search(r'trail: pairing (\d+) of (\d+) samples from an older frame and (\d+) between '
                     r'snapshots, last (-?\d+) behind \(ack (-?\d+) behind\), (\d+) waits', text)
    return dict(marks=tables.get(which, []), span=span.get(which, (0.0, 0.0)),
                samples=int(samples[1]) if samples else 0,
                pair=tuple(map(int, pair.groups())) if pair else None)


class LiveLag(unittest.TestCase):
    subject = control = rec = control_rec = None
    frame = 0.010

    def setUp(self):
        if self.subject is None:
            self.skipTest('requires a retained rig')
        if not self.rec.rides():
            self.fail(CANNOT + 'no save in the rig holds a ramp ride with its exit')

    def allowed(self, rec, row):
        """One tick and one rendered frame of travel at the recorded speed, plus the 0.01 u print.

        Under the tick rate it is two frames: a command then spans a tick or two, and one sample in ten
        is a frame off with no latency at all (measured at 60 fps: 17 u at the 90th centile)."""
        frames = 2 if self.frame > rec.tick else 1
        return dist(row[1], (0, 0, 0)) * (rec.tick + frames * self.frame) + 1.0

    def off_record(self, side, rec):
        """[(what, distance, allowed)] for every mark; LookupError if the recording lacks its clock."""
        out = []
        for m in side['marks']:
            what = '%s mark at %.4f' % ({E_LAND: 'land', E_LEAVE: 'leave'}.get(m['kind'], 'kind %d' % m['kind']),
                                        m['t'])
            row = rec.at(m['t'])
            if row is None:
                raise LookupError('%s: the recording has no sample with that clock' % what)
            out.append((what, dist(m['pos'], row[0]), self.allowed(rec, row)))
        return out

    def ramp_marks(self, side, rec):
        """[(name, the mark, the recorded contact tick)] for the first recorded ride; asserts one of each."""
        first, last = rec.rides()[0]
        out = []
        for name, i, kind, sub in (('land', first, E_LAND, AIR_TO_RAMP), ('leave', last, E_LEAVE, RAMP_TO_AIR)):
            got = [m for m in side['marks'] if m['kind'] == kind and m['sub'] == sub]
            self.assertEqual(len(got), 1, '%s marks' % name)
            out.append((name, got[0], i))
        return out

    def test_the_run_had_latency_and_the_line_kept_its_samples(self):
        pair = self.subject['pair']
        self.assertIsNotNone(pair, 'no `trail: pairing` report: a build before Patch 611')
        older, total, filled, _, ack, waits = pair
        if (ack - 2) * max(self.rec.tick, self.frame) < MIN_LAG:
            self.fail(CANNOT + 'the acknowledged frame was %d behind, as on a local server' % ack)
        print('\n  tick %.4f; acknowledged frame %d behind; of %d samples %d from an older frame and %d '
              'between snapshots; %d waits' % (self.rec.tick, ack, total, older, filled, waits))
        self.assertEqual(total, self.subject['samples'])
        self.assertGreaterEqual(older + filled, 0.9 * total)
        # One sample a command: a snapshot that never came may not thin the line.
        t0, t1 = self.subject['span']
        commands = (t1 - t0) / max(self.rec.tick, self.frame)
        self.assertGreater(commands, 30)
        self.assertGreaterEqual(total, 0.9 * commands, 'the line lost samples')

    def test_every_mark_on_the_recorded_sample(self):
        try:
            rows = self.off_record(self.subject, self.rec)
        except LookupError as e:
            self.fail(CANNOT + str(e))
        self.assertGreaterEqual(len(rows), 2)
        for what, d, allowed in rows:
            print('\n  %s: %.1f u from the recorded sample (allowed %.1f)' % (what, d, allowed), end='')
        print()
        for what, d, allowed in rows:
            self.assertLessEqual(d, allowed, what)

    def test_ramp_marks_within_a_tick_of_the_recorded_contact(self):
        # The line takes one sample a rendered frame: under the tick rate that is the resolution.
        ticks = max(1, math.ceil(self.frame / self.rec.tick))
        for name, m, i in self.ramp_marks(self.subject, self.rec):
            self.assertLessEqual(abs(round(m['t'] / self.rec.tick) - i), ticks, name)
            d = dist(m['pos'], self.rec.rows[i][0])
            print('\n  %s: %.1f u from the recorded contact sample' % (name, d), end='')
            self.assertLessEqual(d, 2 * self.allowed(self.rec, self.rec.rows[i]), name)
        print()

    def test_control_build_is_refused(self):
        if self.control is None:
            self.skipTest('no --control rig')
        rec = self.control_rec
        if not rec.rides():
            self.fail(CANNOT + 'the control rig holds no recorded ride')
        self.assertIsNone(self.control['pair'], 'the control build has the patch')
        # The old build prints no latency, so its own ramp marks have to show it: both out of place.
        for name, m, i in self.ramp_marks(self.control, rec):
            d, allowed = dist(m['pos'], rec.rows[i][0]), self.allowed(rec, rec.rows[i])
            print('\n  control %s: %.1f u from the recorded contact sample (allowed %.1f)' % (name, d, allowed),
                  end='')
            if d <= 2 * allowed:
                self.fail(CANNOT + 'the control run shows no latency in its %s mark' % name)
        print()


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('gamedir', type=Path)
    ap.add_argument('--fps', type=float, default=100, help="the arm's cl_maxfps")
    ap.add_argument('--control', type=Path)
    args = ap.parse_args()
    LiveLag.frame = 1.0 / args.fps
    LiveLag.subject = live(args.gamedir)
    LiveLag.rec = Recording(args.gamedir)
    if args.control:
        LiveLag.control = live(args.control)
        LiveLag.control_rec = Recording(args.control)
    result = unittest.main(argv=[sys.argv[0]], exit=False).result
    said = [text for _, text in result.failures + result.errors]
    if any(CANNOT in text for text in said):
        print('CANNOT MEASURE (exit 2): not a pass and not a defect; run the arm again')
        sys.exit(2)
    sys.exit(0 if result.wasSuccessful() else 1)
