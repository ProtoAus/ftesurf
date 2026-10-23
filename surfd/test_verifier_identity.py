#!/usr/bin/env python3
"""One unambiguous verifier result per path; real files/SQLite/badge SQL.

The runner's synthetic stdout is explicitly observed. This is output attribution,
not immutable engine-input binding, hardware provenance or historical revocation.
"""
import os
import unittest

import test_sweep as suite
import test_verifier_counts as controls
import test_verifier_sources as sources


class Identity(unittest.TestCase):
    setUp = controls.Counts.setUp
    cleanup_home = controls.Counts.cleanup_home
    source = sources.Sources.source
    state = sources.Sources.state

    def run_output(self, output, now=100):
        acted = []
        def runner(map_dir, paths):
            self.assertEqual(map_dir, 'bhop_eazy')
            acted.extend(paths)
            return suite.input_bound_stub(self.sw, paths, output(paths))
        result = self.sw.sweep(self.c, 20, runner=runner, now=now)
        self.assertTrue(acted)
        return result

    def assert_unavailable(self, rid):
        self.assertEqual(self.state(rid), ('ERROR', 0, 0, ''))
        row = self.c.execute('SELECT reason,ticks FROM verdicts WHERE replay_id=? '
                             'ORDER BY id DESC LIMIT 1', (rid,)).fetchone()
        self.assertEqual(tuple(row), ('ambiguous duplicate VERIFY lines', -1))

    def test_parser_never_selects_between_duplicate_results(self):
        for a in ('PASS ticks 662 rows 1', 'HOLD control', 'REFUSE control'):
            for b in ('PASS ticks 662 rows 1', 'HOLD control', 'REFUSE control'):
                with self.subTest(a=a, b=b):
                    lines = ['VERIFY a '+a, 'VERIFY a '+b, 'VERIFY b PASS ticks 662 rows 1']
                    got = self.sw.parse(lines)
                    self.assertEqual(got['a'], ('ERROR', 'ambiguous duplicate VERIFY lines', -1))
                    self.assertEqual(got['b'], ('PASS', 'ticks 662 rows 1', 662))
                    # A third line must not reset the ambiguity latch.
                    self.assertEqual(self.sw.parse(lines+['VERIFY a PASS ticks 662 rows 1'])['a'], got['a'])

    def test_duplicate_sections_have_no_counts_observation(self):
        diagnostic = '7 record(s): what the input ring delivered is what the view read'
        lines = controls.section('a', diagnostic)+controls.section('a', diagnostic)
        self.assertIsNone(self.sw.parse_counts(lines)['a'])
        lines += controls.section('b', diagnostic)
        self.assertIsNone(self.sw.parse_counts(lines)['a'])
        self.assertEqual(self.sw.parse_counts(lines)['b']['records'], 7)

    def test_duplicate_result_orders_are_retryable_not_player_findings(self):
        outcomes = (('PASS ticks 662 rows 1', 'HOLD control'),
                    ('HOLD control', 'PASS ticks 662 rows 1'),
                    ('REFUSE control', 'PASS ticks 662 rows 1'),
                    ('PASS ticks 662 rows 1', 'PASS ticks 662 rows 1'))
        for number, (a, b) in enumerate(outcomes, 662):
            with self.subTest(a=a, b=b):
                rid, _path, _data, _digest = self.source(number)
                def output(paths):
                    self.assertEqual(len(paths), 1)
                    return (controls.section(paths[0], '7 record(s): what the input ring delivered is what the view read', a)+
                            controls.section(paths[0], '8 record(s): what the input ring delivered is what the view read', b))
                self.assertEqual(self.run_output(output), {'ERROR': 1})
                self.assert_unavailable(rid)
                # Finish this synthetic row without changing the next arm's input.
                self.c.execute('UPDATE replays SET checked=1 WHERE id=?', (rid,))
                self.c.commit()

    def test_stable_companion_is_independent(self):
        bad, _path, _data, _digest = self.source()
        good, _path, _data, _digest = self.source(663)
        def output(paths):
            self.assertEqual(len(paths), 2)
            return (controls.section(paths[0], '7 record(s): what the input ring delivered is what the view read')+
                    controls.section(paths[1], '9 record(s): what the input ring delivered is what the view read', 'PASS ticks 662 rows 1')+
                    controls.section(paths[0], '8 record(s): what the input ring delivered is what the view read', 'PASS ticks 662 rows 1'))
        self.assertEqual(self.run_output(output), {'ERROR': 1, 'PASS': 1})
        self.assert_unavailable(bad)
        self.assertEqual(self.state(good)[:3], ('PASS', 1, 1))
        self.assertIn('"records":9', self.state(good)[3])

    def test_unambiguous_retry_recovers_without_refile(self):
        rid, _path, _data, digest = self.source()
        self.assertEqual(self.run_output(lambda p: ['VERIFY '+p[0]+' PASS ticks 662 rows 1']*2), {'ERROR': 1})
        self.assert_unavailable(rid)
        self.assertEqual(self.run_output(lambda p: ['VERIFY '+p[0]+' PASS ticks 662 rows 1'], now=101), {'PASS': 1})
        self.assertEqual(self.state(rid)[:3], ('PASS', 1, 1))
        self.assertEqual(tuple(self.c.execute('SELECT submitted,sha,sha_at FROM replays WHERE id=?',
                                             (rid,)).fetchone()), (1, digest, 1))

    def test_unknown_other_path_cannot_supply_a_result(self):
        rid, _path, _data, _digest = self.source()
        self.assertEqual(self.run_output(lambda p: controls.section(p[0]+'-other', None, 'PASS ticks 662 rows 1')), {'ERROR': 1})
        self.assertEqual(self.state(rid), ('ERROR', 0, 0, ''))
        self.assertEqual(self.c.execute('SELECT reason FROM verdicts WHERE replay_id=?', (rid,)).fetchone()[0],
                         'no VERIFY line')

    def test_ambiguous_abandon_cannot_promote_reproduction(self):
        self.m.EVIDENCE_DIR = os.path.join(self.m.BASE_DIR, 'ftesurf', 'data', 'evidence')
        self.m.KEEP_DIR = os.path.join(self.m.BASE_DIR, 'keep')
        rid = suite.add_evidence(self.c, '20261008-000000-0-p27510', suite.evbody('20261008-000000-0-p27510'))
        acted = []
        def runner(map_dir, paths):
            acted.extend(paths)
            return suite.input_bound_stub(self.sw, paths,
                    ['VERIFY %s HOLD %s' % (paths[0], self.sw.NO_FINISH)]*2)
        self.assertEqual(self.sw.sweep(self.c, 20, runner=runner, now=100), {'ERROR': 1})
        self.assertEqual(len(acted), 1)
        row = self.c.execute('SELECT verdict,reason,ticks,counts_metrics FROM verdicts WHERE replay_id=?', (rid,)).fetchone()
        self.assertEqual(tuple(row), ('ERROR', 'ambiguous duplicate VERIFY lines', -1, ''))
        self.assertEqual(self.c.execute('SELECT checked FROM replays WHERE id=?', (rid,)).fetchone()[0], 0)


if __name__ == '__main__':
    unittest.main()
