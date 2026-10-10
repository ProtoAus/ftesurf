#!/usr/bin/env python3
"""Grade the live Segments column around a teleport (Patch 616).

  python tools/test_runlines_seglive.py <rig>/ftesurf/logs/runlines_smoke.log
      --control-log <the same arm on a build with the Board_LiveMoved call compiled out>
      [--landing-control-log <...on a build without Board_Frame's seg_laste line>]
      [--load-control-log <...on a build whose Board_LiveMoved tells a load's step like any other>]

The log is tools/runlines_smoke.py's, from ftesurf/cfg/test/runlines_seglive.cfg, as a listen server or
with --dedicated --map surf_kitsune (and any --server-arg "+set sv_minping N" well under 300: STOP
puts the body back 0.3 s after it lifts it). The arm stays in surf_kitsune's spawn room and prints the
column (`replay seq live`) after each of seven stages:

  JUMP      a plain jump off the floor: the row every other row is compared with
  MIDAIR    the same jump, moved about 250 u straight up a quarter of a second in (`cmd setpos`)
  DROP      standing on the floor, moved 200 u straight up, and the fall back
  STOP      moved 200 u up again and, 0.3 s into the fall, put back on the floor
  LOAD      moved 200 u up a third time, saved 0.2 s into the fall, landed, walked 200 u along the
            floor, then loaded with the load key's own pair (load, hold, release)
  DOOR      walking into the room's door: a map teleporter that lifts the body 300 u onto the floor
            above, where it lands within a tick or two
  DOORJUMP  a plain jump on that floor

The rule: the energy step across a teleport is charged to no row, and the ground left behind is not
the next hop's launch point. So the MIDAIR and DOORJUMP rows read what the plain jump read, and the
DROP and STOP rows are falls that gained nothing and are not named hops. Without the patch the four
read 250, 200, 200 and 300 more: the last because the short fall after the door is too short to be
a row and its 300 is carried into the next one.

Two stages are each there for one line, and each has its own control:
  STOP  Its row closes on the frame the body is moved, and an air time that lands closes at the
        frame before's energy (build 88): the other side of the step unless Board_Frame moves it.
  LOAD  A save-lock load is NOT a teleport to tell: its restore puts the open row back with the
        reference the save holds. The fall it restores gained nothing, so the column's total may
        not move; told like a teleport, the restored row loses the step (-185 here). The subject
        has to SAY it saw the load's step and did not tell it, or a refused load would pass.

Against a server the door is a teleporter the client predicts (the log has cl_triggers.qc's
`prediction hook alive`), and its break has to be of that kind; on a listen server it is kinematic.

EXIT STATUSES. 0: measured and right. 1: measured and wrong. 2: CANNOT MEASURE -- a log is missing
or unfinished, a stage or a dump is short, or the body is not where its stage should have left it,
in the subject or in a control. That is not a pass and not a defect; run the arm again. 64: the
command line. The control log is required: a grader for a display rule that cannot be shown failing
shows nothing. The two optional controls are named when they were not given.
"""
import argparse
from pathlib import Path
import re
import sys
import unittest

AIR = 1
STAGES = ('JUMP', 'MIDAIR', 'DROP', 'STOP', 'LOAD', 'DOOR', 'DOORJUMP')
TOLD = [0, 1, 2, 4, 5, 6, 6]    # teleports the column has been told of by the end of each stage
NOTHING = 10                    # energy, in units of height: over eight variants a moved jump read within 1.1 of its plain one
CANNOT = 'CANNOT MEASURE: '


class Run:
    """One log: per stage, the column it printed and what it said of each step; and the body's place."""

    def __init__(self, text):
        self.complete = 'RUNLINES COMPLETE' in text
        self.hook = 'prediction hook alive' in text
        self.short = None
        self.stages = {}
        parts = re.split(r'==== ([A-Z]+) ====', text)
        for name, body in zip(parts[1::2], parts[2::2]):
            # The stage's LAST dump: from its `lvsb <rows> <predicted> <kinematic>` to its `lvse`.
            rows = told = None
            start = body.rfind('lvsb ')
            end = body.find('lvse', start) if start >= 0 else -1
            if end >= 0:
                block = body[start:end]
                head = block.split()
                told = tuple(int(float(x)) for x in head[2:4])
                rows = [dict(kind=int(f[1]), sub=int(f[2]), dur=float(f[3]), de=float(f[4]))
                        for f in (m.split() for m in re.findall(r'\blvs ([^\r\n]+)', block))]
                if len(rows) != int(float(head[1])):
                    self.short = name
            breaks = [(int(k), float(moved), int(kind)) for k, moved, kind in
                      re.findall(r'seg: live break (\d) at command \d+ \(teleport on \d+\), moved ([\d.]+), open (\d)',
                                 body)]
            quiet = [float(moved) for moved in re.findall(r"seg: live step of ([\d.]+) is a load's, not told", body)]
            self.stages[name] = dict(rows=rows, told=told, breaks=breaks, quiet=quiet)
        # The arm's three `cmd viewpos` answers, in order. NOT read per stage: the server's answer
        # arrives a round trip later, after the next stage's marker has been echoed.
        self.where = [float(z) for z in
                      re.findall(r'\bsetpos -?[\d.]+ -?[\d.]+ (-?[\d.]+) -?[\d.]+ -?[\d.]+ -?[\d.]+', text)]
        self.saved = len(re.findall(r'\bsave 1 \(slot', text))
        fps = re.findall(r'(\d+) fps\^7 measured|(\d+) fps measured', text)
        self.fps = int(next(x for x in fps[-1] if x)) if fps else None

    def why_not(self):
        """Why this log measures nothing, or None."""
        if not self.complete:
            return 'the arm did not finish'
        for name in STAGES:
            if name not in self.stages or self.stages[name]['rows'] is None:
                return 'stage %s printed no column' % name
        if self.short:
            return 'stage %s printed fewer rows than its dump says it has' % self.short
        if len(self.where) != 3:
            return 'the body said where it was %d times, not 3' % len(self.where)
        if abs(self.where[1] - 96) > 2:
            return 'the body is not back on the spawn floor after DROP'
        if abs(self.where[2] - 392) > 2:
            return 'the door did not put the body on the floor above'
        if self.saved != 1:
            return 'LOAD took %d saves, not 1' % self.saved
        return None

    def rows(self, name):
        return self.stages[name]['rows']

    def last(self, name):
        rows = self.rows(name)
        return rows[-1] if rows else dict(kind=0, sub=0, dur=0, de=0)

    def total(self, name):
        return sum(row['de'] for row in self.rows(name))

    def told(self):
        return [sum(self.stages[name]['told']) for name in STAGES]


class SegLive(unittest.TestCase):
    subject = control = landing = load = None

    def one_more(self, name, before):
        self.assertEqual(len(self.subject.rows(name)), len(self.subject.rows(before)) + 1)

    def test_the_plain_jump_is_a_hop_row(self):
        row = self.subject.last('JUMP')
        print('\n  plain jump: %.2f' % row['de'])
        self.assertEqual(row['kind'], AIR)
        self.assertNotEqual(row['sub'], 0)
        self.assertTrue(40 < row['de'] < 70, row)

    def test_a_jump_moved_in_mid_air_reads_as_the_jump(self):
        ref, row = self.subject.last('JUMP'), self.subject.last('MIDAIR')
        print('\n  jump moved in mid-air: %.2f' % row['de'])
        self.one_more('MIDAIR', 'JUMP')
        self.assertEqual((row['kind'], row['sub']), (AIR, ref['sub']))
        self.assertLess(abs(row['de'] - ref['de']), NOTHING)

    def test_a_body_moved_off_the_floor_falls_for_nothing_and_is_no_hop(self):
        row = self.subject.last('DROP')
        print('\n  moved off the floor: %.2f, sub %d' % (row['de'], row['sub']))
        self.one_more('DROP', 'MIDAIR')
        self.assertEqual((row['kind'], row['sub']), (AIR, 0))
        self.assertLess(abs(row['de']), NOTHING)

    def test_a_fall_put_back_on_the_floor_closes_this_side_of_the_step(self):
        row = self.subject.last('STOP')
        print('\n  put back on the floor: %.2f over %.2f s, sub %d' % (row['de'], row['dur'], row['sub']))
        self.one_more('STOP', 'DROP')
        self.assertEqual((row['kind'], row['sub']), (AIR, 0))
        self.assertTrue(0.15 < row['dur'] < 0.6, row)
        self.assertLess(abs(row['de']), NOTHING)

    def test_a_load_keeps_the_row_its_save_held(self):
        s = self.subject
        moved = s.total('LOAD') - s.total('STOP')
        quiet, breaks = s.stages['LOAD']['quiet'], s.stages['LOAD']['breaks']
        print('\n  a saved fall, loaded: the column moved %.2f in all, %d rows after %d; steps not told %s'
              % (moved, len(s.rows('LOAD')), len(s.rows('STOP')), quiet))
        # The load happened and the subject saw its step: without this a refused load passes.
        self.assertTrue(quiet and 250 < quiet[0] < 330, quiet)
        # Told of the lift before the save, and of nothing after it.
        self.assertEqual(len(breaks), 1, breaks)
        # The restored fall joins the row above it or stands as its own; either way it gained nothing.
        self.assertIn(len(s.rows('LOAD')) - len(s.rows('STOP')), (0, 1))
        self.assertLess(abs(moved), NOTHING)
        self.assertEqual(s.last('LOAD')['sub'], 0)

    def test_the_door_leaves_nothing_for_the_next_row(self):
        before, after = self.subject.rows('LOAD'), self.subject.rows('DOOR')
        # The fall onto the floor above is a tick or two: no row, or one that says nothing.
        for row in after[len(before):]:
            self.assertEqual(row['sub'], 0)
            self.assertLess(abs(row['de']), NOTHING)
        ref, row = self.subject.last('JUMP'), self.subject.last('DOORJUMP')
        print('\n  jump after the door: %.2f' % row['de'])
        self.one_more('DOORJUMP', 'DOOR')
        self.assertEqual((row['kind'], row['sub']), (AIR, ref['sub']))
        self.assertLess(abs(row['de'] - ref['de']), NOTHING)

    def test_the_column_was_told_of_each_teleport_once(self):
        s = self.subject
        told = [s.stages[name]['told'] for name in STAGES]
        print('\n  %s; teleports told (predicted, kinematic) after each stage: %s'
              % ('a server, the door predicted' if s.hook else 'a listen server', told))
        self.assertEqual(s.told(), TOLD)
        mid, drop, stop, door = (s.stages[name]['breaks'] for name in ('MIDAIR', 'DROP', 'STOP', 'DOOR'))
        # The subject's own lines: what kind, what was open, and how far the body went. Behind a
        # ping the server's body has been falling for the round trip before the client hears.
        self.assertTrue(mid and mid[0][0] == 2 and mid[0][2] == AIR and 150 < mid[0][1] < 300, mid)
        self.assertTrue(drop and drop[0][0] == 2 and drop[0][2] == 0 and 150 < drop[0][1] < 210, drop)
        self.assertTrue(len(stop) >= 2 and stop[0][2] == 0 and stop[-1][2] == AIR, stop)
        self.assertTrue(door and door[0][2] == 0 and 280 < door[0][1] < 310, door)
        # The door's kind: predicted where the hook runs, and counted as such; kinematic where not.
        self.assertEqual(door[0][0], 1 if s.hook else 2, door)
        self.assertEqual(told[-1], (1, 5) if s.hook else (0, 6))

    def test_control_build_is_refused(self):
        c = self.control
        ref = c.last('JUMP')['de']
        got = [c.last('MIDAIR')['de'] - ref, c.last('DROP')['de'], c.last('STOP')['de'],
               c.last('DOORJUMP')['de'] - ref]
        print('\n  control: the four rows read %s more than they should' % ', '.join('%.1f' % g for g in got))
        self.assertFalse(any(c.stages[name]['breaks'] for name in STAGES), 'the control was told of a teleport')
        for g in got:
            self.assertGreater(g, 150)
        self.assertNotEqual(c.last('DROP')['sub'], 0)

    def test_landing_control_is_refused(self):
        c = self.landing
        if c is None:
            self.skipTest('no --landing-control-log')
        self.assertEqual(c.told(), TOLD)
        row = c.last('STOP')
        print('\n  landing control: the row put back on the floor reads %.2f' % row['de'])
        self.assertGreater(row['de'], 150)
        # ...and nothing else moves: the line is only read by a row that lands on a moved frame.
        ref = c.last('JUMP')['de']
        for name in ('MIDAIR', 'DOORJUMP'):
            self.assertLess(abs(c.last(name)['de'] - ref), NOTHING)
        self.assertLess(abs(c.last('DROP')['de']), NOTHING)

    def test_load_control_is_refused(self):
        c = self.load
        if c is None:
            self.skipTest('no --load-control-log')
        moved = c.total('LOAD') - c.total('STOP')
        print('\n  load control: told %s, and the column moved %.2f over the load' % (c.told(), moved))
        self.assertFalse(c.stages['LOAD']['quiet'], 'the load control kept quiet about a step')
        self.assertEqual(c.told(), TOLD[:4] + [n + 1 for n in TOLD[4:]])
        self.assertGreater(abs(moved), 150)


def usage(parser):
    def error(message):
        parser.print_usage(sys.stderr)
        sys.stderr.write('%s: error: %s\n' % (parser.prog, message))
        sys.exit(64)
    return error


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.error = usage(ap)
    ap.add_argument('log', type=Path)
    ap.add_argument('--control-log', type=Path, required=True)
    ap.add_argument('--landing-control-log', type=Path)
    ap.add_argument('--load-control-log', type=Path)
    args = ap.parse_args()
    runs = {}
    for name, path in (('subject', args.log), ('control', args.control_log),
                       ('landing', args.landing_control_log), ('load', args.load_control_log)):
        if path is None:
            print('NOTE: no %s control log, so its one line has no control in this verdict' % name)
            continue
        try:
            runs[name] = Run(path.read_text(errors='replace'))
        except OSError as e:
            print(CANNOT + 'the %s log cannot be read (%s)' % (name, e))
            sys.exit(2)
        why = runs[name].why_not()
        if why:
            print(CANNOT + 'the %s log: %s' % (name, why))
            sys.exit(2)
        setattr(SegLive, name, runs[name])
    print('measured frame rate: %s fps' % (runs['subject'].fps if runs['subject'].fps else 'not printed'))
    unittest.main(argv=['test_runlines_seglive.py'])
