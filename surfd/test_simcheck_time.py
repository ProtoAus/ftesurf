"""Cooperative elapsed admission; acted fake-clock controls, no timing sleeps."""
import inspect
import math
import unittest
from unittest import mock
from test_simcheck_collection import CollectorAvailability, simcheck

class ElapsedBudget(CollectorAvailability):
    def setUp(self):
        super().setUp()
        self.elapsed=0.
        clock=mock.patch.object(simcheck.time,'monotonic',side_effect=lambda:self.elapsed)
        clock.start();self.addCleanup(clock.stop)

    def step(self, seconds=1., pairs=200):
        kw={'max_seconds':seconds} if 'max_seconds' in inspect.signature(simcheck.similarity_step).parameters else {}
        return simcheck.similarity_step(self.conn,self.surfd,max_pairs=pairs,**kw)

    def test_inflight_comparison_finishes_and_flushes_no_more_admission(self):
        def slow(a,b,**kw):
            result=self.compare(a,b,**kw)
            self.elapsed+=2.
            return result
        self.reader.compare_paths.side_effect=slow
        stored,notable,note=self.step()
        self.assertEqual((stored,notable,len(self.compared)),(1,1,1))
        self.assertEqual(self.resolved,[1,2])
        self.assertIn('time limit reached',note)
        self.assertIn('cooperative',note)
        self.assertEqual(self.conn.execute('SELECT compared FROM sims').fetchone()[0],80)
        self.assertFalse(self.conn.in_transaction)
        self.elapsed=0.;self.reader.compare_paths.side_effect=self.compare
        stored,notable,note=self.step()
        self.assertGreater(stored,0)  # untouched row acts on next pass

    def test_unresolved_primaries_stop_new_rows_at_deadline(self):
        def resolve(row):
            self.resolved.append(row['id']);self.elapsed+=.5
            return None,'private path'
        self.surfd.replay_file.side_effect=resolve
        stored,notable,note=self.step()
        self.assertEqual(self.resolved,[1,2])
        self.assertEqual((stored,notable,self.compared),(0,0,[]))
        self.assertIn('2 source unavailable',note)
        self.assertIn('time limit reached',note)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM sims').fetchone()[0],0)

    def test_peer_resolution_and_failure_cost_time(self):
        def resolve(row):
            self.resolved.append(row['id'])
            if row['id']==2:
                self.elapsed+=2.;return None,'unresolved'
            return str(row['id']),''
        self.surfd.replay_file.side_effect=resolve
        stored,notable,note=self.step()
        self.assertEqual((stored,notable,self.resolved),(1,0,[1,2]))
        self.assertIn('time limit reached',note)
        self.assertEqual(self.conn.execute('SELECT skip_code FROM sims').fetchone()[0],'peer_unresolved')
        self.conn.execute('DELETE FROM sims');self.conn.commit()
        self.elapsed=0.;self.resolved.clear();self.surfd.replay_file.side_effect=self.resolve
        def failing(a,b,**kw):
            self.compared.append((a,b));self.elapsed+=2.
            raise RuntimeError('synthetic failure')
        self.reader.compare_paths.side_effect=failing
        stored,notable,note=self.step()
        self.assertEqual((stored,notable,len(self.compared)),(0,0,1))
        self.assertIn('1 pair failed',note);self.assertIn('time limit reached',note)

    def test_zero_elapsed_budget_disables_before_support_import(self):
        with mock.patch.object(simcheck,'_recsim',return_value=(self.reader,'')) as loader:
            self.assertEqual(self.step(0),(0,0,''))
        loader.assert_not_called();self.assertEqual(self.resolved,[])

    def test_finite_positive_budget_and_independent_pair_cap(self):
        stored,notable,note=self.step(seconds=10.,pairs=1)
        self.assertEqual((stored,notable,len(self.compared)),(1,1,1))
        self.assertIn('pair limit reached',note);self.assertNotIn('time limit',note)

    def test_nonfinite_module_budget_is_rejected(self):
        for seconds in (math.nan,math.inf,-math.inf):
            with self.assertRaises(ValueError):self.step(seconds)

if __name__=='__main__':unittest.main()
