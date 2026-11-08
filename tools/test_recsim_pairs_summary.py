"""Exercise real cmd_pairs summaries with synthetic metrics, not calibration."""
import argparse
import contextlib
import io
import re
from types import SimpleNamespace
import unittest
from unittest import mock

from test_recsim_parsing import rs


class PairsSummary(unittest.TestCase):
    def summary(self, fractions):
        count = len(fractions)
        size = 0
        while size * (size - 1) // 2 < count:
            size += 1
        paths = ['data/runs/synthetic/main/r%03d.rec' % i for i in range(size)]
        remaining = iter(fractions)
        negative_calls = []
        positive_calls = []

        def parse(path, **kwargs):
            return SimpleNamespace(moves=[(450, 0, 0)] * 200, mt=list(range(200)))

        def offset(a, b, **kwargs):
            if b.mt[0] - a.mt[0] == 12345:
                positive_calls.append(True)
                return 0, 100, 100, 80, 0.125
            matched, compared = next(remaining)
            negative_calls.append(True)
            return 0, matched, compared, 80, 0.125

        output = io.StringIO()
        with mock.patch.object(rs, 'collect', return_value=paths) as collect, \
                mock.patch.object(rs, 'parse_rec', side_effect=parse) as parser, \
                mock.patch.object(rs, 'derive_leg', return_value=('synthetic', 'main')), \
                mock.patch.object(rs, 'best_offset', side_effect=offset), \
                mock.patch.object(rs, 'open', create=True,
                                  side_effect=lambda path, mode: io.BytesIO(path.encode('ascii'))) as opened, \
                mock.patch.object(rs.os.path, 'getsize', return_value=42), \
                contextlib.redirect_stdout(output):
            self.assertEqual(rs.cmd_pairs(argparse.Namespace(
                root='synthetic-summary-only', max=count, per_map=count, min_len=50)), 0)
        collect.assert_called_once_with('synthetic-summary-only')
        self.assertEqual(parser.call_count, size)
        self.assertEqual(opened.call_count, size)
        self.assertEqual(len(negative_calls), count)
        self.assertEqual(len(positive_calls), min(size, count))
        text = output.getvalue()
        self.assertIn('POSITIVE pairs (same recording, shifted tick epoch): %d' % min(size, count), text)
        if count:
            self.assertIn('NEGATIVE pairs (different runs, same map+leg): %d' % count, text)
            self.assertIn('  cover (exact contiguous prefix / the LONGER run) -- diagnostic:\n'
                          '      max 0.1250  median 0.1250\n', text)
        return text

    def p99(self, fractions):
        text = self.summary(fractions)
        found = re.search(r'^      max [0-9.]+  p99 ([0-9.]+)  median ', text, re.M)
        self.assertIsNotNone(found, text)
        return found.group(1)

    def test_hundred_distinct_upper_tail(self):
        self.assertEqual(self.p99([(i, 100) for i in range(1, 101)]), '0.9900')

    def test_nonintegral_nearest_rank(self):
        self.assertEqual(self.p99([(i, 101) for i in range(1, 102)]), '0.9901')

    def test_two_samples_not_below_existing_median(self):
        self.assertEqual(self.p99([(25, 100), (90, 100)]), '0.9000')

    def test_single_sample_control(self):
        self.assertEqual(self.p99([(37, 100)]), '0.3700')

    def test_detail_reports_acquired_compared_not_source_length(self):
        text = self.summary([(37, 100)])
        lines = [line for line in text.splitlines() if line.startswith('    match ')]
        self.assertEqual(len(lines), 1, text)
        self.assertEqual(lines[0].split()[:8],
                         ['match', '0.3700', 'cover', '0.1250', 'prefix', '80', 'compared', '100'])

    def test_detail_full_length_opportunity_control(self):
        text = self.summary([(74, 200)])
        lines = [line for line in text.splitlines() if line.startswith('    match ')]
        self.assertEqual(len(lines), 1, text)
        self.assertEqual(lines[0].split()[:8],
                         ['match', '0.3700', 'cover', '0.1250', 'prefix', '80', 'compared', '200'])

    def test_measured_zero_control(self):
        self.assertEqual(self.p99([(0, 100)] * 4), '0.0000')

    def test_tied_control(self):
        self.assertEqual(self.p99([(42, 100)] * 7), '0.4200')

    def test_no_pairs_stays_unavailable(self):
        text = self.summary([])
        self.assertIn('NOTHING COMPARABLE', text)
        self.assertNotIn('  MATCH (agreement over compared rows)', text)


if __name__ == '__main__':
    unittest.main()
