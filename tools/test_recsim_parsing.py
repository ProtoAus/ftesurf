"""Move-stream parser: malformed files abstain, valid conversions stay unchanged."""
import argparse
import contextlib
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


class Parsing(Fixture):
    def test_valid_control(self):
        r = rs.parse_rec(str(self.a))
        self.assertEqual([len(r.mt), len(r.moves), len(r.btns)], [80]*3)
        verdict, detail = rs.compare_paths(str(self.a), str(self.b))
        self.assertEqual((verdict, detail['match'], detail['compared']), ('compared', 1.0, 80))

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
