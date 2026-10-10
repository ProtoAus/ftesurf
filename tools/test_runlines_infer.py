#!/usr/bin/env python3
"""Grade inferred ramp contact as the client built it, against tools/rampinfer.py.

  python tools/test_runlines_infer.py <rig>/ftesurf/logs/runlines_smoke.log
      --recording <the import the arm was given> --native <its native control>
      --control-log <the same arm on a build without the inference>

The log is tools/runlines_smoke.py's, from ftesurf/cfg/test/runlines_infer.cfg.  Four sections:

  IMPORT       a re-imported Momentum run, replayed.  `replay status` must say `inferred` with the
               reference's step, airborne pairs and contact ticks; every mark (`replay marks 0`) must
               be the one tools/p449mark.py derives from the file with the reference's bits; the
               segment column has ramp rows; a ramp edge's label starts with ~ and no other does.
  BOARDLINE    the same file as a board line (`scores lineat 1`).  Its job reads the step itself and
               seeds from the last sample before the clock starts: its marks must be the model's for
               that window, and it must have fed the reference's contact ticks.
  NATIVE       a native recording: `measured`, its marks the file's own bit 16, no ~ anywhere.
  UNAVAILABLE  cfg/test/momflag.rec, an import with no `momdemo`: `unavailable`, no contact tick,
               no ramp mark and no ramp row, replayed and as a board line.

The reference is not the client's code: tools/rampinfer.py was written from the measurement and
scored against native bit 16.  tools/p449mark.py's seed rule WAS written beside the client's.

EXIT STATUSES.  0: measured and right.  1: measured and wrong -- which includes a control that is
not one (it must lack the `ramp contact` line and every ramp mark the subject has).  2: CANNOT
MEASURE -- a log or a recording is missing, or a section is short.  64: the command line.
"""
import argparse
from pathlib import Path
import re
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import p449mark  # noqa: E402
import rampinfer  # noqa: E402

RAMP = 2
E_LAND, E_LEAVE, E_BREAK = 1, 2, 7
CANNOT = 'CANNOT MEASURE: '
STATUS = re.compile(r'ramp contact (.+?) \(line (\d+)\)\s+step ([\d.]+)\s+share ([\d.]+) of (\d+) '
                    r'airborne pairs\s+ticks (\d+)')


def ramp_edge(kind, sub):
    return kind in (E_LAND, E_LEAVE) and (sub // 4 == RAMP or sub % 4 == RAMP)


class Section:
    def __init__(self, body):
        self.body = body
        m = STATUS.search(body)
        self.status = m.groups() if m else None
        self.slots = {}                     # slot -> {'marks': [...], 'inf': (...)}
        slot = None
        for line in body.splitlines():
            line = re.sub(r'^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d ', '', line.strip())
            f = line.split()
            if line.startswith('lnmb '):
                slot = int(float(f[1]))
                self.slots[slot] = {'marks': [], 'text': [], 'inf': None,
                                    'hdr': (int(float(f[2])), int(float(f[3])), int(float(f[4])))}
            elif line.startswith('lnm ') and slot is not None:
                self.slots[slot]['marks'].append((int(float(f[2])), int(float(f[3])), float(f[4]), int(float(f[5])),
                                                  float(f[9]), float(f[10]), float(f[11]), float(f[12])))
            elif line.startswith('lnml ') and slot is not None:
                self.slots[slot]['text'].append(line.split(' ', 2)[2].strip('"'))
            elif line.startswith('lnmi ') and slot is not None:
                self.slots[slot]['inf'] = (int(float(f[2])), float(f[3]), int(float(f[4])))
        self.rows = [int(m[1]) for m in re.finditer(r'\blns \d+ (\d+) ', body)]     # each row's kind
        self.seq_printed = 'lnse ' in body
        # the playhead's own contact, each time `replay status` was asked: (seconds, rc)
        self.at = [(float(m[1]), int(m[2])) for m in
                   re.finditer(r'\bt ([-\d.]+)\s+span [^\n]*\n(?:[^\n]*\n){0,24}?[^\n]*\bv4 \d+\s+rc (\d)', body)]
        # every nth point's air-control grade: (point, q)
        self.grades = [(int(m[1]), float(m[2])) for m in
                       re.finditer(r'\blnc (\d+) [-\d.]+ [-\d.]+ [-\d.]+ [-\d.]+ ([-\d.]+)', body)]
        # what drew: lndm <slot> <kind> <t> <x> <y> <"label"|->
        self.labels = [(int(float(m[1])), float(m[2]), m[3]) for m in
                       re.finditer(r'lndm 0 (\d+) ([-\d.]+) [-\d.]+ [-\d.]+ (".*?"|-)\s*$', body, re.M)]

    def ramp_marks(self, slot=0):
        return [m for m in self.slots.get(slot, {'marks': []})['marks'] if ramp_edge(m[0], m[1])]


class Run:
    def __init__(self, text):
        self.complete = 'RUNLINES COMPLETE' in text
        parts = re.split(r'==== ([A-Z]+) ====', text)
        self.s = {name: Section(body) for name, body in zip(parts[1::2], parts[2::2])}

    def why_not(self, need):
        if not self.complete:
            return 'the run did not finish'
        for name in need:
            if name not in self.s:
                return 'no %s section' % name
            if 0 not in self.s[name].slots and name != 'BOARDLINE':
                return 'the %s section printed no marks' % name
        return None


def compare(test, got, want, what):
    test.assertEqual(len(got), len(want), '%s: %d marks, the model has %d' % (what, len(got), len(want)))
    for i, (g, w) in enumerate(zip(got, want)):
        test.assertEqual((g[0], g[1], g[3]), (w[0], w[1], w[3]), '%s mark %d at t %.4f: kind/sub/sample' % (what, i, w[2]))
        test.assertAlmostEqual(g[2], w[2], delta=0.0002, msg='%s mark %d: time' % (what, i))
        test.assertAlmostEqual(g[4], w[4], delta=0.02, msg='%s mark %d: speed' % (what, i))
        test.assertAlmostEqual(g[6], w[6], delta=0.02, msg='%s mark %d: vz' % (what, i))
        test.assertAlmostEqual(g[7], w[7], delta=0.0002, msg='%s mark %d: edge clock' % (what, i))


class Infer(unittest.TestCase):
    subject = control = None
    recording = native = None

    @classmethod
    def setUpClass(cls):
        cls.keys, cls.rows = rampinfer.read(cls.recording)
        cls.bits, cls.step, cls.nair, cls.share, cls.why = rampinfer.verdict(cls.keys, cls.rows)

    def test_reference_infers_this_file(self):
        self.assertEqual(self.why, '', 'the reference does not infer the recording given: %s' % self.why)
        self.assertGreater(sum(self.bits), 100)

    def test_import_scan_is_the_reference(self):
        st = self.subject.s['IMPORT'].status
        self.assertIsNotNone(st, 'no `ramp contact` line in `replay status`')
        print('\n  import: %s, step %s, share %s of %s pairs, %s contact ticks; reference %.2f, %.3f of %d, %d'
              % (st[0], st[2], st[3], st[4], st[5], self.step, self.share, self.nair, sum(self.bits)))
        self.assertEqual((st[0], st[1]), ('inferred', '1'))
        self.assertAlmostEqual(float(st[2]), self.step, delta=0.006)
        self.assertEqual(int(st[4]), self.nair)
        self.assertAlmostEqual(float(st[3]), self.share, delta=0.0006)
        self.assertEqual(int(st[5]), sum(self.bits))

    def test_import_marks_are_the_models(self):
        sec = self.subject.s['IMPORT']
        got = sec.slots[0]['marks']
        self.assertEqual(sec.slots[0]['hdr'][1:], (0, 0), 'the mark table was cut or dropped marks')
        breaks = {m[3] for m in got if m[0] == E_BREAK}
        want, n = p449mark.derive(str(self.recording), breaks, bits=self.bits)
        self.assertEqual(n, len(self.rows))
        compare(self, got, want, 'replay')
        ramp = sec.ramp_marks()
        lands = sum(1 for m in ramp if m[0] == E_LAND)
        print('\n  import: %d marks, %d on a ramp edge (%d on, %d off); %d segment rows, %d ramp'
              % (len(got), len(ramp), lands, len(ramp) - lands, len(sec.rows), sec.rows.count(RAMP)))
        self.assertGreater(lands, 3)
        self.assertGreater(len(ramp) - lands, 3)
        self.assertGreater(sec.rows.count(RAMP), 3)

    def test_import_labels_say_inferred(self):
        sec = self.subject.s['IMPORT']
        sub = {(m[0], round(m[2], 4)): m[1] for m in sec.slots[0]['marks']}
        drawn = [(k, t, lab) for k, t, lab in sec.labels if lab != '-']
        self.assertGreater(len(drawn), 0, 'no label drew')
        tilde = plain = 0
        for k, t, lab in drawn:
            self.assertIn((k, round(t, 4)), sub, 'a label at no mark')
            if ramp_edge(k, sub[(k, round(t, 4))]):
                self.assertTrue(lab.startswith('"~'), 'a ramp edge label without ~: %s' % lab)
                tilde += 1
            else:
                self.assertFalse(lab.startswith('"~'), 'a ~ on a mark that is not a ramp edge: %s' % lab)
                plain += 1
        self.assertGreater(tilde, 0, 'no ramp edge label drew in the frames traced')
        # A camera shows a few marks.  Every mark's label, as the draw pass would write it:
        marks, text = sec.slots[0]['marks'], sec.slots[0]['text']
        self.assertEqual(len(text), len(marks), 'not one label line a mark')
        edge = [t for m, t in zip(marks, text) if ramp_edge(m[0], m[1])]
        other = [t for m, t in zip(marks, text) if not ramp_edge(m[0], m[1]) and m[0] != E_BREAK]
        print('\n  import labels: drawn %d with ~ (%d plain); of all %d marks, %d ramp edges and %d others'
              % (tilde, plain, len(marks), len(edge), len(other)))
        self.assertGreater(len(other), 3, 'the run has no other mark: nothing shows the ~ is kept to ramp edges')
        self.assertEqual([t for t in edge if not t.startswith('~')], [], 'a ramp edge label without ~')
        self.assertEqual([t for t in other if t.startswith('~') or not t], [], 'a ~ (or no label) on another mark')

    def test_playhead_contact_is_the_reference(self):
        sec = self.subject.s['IMPORT']
        self.assertGreaterEqual(len(sec.at), 3, '`replay status` was not read at three playheads')
        seen = set()
        for t, rc in sec.at:
            idx = max(i for i, r in enumerate(self.rows) if r[0] <= rampinfer.f32(t) + 1e-6)
            seen.add(rc)
            self.assertEqual(rc, int(self.bits[idx]), 'the playhead at %.3f reads contact %d' % (t, rc))
        print('\n  playhead contact at %s' % ', '.join('%.1f s: %d' % a for a in sec.at))
        self.assertEqual(seen, {0, 1}, 'the playheads read did not include both answers')

    def test_inferred_ticks_are_not_graded(self):
        grades = self.subject.s['IMPORT'].grades
        self.assertGreater(len(grades), 1000, '`replay colours` printed too few points')
        on = [q for i, q in grades if self.bits[i]]
        off = [q for i, q in grades if not self.bits[i]]
        print('\n  air-control grade: %d contact points, %d graded; %d others, %d graded'
              % (len(on), sum(1 for q in on if q >= 0), len(off), sum(1 for q in off if q >= 0)))
        self.assertGreater(len(on), 200)
        self.assertEqual([q for q in on if q != -1], [], 'an inferred ramp tick was graded with no plane')
        self.assertGreater(sum(1 for q in off if q >= 0), 100, 'nothing else was graded either')

    def test_board_line_is_the_same_contact(self):
        sec = self.subject.s['BOARDLINE']
        self.assertIn(1, sec.slots, 'the board line printed no marks')
        got, inf = sec.slots[1]['marks'], sec.slots[1]['inf']
        self.assertIsNotNone(inf)
        pre = [i for i, r in enumerate(self.rows) if r[0] < 0]
        seed = pre[-1] if pre else None
        tail = [i for i, r in enumerate(self.rows) if r[0] >= rampinfer.f32(-0.5)]
        fed = sum(self.bits[i] for i in tail[1:]) if pre else sum(self.bits)
        print('\n  board line: source %d, step %.2f, fed %d contact ticks (reference %d); seeded at sample %s'
              % (inf[0], inf[1], inf[2], fed, seed))
        self.assertEqual(inf[0], 1)
        self.assertAlmostEqual(inf[1], self.step, delta=0.006)
        self.assertEqual(inf[2], fed)
        breaks = {m[3] for m in got if m[0] == E_BREAK}
        want, _ = p449mark.derive(str(self.recording), breaks, bits=self.bits, seed=seed)
        compare(self, got, want, 'board line')
        self.assertGreater(len([m for m in got if ramp_edge(m[0], m[1])]), 6)

    def test_native_is_measured(self):
        sec = self.subject.s['NATIVE']
        st = sec.status
        self.assertIsNotNone(st)
        self.assertEqual((st[0], st[1], st[5]), ('measured', '0', '0'))
        got = sec.slots[0]['marks']
        breaks = {m[3] for m in got if m[0] == E_BREAK}
        want, _ = p449mark.derive(str(self.native), breaks)
        if sec.slots[0]['hdr'][1] or sec.slots[0]['hdr'][2]:
            want = [w for w in want if w[0] not in (4, 5)]
            got = [g for g in got if g[0] not in (4, 5)]
        compare(self, got, want, 'native')
        print('\n  native: %d marks, %d on a ramp edge; %d labels drawn'
              % (len(got), len(sec.ramp_marks()), sum(1 for _, _, lab in sec.labels if lab != '-')))
        self.assertGreater(len(sec.ramp_marks()), 3, 'the native control has no ramp edge: it controls nothing')
        self.assertGreater(sum(1 for _, _, lab in sec.labels if lab != '-'), 0)
        self.assertFalse([lab for _, _, lab in sec.labels if lab.startswith('"~')], 'a ~ on a measured line')
        self.assertEqual(len(sec.slots[0]['text']), len(sec.slots[0]['marks']))
        self.assertFalse([t for t in sec.slots[0]['text'] if t.startswith('~')], 'a ~ on a measured line')

    def test_unavailable_marks_nothing(self):
        sec = self.subject.s['UNAVAILABLE']
        st = sec.status
        self.assertIsNotNone(st)
        self.assertEqual((st[0], st[1], st[5]), ('unavailable: no per-tick data', '2', '0'))
        self.assertGreater(len(sec.slots[0]['marks']), 0, 'the file drew no mark at all: nothing was read')
        self.assertEqual(sec.ramp_marks(), [])
        self.assertTrue(sec.seq_printed)
        self.assertEqual(sec.rows.count(RAMP), 0)
        self.assertIn(3, sec.slots, 'its board line printed no marks')
        self.assertEqual(sec.slots[3]['inf'], (2, 0.0, 0))
        self.assertGreater(len(sec.slots[3]['marks']), 0, 'its board line drew no mark at all: nothing was built')
        self.assertEqual(sec.ramp_marks(3), [])

    def test_control_has_none_of_it(self):
        c = self.control.s['IMPORT']
        ramp = c.ramp_marks()
        print('\n  control: `ramp contact` line %s; %d marks, %d on a ramp edge; %d ramp rows'
              % ('present' if c.status else 'absent', len(c.slots[0]['marks']), len(ramp), c.rows.count(RAMP)))
        self.assertIsNone(c.status)
        self.assertEqual(ramp, [])
        self.assertEqual(c.rows.count(RAMP), 0)
        self.assertGreater(len(c.slots[0]['marks']), 0, 'the control read nothing')


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
    ap.add_argument('--native', type=Path, required=True)
    ap.add_argument('--control-log', type=Path, required=True)
    args = ap.parse_args()
    for name, path in (('recording', args.recording), ('native', args.native)):
        if not path.is_file():
            print(CANNOT + 'the %s is not a file' % name)
            sys.exit(2)
    for name, path, need in (('subject', args.log, ('IMPORT', 'BOARDLINE', 'NATIVE', 'UNAVAILABLE')),
                             ('control', args.control_log, ('IMPORT',))):
        try:
            run = Run(path.read_text(errors='replace'))
        except OSError as e:
            print(CANNOT + 'the %s log cannot be read (%s)' % (name, e))
            sys.exit(2)
        why = run.why_not(need)
        if why:
            print(CANNOT + 'the %s log: %s' % (name, why))
            sys.exit(2)
        setattr(Infer, name, run)
    Infer.recording, Infer.native = args.recording, args.native
    unittest.main(argv=['test_runlines_infer.py'])
