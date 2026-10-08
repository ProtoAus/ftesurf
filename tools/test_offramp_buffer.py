#!/usr/bin/env python3
"""Synthetic structural tests plus optional ACTED capture counterfactual controls."""
import argparse
import hashlib
import json
import lzma
from pathlib import Path
import struct
import tempfile
import unittest

from offramp_buffer import compare, grade
from offramp_geometry import analyse, candidates, gap, load_brushes


def fixture():
    head = ('map pin   file abc123  world abc123  -- MATCH\n'
            'v9 state  pin 70/70 names, seed exact, 0 pm, 1 pe, 0 portal -- EXACT REPLAY\n'
            'seed      0 0 0\nARM 4  exact: 13 of 13 packets reproduce\n')
    rows = ['OFFRAMPBUF_BEGIN 1 32768']
    hits = []
    for i in range(13):
        contact = i < 6 or i >= 9
        rows.append('OFFRAMPBUF_TICK ' + ' '.join(map(str,
                    [i, i, i, i+1, .015, int(contact), 0, i, 0, 0, 100, 0, 0] +
                    ([.8, 0, .6] if contact else [0, 0, 0]))))
        if contact:
            hits.append('OFFRAMPBUF_CONTACT ' + ' '.join(map(str,
                        [len(hits), i, 0, 0, .5, 123, .8, 0, .6, i, 0, 0, i+1, 0, 0,
                         -16, -16, 0, 16, 16, 62, 0, 0, 0])))
    return head + '\n'.join(rows + hits + [f'OFFRAMPBUF_END 13 {len(hits)} 0', 'OFFRAMPBUF_COMPLETE']) + '\n'


def change(text, tag, index, value, pred=lambda r: True):
    lines = text.splitlines()
    for i, line in enumerate(lines):
        token = f'OFFRAMPBUF_{tag} '
        if token not in line:
            continue
        prefix, tail = line.split(token, 1)
        row = tail.split()
        if pred(row):
            row[index] = str(value)
            lines[i] = prefix + token + ' '.join(row)
            return '\n'.join(lines) + '\n'
    raise AssertionError('Counterfactual did not ACT')


def drop(text, tag):
    return '\n'.join(l for l in text.splitlines() if f'OFFRAMPBUF_{tag}' not in l) + '\n'


def controls(text):
    return [
        ('missing-begin', drop(text, 'BEGIN')),
        ('missing-ticks', drop(text, 'TICK')),
        ('missing-contacts', drop(text, 'CONTACT')),
        ('missing-end', drop(text, 'END')),
        ('missing-completion', drop(text, 'COMPLETE')),
        ('duplicate-tick', text + next(l for l in text.splitlines() if 'OFFRAMPBUF_TICK' in l) + '\n'),
        ('ordinal-gap', change(text, 'TICK', 0, 123456)),
        ('negative-row', change(text, 'TICK', 1, -1)),
        ('invalid-native-clock', change(text, 'TICK', 3, 123456)),
        ('invalid-tickrate', change(text, 'TICK', 4, -1)),
        ('raw-contact-fake', change(text, 'TICK', 5, 0, lambda r: r[5] == '1')),
        ('invalid-ground', change(text, 'TICK', 6, 2)),
        ('nonfinite-body', change(text, 'TICK', 7, 'nan')),
        ('wrong-tick-normal', change(text, 'TICK', 13, 99, lambda r: r[5] == '1')),
        ('contact-to-wrong-tick', change(text, 'CONTACT', 1, -1)),
        ('contact-bump-fake', change(text, 'CONTACT', 2, 999)),
        ('contact-physent-fake', change(text, 'CONTACT', 3, -1)),
        ('contact-fraction-fake', change(text, 'CONTACT', 4, 1)),
        ('nonfinite-plane-dist', change(text, 'CONTACT', 5, 'inf')),
        ('not-ramp-plane', change(text, 'CONTACT', 8, 1)),
        ('invalid-hull', change(text, 'CONTACT', 15, 99999)),
        ('recovery-flag-fake', change(text, 'CONTACT', 21, 2)),
        ('solid-state-fake', change(text, 'CONTACT', 22, 2)),
        ('unsupported-version', change(text, 'BEGIN', 0, 2)),
        ('overflow', change(text, 'END', 2, 1)),
        ('end-count-fake', change(text, 'END', 0, 1)),
        ('unknown-trace', text + 'OFFRAMPBUF_MYSTERY 1\n'),
        ('malformed-trace', text + 'OFFRAMPBUF_TICK 1\n'),
        ('runtime-fault', text + 'QC VM error\n'),
        ('wrong-map', text.replace('-- MATCH', '-- MISMATCH')),
        ('incomplete-state', text.replace('EXACT REPLAY', 'INEXACT')),
        ('non-exact-arm', text.replace('packets reproduce', 'packets differ')),
    ]


class Tests(unittest.TestCase):
    def test_positive(self):
        result = grade(fixture())
        self.assertEqual(result['ticks'], 13)
        self.assertEqual(result['losses'][0]['gap_ticks'], 3)
        self.assertEqual(result['physical_exit_acceptance'], 'NOT_TESTED')

    def test_counterfactuals(self):
        for name, text in controls(fixture()):
            with self.subTest(name=name), self.assertRaises(AssertionError):
                grade(text)

    def test_comparison(self):
        text = fixture()
        clean = '\n'.join(l for l in text.splitlines() if 'OFFRAMPBUF_' not in l) + '\nOFFRAMPBUF_COMPLETE\n'
        self.assertEqual(compare(clean, clean, text, text)['repeat_trace_equality'], 'PASS')
        for changed in (text + 'OFFRAMPBUF_MYSTERY 1\n', change(text, 'TICK', 7, 999)):
            with self.assertRaises(AssertionError):
                compare(clean, clean, text, changed)
        with self.assertRaises(AssertionError):
            compare(clean.replace('70/70', '69/70'), clean, text, text)
        with self.assertRaises(AssertionError):
            compare(clean, text, text, text)


class GeometryTests(unittest.TestCase):
    def setUp(self):
        self.planes = [(.8, 0, .6, 0), (0, 0, -1, 5), (1, 0, 0, 1), (-1, 0, 0, 1),
                       (0, 1, 0, 1), (0, -1, 0, 1)]
        self.brushes = [{'index': 0, 'contents': 1, 'planes': list(range(6))}]
        self.by_plane = {i: [0] for i in range(6)}
        self.loss = {'previous_position': [0, 0, 0], 'loss_position': [2, 0, -3],
                     'previous_trace': {'physent_index': 0, 'recovery_plane': False,
                                        'normal': [.8, 0, .6], 'plane_dist': 0,
                                        'hull_mins': [0, 0, 0], 'hull_maxs': [0, 0, 0]}}

    def test_halfspace_support(self):
        self.assertAlmostEqual(gap((0, 0, 1, 10), [0, 0, 10], [-16, -16, 0], [16, 16, 62]), 0)
        self.assertAlmostEqual(gap((0, 0, -1, -72), [0, 0, 10], [-16, -16, 0], [16, 16, 62]), 0)

    def test_numeric_edge_vs_face_support(self):
        result = candidates(self.loss, self.planes, self.brushes, self.by_plane)['candidates'][0]
        self.assertEqual(result['loss_outside_nonface_planes'], [2])
        self.assertAlmostEqual(result['face_support_gaps'][0]['loss'], -.2)
        self.loss['loss_position'] = [0, 0, 1]
        result = candidates(self.loss, self.planes, self.brushes, self.by_plane)['candidates'][0]
        self.assertEqual(result['loss_outside_nonface_planes'], [])
        self.assertAlmostEqual(result['face_support_gaps'][0]['loss'], .6)

    def test_no_winner_manufactured(self):
        self.brushes.append(dict(self.brushes[0], index=1))
        self.by_plane = {i: [0, 1] for i in range(6)}
        self.assertEqual(len(candidates(self.loss, self.planes, self.brushes, self.by_plane)['candidates']), 2)
        self.loss['previous_trace']['recovery_plane'] = True
        self.assertEqual(candidates(self.loss, self.planes, self.brushes, self.by_plane)['candidates'], [])
        self.loss['previous_trace']['recovery_plane'] = False
        self.loss['previous_position'] = [99, 0, 0]
        self.assertEqual(candidates(self.loss, self.planes, self.brushes, self.by_plane)['candidates'], [])

    def test_load_and_identity_refusal(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'fixture.bsp'
            node = bytearray(32)
            struct.pack_into('<2i', node, 4, -1, -1)
            leaf = bytearray(32)
            struct.pack_into('<2H', leaf, 24, 0, 1)
            packed_leaf = lzma.compress(bytes(leaf) + b'\0', format=lzma.FORMAT_RAW,
                                        filters=[{'id': lzma.FILTER_LZMA1, 'dict_size': 4096,
                                                  'lc': 3, 'lp': 0, 'pb': 2}])
            compressed_leaf = (b'LZMA' + struct.pack('<II', len(leaf), len(packed_leaf)) +
                               bytes([93]) + struct.pack('<I', 4096) + packed_leaf)
            lumps = {1: b''.join(struct.pack('<4fi', *p, 0) for p in self.planes),
                     5: bytes(node), 10: compressed_leaf, 14: bytes(48), 17: struct.pack('<H', 0),
                     18: struct.pack('<iii', 0, 6, 1) * 2,  # second brush belongs to an inline model
                     19: b''.join(struct.pack('<Hhhh', i, 0, -1, 0) for i in range(6))}
            header = bytearray(b'VBSP' + struct.pack('<i', 20))
            offset, payload = 1036, bytearray()
            for i in range(64):
                data = lumps.get(i, b'')
                header += struct.pack('<4i', offset, len(data), int(i == 10), 0)
                offset += len(data)
                payload += data
            path.write_bytes(header + struct.pack('<i', 0) + payload)
            planes, brushes, by_plane = load_brushes(path)
            self.assertEqual(len(planes), 6)
            self.assertEqual(brushes[:1], self.brushes)
            self.assertEqual(len(brushes), 2)
            self.assertEqual(by_plane, self.by_plane)  # inline brush 1 is excluded
            with self.assertRaisesRegex(AssertionError, 'differs from captured'):
                analyse(fixture(), path, 'not-the-captured-hash')
            result = analyse(fixture(), path, hashlib.sha256(path.read_bytes()).hexdigest())
            self.assertEqual(result['physical_exit_acceptance'], 'NOT_TESTED')
            path.write_bytes(b'not a map')
            with self.assertRaises(AssertionError):
                load_brushes(path)


def captured(arms_file):
    arms = json.loads(arms_file.read_text())
    texts = {name: Path(arm['log']).read_text(errors='replace') for name, arm in arms.items()}
    compare(*(texts[n] for n in ('clean', 'off', 'on', 'repeat')))
    print('PASS acted clean/OFF/ON/repeat replay controls')
    counter = controls(texts['on'])
    for name, text in counter:
        try:
            grade(text)
        except AssertionError:
            print(f'PASS {name}: refused')
        else:
            raise AssertionError(f'{name}: malformed capture accepted')
    # A valid-looking but different repeat must also be refused, not just
    # malformed rows. Control itself is asserted to parse and grade first.
    changed = change(texts['repeat'], 'TICK', 7, 99999)
    grade(changed)
    try:
        compare(texts['clean'], texts['off'], texts['on'], changed)
    except AssertionError:
        print('PASS changed-repeat-body: refused')
    else:
        raise AssertionError('Changed repeat body accepted')
    # Keep one valid numeric summary mutation in the clean arm.
    changed = texts['clean'].replace('pin 70/70 names', 'pin 69/70 names')
    assert changed != texts['clean'], 'Summary mutation did not ACT'
    try:
        compare(changed, texts['off'], texts['on'], texts['repeat'])
    except AssertionError:
        print('PASS changed-control-summary: refused')
    else:
        raise AssertionError('Changed control summary accepted')
    print(f'{len(counter)+3} acted controls, 0 failed')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--arms', type=Path)
    a = ap.parse_args()
    if a.arms:
        captured(a.arms)
    else:
        unittest.main(argv=['test_offramp_buffer.py'])
