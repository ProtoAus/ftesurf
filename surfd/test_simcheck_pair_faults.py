"""Pair faults retain no fake observation and cannot discard other measurements."""
import unittest

import simcheck
import test_simcheck_source_cursor as fixture


class PairFaultTests(fixture.SourceCursorTests):
    def setup_fault(self, bad=3, mode='exception'):
        for i in range(1, 5):
            self.add(i)
        self.calls = []

        def compare(a, b, **limits):
            self.assertFalse(self.conn.in_transaction)
            self.calls.append((a, b))
            if b == bad:
                if mode == 'missing_metric':
                    return 'compared', {'match': 1.}
                if mode == 'skip':
                    return 'too short', 'synthetic unavailable detail'
                raise RuntimeError('synthetic private source path')
            return self.compare(a, b, **limits)

        self.mod.compare_paths = compare

    def pairs(self):
        return [tuple(r) for r in self.conn.execute(
            'SELECT a_id,b_id,verdict,compared,match FROM sims ORDER BY b_id')]

    def test_fault_between_successes_retains_both_and_later_pair_acts(self):
        self.setup_fault()
        stored, notable, note = self.step(pairs=3)
        self.assertEqual((stored, notable), (2, 2))
        self.assertEqual(self.calls, [(1, 2), (1, 3), (1, 4)])
        self.assertEqual(self.pairs(), [(1, 2, 'compared', 1, 1.), (1, 4, 'compared', 1, 1.)])
        self.assertIn('1 pair failed', note)
        self.assertNotIn('row failed', note)
        self.assertNotIn('synthetic private source path', note)
        self.assertFalse(self.conn.in_transaction)
        self.restart()
        self.assertEqual(len(self.pairs()), 2)

    def test_fault_consumes_second_and_final_budget_slot(self):
        self.setup_fault()
        stored, notable, note = self.step(pairs=2)
        self.assertEqual((stored, notable), (1, 1))
        self.assertEqual(self.calls, [(1, 2), (1, 3)])
        self.assertEqual(self.pairs(), [(1, 2, 'compared', 1, 1.)])
        self.assertIn('2 attempted', note)
        self.assertIn('1 pair failed', note)
        self.assertEqual(self.conn.execute("SELECT after_id FROM sim_cursor"
                                          " WHERE scope='peer' AND source_id=1").fetchone()[0], 3)

    def test_fault_first_does_not_stop_later_peers(self):
        self.setup_fault(bad=2)
        self.assertEqual(self.step(pairs=3)[:2], (2, 2))
        self.assertEqual(self.calls, [(1, 2), (1, 3), (1, 4)])
        self.assertEqual([r[1] for r in self.pairs()], [3, 4])

    def test_all_faults_report_when_nothing_stored_and_no_zero_sample(self):
        self.setup_fault()

        def fail(a, b, **limits):
            self.calls.append((a, b))
            raise RuntimeError('synthetic private source path')

        self.mod.compare_paths = fail
        stored, notable, note = self.step(pairs=3)
        self.assertEqual((stored, notable), (0, 0))
        self.assertEqual(len(self.calls), 3)
        self.assertIn('3 pair failed', note)
        self.assertNotIn('synthetic private source path', note)
        self.assertEqual(self.pairs(), [])
        self.assertEqual(simcheck.summary(self.conn)['state'], 'empty')
        self.assertEqual(simcheck.summary_line(self.conn), 'sims: no pairs stored yet')

    def test_result_processing_exception_is_not_a_zero_observation(self):
        self.setup_fault(mode='missing_metric')
        self.assertEqual(self.step(pairs=3)[:2], (2, 2))
        self.assertEqual(self.calls, [(1, 2), (1, 3), (1, 4)])
        self.assertEqual([r[1] for r in self.pairs()], [2, 4])
        self.assertIsNone(self.conn.execute('SELECT id FROM sims WHERE b_id=3').fetchone())

    def test_real_zero_measurement_is_distinct_from_failed_pair(self):
        self.setup_fault()
        original = self.mod.compare_paths

        def compare(a, b, **limits):
            verdict, result = original(a, b, **limits)
            if b == 4:
                result['match'] = 0.
            return verdict, result

        self.mod.compare_paths = compare
        self.assertEqual(self.step(pairs=3)[:2], (2, 1))
        self.assertEqual(self.pairs(), [(1, 2, 'compared', 1, 1.), (1, 4, 'compared', 1, 0.)])
        self.assertEqual(simcheck.summary(self.conn)['compared'], 2)

    def test_legitimate_skip_keeps_code_and_history_not_pair_failure(self):
        self.setup_fault(mode='skip')
        stored, notable, note = self.step(pairs=3)
        self.assertEqual((stored, notable), (3, 2))
        self.assertNotIn('pair failed', note)
        row = self.conn.execute('SELECT verdict,reason,skip_code FROM sims WHERE b_id=3').fetchone()
        self.assertEqual(tuple(row), ('skip', 'synthetic unavailable detail', 'too_short'))
        self.assertEqual(simcheck.summary(self.conn)['skip_codes'], {'too_short': 1})

    def test_storage_failure_stays_row_failure_and_rolls_back_all_observations(self):
        self.setup_fault(bad=0)  # all comparisons succeed before storage acts
        inserted = []
        self.conn.create_function('storage_probe', 1, lambda b: inserted.append(b) or 0)
        self.conn.executescript('''
            CREATE TRIGGER pair_write_probe BEFORE INSERT ON sims BEGIN
                SELECT storage_probe(NEW.b_id);
                SELECT CASE WHEN NEW.b_id=3 THEN RAISE(ABORT, 'synthetic storage fault') END;
            END;
        ''')
        stored, notable, note = self.step(pairs=3)
        self.assertEqual((stored, notable), (0, 0))
        self.assertEqual(self.calls, [(1, 2), (1, 3), (1, 4)])
        self.assertEqual(inserted, [2, 3])  # storage ACTED after first insertion
        self.assertIn('1 row failed', note)
        self.assertNotIn('pair failed', note)
        self.assertEqual(self.pairs(), [])  # first insert actually rolled back
        self.assertFalse(self.conn.in_transaction)


if __name__ == '__main__':
    unittest.main()
