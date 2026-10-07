"""Per-call I/O outcomes do not become successfully-read no-input outcomes."""
import argparse
import contextlib
import io
from unittest import mock
import unittest
from test_recsim_parsing import Fixture, recording, rs


class Unreadable(Fixture):
    def test_missing_denied_and_subsequent_controls(self):
        self.assertEqual(rs.compare_paths(str(self.root/'missing.rec'), str(self.b))[0], 'unreadable')
        with mock.patch('builtins.open', side_effect=PermissionError('synthetic denial')):
            self.assertEqual(rs.compare_paths(str(self.a), str(self.b))[0], 'unreadable')
            self.assertIsNone(rs.parse_rec(str(self.a)))
        verdict, detail = rs.compare_paths(str(self.a), str(self.b))
        self.assertEqual((verdict, detail['match'], detail['compared']), ('compared', 1.0, 80))
        self.a.write_text('FTESURF-REC 9\nbegin\n')
        self.assertEqual(rs.compare_paths(str(self.a), str(self.b))[0], 'no sample rows')

    def test_pair_cli_distinguishes_unreadable_and_empty(self):
        args = argparse.Namespace(a=str(self.a), b=str(self.b), min_len=50)
        output = io.StringIO()
        with mock.patch('builtins.open', side_effect=PermissionError('synthetic denial')):
            with contextlib.redirect_stdout(output):
                self.assertEqual(rs.cmd_one(args), 1)
        self.assertIn('not compared: unreadable recording', output.getvalue())
        self.assertNotIn('no `in` rows', output.getvalue())
        self.assertNotIn('match   ', output.getvalue())
        self.a.write_text('begin\n')
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(rs.cmd_one(args), 1)
        self.assertEqual(output.getvalue(), 'one of those has no `in` rows\n')

    def test_mid_read_unavailable_even_after_valid_rows(self):
        class BrokenRead(io.StringIO):
            def __iter__(self):
                yield from recording().splitlines(True)
                raise OSError('synthetic mid-read failure')
        with mock.patch('builtins.open', side_effect=lambda *a, **kw: BrokenRead()):
            self.assertEqual(rs.compare_paths(str(self.a), str(self.b))[0], 'unreadable')
            self.assertIsNone(rs.parse_rec(str(self.a)))

    def test_census_does_not_count_unavailable_as_samples_only(self):
        args = argparse.Namespace(root=str(self.root), limit=0)
        for _ in range(2):
            output = io.StringIO()
            with mock.patch('builtins.open', side_effect=PermissionError('synthetic denial')):
                with contextlib.redirect_stdout(output):
                    rs.cmd_census(args)
            self.assertIn('without (samples only): 0', output.getvalue())
            self.assertIn('SKIPPED unreadable: 2', output.getvalue())
        self.a.write_text('begin\n')
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            rs.cmd_census(args)
        self.assertIn('with `in` rows: 1   without (samples only): 1', output.getvalue())
        self.assertNotIn('SKIPPED', output.getvalue())


if __name__ == '__main__':
    unittest.main()
