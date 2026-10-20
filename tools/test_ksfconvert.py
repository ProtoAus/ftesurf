#!/usr/bin/env python3
"""Independent layout/timeline/namespace tests; no installed player data used."""
import math
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
import ksfconvert as C


def binary(version=2, marks=None, cells=18, frames=9, repeat=()):
    if marks is None:
        marks = [(0, 2, 1, ''), (2, 3, 1, ''), (6, 2, 99, '')]
    b = struct.pack('<4i', version, 3, 12345, len(marks))  # not frame/run duration
    if version == 3:
        b += struct.pack('<2i', cells, 3) + bytes(12)
    for tick, touch, zone, name in marks:
        b += struct.pack('<3i', tick, touch, zone) + name.encode().ljust(256, b'\0') + bytes(256)
    for i in range(frames):
        # First integer is buttons, roll is a FLOAT. All axes intentionally distinct.
        buttons = 8 | 512 | 2 | 4 | 1 | 128
        p = i - 1 if i in repeat else i     # a frame the recorder wrote twice
        b += struct.pack('<i9f', buttons, p + .25, p + .5, p + .75, i + 1.25,
                         i + 1.5, i + 1.75, i + 2.25, i + 2.5, i + 2.75)
        if version == 3:
            extra = struct.pack('<3i2f2if', 3, i + 100, i + 200, 123.25, -456.5, 20, 30, 7.75)
            b += extra[:(cells - 10) * 4].ljust((cells - 10) * 4, b'\0')
    return b


def rows(text):
    return [s.split() for s in text.splitlines() if s[0].isdigit() or s[0] == '-']


class Convert(unittest.TestCase):
    def test_exact_prefix_and_namespaces(self):
        for v in (2, 3):
            text, info = C.convert(binary(v), 'surf_test', owner='test', style='SW', seconds=.06)
            r = rows(text)
            self.assertEqual((info['start'], info['stop'], info['seconds']), (2, 6, .06))
            self.assertEqual(len(r), 7)
            self.assertEqual(list(map(float, r[2][:9])), [0, 2.25, 2.5, 2.75, 4.25, 4.5, 4.75, 3.25, 3.5])
            self.assertEqual(int(r[2][9]), 12 + (v == 3))  # NEVER map ambiguous bit1 to ducked
            self.assertEqual(int(r[2][10]), 1 + 4 + 16 + 32 + 64 + 256)
            self.assertEqual(list(map(float, r[2][11:14])), [123.25, -456.5, 7.75] if v == 3 else [1, -1, 0])
            self.assertEqual(r[2][14:], ['0', '0', '0'])
            self.assertEqual(text.splitlines()[-1], 'end 4 7 2 0')
            self.assertIn('foreign ksf ', text)
            self.assertIn('mapbuild unknown', text)
            self.assertIn('clock sampled', text)
            self.assertIn('ksfbuttons 2 655', text)
            self.assertIn('moves recorded' if v == 3 else 'moves buttons 1', text)
            self.assertEqual('demodata 1' in text, v == 3)
            for key in ('nonce ', 'mapcrc ', 'zonecrc ', 'pmpin ', 'warp ', '\nin ', 'momdemo ', 'momquality '):
                self.assertNotIn(key, text)

    def test_bookmark_bonus_and_named_triggers(self):
        for names in (('', '', ''), ('5939107', '5939107', '5939108')):
            marks = [(0, 2, 34, names[0]), (2, 3, 34, names[1]), (6, 2, 34, names[2])]
            text, info = C.convert(binary(marks=marks), 'surf_bonus', bonus=4)
            self.assertIn('track 4\nstartseg 0\nleg 0', text)
            self.assertEqual(info['stop'], 6)
        # Named BONUS START re-entry must not act as finish.
        marks[-1] = (6, 2, 34, '5939107')
        with self.assertRaises(ValueError): C.convert(binary(marks=marks), 'surf_bonus', bonus=4)

    def test_refuse_ambiguous_missing_wrong_course(self):
        good = [(0, 2, 1, ''), (2, 3, 1, ''), (6, 2, 99, '')]
        for marks in ([], good[:2], good[1:], good + [(7, 2, 99, '')],
                      [good[0], (1, 3, 1, ''), *good[1:]], good[::-1]):
            with self.subTest(marks=marks), self.assertRaises(ValueError):
                C.convert(binary(marks=marks), 'surf_test')
        with self.assertRaises(ValueError): C.convert(binary(), 'surf_test', bonus=4)
        for kwargs in ({'mapname': '../map'}, {'mapname': 'X'}, {'bonus': -1},
                       {'bonus': 99}, {'style': 'auto'}, {'seconds': 1}, {'seconds': math.nan}):
            args = dict(mapname='surf_test'); args.update(kwargs)
            with self.assertRaises(ValueError): C.convert(binary(), **args)

    def test_lead_in_needs_the_official_time(self):
        # Patch 757: a recording that begins inside the start zone has no entry before
        # its one exit; only an official time that matches may bind that interval.
        for zone, stopz, bonus in ((34, 34, 4), (1, 99, 0)):
            marks = [(2, 3, zone, ''), (6, 2, stopz, '')]
            with self.subTest(bonus=bonus):
                with self.assertRaises(ValueError): C.convert(binary(marks=marks), 'surf_test', bonus=bonus)
                text, info = C.convert(binary(marks=marks), 'surf_test', bonus=bonus, seconds=.06)
                self.assertEqual((info['start'], info['stop']), (2, 6))
                with self.assertRaises(ValueError):
                    C.convert(binary(marks=marks), 'surf_test', bonus=bonus, seconds=.06 + 3 * .015)
        # Two exits stay ambiguous with a time as well.
        with self.assertRaises(ValueError):
            C.convert(binary(marks=[(1, 3, 1, ''), (2, 3, 1, ''), (6, 2, 99, '')]), 'surf_test', seconds=.06)

    def test_official_time_tolerance(self):
        # 2.5 ticks, plus one a 10,000 frames (3996 ticks: 2.9), plus each frame the
        # recorder repeated while moving (20 here: 22.9).
        for off, ok in ((2.4, True), (-2.4, True), (2.6, False), (-2.6, False)):
            with self.subTest(off=off):
                if ok:
                    C.convert(binary(), 'surf_test', seconds=.06 + off * .015)
                else:
                    with self.assertRaises(ValueError): C.convert(binary(), 'surf_test', seconds=.06 + off * .015)
        marks = [(0, 2, 1, ''), (2, 3, 1, ''), (3998, 2, 99, '')]
        long = binary(marks=marks, frames=4000)
        rep = binary(marks=marks, frames=4000, repeat=range(1000, 1040, 2))
        for data, lim, n in ((long, 2.9, 0), (rep, 22.9, 20)):
            for off, ok in ((lim - .2, True), (-(lim - .2), True), (lim + .2, False), (-(lim + .2), False)):
                with self.subTest(off=off, repeats=n):
                    if ok:
                        text, info = C.convert(data, 'surf_test', seconds=59.94 + off * .015)
                        self.assertEqual(info['repeats'], n)
                    else:
                        with self.assertRaises(ValueError): C.convert(data, 'surf_test', seconds=59.94 + off * .015)

    def test_malformed_and_nonfinite(self):
        data = binary(3)
        for b in (b'', b'<html>' * 100, data[:-1], data[:24], struct.pack('<i', 1) + data[4:]):
            with self.assertRaises(ValueError): C.convert(b, 'surf_test')
        for cell in (1, 8, 13, 17):
            bad = bytearray(data)
            off = 24 + 12 + 3 * 524
            struct.pack_into('<f', bad, off + cell * 4, math.nan)
            with self.assertRaises(ValueError): C.convert(bad, 'surf_test')

    def test_unknown_extra_stride_does_not_claim_moves(self):
        text, info = C.convert(binary(3, cells=19), 'surf_test')
        self.assertFalse(info['moves_recorded'])
        self.assertEqual(rows(text)[2][11:14], ['1.000000', '-1.000000', '0.000000'])

    def test_opposed_buttons_not_guessed_and_move_keys_resolved(self):
        data = bytearray(binary())
        struct.pack_into('<i', data, 16 + 3 * 524, 8 | 16 | 512 | 1024)
        text, _ = C.convert(data, 'surf_test')
        self.assertEqual(rows(text)[0][10:14], ['0', '0.000000', '0.000000', '0.000000'])
        self.assertIn('ksfbuttons 0 1560', text)
        data = bytearray(binary(3))
        off = 24 + 12 + 3 * 524
        struct.pack_into('<i', data, off, 0)  # commands still positive fwd/negative side
        text, _ = C.convert(data, 'surf_test')
        self.assertEqual(rows(text)[0][10], '5')

    def test_tiny_analog_directions_follow_written_precision(self):
        for value in (1e-8, -1e-8, 5e-7, -5e-7):
            data = bytearray(binary(3))
            off = 24 + 12 + 3 * 524
            struct.pack_into('<2f', data, off + 52, value, -value)
            text, _ = C.convert(data, 'surf_test')
            sample = rows(text)[0]
            fwd, side = map(float, sample[11:13])
            want = (1 if fwd > 0 else 2 if fwd < 0 else 0) | (8 if side > 0 else 4 if side < 0 else 0)
            self.assertEqual(int(sample[10]) & 15, want)

    def test_stage_is_its_own_recording(self):
        # Patch 891: stage N exits zone N and finishes entering zone N+1, filed as leg N.
        text, info = C.convert(binary(marks=[(0, 2, 3, ''), (2, 3, 3, ''), (6, 2, 4, '')]),
                               'surf_test', stage=3)
        self.assertEqual((info['start'], info['stop'], info['stage'], info['timed_stop']), (2, 6, 3, False))
        self.assertIn('track 0\nstartseg 2\nleg 3\n', text)
        self.assertNotIn('ksfstop', text)
        for marks in ([(0, 2, 3, ''), (2, 3, 3, ''), (6, 2, 5, '')],          # not the next stage
                      [(0, 2, 3, ''), (2, 3, 3, ''), (6, 2, 99, '')],         # end zone, not last
                      [(0, 2, 3, ''), (2, 3, 3, ''), (6, 2, 4, ''), (7, 2, 4, '')],
                      [(0, 2, 3, ''), (1, 3, 3, ''), (2, 3, 3, ''), (6, 2, 4, '')],
                      [(0, 2, 3, ''), (2, 3, 3, '')]):
            with self.subTest(marks=marks), self.assertRaises(ValueError):
                C.convert(binary(marks=marks), 'surf_test', stage=3, seconds=.06)
        good = binary(marks=[(0, 2, 3, ''), (2, 3, 3, ''), (6, 2, 4, '')])
        for kwargs in ({'stage': 31}, {'stage': -1}, {'stage': 3, 'bonus': 1}, {'last': True},
                       {'stage': 3, 'last': 1}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                C.convert(good, 'surf_test', **kwargs)
        # A stage recording that begins inside its zone needs the official time, as P757's.
        lead = binary(marks=[(2, 3, 3, ''), (6, 2, 4, '')])
        with self.assertRaises(ValueError): C.convert(lead, 'surf_test', stage=3)
        self.assertEqual(C.convert(lead, 'surf_test', stage=3, seconds=.06)[1]['stop'], 6)

    def test_last_stage_finish_is_the_official_time(self):
        last = [(0, 2, 9, ''), (2, 3, 9, '')]
        text, info = C.convert(binary(marks=last), 'surf_test', stage=9, last=True, seconds=.06)
        self.assertEqual((info['start'], info['stop'], info['timed_stop']), (2, 6, True))
        self.assertIn('leg 9\n', text)
        self.assertIn('ksfstop timed\n', text)
        self.assertEqual(text.splitlines()[-1], 'end 4 7 2 0')
        # A file that ends on the tick before its sub-tick finish keeps its last frame.
        self.assertEqual(C.convert(binary(marks=last), 'surf_test', stage=9, last=True,
                                   seconds=.105)[1]['stop'], 8)
        for seconds in (None, .15, math.nan, -1):
            with self.subTest(seconds=seconds), self.assertRaises(ValueError):
                C.convert(binary(marks=last), 'surf_test', stage=9, last=True, seconds=seconds)
        # The end zone, when bookmarked, is the finish; not a timed one.
        text, info = C.convert(binary(marks=last + [(6, 2, 99, '')]), 'surf_test', stage=9, last=True)
        self.assertEqual((info['stop'], info['timed_stop']), (6, False))
        self.assertNotIn('ksfstop', text)
        # Only the last stage may go unbookmarked.
        with self.assertRaises(ValueError):
            C.convert(binary(marks=last), 'surf_test', stage=9, seconds=.06)

    def test_owner_cannot_inject_header(self):
        text, _ = C.convert(binary(), 'surf_test', owner='Hi\nnonce bad\r"x"//foo')
        self.assertNotIn('\nnonce ', text)
        self.assertNotIn('"', text)
        self.assertNotIn('//', text)
        self.assertIn('owner Hi nonce bad', text)

    def test_cli_no_overwrite_or_output_on_rejection(self):
        with tempfile.TemporaryDirectory() as d:
            source, dest = Path(d, 'input.rec'), Path(d, 'output.rec')
            source.write_bytes(binary())
            args = [sys.executable, str(Path(C.__file__)), str(source), '--map', 'surf_test',
                    '--style', 'FW', '--out', str(dest)]
            r = subprocess.run(args, capture_output=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            first = dest.read_bytes()
            self.assertNotEqual(subprocess.run(args, capture_output=True).returncode, 0)
            self.assertEqual(dest.read_bytes(), first)
            dest.unlink(); source.write_bytes(b'<html>')
            self.assertNotEqual(subprocess.run(args, capture_output=True).returncode, 0)
            self.assertFalse(dest.exists())


if __name__ == '__main__':
    unittest.main()
