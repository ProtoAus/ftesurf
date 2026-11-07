"""Actual zero agreement is measured; absent/torn opportunities are not."""
from unittest import mock
import hashlib
import unittest
from test_recsim_parsing import Fixture, recording, rs


class Opportunities(Fixture):
    def test_zero_agreement_has_denominator(self):
        self.b.write_text(recording(other=True))
        verdict, detail = rs.compare_paths(str(self.a), str(self.b))
        self.assertEqual(verdict, 'compared')
        self.assertEqual((detail['matched'], detail['match']), (0, 0.0))
        self.assertGreater(detail['compared'], 0)
        self.assertEqual((detail['offset'], detail['compared']), (-4, 76))

    def test_positive_ordering_and_ties_preserved(self):
        a = rs.parse_rec(str(self.a)); b = rs.parse_rec(str(self.b))
        self.assertEqual(rs.best_offset(a, b), (0, 80, 80, 80, 1.0))
        b.moves[40] = (999, 999, 0)
        self.assertEqual(rs.best_offset(a, b), (0, 79, 80, 40, 0.5))
        a.moves = b.moves = [(1, 2, 0)] * 80
        self.assertEqual(rs.best_offset(a, b, max_shift=0), (0, 80, 80, 80, 1.0))

    def test_prefix_starts_at_aligned_overlap_in_both_directions(self):
        verdict, exact = rs.compare_paths(str(self.a), str(self.b))
        self.assertEqual((verdict, exact['matched'], exact['compared'], exact['prefix'], exact['cover']),
                         ('compared', 80, 80, 80, 1.0))
        for mismatch, prefix, matched in ((None, 79, 79), (40, 40, 78)):
            rows = []
            i = 0
            for row in recording().splitlines():
                if row.startswith('in '):
                    fields = row.split()
                    fields[4] = str(999 if i == mismatch else i + 1)
                    fields[5], fields[10] = str((i + 1) % 7), str((i + 1) % 3)
                    row = ' '.join(fields)
                    i += 1
                rows.append(row)
            self.assertEqual(i, 80)
            self.b.write_text('\n'.join(rows) + '\n', encoding='ascii')
            measured = []
            for a, b, offset in ((self.b, self.a, 1), (self.a, self.b, -1)):
                buffers = [p.read_bytes() for p in (a, b)]
                verdict, detail = rs.compare_paths(str(a), str(b), max_bytes=8192, max_moves=100)
                self.assertEqual(verdict, 'compared')
                self.assertEqual((detail['offset'], detail['matched'], detail['compared']),
                                 (offset, matched, 79))
                self.assertEqual(detail['match'], matched / 79)
                self.assertEqual((detail['moves_a'], detail['moves_b']), (80, 80))
                self.assertEqual(detail['sources']['version'], 1)
                for label, path, raw in zip(('a', 'b'), (a, b), buffers):
                    self.assertEqual(detail['sources'][label],
                                     {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)})
                    self.assertEqual(path.read_bytes(), raw)
                measured.append(detail)
            for detail in measured:
                with self.subTest(mismatch=mismatch, offset=detail['offset']):
                    self.assertEqual((detail['prefix'], detail['cover']), (prefix, prefix / 80))

    def test_prefix_without_aligned_overlap_is_zero(self):
        a = rs.parse_rec(str(self.a)); b = rs.parse_rec(str(self.b))
        self.assertEqual((len(rs.stream(a)), len(rs.stream(b))), (80, 80))
        for offset in (-81, -80, 80, 81):
            with self.subTest(offset=offset):
                self.assertEqual(rs.prefix_len(a, b, offset), 0)

    def test_absent_and_torn_streams(self):
        empty = rs.Rec('empty')
        self.assertEqual(rs.best_offset(empty, empty), (0, 0, 0, 0, 0.0))
        a = rs.parse_rec(str(self.a)); a.btns.pop()
        with self.assertRaises(ValueError):
            rs.stream(a)
        self.a.write_text('begin\n')
        self.assertEqual(rs.compare_paths(str(self.a), str(self.b))[0], 'no sample rows')

    def test_zero_opportunity_boundary_abstains(self):
        with mock.patch.object(rs, 'best_offset', return_value=(0, 0, 0, 0, 0.0)):
            self.assertEqual(rs.compare_paths(str(self.a), str(self.b))[0], 'no comparison opportunities')


if __name__ == '__main__':
    unittest.main()
