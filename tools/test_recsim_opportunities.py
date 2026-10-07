"""Actual zero agreement is measured; absent/torn opportunities are not."""
from unittest import mock
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
