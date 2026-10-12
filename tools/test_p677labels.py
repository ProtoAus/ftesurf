#!/usr/bin/env python3
"""Run-label styling runtime falsifier (no player recordings).

Generate two authored hop fixtures:
  python tools/test_p677labels.py --write <owned-output-dir>
Run p677labels.cfg with tools/runlines_smoke.py, supplying p677hop.rec and
p677hop_mom.rec via --also, once with pre-change CSQC and once with subject.
Grade the acting pair:
  python tools/test_p677labels.py --log <subject-log> --control-log <control-log>

The existing peak fixture supplies tops/bottoms and ordinary ramp contacts.
The new fixture has a one-sample ground touch+jump, a real landing held for
several samples then a jump, and a landing followed by walking off. Tables and
Segments must stay byte-for-byte the control's; only the first contact's ink
is removed. Image checks read actual coloured pixels, not requested cvars.
"""
import argparse
from pathlib import Path
import re
import unittest

from test_runlines_peaks import Motion, text


def hop():
    m = Motion()
    m.fall(12)
    m.tick(0, ground=True, jump=True)  # one sampled contact; autohop
    m.v[2] = 270
    m.fall(1)
    m.fall(32)
    m.tick(0, ground=True)             # ordinary landing, not hidden
    m.tick(0, ground=True, n=4)
    m.tick(0, ground=True, jump=True)
    m.v[2] = 270
    m.fall(1)
    m.fall(32)
    m.tick(0, ground=True)             # walking off is not a hop
    m.tick(0, ground=True, n=3)
    m.fall(10)
    return m


def sections(txt):
    parts = re.split(r'==== ([A-Z]+) ====', txt)
    return dict(zip(parts[1::2], parts[2::2]))


def marks(txt):
    return [tuple(map(float, r.split())) for r in re.findall(r'^lnm ([^\r\n]+)', txt, re.M)]


def drawn(txt, slot=0):
    return [(int(k), float(t), float(x), float(y), lab) for k, t, x, y, lab in
            re.findall(rf'^lndm {slot} (\d+) ([\d.-]+) ([\d.-]+) ([\d.-]+) (.*)$', txt, re.M)]


def pixels(path):
    from PIL import Image
    return Image.open(path).convert('RGB')


def ink(image, rect, colour):
    # Bright cores survive alpha/AA; dark map/line/shadow ink cannot pass.
    tests = {'yellow': lambda r, g, b: r > 110 and g > 110 and b < min(r, g) * .4,
             'green': lambda r, g, b: g > 110 and r < g * .5 and b < g * .65,
             'pink': lambda r, g, b: r > 100 and g < r * .55 and r * .5 < b < r * .8,
             'purple': lambda r, g, b: b > 100 and b * .55 < r < b * .85 and g < b * .55}
    x0, y0, x1, y1 = map(int, rect)
    return [(x, y) for y in range(max(0, y0), min(image.height, y1))
            for x in range(max(0, x0), min(image.width, x1))
            if tests[colour](*image.getpixel((x, y)))]


class Styling(unittest.TestCase):
    subject = control = None
    images = None

    def setUp(self):
        if self.subject is None:
            self.skipTest('supply paired runtime logs')

    def test_runtime_finished_and_drew(self):
        for txt in (self.subject, self.control):
            self.assertIn('RUNLINES COMPLETE', txt)
            self.assertNotRegex(txt, r'QC runtime error|CSQC_Abort|runaway loop|Unknown command "replay"')
            self.assertGreater(len(drawn(sections(txt)['BOTH'])), 3)

    def test_tables_labels_and_segments_unchanged(self):
        for name in ('BOTH', 'HOP', 'IMPORT', 'BOARD'):
            a, b = sections(self.subject)[name], sections(self.control)[name]
            for prefix in ('lnm ', 'lnml ', 'lng ', 'lnf ', 'lnmz ', 'lns '):
                self.assertEqual(re.findall('^' + prefix + r'.*$', a, re.M),
                                 re.findall('^' + prefix + r'.*$', b, re.M), (name, prefix))
            self.assertGreater(len(marks(a)), 3)

    def test_autohop_only_contact_is_suppressed(self):
        for name in ('HOP', 'IMPORT', 'BOARD'):
            slot = 1 if name == 'BOARD' else 0
            a, b = sections(self.subject)[name], sections(self.control)[name]
            table = marks(a)
            contacts = [r for r in table if int(r[1]) == 1 and int(r[2]) % 4 == 0]
            self.assertEqual(len(contacts), 3)
            auto, normal, walk = contacts
            jump = next(r for r in table if int(r[1]) == 3)
            self.assertEqual(jump[4] - auto[4], 1)
            key = lambda r: (int(r[1]), r[3])
            before = {(k, t) for k, t, _, _, _ in drawn(b, slot)}
            after = {(k, t) for k, t, _, _, _ in drawn(a, slot)}
            for r in (auto, normal, walk, jump):
                self.assertIn(key(r), before, 'control must draw every tested mark')
            self.assertNotIn(key(auto), after)
            for r in (normal, walk, jump):
                self.assertIn(key(r), after)
            self.assertEqual(before - after, {key(auto)})
            self.assertEqual(after - before, set())

    def test_jump_switch_keeps_contact_when_no_jump_is_drawn(self):
        a = sections(self.subject)
        auto = next(r for r in marks(a['HOP']) if int(r[1]) == 1)
        shown = {(k, t) for k, t, _, _, _ in drawn(a['JUMPOFF'])}
        self.assertIn((1, auto[3]), shown)
        self.assertNotIn(3, {k for k, _ in shown})

    def test_switches_and_plain_diagnostics(self):
        a = sections(self.subject)
        for name in ('BOTH', 'ENERGY', 'SPEED', 'UNITZERO'):
            rows = drawn(a[name])
            labels = [lab for *_, lab in rows if lab != '-']
            self.assertGreater(len(labels), 0, name)
            self.assertNotIn('^x', ''.join(labels))
            if name == 'ENERGY':
                self.assertNotIn('u/s', ''.join(labels))
                self.assertIn('E ', ''.join(labels))
            if name == 'SPEED':
                self.assertNotIn('E ', ''.join(labels))
                self.assertIn('u/s', ''.join(labels))
        self.assertTrue(all(lab == '-' for *_, lab in drawn(a['NUMSOFF'])))
        self.assertNotIn(4, {k for k, *_ in drawn(a['NUMSOFF'])})
        self.assertNotIn(5, {k for k, *_ in drawn(a['NUMSOFF'])})
        self.assertEqual(drawn(a['MARKSOFF']), [])

    def test_actual_label_ink(self):
        # This fixture's first ramp leave has a clear label immediately above it.
        # Anchor to the pass's projection, not the map/HUD's colourful background.
        for name, wanted, absent in [('both', ('yellow', 'green'), ()),
                                     ('energy', ('green',), ('yellow',)),
                                     ('speed', ('yellow',), ('green',)),
                                     ('unitzero', ('yellow', 'green'), ())]:
            im = pixels(self.images / ('p677_' + name + '.png'))
            leave = next(r for r in drawn(sections(self.subject)[name.upper()]) if r[0] == 2)
            x, y = leave[2:4]
            rect = (x + 6, y - 32, x + 156, y)
            for col in wanted:
                self.assertGreater(len(ink(im, rect, col)), 20, (name, col))
            for col in absent:
                self.assertEqual(len(ink(im, rect, col)), 0, (name, col))

    def test_peak_triangle_colour_and_orientation(self):
        im = pixels(self.images / 'p677_both.png')
        seen = set()
        for kind, _, x, y, _ in drawn(sections(self.subject)['BOTH']):
            if kind not in (4, 5):
                continue
            col = 'pink' if kind == 4 else 'purple'
            pts = ink(im, (x - 11, y - 11, x + 12, y + 12), col)
            if len(pts) < 15:
                continue                    # a covered/faded mark is not the witness
            upper = [p for p in pts if p[1] < y - 3]
            lower = [p for p in pts if p[1] > y + 3]
            self.assertTrue(upper and lower, (kind, x, y))
            width = lambda row: max(p[0] for p in row) - min(p[0] for p in row)
            self.assertGreater(width(lower) if kind == 4 else width(upper),
                               width(upper) if kind == 4 else width(lower), (kind, x, y))
            seen.add(kind)
        self.assertEqual(seen, {4, 5}, 'both top and bottom must visibly act')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write', type=Path)
    ap.add_argument('--log', type=Path)
    ap.add_argument('--control-log', type=Path)
    args = ap.parse_args()
    if args.write:
        args.write.mkdir(parents=True, exist_ok=True)
        for foreign, name in ((False, 'p677hop.rec'), (True, 'p677hop_mom.rec')):
            (args.write / name).write_text(text(hop(), foreign))
        print('Wrote authored fixtures to', args.write)
    if args.log:
        if not args.control_log:
            ap.error('--log requires --control-log')
        normalize = lambda p: re.sub(r'^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d ', '',
                                     p.read_text(errors='replace'), flags=re.M)
        Styling.subject = normalize(args.log)
        Styling.control = normalize(args.control_log)
        Styling.images = args.log.parent.parent / 'screenshots'
        unittest.main(argv=['test_p677labels.py'])
