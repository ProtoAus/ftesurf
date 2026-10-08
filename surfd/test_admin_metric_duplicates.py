#!/usr/bin/env python3
"""Ambiguous stored metrics abstain in actual authenticated historical projection."""
import json
import unittest
from unittest import mock

import simcheck
import test_admin_metric_bounds as bounds


class MetricDuplicates(bounds.MetricBounds):
    def test_duplicate_keys_at_every_level_are_unavailable_not_last_value(self):
        journals = (
            '{"version":2,"version":1,"metrics":{}}',
            '{"version":1,"metrics":{"identity_judged":80,"identity_judged":0}}',
            '{"version":1,"metrics":{"identity_yaw_exclusions":{"seed":2,"seed":0}}}',
            '{"version":1,"metrics":{"join_checked":80},"metrics":{}}',
            '{"version":1,"metrics":{"identity_judged":80,"identity_\\u006audged":0}}',
        )
        counts = (
            '{"version":2,"version":1,"state":"measured","records":80,"disagree":0}',
            '{"version":1,"state":"measured","state":"no_records","records":0}',
            '{"version":1,"state":"measured","records":0,"records":80,"disagree":0}',
            '{"version":1,"state":"measured","records":80,"disagree":1,"disagree":0}',
            '{"version":1,"state":"measured","records":80,"disagree":0,"disagr\\u0065e":0}',
        )
        for index, (j, c) in enumerate(zip(journals, counts)):
            for raw_j, raw_c in ((j, c), (j.encode(), c.encode())):
                with self.subTest(index=index, blob=isinstance(raw_j, bytes)):
                    self.put(raw_j, raw_c)
                    before = self.stored()
                    with mock.patch.object(simcheck, '_recsim', side_effect=AssertionError('no source reader in historical review')):
                        out, seen = self.fetch()
                    for field, value in (('journal', out['receipt']['journal_metrics']),
                                         ('counts', out['verdicts'][0]['counts_metrics'])):
                        with self.subTest(projection=field):
                            self.assertIsNone(value)
                    self.assertEqual(out['receipt']['verdict'], 'VALID')
                    self.assertEqual(out['verdicts'][0]['verdict'], 'PASS')
                    self.assertEqual(self.stored(), before)
        self.assertEqual(self.m.app.test_client().get(self.route).status_code, 401)

    def test_unique_measured_zero_empty_and_no_records_keep_meaning(self):
        for journal, counts in (
                ({'version': 1, 'metrics': {}}, {'version': 1, 'state': 'no_records', 'records': 0}),
                ({'version': 1, 'metrics': {'identity_judged': 80, 'identity_mouse_frames': 0,
                                          'identity_yaw_exclusions': {'seed': 0},
                                          'join_declared_transform_profile': False}},
                 {'version': 1, 'state': 'measured', 'records': 80, 'disagree': 0})):
            for blob in (False, True):
                j, c = json.dumps(journal), json.dumps(counts)
                self.put(j.encode() if blob else j, c.encode() if blob else c)
                before = self.stored()
                out, seen = self.fetch()
                self.assertEqual(out['receipt']['journal_metrics'], journal)
                self.assertEqual(out['verdicts'][0]['counts_metrics'], counts)
                self.assertEqual(self.stored(), before)


if __name__ == '__main__':
    unittest.main()
