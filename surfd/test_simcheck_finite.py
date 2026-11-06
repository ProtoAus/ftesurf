"""Non-finite output is unavailable, not silent omission or stored metadata."""
import math
import os
import sqlite3
from types import SimpleNamespace
import unittest
from unittest import mock

import test_simcheck_sources as fixture

sc = fixture.sc
if os.environ.get('SIMCHECK_UNDER_TEST'):
    sc = fixture.load('finite_control', os.environ['SIMCHECK_UNDER_TEST'])
    fixture.sc = sc


class FiniteObservations(unittest.TestCase):
    def setUp(self):
        fixture.StoredSources.setUp(self)
        self.conn.execute("INSERT INTO sims(id,a_id,b_id,map,track,leg,verdict,match,compared,at)"
                          " VALUES(100,91,92,'historical',0,0,'compared',0.25,80,1)")
        self.conn.commit()
        self.old = tuple(self.conn.execute('SELECT * FROM sims WHERE id=100').fetchone())
        self.replays = list(self.conn.execute('SELECT * FROM replays ORDER BY id'))
        self.acted = []
        self.diag = {'source_unavailable': 0, 'pair_failed': 0}

    def rate(self, rid, token):
        self.paths[rid].write_bytes(self.data[rid].replace(b'tickrate 100',
                                   ('tickrate ' + token).encode()))

    def reset(self):
        self.conn.execute('DELETE FROM sims WHERE id!=100')
        self.conn.execute('DELETE FROM sim_cursor')
        self.conn.commit()
        self.acted.clear()
        self.diag = {'source_unavailable': 0, 'pair_failed': 0}

    def reader(self, mutate=None, comparisons=80):
        def compare(a, b, **kw):
            self.assertFalse(self.conn.in_transaction)
            with sqlite3.connect(self.db) as writer:
                writer.execute('INSERT INTO probe VALUES(1)')
            verdict, detail = fixture.rs.compare_paths(a, b, **kw)
            self.assertEqual(verdict, 'compared')
            if comparisons is None:
                self.assertGreater(detail['compared'], 0)
            else:
                self.assertEqual(detail['compared'], comparisons)
            # Synthetic contract corruption, where requested, happens only AFTER
            # the real parser/comparison has acted. Header cases need no mutation.
            if mutate is not None:
                mutate(a, b, detail)
            self.acted.append((a, b, detail.copy()))
            return verdict, detail
        return SimpleNamespace(compare_paths=compare)

    def run_source(self, rid=1, reader=None, budget=None):
        row = self.conn.execute('SELECT * FROM replays WHERE id=?', (rid,)).fetchone()
        return sc.compare_run(self.sf, self.conn, row, limit_peers=2,
                              diagnostics=self.diag, reader=reader or self.reader(),
                              budget=budget)

    def measured(self):
        return list(self.conn.execute('SELECT * FROM sims WHERE id!=100 ORDER BY id'))

    def preserved(self, before):
        self.assertFalse(self.conn.in_transaction)
        self.assertEqual(tuple(self.conn.execute('SELECT * FROM sims WHERE id=100').fetchone()), self.old)
        self.assertEqual(list(self.conn.execute('SELECT * FROM replays ORDER BY id')), self.replays)
        self.assertEqual({i: p.read_bytes() for i, p in self.paths.items()}, before)
        for row in self.measured():
            self.assertEqual(row['verdict'], 'compared')
            self.assertEqual(row['compared'], 80)
            self.assertTrue(all(math.isfinite(row[k]) for k in ('match', 'cover', 'tick_a', 'tick_b')))

    def test_real_nan_peer_is_reported_unavailable_not_silently_ignored(self):
        self.rate(3, 'NaN')
        before = {i: p.read_bytes() for i, p in self.paths.items()}
        result = self.run_source()
        self.assertEqual(len(self.acted), 2)
        self.assertTrue(math.isnan(self.acted[1][2]['tickrate_b']))
        self.preserved(before)
        self.assertEqual(result, (1, 0, 1))
        self.assertEqual(self.diag['pair_failed'], 1)
        row, = self.measured()
        self.assertEqual((row['a_id'], row['b_id']), (1, 2))
        self.assertEqual(fixture.StoredSources.snap(self, row), fixture.capture(before[1], before[2]))
        self.assertEqual(sc._cursor(self.conn, 'peer', 1), 3)

    def test_real_nan_before_good_peer_keeps_later_measurement(self):
        self.rate(2, 'nan')
        before = {i: p.read_bytes() for i, p in self.paths.items()}
        result = self.run_source()
        self.assertEqual(len(self.acted), 2)
        self.assertTrue(math.isnan(self.acted[0][2]['tickrate_b']))
        self.preserved(before)
        self.assertEqual(result, (1, 0, 1))
        self.assertEqual(self.diag['pair_failed'], 1)
        self.assertEqual([(r['a_id'], r['b_id']) for r in self.measured()], [(1, 3)])

    def test_real_nonfinite_header_spellings_never_become_observations(self):
        for token in ('inf', '-inf', '1e9999', '-1e9999', 'nan'):
            with self.subTest(token=token):
                self.reset()
                self.rate(3, token)
                before = {i: p.read_bytes() for i, p in self.paths.items()}
                result = self.run_source()
                self.assertEqual(len(self.acted), 2)
                self.assertFalse(math.isfinite(self.acted[1][2]['tickrate_b']))
                self.assertEqual(result, (1, 0, 1))
                self.assertEqual(self.diag['pair_failed'], 1)
                self.preserved(before)

    def test_real_nonfinite_primary_stays_unmeasured_and_other_source_acts(self):
        self.rate(1, 'nan')
        before = {i: p.read_bytes() for i, p in self.paths.items()}
        first = self.run_source()
        self.assertEqual(len(self.acted), 2)
        self.assertTrue(all(math.isnan(d['tickrate_a']) for _, _, d in self.acted))
        self.assertEqual(first, (0, 0, 0))
        self.assertEqual(self.diag['pair_failed'], 2)
        self.assertEqual(self.run_source(2), (1, 0, 1))
        self.assertEqual(self.diag['pair_failed'], 3)
        self.assertEqual([(r['a_id'], r['b_id']) for r in self.measured()], [(2, 3)])
        self.preserved(before)

    def test_all_four_float_outputs_are_checked_after_real_comparison(self):
        for key in ('match', 'cover', 'tickrate_a', 'tickrate_b'):
            for value in (float('nan'), float('inf'), float('-inf')):
                with self.subTest(key=key, value=str(value)):
                    self.reset()
                    def corrupt(a, b, detail):
                        if b == str(self.paths[3]):
                            detail[key] = value
                    result = self.run_source(reader=self.reader(corrupt))
                    self.assertEqual(len(self.acted), 2)
                    self.assertEqual(result, (1, 0, 1))
                    self.assertEqual(self.diag['pair_failed'], 1)
                    self.assertEqual([(r['a_id'], r['b_id']) for r in self.measured()], [(1, 2)])

    def test_finite_rate_mismatch_zero_negative_and_large_retain_old_behavior(self):
        for token in ('66.67', '0', '-1', '1e300'):
            with self.subTest(token=token):
                self.reset()
                self.rate(3, token)
                before = {i: p.read_bytes() for i, p in self.paths.items()}
                self.assertEqual(self.run_source(), (2, 0, 2))
                self.assertEqual(len(self.acted), 2)
                self.assertEqual(self.diag['pair_failed'], 0)
                self.assertEqual(self.measured()[1]['tick_b'], float(token))
                self.preserved(before)

    def test_finite_measured_zero_is_not_an_unavailable_pair(self):
        rows = ['FTESURF-REC 9', 'map synthetic', 'tickrate 100', 'begin']
        rows += ['in %d %d 0 %d 0 0 0 0 0 4' % (i, i, 900+i%7) for i in range(80)]
        self.paths[2].write_text('\n'.join(rows + ['end 80']) + '\n')
        self.rate(3, 'nan')
        self.assertEqual(self.run_source(reader=self.reader(comparisons=None)), (1, 0, 0))
        self.assertEqual([d['compared'] for _, _, d in self.acted], [76, 80])
        self.assertEqual(self.diag['pair_failed'], 1)
        row, = self.measured()
        # The unchanged zero-match offset tie selects -4: 76 real opportunities.
        self.assertEqual((row['match'], row['compared'], row['skip_code']), (0, 76, ''))

    def test_invalid_output_consumes_admission_without_a_fake_skip_or_zero(self):
        self.rate(2, 'nan')
        budget = sc._PairBudget(1, 60)
        self.assertEqual(self.run_source(budget=budget), (0, 0, 0))
        self.assertEqual((budget.attempted, budget.remaining), (1, 0))
        self.assertEqual(len(self.acted), 1)
        self.assertEqual(self.diag['pair_failed'], 1)
        self.assertEqual(self.measured(), [])
        self.assertEqual(sc._cursor(self.conn, 'peer', 1), 2)
        self.assertEqual(self.run_source(), (1, 0, 1))
        self.assertEqual(self.diag['pair_failed'], 2)
        self.assertEqual(self.measured()[0]['b_id'], 3)

    def test_actual_step_reports_failures_and_continues_other_source(self):
        self.rate(1, 'nan')
        before = {i: p.read_bytes() for i, p in self.paths.items()}
        reader = self.reader()
        with mock.patch.object(sc, '_recsim', return_value=(reader, 'fixture')):
            first = sc.similarity_step(self.conn, self.sf, limit=1, max_pairs=2, max_seconds=60)
            self.assertEqual(first[:2], (0, 0))
            self.assertIn('2 pair failed', first[2])
            self.assertEqual(len(self.acted), 2)
            self.assertEqual(sc._cursor(self.conn, 'source'), 1)
            self.assertIsNone(self.conn.execute("SELECT 1 FROM sim_cursor WHERE scope='source' AND source_id=1").fetchone())
            second = sc.similarity_step(self.conn, self.sf, limit=1, max_pairs=2, max_seconds=60)
        self.assertEqual(second[:2], (1, 1))
        self.assertIn('1 pair failed', second[2])
        self.assertEqual(len(self.acted), 4)
        self.assertEqual([(r['a_id'], r['b_id']) for r in self.measured()], [(2, 3)])
        self.preserved(before)
        with sqlite3.connect(self.db) as reopened:
            self.assertEqual(reopened.execute('SELECT COUNT(*) FROM sims WHERE id!=100').fetchone()[0], 1)
            self.assertEqual(tuple(reopened.execute('SELECT * FROM sims WHERE id=100').fetchone()), self.old)

    def test_actual_sql_abort_still_rolls_back_whole_flush_not_pair_isolation(self):
        self.conn.execute("CREATE TRIGGER stop BEFORE INSERT ON sims WHEN new.b_id=3"
                          " BEGIN SELECT RAISE(ABORT,'owned SQL rollback'); END")
        self.conn.commit()
        before = {i: p.read_bytes() for i, p in self.paths.items()}
        with self.assertRaises(sqlite3.IntegrityError):
            self.run_source()
        self.assertEqual(len(self.acted), 2)
        self.assertEqual(self.diag['pair_failed'], 0)
        self.assertEqual(self.measured(), [])
        self.assertEqual(sc._cursor(self.conn, 'peer', 1), 0)
        self.preserved(before)


if __name__ == '__main__':
    unittest.main()
