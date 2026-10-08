"""Exclude observed pairs before the peer window; preserve bounded admission."""
import unittest
from unittest import mock

import simcheck
import test_simcheck_pending as fixture


class PeerTests(fixture.PendingTests):
    def direct(self, source=1, limit_peers=200, budget=None):
        row = self.conn.execute('SELECT * FROM replays WHERE id=?', (source,)).fetchone()
        with mock.patch.object(simcheck, '_recsim', return_value=(self.mod, 'fake')):
            return simcheck.compare_run(self.surfd, self.conn, row,
                                        limit_peers=limit_peers, budget=budget)

    def crowded(self):
        for i in range(1, 207):
            self.add(i)
        for i in range(2, 202):
            # Historical rows may use either orientation; never reconstruct them.
            a, b = (1, i) if i % 2 else (i, 1)
            self.conn.execute('INSERT INTO sims(a_id,b_id,map,track,leg,verdict,at)'
                              " VALUES(?,?, 'm',0,0,'compared',0)", (a, b))
        self.conn.commit()

    def test_observed_first_two_hundred_do_not_hide_new_peers(self):
        self.crowded()
        self.assertEqual(self.direct(), (5, 0, 5))
        self.assertEqual(self.compared, [(1, i) for i in range(202, 207)])
        self.assertEqual(self.resolved, [1] + list(range(202, 207)))
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM sims').fetchone()[0], 205)

    def test_crowded_window_still_obeys_one_pair_per_pass(self):
        self.crowded()
        # Pin this source's peer-window contract independently of global source
        # rotation. Each call gets a fresh shared-style one-pair admission budget.
        self.assertEqual([self.direct(budget=simcheck._PairBudget(1, 1.))[0]
                          for _ in range(5)], [1] * 5)
        self.assertEqual(self.compared, [(1, i) for i in range(202, 207)])
        self.assertNotIn(1, self.pending_ids())

    def test_candidate_limit_still_caps_new_peers(self):
        for i in range(1, 207):
            self.add(i)
        self.assertEqual(self.direct(limit_peers=3), (3, 0, 3))
        self.assertEqual(self.compared, [(1, 2), (1, 3), (1, 4)])
        self.compared.clear()
        self.assertEqual(self.direct(), (200, 0, 200))
        self.assertEqual(self.compared, [(1, i) for i in range(5, 205)])
        self.compared.clear()
        self.assertEqual(self.direct(), (2, 0, 2))
        self.assertEqual(self.compared, [(1, 205), (1, 206)])

    def test_completed_direct_source_has_no_resolution(self):
        self.add(1)
        self.add(2)
        self.seed(1, 2, 'skip')
        self.assertEqual(self.direct(), (0, 0, 0))
        self.assertEqual(self.compared, [])
        self.assertEqual(self.resolved, [])

    def test_unresolved_new_peer_consumes_budget_after_stored_window(self):
        self.crowded()
        original = self.surfd.replay_file

        def path(row):
            if row['id'] == 202:
                self.resolved.append(202)
                return None, 'unavailable'
            return original(row)

        self.surfd.replay_file = path
        budget = simcheck._PairBudget(1, 1.)
        stored, skipped, notable = self.direct(budget=budget)
        self.assertEqual((stored, skipped, notable), (1, 1, 0))
        self.assertEqual(budget.attempted, 1)
        self.assertEqual(self.resolved, [1, 202])
        self.assertEqual(self.compared, [])
        row = self.conn.execute('SELECT verdict,skip_code FROM sims'
                                ' WHERE a_id=1 AND b_id=202').fetchone()
        self.assertEqual(tuple(row), ('skip', 'peer_unresolved'))
        self.assertEqual(self.direct(budget=simcheck._PairBudget(1, 1.))[0], 1)
        self.assertEqual(self.compared, [(1, 203)])  # valid next peer ACTED


if __name__ == '__main__':
    unittest.main()
