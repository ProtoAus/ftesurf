"""Move-stream parser: malformed files abstain, valid conversions stay unchanged."""
import argparse
import contextlib
import hashlib
import importlib.util
import io
import os
from pathlib import Path
import tempfile
import unittest

SOURCE = Path(os.environ.get('RECSIM_SOURCE', Path(__file__).parent / 'census/recsim.py'))
spec = importlib.util.spec_from_file_location('recsim_under_test', SOURCE)
rs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rs)


def recording(n=80, other=False):
    rows = ['FTESURF-REC 9', 'map synthetic', 'tickrate 100', 'begin']
    rows += ['in %d %d 0 %d %d 0 0 0 0 %d' %
             (i, i, i + (1000 if other else 0), i % 7, i % 3) for i in range(n)]
    return '\n'.join(rows) + '\n'


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='recsim-parser-')
        self.root = Path(self.tmp.name)
        self.addCleanup(self.cleanup)
        self.a = self.root / 'a.rec'; self.b = self.root / 'b.rec'
        self.a.write_text(recording()); self.b.write_text(recording())

    def cleanup(self):
        self.tmp.cleanup()
        self.assertFalse(self.root.exists())

    def large_pair(self):
        self.a = self.root / 'data/runs/synthetic/main/a.rec'
        self.a.parent.mkdir(parents=True)
        self.b = self.a.with_name('b.rec')
        padding = b'# ' + b'x' * (1 << 20) + b'\n'
        raw = recording().encode('ascii').replace(b'begin\n', b'begin\n' + padding, 1)
        self.a.write_bytes(raw); self.b.write_bytes(raw)
        return raw

    def pairs_output(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(rs.cmd_pairs(argparse.Namespace(
                root=str(self.a.parent), max=4, per_map=4, min_len=50)), 0)
        return output.getvalue()


class Parsing(Fixture):
    def test_valid_control(self):
        r = rs.parse_rec(str(self.a))
        self.assertEqual([len(r.mt), len(r.moves), len(r.btns)], [80]*3)
        verdict, detail = rs.compare_paths(str(self.a), str(self.b))
        self.assertEqual((verdict, detail['match'], detail['compared']), ('compared', 1.0, 80))

    def test_pairs_large_identical_copy_is_still_deduplicated(self):
        raw = self.large_pair()
        self.assertGreater(len(raw), 1 << 20)
        for path in (self.a, self.b):
            self.assertEqual(len(rs.parse_rec(str(path)).moves), 80)
        verdict, detail = rs.compare_paths(str(self.a), str(self.b),
                                            max_bytes=len(raw), max_moves=80)
        self.assertEqual((verdict, detail['matched'], detail['compared']), ('compared', 80, 80))
        self.assertEqual(detail['sources']['a'],
                         {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)})
        self.assertEqual(detail['sources']['a'], detail['sources']['b'])
        output = self.pairs_output()
        self.assertIn('byte-identical duplicates skipped: 1', output)
        self.assertIn('fixtures excluded by name): 1 in 1 map/leg groups', output)
        self.assertIn('NEGATIVE pairs (different runs, same map+leg): 0', output)
        self.assertIn('POSITIVE pairs (same recording, shifted tick epoch): 1', output)

    def test_pairs_equal_size_shared_prefix_does_not_hide_a_different_tail(self):
        raw = self.large_pair()
        row = b'in 79 79 0 79 2 0 0 0 0 1\n'
        self.assertEqual(raw.count(row), 1)
        other = raw.replace(row, row.replace(b' 79 2 ', b' 78 2 '))
        changes = [i for i, (a, b) in enumerate(zip(raw, other)) if a != b]
        self.assertEqual(len(changes), 1)
        self.assertGreaterEqual(changes[0], 1 << 20)
        self.assertEqual(len(raw), len(other))
        self.assertEqual(raw[:1 << 20], other[:1 << 20])
        self.assertNotEqual(hashlib.sha256(raw).digest(), hashlib.sha256(other).digest())
        self.b.write_bytes(other)
        for path in (self.a, self.b):
            self.assertEqual(len(rs.parse_rec(str(path)).moves), 80)
        verdict, detail = rs.compare_paths(str(self.a), str(self.b),
                                            max_bytes=len(raw), max_moves=80)
        self.assertEqual((verdict, detail['matched'], detail['compared']), ('compared', 79, 80))
        for label, data in (('a', raw), ('b', other)):
            self.assertEqual(detail['sources'][label],
                             {'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)})
        output = self.pairs_output()
        if 'byte-identical duplicates skipped: 1' in output:
            self.assertIn('fixtures excluded by name): 1 in 1 map/leg groups', output)
            self.assertIn('NEGATIVE pairs (different runs, same map+leg): 0', output)
            self.assertIn('POSITIVE pairs (same recording, shifted tick epoch): 1', output)
        self.assertIn('byte-identical duplicates skipped: 0', output,
                      'A_SHARED_PREFIX_IS_NOT_WHOLE_FILE_IDENTITY')
        self.assertIn('fixtures excluded by name): 2 in 1 map/leg groups', output)
        self.assertIn('NEGATIVE pairs (different runs, same map+leg): 1', output)
        self.assertIn('POSITIVE pairs (same recording, shifted tick epoch): 2', output)
        self.assertEqual((self.a.read_bytes(), self.b.read_bytes()), (raw, other))

    def test_ordinary_keyword_malformed_payload_is_not_dropped(self):
        verdict, detail = rs.compare_paths(str(self.a), str(self.b), max_bytes=8192, max_moves=100)
        self.assertEqual((verdict, detail['matched'], detail['compared'], detail['match']),
                         ('compared', 80, 80, 1.0))
        original = recording().splitlines()
        for payload in ('in 0', 'in', 'in\tbad'):
            with self.subTest(payload=repr(payload)):
                rows = original.copy(); rows[-1] = payload
                self.assertEqual([i for i, pair in enumerate(zip(original, rows)) if pair[0] != pair[1]], [83])
                self.a.write_text('\n'.join(rows) + '\n', encoding='ascii')
                buffers = [p.read_bytes() for p in (self.a, self.b)]
                verdict, detail = rs.compare_paths(str(self.a), str(self.b), max_bytes=8192, max_moves=100)
                if verdict == 'compared':
                    # Acting legacy control: a known bad row must not become a measured prefix.
                    self.assertEqual((detail['matched'], detail['compared'], detail['match']), (79, 79, 1.0))
                    self.assertEqual((detail['moves_a'], detail['moves_b']), (79, 80))
                    self.assertEqual(detail['sources']['version'], 1)
                    for label, path, raw in zip(('a', 'b'), (self.a, self.b), buffers):
                        self.assertEqual(detail['sources'][label],
                                         {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)})
                        self.assertEqual(path.read_bytes(), raw)
                self.assertEqual(verdict, 'malformed input', 'KNOWN_INPUT_ROW_MUST_NOT_BECOME_MEASURED_PREFIX')
                self.assertIsInstance(detail, str)
                self.assertIsNone(rs.parse_rec(str(self.a)))

    def test_ordinary_keyword_whitespace_and_unknown_records_keep_their_meaning(self):
        original = recording().splitlines()
        variants = []
        for prefix in ('in ', 'in\t', ' \tin\t'):
            rows = original.copy(); rows[-1] = prefix + original[-1][3:]
            variants.append('\n'.join(rows) + '\n')
        for keyword in ('input', 'inert', 'in-extra'):
            variants.append(recording() + keyword + ' unknown payload\n')
        for text in variants:
            with self.subTest(last_row=text.splitlines()[-1]):
                self.a.write_text(text, encoding='ascii')
                r = rs.parse_rec(str(self.a))
                self.assertEqual([len(r.mt), len(r.moves), len(r.btns)], [80]*3)
                self.assertEqual((r.mt[-1], r.moves[-1], r.btns[-1]), (79, (79, 2, 0), 1))
                buffers = [p.read_bytes() for p in (self.a, self.b)]
                verdict, detail = rs.compare_paths(str(self.a), str(self.b), max_bytes=8192, max_moves=100)
                self.assertEqual((verdict, detail['offset'], detail['matched'], detail['compared'], detail['match']),
                                 ('compared', 0, 80, 80, 1.0))
                self.assertEqual((detail['prefix'], detail['cover']), (80, 1.0))
                self.assertEqual(detail['sources']['version'], 1)
                for label, path, raw in zip(('a', 'b'), (self.a, self.b), buffers):
                    self.assertEqual(detail['sources'][label],
                                     {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)})
                    self.assertEqual(path.read_bytes(), raw)

    def test_map_keyword_missing_payload_abstains_instead_of_path_fallback(self):
        self.a = self.root / 'data/runs/path_map/main/a.rec'
        self.a.parent.mkdir(parents=True)
        original = recording().encode('ascii')
        for header in (b'map', b'map\t', b' \tmap\t '):
            with self.subTest(header=header):
                raw = original.replace(b'map synthetic', header)
                self.assertEqual(raw.splitlines()[2:], original.splitlines()[2:])
                self.a.write_bytes(raw)
                verdict, detail = rs.compare_paths(str(self.a), str(self.b), max_bytes=8192, max_moves=100)
                if verdict == 'compared':
                    # Acting counterfactual: all 80 moves and captured bytes survived.
                    self.assertEqual((detail['matched'], detail['compared'], detail['prefix'], detail['cover']),
                                     (80, 80, 80, 1.0))
                    self.assertEqual(detail['sources']['a'],
                                     {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)})
                    self.assertEqual(rs.derive_leg(str(self.a), rs.parse_rec(str(self.a))), ('path_map', 'main'))
                self.assertEqual(self.a.read_bytes(), raw)
                self.assertEqual((verdict, detail), ('malformed input', 'malformed required move-stream input'))
                self.assertIsNone(rs.parse_rec(str(self.a)))
                with self.assertRaises(rs.MalformedRec):
                    rs.parse_rec(str(self.a), strict=True)

    def test_map_keyword_whitespace_identity_and_absent_unknown_controls(self):
        self.a = self.root / 'data/runs/path_map/main/a.rec'
        self.a.parent.mkdir(parents=True)
        self.b = self.a.with_name('b.rec')
        original = recording().encode('ascii')
        cases = [(header, ('synthetic', '')) for header in
                 (b'map synthetic', b'map\tsynthetic', b' \tmap\t synthetic')]
        cases += [(header, ('path_map', 'main')) for header in
                  (None, b'mapfoo synthetic', b'mapper synthetic')]
        for header, identity in cases:
            with self.subTest(header=header):
                raw = original.replace(b'map synthetic\n', b'' if header is None else header + b'\n')
                self.a.write_bytes(raw); self.b.write_bytes(raw)
                verdict, detail = rs.compare_paths(str(self.a), str(self.b), max_bytes=8192, max_moves=100)
                self.assertEqual((verdict, detail['matched'], detail['compared'], detail['prefix'], detail['cover']),
                                 ('compared', 80, 80, 80, 1.0))
                self.assertEqual((detail['moves_a'], detail['moves_b'], detail['sources']['version']), (80, 80, 1))
                for label, path in (('a', self.a), ('b', self.b)):
                    self.assertEqual(detail['sources'][label],
                                     {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)})
                    self.assertEqual(path.read_bytes(), raw)
                r = rs.parse_rec(str(self.a))
                self.assertEqual(rs.derive_leg(str(self.a), r), identity)
                self.assertEqual(r.map, 'synthetic' if identity[0] == 'synthetic' else '')
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    self.assertEqual(rs.cmd_census(argparse.Namespace(root=str(self.a.parent), limit=0)), 0)
                self.assertIn('with `in` rows: 2', output.getvalue())
                self.assertIn('map/leg groups: 1, of which 1 hold >1 comparable run', output.getvalue())
                self.assertIn('comparable PAIRS available: 1', output.getvalue())
                self.assertIn(identity[0], output.getvalue())

    def test_release_keyword_whitespace_and_malformed_payload_are_not_dropped(self):
        base = recording().replace('FTESURF-REC 9', 'FTESURF-REC 11')
        original = base.splitlines()[44]
        for prefix in ('fzin ', 'fzin\t', ' \tfzin\t'):
            with self.subTest(prefix=repr(prefix)):
                text = base.replace(original, prefix + original[3:])
                self.a.write_text(text)
                r = rs.parse_rec(str(self.a))
                self.assertEqual([len(r.mt), len(r.moves), len(r.btns)], [80]*3)
                self.assertEqual(r.moves[40], (40, 5, 0))
                verdict, detail = rs.compare_paths(str(self.a), str(self.b))
                self.assertEqual((verdict, detail['match'], detail['compared']), ('compared', 1.0, 80))
        for row in ('fzin', ' \tfzin\t', 'fzin\tbad'):
            self.a.write_text(base.replace(original, row))
            self.assertIsNone(rs.parse_rec(str(self.a)))
            self.assertEqual(rs.compare_paths(str(self.a), str(self.b))[0], 'malformed input')
        self.a.write_text(base.replace(original, 'fzin\t' + original[3:]).replace('FTESURF-REC 11', 'FTESURF-REC 9'))
        self.assertIsNone(rs.parse_rec(str(self.a)))

    def test_sv_timer_viewclock_format_is_explicitly_unsupported(self):
        for version in (12, 13, 14, 16):
            with self.subTest(version=version):
                self.a.write_text(recording().replace('FTESURF-REC 9',
                                                      'FTESURF-REC %d' % version))
                self.assertIsNone(rs.parse_rec(str(self.a)))
                verdict, detail = rs.compare_paths(str(self.a), str(self.b),
                                                    max_bytes=8192, max_moves=100)
                self.assertEqual(verdict, 'unmodelled recording')
                self.assertEqual(detail, 'recording clock model unavailable')
                with self.assertRaises(rs.UnmodelledRec):
                    rs.parse_rec(str(self.a), strict=True)
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    self.assertEqual(rs.cmd_one(argparse.Namespace(a=str(self.a), b=str(self.b), min_len=50)), 1)
                self.assertIn('not compared: recording clock model unavailable', output.getvalue())
                self.assertNotIn('match   ', output.getvalue())
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    self.assertEqual(rs.cmd_census(argparse.Namespace(root=str(self.root), limit=0)), 0)
                self.assertIn('SKIPPED unmodelled: 1', output.getvalue())
                self.assertNotIn('SKIPPED malformed', output.getvalue())
                self.assertIn('with `in` rows: 1', output.getvalue())

    def test_supported_native_comparison_and_bad_witness_keep_their_meaning(self):
        from test_held_readers import recording as native_recording
        for version in (13, 15):
            with self.subTest(version=version):
                data = native_recording(version=version)
                self.a.write_bytes(data); self.b.write_bytes(data)
                verdict, detail = rs.compare_paths(str(self.a), str(self.b), min_len=1,
                                                    max_bytes=65536, max_moves=100)
                self.assertEqual((verdict, detail['match'], detail['compared']), ('compared', 1.0, 3))
                self.assertEqual(detail['sources']['version'], 1)
                self.assertEqual(detail['sources']['a']['bytes'], len(data))
                self.assertEqual(detail['sources']['a'], detail['sources']['b'])
                self.assertIn(b'hseal ', data)
                broken = data.replace(b'hseal ', b'hbroken ', 1)
                self.assertNotEqual(broken, data)
                self.a.write_bytes(broken)
                verdict, detail = rs.compare_paths(str(self.a), str(self.b), min_len=1,
                                                    max_bytes=65536, max_moves=100)
                self.assertEqual((verdict, detail), ('malformed input', 'malformed required move-stream input'))

    def test_each_malformed_required_row_abstains(self):
        for position in (0, 40, 79):
            for column in (2, 4, 5, 6, 10):
                for token in ('bad', 'nan', 'inf', '-inf'):
                    with self.subTest(position=position, column=column, token=token):
                        rows = recording().splitlines(); fields = rows[4+position].split()
                        fields[column] = token; rows[4+position] = ' '.join(fields)
                        self.a.write_text('\n'.join(rows)+'\n')
                        verdict, detail = rs.compare_paths(str(self.a), str(self.b))
                        self.assertEqual(verdict, 'malformed input')
                        self.assertIsInstance(detail, str)
                        self.assertIsNone(rs.parse_rec(str(self.a)))

    def test_missing_button_and_malformed_map(self):
        for text in (recording().replace('in 0 0 0 0 0 0 0 0 0 0', 'in 0 0 0 0 0 0 0 0 0'),
                     recording().replace('in 0 0 0 0 0 0 0 0 0 0', 'in 0'),
                     recording().replace('map synthetic', 'map ')):
            self.a.write_text(text)
            self.assertEqual(rs.compare_paths(str(self.a), str(self.b))[0], 'malformed input')

    def test_pair_cli_distinguishes_malformed(self):
        args = argparse.Namespace(a=str(self.a), b=str(self.b), min_len=50)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(rs.cmd_one(args), 0)
        self.assertIn('match   1.0000', output.getvalue())
        self.a.write_text(recording().replace('in 40 40 0', 'in 40 nan 0'))
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(rs.cmd_one(args), 1)
        self.assertIn('not compared: malformed required move-stream input', output.getvalue())
        self.assertNotIn('no `in` rows', output.getvalue())
        self.assertNotIn('match   ', output.getvalue())

    def test_fractional_numeric_semantics_preserved(self):
        self.a.write_text(recording().replace('in 0 0 0 0 0 0 0 0 0 0',
                                              'in 0 0.9 0 -2.9 3.9 4.9 0 0 0 1.9'))
        r = rs.parse_rec(str(self.a))
        self.assertEqual((r.mt[0], r.moves[0], r.btns[0]), (0, (-2, 3, 4), 1))


if __name__ == '__main__':
    unittest.main()
